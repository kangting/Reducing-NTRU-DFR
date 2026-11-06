"""Lower bound on the internal residue-recovery error via one pair of coefficients.

Uses exact subprobability masses for odd f, otherwise the unconditional
product laws. See orient.py for the upper bound. Python standard library.
"""
from collections import Counter
from fractions import Fraction as F
from itertools import product
from math import log2
from orient import f, g, r, m, mul, convolution, accepted


def project(left, right, factor, v, odd=False, sign=1):
    """Signed weights let a product of (-1)^parity track total f parity."""
    out = Counter()
    for (a, pa), (b, pb) in product(left.items(), right.items()):
        b = tuple(x*sign**i for i, x in enumerate(b))
        c = mul(factor, mul(a, b))
        key = sum(x*y for x, y in zip(v, c))
        out[key] += pa*pb * (-1 if odd and sum(a)%2 else 1)
    return out


def pmf(v, odd=False, sign=1):
    a = project(g, r, (1, 0, 1, 0), v, sign=sign)
    b = project(f, m, (1, 0, 0, 0), v, odd=odd, sign=sign)
    w = convolution(a, b)
    tot = Counter({0: 1})
    for _ in range(128):
        tot = convolution(tot, w)
    den = (sum(f.values())*sum(g.values())*sum(r.values())*sum(m.values()))**128
    assert sum(tot.values()) == (den if not odd else den*F(119,128)**128)
    return tot, den


def lower(sign=1):
    t, D = pmf((1,0,0,0), sign=sign)
    s, _ = pmf((1,0,0,0), True, sign)
    # Odd f and precisely one positive wrap of V0.
    first = F(sum(t[k]-s[k] for k in range(106,317)), 2*D)
    bad = []
    for d in [1, -1]:
        pair, _ = pmf((1,0,d,0), sign=sign)
        bad.append(F(sum(a for k,a in pair.items() if k>=212),D))
    # If V0>=106 and its partner also wraps then V0+V256 or
    # V0-V256 must be >=212. On the remaining event the seed bit changes.
    failed = (first - sum(bad) - F(15,32)**128)/accepted
    assert failed > 0
    return first, bad, failed


if __name__ == '__main__':
    first, bad, p = lower()
    e = lambda x:log2(x.denominator)-log2(x.numerator)
    assert 2**101 * first > F(65,64) and all(2**177 * x < 1 for x in bad)
    assert 2**139 * F(15,32)**128 < 1 and accepted < F(1,2)
    assert 2**100 * p > 1  # Check an integer lower bound, no floating-point use.
    print('same orientation; -log2 of: odd f & V0 in [106,316] =', e(first))
    print('two subtracted joint-wrap upper bounds:', [e(x) for x in bad])
    print('accepted-key internal residue-recovery error lower bound 2^-',e(p),sep='')
