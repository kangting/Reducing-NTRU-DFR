"""Check admission boundaries without invoking sudo, PMU or host controls."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import analyze
import build
import run


class RunnerTests(unittest.TestCase):
    def test_preflight_geometry_is_bound(self):
        info = build.get_spec('p03-ref')
        wrong = dict(status='passed',roundtrips=256,keys=8,pk_bytes=1,ct_bytes=info['ct_bytes'],
                     seed_bytes=info['message_bytes'],scheme=info['profile_id'])
        process = subprocess.CompletedProcess([],0,json.dumps(wrong),'')
        with patch.object(run.subprocess,'run',return_value=process):
            with self.assertRaisesRegex(ValueError,'geometry'):run.preflight({'p03-ref':info},'family')

    def test_failed_final_validation_does_not_mark_restoration_admitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);output = root/'synthetic.json.gz';environment = root/'environment.json'
            control = root/'control';control.write_text('original')
            data = analyze.load(Path(__file__).resolve().parents[2]/'results/raw/ntru512.json.gz')
            data['environment']['settings_restored'] = False
            run.save(output,data);before = output.read_bytes()
            state = dict(status='completed',benchmark_returncode=0,restoration_verified=True,
                         original={'fixture':'original'},restored={'fixture':'original'},
                         restoration_errors=[],paths={'fixture':str(control)})
            environment.write_text(json.dumps(state))
            with patch.object(run.analyze,'validate',side_effect=ValueError('invalid synthetic data')):
                with self.assertRaisesRegex(ValueError,'invalid synthetic'):run.finalize(output,environment)
            self.assertEqual(output.read_bytes(),before)


if __name__=='__main__':unittest.main()
