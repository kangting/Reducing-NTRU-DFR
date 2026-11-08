"""Exact representative controls for the revised paper, Python 3.10+.

Run: python3 reproduction/ablation_check.py
The only non-standard dependency is numpy, used for exact object-integer
transfer matrices. All comparisons use integer/rational arithmetic.
Probabilities refer to accepted-key-average INTERNAL message recovery.
The finite atom/PGF helpers are transcribed from the manuscript. This script
is self-contained and does not fetch or import the public code artifact.
"""
from collections import defaultdict
from fractions import Fraction as F
from math import gcd, lcm, log2
from pathlib import Path
import json
import numpy as np


def rotate(a, s=1):
    for _ in range(s % 8):
        a = (-a[3], a[0], a[1], a[2])
    return a


def multiply(a, b):
    n = len(a)
    out = [0] * n
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[(i+j) % n] += (-1 if i+j >= n else 1) * x*y
    return tuple(out)


SUPPORT = ([(0, 0, 0, 0)]
           + [rotate((1, 0, 0, 0), s) for s in range(8)]
           + [rotate((1, 1, 0, 0), s) for s in range(8)])
JSUPPORT = [(a[0], -a[1], a[2], -a[3]) for a in SUPPORT]


def triple(nums, den):
    return tuple(F(x, den) for x in nums)


def probabilities(t):
    return [t[0]] + [t[1]/8]*8 + [t[2]/8]*8


def block_value(a, b, with_p):
    c = multiply(a, b)
    return multiply((1, 0, 1, 0), c) if with_p else c


def pgf(left, right, with_p=False, orient=True, parity=False, coord2=0):
    out = defaultdict(F)
    for i, a in enumerate(SUPPORT):
        for j, b in enumerate(JSUPPORT if orient else SUPPORT):
            c = block_value(a, b, with_p)
            out[c[0]+coord2*c[2]] += left[i]*right[j]*(-1 if parity and 1 <= i <= 8 else 1)
    den = lcm(*(x.denominator for x in out.values()))
    minimum = min(out)
    return ([int(out[k]*den) for k in range(minimum, max(out)+1)], minimum, den)


def convolution(x, y):
    out = [0]*(len(x)+len(y)-1)
    for i, a in enumerate(x):
        if a:
            for j, b in enumerate(y):
                out[i+j] += a*b
    return out


def pgf_product(x, y):
    return convolution(x[0], y[0]), x[1]+y[1], x[2]*y[2]


def pgf_power(x, n):
    a, minimum, den = x
    out, exponent = [1], n
    while exponent:
        if exponent & 1:
            out = convolution(out, a)
        exponent //= 2
        if exponent:
            a = convolution(a, a)
    return out, minimum*n, den**n


def mass(x, lower, upper=None):
    a, minimum, den = x
    lo = max(0, lower-minimum)
    hi = len(a) if upper is None else max(0, min(len(a), upper-minimum+1))
    return F(sum(a[lo:hi]), den)


def exponent(x):
    assert x > 0
    return log2(x.denominator)-log2(x.numerator)


def acceptance(fp, gp, length):
    return (1-(1-2*fp[1])**length)/2*(1-gp[0]**length)


def conditional_pgf_terms(fp, gp, rp, mp, length, orient):
    f, g, r, m = map(probabilities, [fp, gp, rp, mp])
    gr = pgf(g, r, with_p=True, orient=orient)
    fm = pgf(f, m, orient=orient)
    chi = pgf(f, m, orient=orient, parity=True)
    return (pgf_power(pgf_product(gr, fm), length),
            pgf_power(pgf_product(gr, chi), length),
            pgf_power(fm, length), pgf_power(chi, length))


def accepted_mass(terms, gp, length, lower, upper=None):
    a, b, c, d = (mass(t, lower, upper) for t in terms)
    return (a-b-gp[0]**length*(c-d))/2


def record(x):
    return {'minus_log2': exponent(x), 'numerator_hex': hex(x.numerator),
            'denominator_hex': hex(x.denominator)}


def check_s512():
    n, q, length = 512, 251, 128
    fp = triple((247,80,185),512)
    gp = triple((256,71,185),512)
    rp = triple((256,113,143),512)
    mp = triple((1,2,1),4)
    acc = acceptance(fp,gp,length)
    on = conditional_pgf_terms(fp,gp,rp,mp,length,True)
    bound_on = 2*n*accepted_mass(on,gp,length,126)/acc
    assert bound_on < F(1,2**166)
    print('S512 J-on upper exponent', exponent(bound_on), flush=True)
    off = conditional_pgf_terms(fp,gp,rp,mp,length,False)
    # The positive moderate-wrap marginal includes exact key conditioning.
    moderate = accepted_mass(off,gp,length,126,376)
    f,g,r,m = map(probabilities,[fp,gp,rp,mp])
    # If |V_256| >=126, V0+/-V_256 >=252 in one sign.
    pairs=[]
    for sign in (-1,1):
        poly=pgf_product(pgf(g,r,True,False,coord2=sign),
                         pgf(f,m,False,False,coord2=sign))
        pairs.append(mass(pgf_power(poly,length),252))
    # Pair bounds are unconditioned and dominate intersection with Acc.
    lower=(moderate-sum(pairs))/acc
    assert lower > F(1,2**115)
    print('S512 J-off lower exponent',exponent(lower),flush=True)
    print('S512 pair-tail exponents',*[exponent(p) for p in pairs],flush=True)
    return {'on_upper':record(bound_on),'off_lower':record(lower),
            'off_moderate_joint_acceptance':record(moderate),
            'off_pair_majorants':[record(p) for p in pairs],
            'claims':{'on_less_than_2^-166':True,'off_greater_than_2^-115':True}}


