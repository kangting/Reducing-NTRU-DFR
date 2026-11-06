"""Reproduce the q=349 matched-tail experiment. Python standard library only.
Complementary experiment: exact integer law and rational union bound.
Isotropic control: 70-digit decimal evaluation of a law involving sqrt(7).
"""
from collections import defaultdict
from decimal import Decimal as D, getcontext
from fractions import Fraction as F
from itertools import combinations, product, permutations
import math

getcontext().prec = 70
def orbit(a):
    out = []
    for _ in range(8):
        out.append(a)
        a = (-a[3], a[0], a[1], a[2])
    return out
zero = (0, 0, 0, 0)
U = orbit((1, 0, 0, 0))
A = orbit((1, 1, 0, 0))
full = orbit((1, 1, 1, 1))
pairs = []
for i, j in combinations(range(4), 2):
    for s, t in product([-1, 1], repeat=2):
        a = [0]*4; a[i] = s; a[j] = t
        pairs.append(tuple(a))
def atoms(*groups):
    """Each pair (list, weight) specifies the mass of each atom in list."""
    return [(v, w) for g, w in groups for v in g]
def scalar(k, m, with_P):
    out = defaultdict(lambda: 0)
    for a, pa in k:
        for b, pb in m:
            c = [0]*4
            for i, j in product(range(4), repeat=2):
                c[(i+j)%4] += a[i]*b[j]*(-1 if j%2 else 1)*(-1 if i+j>=4 else 1)
            out[c[0] - (c[2] if with_P else 0)] += pa*pb
    return out
def convolution(a,b):
    r = [0]*(len(a)+len(b)-1)
    for j,y in enumerate(b):
        for i,x in enumerate(a):
            r[i+j] += x*y
    return r
def experiment(key, msg):
    p, s = scalar(key,key,True), scalar(key,msg,False)
    z = convolution([p[j] for j in range(min(p), max(p)+1)],
                    [s[j] for j in range(min(s), max(s)+1)])
    offset = min(p)+min(s)
    v = sum((i+offset)**2*pi for i,pi in enumerate(z))/sum(z)*128
    law = [1]
    for _ in range(128):
        law = convolution(law,z)
    return sum(law[175-128*offset:]), v
def det(law):
    norm = sum(p for _,p in law); zero = 0*norm
    mat = [[sum((p*x[i]*x[j] for x,p in law),zero) for j in range(4)] for i in range(4)]
    val = sum((-1)**sum(s[i]>s[j] for i,j in combinations(range(4),2))*
              math.prod(mat[i][s[i]] for i in range(4)) for s in permutations(range(4)))
    return val / norm**4
k = atoms((U,1),(A,1))
m = atoms(([zero],8),(U,4),(A,2),(full,1))
tail_integer, v_comp = experiment(k,m)
accept = (F(1,2)-F(1,2**127))**2
bound = F(1024*tail_integer,(16**3*64)**128)/accept
assert bound <= F(1,2**129)
print("Complementary upper-bound exponent =", -math.log2(bound))
# Isotropic input covariance e*I; all four inputs have the matched determinant.
e = D(7).sqrt()/8
beta = 4*e-1
lift = 2*e-D(1)/2
ki = atoms((U,(1-beta)/8),(pairs,beta/24))
same = [v for v in pairs if v[0]*v[2] or v[1]*v[3]]
cross = [v for v in pairs if v not in same]
mi = atoms(([zero], D(1)/4-lift),(U,D(1)/16),(cross,D(1)/64),(same,lift/8))
for law in (k,m,ki,mi):
    assert abs(D(str(det(law)))-e**4) < D('1e-18')
for law in (m,mi):
    masses = defaultdict(lambda: 0)
    for x,p in law:
        masses[(x[0]+x[2])%2,(x[1]+x[3])%2] += p
    norm=sum(masses.values())
    assert len(masses)==4
    assert all(abs(4*x-norm) < D('1e-58') for x in masses.values())
tail, v_iso = experiment(ki,mi)
assert v_comp == 168 and abs(v_iso-168) < D('1e-58')
# Both f and g are required to be units modulo P and q. Each unit vector
# block projects nonzero in either q-factor field; each projection thus
# vanishes with probability at most beta^128. No independence of outputs.
accept_i = ((1-(2*beta-1)**128)/2 - 2*beta**128)**2
print("Isotropic upper-bound exponent (numerical) =", -math.log2(1024*tail/accept_i))
print("Unconditioned coefficient variance = 168; common input determinant =", e**4)
