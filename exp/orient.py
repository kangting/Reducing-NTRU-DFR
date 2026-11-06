"""Exact q=211 orientation control; Python 3.8+, standard library.

Only the substitution on the 4-coefficient r,m blocks changes.
The reported failure probability is a union bound divided by key
acceptance; it is not a measured or exact joint failure probability.
"""
from collections import Counter
from fractions import Fraction as F
from math import log2
from itertools import product


def rotate(v):
    return (-v[-1],) + v[:3]


def orbit(v):
    out = []
    for _ in range(8):
        out.append(v)
        v = rotate(v)
    return out


zero = (0, 0, 0, 0)
U = orbit((1, 0, 0, 0))
A = orbit((1, 1, 0, 0))


def law(z, u, a):
    return {zero: z, **dict.fromkeys(U, u), **dict.fromkeys(A, a)}


# Integer weights for Table II; normalize only after multiplication.
f = law(1024, 9, 119)
g = law(960, 85, 51)
r = law(224, 27, 9)
m = law(8, 2, 1)
accepted = (1-F(119, 128)**128) * (1-F(15, 32)**128) / 2


def mul(v, w):
    out = [0]*4
    for i, j in product(range(4), repeat=2):
        out[(i+j) % 4] += (-1 if i+j >= 4 else 1)*v[i]*w[j]
    return tuple(out)


def block(left, right, p, sign, coordinate):
    weights = Counter()
    for (v, pv), (w, pw) in product(left.items(), right.items()):
        w = tuple(x*sign**i for i, x in enumerate(w))
        value = mul(p, mul(v, w))[coordinate]
        weights[value] += pv*pw
    return weights


def convolution(left, right):
    out = Counter()
    for (i, a), (j, b) in product(left.items(), right.items()):
        out[i+j] += a*b
    return out


def variance(w):
    mass = sum(w.values())
    assert sum(i*a for i, a in w.items()) == 0
    return F(sum(i*i*a for i, a in w.items()), mass)


def compare(sign):
    pg = block(g, r, (1, 0, 1, 0), sign, 0)
    fm = block(f, m, (1, 0, 0, 0), sign, 0)
    for j in range(1, 4):
        assert block(g, r, (1, 0, 1, 0), sign, j) == pg
        assert block(f, m, (1, 0, 0, 0), sign, j) == fm
    w = convolution(pg, fm)
    assert all(w[-i] == a for i, a in w.items())
    total = Counter({0: 1})
    for _ in range(128):
        total = convolution(total, w)
    assert sum(total.values()) == sum(w.values())**128
    t = F(sum(a for i, a in total.items() if i >= 106), sum(total.values()))
    upper = 1024*t/accepted
    e = log2(upper.denominator) - log2(upper.numerator)
    k = round(e)
    if 2**k * upper > 1:
        k -= 1
    assert 2**k * upper <= 1 < 2**(k+1) * upper
    return 128*variance(pg), 128*variance(fm), e, k


if __name__ == '__main__':
    for sign, name in [(-1, 'complementary'), (1, 'same orientation')]:
        v1, v2, exponent, certified = compare(sign)
        print(f'{name}: var(Pgr)={v1}, var(fm)={v2}, '
              f'var(V)={v1+v2} ({float(v1+v2):.6f}); '
              f'bound exponent={exponent:.10f}, integer={certified}')
