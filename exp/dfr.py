"""Exact average internal-residue error bound at n=512, q=211 (Section V)."""
import argparse
import json
import math
from collections import defaultdict
from fractions import Fraction
from pathlib import Path


def rotate(a):
    return (-a[3], a[0], a[1], a[2])


def multiply(a, b):
    result = [0] * 4
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            result[(i + j) % 4] += x * y * (-1 if i + j >= 4 else 1)
    return tuple(result)


def product_law(left, right, factor):
    result = defaultdict(Fraction)
    for a, pa in left.items():
        for b, pb in right.items():
            opposite = (b[0], -b[1], b[2], -b[3])
            value = multiply(factor, multiply(a, opposite))[0]
            result[value] += pa * pb
    return result


def convolution(left, right):
    result = [0] * (len(left) + len(right) - 1)
    for i, x in enumerate(left):
        for j, y in enumerate(right):
            result[i + j] += x * y
    return result


def run(path):
    data = json.loads(Path(path).read_text())
    assert data['n'] == 512 and data['q'] == 211
    allowed = {(0, 0, 0, 0)}
    for start in [(1, 0, 0, 0), (1, 1, 0, 0)]:
        atom = start
        for _ in range(8):
            allowed.add(atom)
            atom = rotate(atom)
    laws = []
    for table in data['tables']:
        law = {tuple(row['atom']): Fraction(int(row['numerator']),
                                          int(row['denominator']))
               for row in table['rows']}
        assert set(law) <= allowed and sum(law.values()) == 1
        assert all(law[rotate(a)] == p for a, p in law.items())
        laws.append(law)
    f, g, r, m = laws
    for residue in range(4):
        assert sum(p for a, p in m.items()
                   if (a[0] + a[2]) % 2 + 2 * ((a[1] + a[3]) % 2)
                   == residue) == Fraction(1, 4)
    pg = product_law(g, r, (1, 0, 1, 0))
    fm = product_law(f, m, (1, 0, 0, 0))
    joint = defaultdict(Fraction)
    for x, px in pg.items():
        for y, py in fm.items():
            joint[x + y] += px * py
    low, high = min(joint), max(joint)
    denominator = math.lcm(*(p.denominator for p in joint.values()))
    weights = [int(joint.get(k, 0) * denominator)
               for k in range(low, high + 1)]
    assert sum(weights) == denominator and weights == weights[::-1]
    coefficients = [1]
    for _ in range(128):
        coefficients = convolution(coefficients, weights)
    tail = Fraction(sum(coefficients[106 - 128 * low:]), denominator**128)
    parity_bias = sum(p * (-1 if sum(a) % 2 else 1) for a, p in f.items())
    # On these q=211 supports, f's odd sum ensures both required units;
    # the only nonunit g is the all-zero polynomial (Section V).
    acceptance = (1 - parity_bias**128) / 2 * (1 - g[(0, 0, 0, 0)]**128)
    bound = 1024 * tail / acceptance
    assert bound <= Fraction(1, 2**129)
    exponent = math.log2(bound.denominator) - math.log2(bound.numerator)
    size = ((211**512 - 1).bit_length() + 7) // 8
    print(f'Internal average error <= 2^-129; bound exponent {exponent:.10f}')
    print(f'Public key / base polynomial: {size} / {size} bytes')
    print(f'Paper KEM format with 32-byte mask: {size} / {size+32} bytes; '
          f'total {2*size+32} bytes (KEM implementation: kem.py; functional tests: test.py)')
    return bound


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('params', nargs='?',
                        default=Path(__file__).resolve().parents[1] / 'par.json')
    run(parser.parse_args().params)
