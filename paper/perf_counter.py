"""Scoped Linux PMU cycle fd transfer; no global perf policy changes.

The privileged controller attaches a single non-inherited event to a blocked,
ordinary-uid benchmark worker. That PID then execs the frozen benchmark. Raw
counter endpoints are read inside C, not around process startup or wait().
"""
from __future__ import annotations
import array
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import struct
import subprocess
import sys

COUNTER = {'type': 'PERF_TYPE_HARDWARE', 'config': 'PERF_COUNT_HW_CPU_CYCLES',
           'pid': 'benchmark worker only', 'cpu': -1, 'inherit': False,
           'pinned': True, 'exclude_user': False, 'exclude_kernel': False,
           'exclude_hv': True, 'read_format': ['TOTAL_TIME_ENABLED', 'TOTAL_TIME_RUNNING'],
           'unit': 'CPU cycles', 'multiplexing': 'reject; never scale',
           'scope': 'single benchmark thread, including its kernel execution'}
# perf_event_attr ABI v0,64 bytes. No sampling, inheritance or mmap ring.
ATTR = struct.pack('=IIQQQQQIIQ', 0, 64, 0, 0, 0, 3, 4 | 64, 0, 0, 0)


def open_counter(pid):
    if platform.machine() != 'x86_64':
        raise RuntimeError('This cycle protocol currently supports Linux x86_64 only')
    libc = ctypes.CDLL(None, use_errno=True)
    attr = ctypes.create_string_buffer(ATTR)
    fd = libc.syscall(ctypes.c_long(298), ctypes.byref(attr), ctypes.c_int(pid),
                      ctypes.c_int(-1), ctypes.c_int(-1), ctypes.c_ulong(8))
    if fd < 0:
        error = ctypes.get_errno()
        raise OSError(error, 'perf_event_open CPU cycles: '+os.strerror(error))
    os.set_inheritable(fd, False)
    return fd


def recv_fd(sock):
    data, anc, flags, _ = sock.recvmsg(4096, socket.CMSG_SPACE(array.array('i').itemsize))
    if flags or data != b'CPU_CYCLES_V1': raise RuntimeError('Invalid PMU broker response')
    fds = []
    for level, kind, value in anc:
        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
            values = array.array('i'); values.frombytes(value); fds.extend(values)
    if len(fds) != 1:
        for fd in fds: os.close(fd)
        raise RuntimeError('Expected exactly one scoped counter fd')
    return fds[0]


def worker(broker_fd, command):
    """Runs only as the ordinary user; same PID is retained across exec."""
    if os.geteuid() == 0: raise RuntimeError('Counter worker must be unprivileged')
    with socket.socket(fileno=broker_fd) as sock:
        sock.send(json.dumps({'pid': os.getpid(), 'executable': str(Path(command[0]).resolve())}).encode())
        fd = recv_fd(sock)
    os.set_inheritable(fd, True)
    env = os.environ.copy(); env.pop('CNTRU_PERF_BROKER_FD', None)
    env['CNTRU_PERF_FD'] = str(fd)
    os.execve(command[0], command, env)


def serve_request(sock, comparator_pid, uid, repository):
    data = sock.recv(4096)
    if not data: return None
    request = json.loads(data)
    pid = request['pid']
    if type(pid) is not int or pid <= 0: raise RuntimeError('Invalid PMU worker PID')
    status = {}
    for line in Path(f'/proc/{pid}/status').read_text().splitlines():
        if ':' in line:
            key, value = line.split(':', 1); status[key] = value.split()
    if (int(status['PPid'][0]) != comparator_pid or any(int(x) != uid for x in status['Uid'])
            or status['Threads'] != ['1']):
        raise RuntimeError('PMU target must be the comparator single-thread ordinary-uid child')
    executable = Path(request['executable']).resolve()
    allowed_roots=(repository/'family_20261107/build',repository/'paper/build')
    allowed = executable.parent.parent in allowed_roots
    if not allowed or executable.name != 'bench' or not executable.is_file():
        raise RuntimeError('PMU target is outside the benchmark build directories')
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    metadata = json.loads((executable.parent/'build.json').read_text())
    expected=metadata['binary_sha256'] if 'binary_sha256' in metadata else metadata['benchmark_executable_sha256']
    if digest != expected: raise RuntimeError('PMU target hash differs from frozen build')
    fd = open_counter(pid)
    try: sock.sendmsg([b'CPU_CYCLES_V1'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))])
    finally: os.close(fd)
    return {'pid': pid, 'executable': str(executable), 'binary_sha256': digest,
            'counter': COUNTER, 'attr_hex': ATTR.hex()}


def run_benchmark(command, **kwargs):
    """Only timed benchmark children receive the private broker socket."""
    value = os.environ.get('CNTRU_PERF_BROKER_FD')
    if value is None:
        return subprocess.run(command, **kwargs)  # C attempts its own scoped perf event.
    fd = int(value)
    command = [sys.executable, str(Path(__file__).resolve()), '--worker', str(fd), *command]
    return subprocess.run(command, pass_fds=(fd,), **kwargs)


if __name__ == '__main__':
    if len(sys.argv) < 4 or sys.argv[1] != '--worker': raise SystemExit('Internal PMU worker only')
    worker(int(sys.argv[2]), sys.argv[3:])
