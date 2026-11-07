"""Check the conditional law and normalized-key algebra, not BKZ recovery."""
from fractions import Fraction
import json
from math import comb
from pathlib import Path
import ntru
import unittest

import numpy as np

from experiments.affine import MONOMIALS, ZERO, evaluate, model
from ntru import poly


PARAMS = Path(ntru.__file__).with_name('par.json')


class AffineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PARAMS.read_text())
        cls.values = model(cls.data)

    def test_conditional_law(self):
        # Independently sum all odd counts rather than use the parity formula.
        f = self.data['tables'][0]['rows']
        odd = sum(Fraction(r['numerator'], r['denominator'])
                  for r in f if sum(r['atom']) % 2)
        accepted = sum(comb(128, k) * odd**k * (1 - odd)**(128 - k)
                       for k in range(1, 129, 2))
        self.assertEqual(accepted, self.values['accepted_f'])
        self.assertEqual(128 * odd * (1 - odd)**127 / accepted,
                         self.values['subset'])
        # Push the derived a law through multiplication by (1+y), using
        # the polynomial implementation rather than the estimator's map.
        image = {}
        for atom, probability in self.values['a_law'].items():
            pair = tuple(int(v) for v in poly.mul(atom, [1, 1, 0, 0]))
            image[pair] = probability
        expected = {tuple(r['atom']): Fraction(r['numerator'], r['denominator']) / (1 - odd)
                    for r in f if not sum(r['atom']) % 2}
        self.assertEqual(image, expected)
        self.assertEqual(sum(image.values()), 1)

    def test_signed_monomial_invariance(self):
        # Exhaust the eight block rotations, including sign changes.
        for table in self.data['tables'][:2]:
            law = {tuple(r['atom']): Fraction(r['numerator'], r['denominator'])
                   for r in table['rows']}
            for unit in MONOMIALS:
                rotated = {tuple(int(v) for v in poly.mul(atom, unit)): probability
                           for atom, probability in law.items()}
                self.assertEqual(rotated, law)

    def test_normalized_affine_relation(self):
        n, q = self.data['n'], self.data['q']
        a_blocks = [ZERO if j % 7 == 0 else MONOMIALS[j % 8] for j in range(128)]
        a = np.asarray(a_blocks, dtype=np.int64).T.reshape(n)
        one_y = np.zeros(n, dtype=np.int64)
        one_y[0] = one_y[128] = 1
        fbar = poly.mul(one_y, a)
        fbar[0] += 1
        g_rows = self.data['tables'][1]['rows']
        gbar = np.asarray([g_rows[j % len(g_rows)]['atom'] for j in range(128)],
                          dtype=np.int64).T.reshape(n)
        h = poly.mul(gbar, poly.invq(fbar, q), q)
        np.testing.assert_array_equal(gbar % q, (h + poly.mul(one_y, poly.mul(h, a, q), q)) % q)
        for k, sign in [(0, 1), (127, -1), (128, 1), (511, -1)]:
            unit = np.zeros(n, dtype=np.int64)
            unit[k] = sign
            inverse = np.zeros(n, dtype=np.int64)
            inverse[0 if k == 0 else n - k] = sign if k == 0 else -sign
            f, g = poly.mul(unit, fbar), poly.mul(unit, gbar)
            # The accepted support remains valid after global normalization.
            for polynomial, table in [(f, self.data['tables'][0]), (g, self.data['tables'][1])]:
                support = {tuple(r['atom']) for r in table['rows']}
                self.assertTrue(all(tuple(block) in support for block in polynomial.reshape(4, 128).T))
            self.assertEqual(sum(sum(block) % 2 for block in f.reshape(4, 128).T), 1)
            np.testing.assert_array_equal(poly.mul(h, f, q), g % q)
            np.testing.assert_array_equal(poly.mul(inverse, f), fbar)
            np.testing.assert_array_equal(poly.mul(inverse, g), gbar)

    def test_estimate_threshold(self):
        result = evaluate(self.data)
        self.assertEqual((result['result']['dimension'], result['result']['beta']), (821, 409))
        self.assertLess(result['previous_beta']['criterion_ratio'], 1)
        self.assertGreaterEqual(result['result']['criterion_ratio'], 1)
        self.assertAlmostEqual(result['result']['classical_leading_sieve_exponent'], 119.428)
        self.assertAlmostEqual(result['result']['quantum_leading_sieve_exponent'], 105.113)


if __name__ == '__main__':
    unittest.main()
