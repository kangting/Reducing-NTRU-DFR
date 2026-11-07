"""Guard scientific reaggregation against missing records and sample changes."""
import copy
from pathlib import Path
import unittest

import analyze


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = analyze.load(Path(__file__).parent/'data/q211-raw.json.gz')

    def setUp(self):
        self.data = copy.deepcopy(self.dataset)

    def test_missing_record_is_rejected(self):
        self.data['records'].pop()
        with self.assertRaisesRegex(ValueError,'reordered'):analyze.validate(self.data)

    def test_target_subset_cannot_be_a_complete_cohort(self):
        label = next(iter(self.data['targets']))
        self.data['targets'].pop(label)
        with self.assertRaisesRegex(ValueError,'cohort'):analyze.validate(self.data)

    def test_geometry_substitution_is_rejected(self):
        self.data['records'][0]['result']['pk_bytes'] += 1
        with self.assertRaisesRegex(ValueError,'geometry'):analyze.validate(self.data)

    def test_keygen_schedule_substitution_is_rejected(self):
        row = next(b for r in self.data['records'] if r['target'].startswith('hardened')
                   for b in r['result']['batches'] if b['operation']=='keygen')
        row['rng_bytes'] += 1
        with self.assertRaisesRegex(ValueError,'RNG schedule'):analyze.validate(self.data)

    def test_counter_delta_substitution_is_rejected(self):
        self.data['records'][0]['result']['batches'][0]['elapsed_cycles'] += 1
        with self.assertRaisesRegex(ValueError,'cycle delta'):analyze.validate(self.data)

    def test_fast_sample_selection_cannot_change(self):
        row = next(b for r in self.data['records'] for b in r['result']['batches'] if b['accepted'])
        row['accepted'] = False
        row['rejection_reasons'] = ['discarded_slow_sample']
        with self.assertRaisesRegex(ValueError,'selection'):analyze.validate(self.data)

    def test_counter_scope_change_is_rejected(self):
        self.data['counter']['exclude_kernel'] = True
        with self.assertRaisesRegex(ValueError,'Counter'):analyze.validate(self.data)

    def test_os_rng_boundary_is_preserved(self):
        row = next(b for r in self.data['records'] for b in r['result']['batches'] if b['operation']=='encaps')
        row['rng_calls'] = 1
        with self.assertRaisesRegex(ValueError,'OS entropy'):analyze.validate(self.data)

    def test_excluded_cells_are_blank(self):
        rows = list(analyze.summary_rows(self.data,self.data['summary']))
        excluded = [row for row in rows if row['status']=='excluded']
        self.assertEqual(len(excluded),3)
        self.assertTrue(all(row['exclusion_reason'] and row['median_kcycles']=='' for row in excluded))


if __name__=='__main__':unittest.main()
