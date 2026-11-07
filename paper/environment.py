"""Inspect or temporarily control one benchmark core, restoring settings.

No settings change without --execute. Run the inspected --execute command
with sudo in the user's terminal; the benchmark subprocess drops root.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import socket
import select
import importlib.util
import sys
import tempfile
import time

CPU = Path('/sys/devices/system/cpu')
SETTING_ATTEMPTS = 50
SETTING_RETRY_SECONDS = 0.02
SETTING_TIMEOUT_SECONDS = 1.0


def read(path: Path) -> str:
    return path.read_text().strip()


def cpu_list(text: str) -> list[int]:
    result = []
    for part in text.replace(' ', ',').split(','):
        if not part:
            continue
        bounds = part.split('-')
        result.extend(range(int(bounds[0]), int(bounds[-1]) + 1))
    return result


def validate_smt_topology(cpu, siblings_before, siblings, observed, sibling_online):
    """Offline siblings may disappear from the kernel's runtime mask.

    Retain the complete pre-control set and require a direct online readback
    for every planned sibling, including those absent from the runtime mask.
    """
    expected = {cpu, *siblings}
    if (cpu in siblings or len(set(siblings)) != len(siblings)
            or set(siblings_before) != expected or len(siblings_before) != len(expected)):
        raise ValueError('Recorded sibling topology is inconsistent')
    current = set(cpu_list(observed))
    if cpu not in current or not current.issubset(expected):
        raise ValueError('Actual sibling topology contradicts the controller record')
    if set(sibling_online) != {str(s) for s in siblings}:
        raise ValueError('Missing planned SMT sibling online readback')
    if any(value != '0' for value in sibling_online.values()):
        raise ValueError('SMT sibling remains online')


def plan(cpu: int, frequency: int) -> dict:
    if cpu not in os.sched_getaffinity(0):
        raise ValueError('Selected CPU is not allowed by current affinity')
    base = CPU / f'cpu{cpu}'
    policy = (base / 'cpufreq').resolve(strict=True)
    low = int(read(policy / 'cpuinfo_min_freq'))
    high = int(read(policy / 'cpuinfo_max_freq'))
    if not low <= frequency <= high:
        raise ValueError(f'Frequency must be within {low}..{high} kHz')
    siblings_before = sorted(set(cpu_list(read(base / 'topology/thread_siblings_list'))))
    if cpu not in siblings_before:
        raise ValueError('Selected CPU is absent from its own sibling topology')
    siblings = [c for c in siblings_before if c != cpu]
    if not set(siblings).issubset(os.sched_getaffinity(0)):
        raise ValueError('An SMT sibling is outside the invoking CPU affinity; refusing to offline it')
    affected = cpu_list(read(policy / 'affected_cpus'))
    if not set(affected).issubset({cpu, *siblings}):
        raise ValueError('Frequency policy also affects other physical cores; refusing this plan')
    paths = {name: policy / name for name in
             ('scaling_governor', 'scaling_min_freq', 'scaling_max_freq')}
    paths['no_turbo'] = CPU / 'intel_pstate/no_turbo'
    for sibling in siblings:
        paths[f'online_{sibling}'] = CPU / f'cpu{sibling}/online'
    return {'cpu': cpu, 'frequency_khz': frequency, 'policy': str(policy),
            'affected_cpus': affected,
            'hardware_min_khz': low, 'siblings': siblings,
            'thread_siblings_before': siblings_before,
            'paths': {k: str(v) for k, v in paths.items()},
            'original': {k: read(v) for k, v in paths.items()},
            'requested': {'scaling_governor': 'performance',
                          'scaling_min_freq': str(frequency),
                          'scaling_max_freq': str(frequency), 'no_turbo': '1',
                          **{f'online_{s}': '0' for s in siblings}},
            'perf_event_paranoid': read(Path('/proc/sys/kernel/perf_event_paranoid')),
            'limitations': ['CPU isolation from all kernel interrupts is not configured',
                            'Performance counter permissions are not changed',
                            'Other physical cores remain available to the user']}


def save_as_user(path: Path, state: dict, uid: int, gid: int, groups: list[int]) -> None:
    """All output filesystem operations run after irrevocably dropping root.

    In particular, a user-selected output path/symlink can never cause a root
    mkdir, write, chown or rename. The parent only controls fixed sysfs paths.
    """
    payload = json.dumps(state, indent=2) + '\n'
    child = os.fork()
    if child == 0:
        try:
            os.setgroups(groups)
            os.setgid(gid)
            os.setuid(uid)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix='.environment-', suffix='.json', dir=path.parent)
            temporary = Path(name)
            try:
                with os.fdopen(fd, 'w') as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            os._exit(0)
        except BaseException as exc:
            print('Cannot save environment record as invoking user: ' + repr(exc), file=sys.stderr, flush=True)
            os._exit(1)
    _, status = os.waitpid(child, 0)
    if status != 0:
        raise RuntimeError('Unprivileged environment record write failed')


class Controller:
    """Record every attempted setting and restore even after partial writes."""
    def __init__(self, state):
        self.state = state
        self.changed = set()
        self.started = time.monotonic()
        self.state['setting_timeout_seconds'] = SETTING_TIMEOUT_SECONDS

    def journal(self, phase, name, value, attempt):
        entry = {'phase': phase, 'name': name, 'requested': value, 'attempt': attempt,
                 'utc': datetime.now(timezone.utc).isoformat(),
                 'elapsed_seconds': time.monotonic() - self.started}
        self.state.setdefault('setting_writes', []).append(entry)
        return entry

    def write(self, name, value):
        self.changed.add(name)
        if name == 'no_turbo':
            # intel_pstate can clamp endpoints as a side effect of Turbo off.
            self.changed.update(('scaling_min_freq', 'scaling_max_freq'))
        path = Path(self.state['paths'][name])
        deadline = time.monotonic() + SETTING_TIMEOUT_SECONDS
        for attempt in range(SETTING_ATTEMPTS):
            entry = self.journal('apply', name, value, attempt + 1)
            try:
                path.write_text(value + '\n')
                observed = read(path)
                entry['observed'] = observed
            except OSError as exc:
                entry['error'] = repr(exc)
                raise
            if observed == value:
                return
            # Hotplug or a policy manager may race setup. Retry only a
            # readback mismatch, under a fixed administrative budget. No
            # performance sample has begun; exact equality remains required.
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if attempt + 1 < SETTING_ATTEMPTS:
                time.sleep(min(SETTING_RETRY_SECONDS, remaining))
                if time.monotonic() >= deadline:
                    break
        raise RuntimeError(f'Kernel did not apply requested setting: {name}; '
                           f'requested={value}, observed={observed}, attempts={attempt + 1}, '
                           f'timeout_seconds={SETTING_TIMEOUT_SECONDS}')

    def apply(self):
        self.write('no_turbo', '1')
        for sibling in self.state['siblings']:
            self.write(f'online_{sibling}', '0')
        self.write('scaling_governor', 'performance')
        self.write('scaling_min_freq', str(self.state['hardware_min_khz']))
        self.write('scaling_max_freq', str(self.state['frequency_khz']))
        self.write('scaling_min_freq', str(self.state['frequency_khz']))
        self.state['applied'] = {k: read(Path(p)) for k, p in self.state['paths'].items()}
        if self.state['applied'] != self.state['requested']:
            raise RuntimeError('Controlled environment check failed: requested='
                               + repr(self.state['requested']) + ', observed='
                               + repr(self.state['applied']))

    def restore(self):
        # Restore Turbo first: otherwise intel_pstate may reject an original
        # maximum above the non-Turbo limit. Then reopen the interval.
        original = self.state['original']
        actions = [('no_turbo', original['no_turbo']),
                   ('scaling_min_freq', str(self.state['hardware_min_khz'])),
                   ('scaling_max_freq', original['scaling_max_freq']),
                   ('scaling_min_freq', original['scaling_min_freq']),
                   ('scaling_governor', original['scaling_governor'])]
        actions += [(f'online_{s}', original[f'online_{s}']) for s in self.state['siblings']]
        errors = []
        for name, value in actions:
            if name not in self.changed:
                continue
            entry = self.journal('restore', name, value, 1)
            path = Path(self.state['paths'][name])
            try:
                path.write_text(value + '\n')
            except OSError as exc:
                entry['error'] = repr(exc)
                errors.append(f'{name}: {exc}')
            else:
                try:
                    entry['observed'] = read(path)
                except OSError as exc:
                    # Final readback below is authoritative for restoration.
                    entry['readback_error'] = repr(exc)
        restored = {}
        for name, path in self.state['paths'].items():
            try:
                restored[name] = read(Path(path))
            except OSError as exc:
                errors.append(f'{name} readback: {exc}')
        self.state.update(restored=restored, restoration_errors=errors,
                          restoration_verified=restored == original and not errors)


def stop_process_group(child):
    """The benchmark starts a separate session; stop its descendants too."""
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', type=int, default=4)
    parser.add_argument('--frequency-khz', type=int, default=3000000)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--out', type=Path, default=Path(__file__).parent / 'results/environment.json')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    state = plan(args.cpu, args.frequency_khz)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    provenance_spec = importlib.util.spec_from_file_location('cntru_provenance', Path(__file__).with_name('provenance.py'))
    provenance = importlib.util.module_from_spec(provenance_spec)
    provenance_spec.loader.exec_module(provenance)
    state['command'] = command
    state['script'] = str(Path(__file__).resolve())
    state['controller_sources_sha256'] = provenance.controller_manifest()
    if not args.execute:
        print(json.dumps({'mode': 'dry_run', **state}, indent=2))
        return
    if os.geteuid() != 0 or 'SUDO_UID' not in os.environ:
        parser.error('--execute requires sudo from the invoking user; no password is accepted by this program')
    if not command:
        parser.error('--execute requires a benchmark command after --')
    uid, gid = int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID'])
    if uid == 0:
        parser.error('Benchmark must execute as an unprivileged user')
    user = pwd.getpwuid(uid)
    groups = []
    # Do not follow a user-created lock symlink or trust an unprivileged owner.
    # /run is root-owned; unlike /run/lock it is not generally world-writable.
    # A persistent flock supports recovery after abrupt process termination.
    lock = os.open('/run/cntru-benchmark.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    lock_stat = os.fstat(lock)
    if lock_stat.st_uid != 0 or lock_stat.st_nlink != 1 or not stat.S_ISREG(lock_stat.st_mode):
        os.close(lock)
        parser.error('Benchmark lock must be a root-owned regular file')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = plan(args.cpu, args.frequency_khz)
    state.update(command=command, script=str(Path(__file__).resolve()))
    state['controller_sources_sha256'] = provenance.controller_manifest()
    original_affinity = os.sched_getaffinity(0)
    state['original_parent_affinity'] = sorted(original_affinity)
    controller = Controller(state)
    state['started_utc'] = datetime.now(timezone.utc).isoformat()
    state['status'] = 'configuring'
    def save() -> None:
        save_as_user(args.out, state, uid, gid, groups)

    def stop(signum, frame):
        del frame
        raise KeyboardInterrupt(f'Received signal {signum}')

    perf_spec = importlib.util.spec_from_file_location('cntru_perf', Path(__file__).with_name('perf_counter.py'))
    perf = importlib.util.module_from_spec(perf_spec); perf_spec.loader.exec_module(perf)
    broker, worker_socket = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    state['cycle_counter'] = perf.COUNTER
    state['cycle_counter_requests'] = []
    child = None
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    save()
    code = 1
    try:
        controller.apply()
        state['status'] = 'running'; save()
        env = os.environ.copy()
        for key in ('SUDO_UID', 'SUDO_GID', 'SUDO_USER', 'SUDO_COMMAND', 'VIRTUAL_ENV'):
            env.pop(key, None)
        env.update(HOME=user.pw_dir, USER=user.pw_name, LOGNAME=user.pw_name)
        env['CNTRU_CONTROLLED_ENVIRONMENT'] = str(args.out)
        env['CNTRU_PERF_BROKER_FD'] = str(worker_socket.fileno())
        os.sched_setaffinity(0, {args.cpu})
        state['benchmark_affinity'] = sorted(os.sched_getaffinity(0))
        save()
        child = subprocess.Popen(command, user=uid, group=gid,
                                 extra_groups=groups, env=env, start_new_session=True,
                                 pass_fds=(worker_socket.fileno(),))
        worker_socket.close()
        while child.poll() is None:
            ready, _, _ = select.select([broker], [], [], 1.0)
            if ready:
                request = perf.serve_request(broker, child.pid, uid, Path(__file__).resolve().parents[1])
                if request is None: break
                state['cycle_counter_requests'].append(request)
        code = child.wait()
        state['benchmark_returncode'] = code
        state['status'] = 'completed' if code == 0 else 'benchmark_failed'
    except BaseException as exc:
        code = 1
        state['status'] = 'interrupted_or_failed'; state['error'] = repr(exc)
        print('Controlled benchmark failed: ' + str(exc), file=sys.stderr, flush=True)
        if child is not None:
            stop_process_group(child)
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        broker.close(); worker_socket.close()
        controller.restore()
        try:
            os.sched_setaffinity(0, original_affinity)
            state['restored_parent_affinity'] = sorted(os.sched_getaffinity(0))
            if os.sched_getaffinity(0) != original_affinity:
                raise RuntimeError('Parent affinity did not restore')
        except (OSError, RuntimeError) as exc:
            state['restoration_verified'] = False
            state['restoration_errors'].append('affinity: '+repr(exc))
        state['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
        os.close(lock)
        if not state['restoration_verified']:
            code = 3
            print('CPU settings did not fully restore; inspect ' + str(args.out), file=sys.stderr)
        elif code != 0:
            print('CPU settings restored. Failed run details: ' + str(args.out),
                  file=sys.stderr, flush=True)
        else:
            print('Controlled benchmark completed; CPU settings restored. Record: '
                  + str(args.out), flush=True)
    raise SystemExit(code)


if __name__ == '__main__':
    main()