def transfer_matrix(left,right,with_p,sign,a):
    values=[[block_value(x,y,with_p)[0] for y in JSUPPORT] for x in SUPPORT]
    return [[left[j]*sum(right[k]*a**(values[i][k]+sign*values[j][k])
                        for k in range(17)) for j in range(17)] for i in range(17)]


def d_bound(n,q,fp,gp,rp,mp,a):
    length=n//4
    f,g,r,m=map(probabilities,[fp,gp,rp,mp]); cache={}
    for kind,left,right,with_p in [('gr',g,r,True),('fm',f,m,False)]:
        for sign in (-1,1):
            rational=transfer_matrix(left,right,with_p,sign,a)
            den=lcm(*(x.denominator for row in rational for x in row))
            matrix=np.array([[int(x*den) for x in row] for row in rational],dtype=object)
            power=1
            while power<=length:
                for s in range(8):
                    trace=sum(matrix[i,SUPPORT.index(rotate(x,s))] for i,x in enumerate(SUPPORT))
                    cache[kind,sign,power,s]=F(trace,den**power)
                if power<length: matrix=matrix@matrix
                power*=2
        poly,minimum,den=pgf(left,right,with_p)
        cache[kind,'single']=sum(F(x,den)*a**(i+minimum) for i,x in enumerate(poly))**length
    def four_moments(delta):
        d,k=delta%length,delta//length
        c=gcd(length,d) if d else length
        power=length//c
        s=(-k*power-d//c)%8 if d else (-k)%8
        return 2*sum((cache['gr',sign,power,s]*cache['fm',sign,power,s])**c for sign in (-1,1))
    acc=acceptance(fp,gp,length)
    pairs=F(n,2)/a**(q+1)*sum(four_moments(d) for d in range(1,n))/acc
    within=F(n,2)/a**q*sum(four_moments(k*length) for k in (1,2,3))/acc
    extreme=2*n/a**q*cache['gr','single']*cache['fm','single']/acc
    return pairs+within+extreme,pairs


def check_d1024():
    n,q,length=1024,251,256
    fp=triple((128,3,125),256)
    gp=rp=triple((128,17,111),256)
    mp=triple((1,0,1),2)
    acc=acceptance(fp,gp,length)
    terms=conditional_pgf_terms(fp,gp,rp,mp,length,True)
    positive_tail=accepted_mass(terms,gp,length,126)/acc
    moderate=accepted_mass(terms,gp,length,126,376)/acc
    upper=2*n*positive_tail
    corrected,pair_majorant=d_bound(n,q,fp,gp,rp,mp,F(5,2))
    assert corrected < F(1,2**166)
    # W is the number of wrapped positions and M counts moderate wraps.
    # 1{W=M=1} >= M-W(W-1), and pair_majorant bounds sum_{i<j}
    # Pr(|Vi|+|Vj|>=q+1 | Acc), hence also all simultaneous wraps.
    lower=2*n*moderate-2*pair_majorant
    coarse_lower=2*n*moderate-2*F(1,2**166)
    assert lower<=upper
    assert coarse_lower > F(1,2**96)
    assert lower>=coarse_lower
    assert upper < F(1,2**95)
    print('D1024 correction-on upper exponent',exponent(corrected),flush=True)
    print('D1024 correction-off no-wrap upper exponent',exponent(upper),flush=True)
    print('D1024 correction-off lower exponent',exponent(lower),flush=True)
    return {'on_upper':record(corrected),'off_lower':record(lower),
            'off_upper':record(upper),'moderate_positive':record(moderate),
            'pair_majorant':record(pair_majorant),'coarse_lower':record(coarse_lower),
            'claims':{'on_less_than_2^-166':True,'off_greater_than_2^-96':True,
                      'off_less_than_2^-95':True}}


if __name__=='__main__':
    result={'S512':check_s512(),'D1024':check_d1024()}
    out=Path(__file__).with_suffix('.json')
    out.write_text(json.dumps(result,indent=2)+'\n')
    print('All exact inequalities passed. Output:',out)
