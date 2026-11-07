"""Exercise controls on fake sysfs files; never modifies host CPU settings."""
import copy
from contextlib import ExitStack
import io
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import environment


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        original = dict(scaling_governor='powersave', scaling_min_freq='800000',
                        scaling_max_freq='6000000', no_turbo='0', online_5='1')
        paths = {key: str(root/key) for key in original}
        for key, value in original.items(): Path(paths[key]).write_text(value+'\n')
        self.state = dict(cpu=4, frequency_khz=3000000, hardware_min_khz=800000,
                          siblings=[5], paths=paths, original=original,
                          requested=dict(scaling_governor='performance', scaling_min_freq='3000000',
                                         scaling_max_freq='3000000', no_turbo='1', online_5='0'))

    def test_roundtrip_and_turbo_restore_order(self):
        controller = environment.Controller(self.state)
        real_write = Path.write_text
        history = []

        def hardware_write(path, text, *args, **kwargs):
            name, value = path.name, text.strip()
            history.append((name, value))
            if name == 'scaling_max_freq' and int(value) > 3200000:
                self.assertEqual(Path(self.state['paths']['no_turbo']).read_text().strip(), '0')
            if name in ('scaling_min_freq', 'scaling_max_freq'):
                other = 'scaling_max_freq' if name == 'scaling_min_freq' else 'scaling_min_freq'
                bound = int(Path(self.state['paths'][other]).read_text())
                self.assertTrue(int(value) <= bound if name == 'scaling_min_freq' else int(value) >= bound)
            return real_write(path, text, *args, **kwargs)

        with patch.object(Path, 'write_text', hardware_write):
            controller.apply()
            self.assertEqual(self.state['applied'], self.state['requested'])
            controller.restore()
        self.assertTrue(self.state['restoration_verified'])
        self.assertEqual(history[6], ('no_turbo', '0'))

    def test_failure_at_every_write_restores_original(self):
        for failure in range(6):
            state = copy.deepcopy(self.state)
            controller = environment.Controller(state)
            real_write = Path.write_text
            calls = 0

            def fail_once(path, text, *args, **kwargs):
                nonlocal calls
                index = calls; calls += 1
                # Model a write that changes state and then reports failure.
                result = real_write(path, text, *args, **kwargs)
                if index == failure: raise OSError('injected partial write failure')
                return result

            with patch.object(Path, 'write_text', fail_once):
                with self.assertRaises(OSError): controller.apply()
                controller.restore()
            self.assertTrue(state['restoration_verified'], (failure, state))

    def test_restoration_read_error_is_reported_and_other_settings_restore(self):
        controller = environment.Controller(self.state)
        controller.apply()
        real_read = Path.read_text

        def fail_read(path, *args, **kwargs):
            if path.name == 'scaling_min_freq': raise OSError('injected unavailable readback')
            return real_read(path, *args, **kwargs)

        with patch.object(Path, 'read_text', fail_read): controller.restore()
        self.assertFalse(self.state['restoration_verified'])
        self.assertEqual(len(self.state['restoration_errors']), 1)
        for key, value in self.state['original'].items():
            self.assertEqual(Path(self.state['paths'][key]).read_text().strip(), value)

    def test_cpu_list_formats(self):
        self.assertEqual(environment.cpu_list('0-2,4,7-8'), [0, 1, 2, 4, 7, 8])
        self.assertEqual(environment.cpu_list('4 5 '), [4, 5])

    def test_offline_online_mask_transition_and_restore(self):
        topology = Path(self.directory.name)/'thread_siblings_list'
        topology.write_text('4-5\n')
        self.state['thread_siblings_before'] = [4, 5]
        real_write = Path.write_text

        def hardware_write(path, text, *args, **kwargs):
            result = real_write(path, text, *args, **kwargs)
            if path.name == 'online_5':
                real_write(topology, '4\n' if text.strip() == '0' else '4-5\n')
            return result

        controller = environment.Controller(self.state)
        with patch.object(Path, 'write_text', hardware_write):
            controller.apply()
            self.assertEqual(topology.read_text().strip(), '4')
            environment.validate_smt_topology(4, self.state['thread_siblings_before'], [5],
                topology.read_text(), {'5': Path(self.state['paths']['online_5']).read_text().strip()})
            controller.restore()
        self.assertTrue(self.state['restoration_verified'])
        self.assertEqual(topology.read_text().strip(), '4-5')

    def test_transient_frequency_readback_mismatch_is_recorded_and_retried(self):
        controller = environment.Controller(self.state)
        real_write = Path.write_text
        clamped = False

        def temporary_clamp(path, text, *args, **kwargs):
            nonlocal clamped
            if path.name == 'scaling_max_freq' and text.strip() == '3000000' and not clamped:
                clamped = True
                return real_write(path, '3200000\n')
            return real_write(path, text, *args, **kwargs)

        with patch.object(Path, 'write_text', temporary_clamp), patch.object(environment.time, 'sleep'):
            controller.apply()
            attempts = [w for w in self.state['setting_writes'] if w['name'] == 'scaling_max_freq']
            self.assertEqual([w['observed'] for w in attempts], ['3200000', '3000000'])
            self.assertEqual(self.state['applied'], self.state['requested'])
            controller.restore()
        self.assertTrue(self.state['restoration_verified'])

    def test_persistent_frequency_clamp_fails_with_actual_value_and_restores(self):
        controller = environment.Controller(self.state)
        real_write = Path.write_text

        def persistent_clamp(path, text, *args, **kwargs):
            if path.name == 'scaling_max_freq' and text.strip() == '3000000':
                return real_write(path, '3200000\n')
            return real_write(path, text, *args, **kwargs)

        with patch.object(Path, 'write_text', persistent_clamp), \
             patch.object(environment.time, 'sleep'), patch.object(environment, 'SETTING_ATTEMPTS', 3):
            with self.assertRaisesRegex(RuntimeError, 'requested=3000000, observed=3200000, attempts=3'):
                controller.apply()
            attempts = [w for w in self.state['setting_writes'] if w['name'] == 'scaling_max_freq']
            self.assertEqual(len(attempts), 3)
            controller.restore()
        self.assertTrue(self.state['restoration_verified'])

    def test_write_and_read_oserrors_are_not_retried(self):
        real_write, real_read = Path.write_text, Path.read_text
        for stage in ['write', 'read']:
            with self.subTest(stage=stage):
                state = copy.deepcopy(self.state)
                for name, value in state['original'].items():
                    real_write(Path(state['paths'][name]), value+'\n')
                controller = environment.Controller(state)
                failed = False

                def fail_write(path, text, *args, **kwargs):
                    nonlocal failed
                    result = real_write(path, text, *args, **kwargs)
                    if stage == 'write' and not failed:
                        failed = True
                        raise OSError('injected write error')
                    return result

                def fail_read(path, *args, **kwargs):
                    nonlocal failed
                    if stage == 'read' and not failed:
                        failed = True
                        raise OSError('injected read error')
                    return real_read(path, *args, **kwargs)

                with patch.object(Path, 'write_text', fail_write), \
                     patch.object(Path, 'read_text', fail_read), patch.object(environment.time, 'sleep') as sleep:
                    with self.assertRaises(OSError): controller.write('scaling_max_freq', '3000000')
                    sleep.assert_not_called()
                    attempts = [w for w in state['setting_writes'] if w['phase'] == 'apply']
                    self.assertEqual(len(attempts), 1)
                    self.assertIn('error', attempts[0])
                    controller.restore()
                self.assertTrue(state['restoration_verified'])

    def test_monotonic_deadline_stops_attempts_before_count_limit(self):
        real_write = Path.write_text

        def clamp(path, text, *args, **kwargs):
            if path.name == 'scaling_max_freq' and text.strip() == '3000000':
                return real_write(path, '3200000\n')
            return real_write(path, text, *args, **kwargs)

        with patch.object(environment.time, 'monotonic', side_effect=[0.0, 0.0, 0.0, 2.0]), \
             patch.object(environment.time, 'sleep') as sleep, patch.object(Path, 'write_text', clamp):
            controller = environment.Controller(self.state)
            with self.assertRaisesRegex(RuntimeError, 'attempts=1, timeout_seconds=1.0'):
                controller.write('scaling_max_freq', '3000000')
            sleep.assert_not_called()
        controller.restore()
        self.assertTrue(self.state['restoration_verified'])

    def test_final_plan_must_match_after_individual_writes(self):
        real_write = Path.write_text

        def interfere(path, text, *args, **kwargs):
            result = real_write(path, text, *args, **kwargs)
            if path.name == 'scaling_min_freq' and text.strip() == '3000000':
                real_write(Path(self.state['paths']['no_turbo']), '0\n')
            return result

        controller = environment.Controller(self.state)
        with patch.object(Path, 'write_text', interfere):
            with self.assertRaisesRegex(RuntimeError, 'Controlled environment check failed: requested=.*observed='):
                controller.apply()
            self.assertEqual(self.state['applied']['no_turbo'], '0')
            controller.restore()
        self.assertTrue(self.state['restoration_verified'])

    def test_cli_reports_configuration_failure_and_never_starts_child(self):
        captured = []
        stderr = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch('sys.argv', ['environment.py', '--execute', '--out',
                                str(Path(self.directory.name)/'record.json'), '--', '/never/launched']))
            stack.enter_context(patch.dict(environment.os.environ, {'SUDO_UID': '1000', 'SUDO_GID': '1000'}))
            stack.enter_context(patch.object(environment, 'plan', side_effect=lambda *a: copy.deepcopy(self.state)))
            stack.enter_context(patch.object(environment.os, 'geteuid', return_value=0))
            stack.enter_context(patch.object(environment.os, 'open', return_value=900))
            stack.enter_context(patch.object(environment.os, 'fstat', return_value=SimpleNamespace(st_uid=0, st_nlink=1, st_mode=stat.S_IFREG)))
            stack.enter_context(patch.object(environment.os, 'close'))
            stack.enter_context(patch.object(environment.fcntl, 'flock'))
            stack.enter_context(patch.object(environment.os, 'sched_getaffinity', return_value={4, 5}))
            stack.enter_context(patch.object(environment.os, 'sched_setaffinity'))
            stack.enter_context(patch.object(environment.signal, 'signal'))
            stack.enter_context(patch.object(environment.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='fixture', pw_dir='/fixture')))
            stack.enter_context(patch.object(environment, 'save_as_user', side_effect=lambda p,s,*a: captured.append(copy.deepcopy(s))))
            stack.enter_context(patch.object(environment.Controller, 'apply', side_effect=RuntimeError('setting mismatch: requested=3000000, observed=3200000')))
            child = stack.enter_context(patch.object(environment.subprocess, 'Popen'))
            stack.enter_context(patch('sys.stderr', stderr))
            with self.assertRaises(SystemExit) as result: environment.main()
            self.assertEqual(result.exception.code, 1)
            child.assert_not_called()
        self.assertIn('Controlled benchmark failed', stderr.getvalue())
        self.assertIn('observed=3200000', stderr.getvalue())
        self.assertIn('CPU settings restored', stderr.getvalue())
        self.assertEqual(captured[-1]['status'], 'interrupted_or_failed')
        self.assertTrue(captured[-1]['restoration_verified'])


if __name__ == '__main__': unittest.main()
