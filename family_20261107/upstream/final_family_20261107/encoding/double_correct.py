"""Conservative zero-wrap certificate for the new W-code message law.

This bound does not claim any numerical benefit from single-wrap correction.
It averages over accepted keys. The exact-unit acceptance condition is checked.
"""
from fractions import Fraction as F
from collections import defaultdict
from math import lcm,log2,isqrt
from pathlib import Path
import json
from double_layer import atoms

def mul(a,b):
    out=[0]*4
    for i,x in enumerate(a):
        for j,y in enumerate(b):out[(i+j)%4]+=x*y*(-1 if i+j>=4 else 1)
    return out

def product_law(left,right,P=False):
    out=defaultdict(F)
    for a,pa in atoms(left):
        for b,pb in atoms(right):
            b=tuple(v*(-1 if i%2 else 1)for i,v in enumerate(b))
            c=mul(a,b);out[c[0]-c[2] if P else c[0]]+=pa*pb
    return {k:p for k,p in out.items()if p}

def order(q,m):
    x=q%m;k=1
    while x!=1:x=x*q%m;k+=1
    return k

def certificate(n,q,laws,target):
    laws=tuple(tuple(F(x)for x in row)for row in laws)
    assert n>=8 and not n&(n-1)
    assert q%2 and all(q%d for d in range(2,isqrt(q)+1))
    assert order(q,2*n)==(n//4)*order(q,8)
    assert all(sum(row)==1 and min(row)>=0 for row in laws)
    assert laws[3]==(F(1,2),F(0),F(1,2))
    f,g,r,m=laws;ell=n//4
    pg=product_law(g,r,True);fm=product_law(f,m)
    # Check the closed one-coordinate expression separately.
    assert fm=={-1:(1-f[0])/8,0:1-(1-f[0])/4,1:(1-f[0])/8}
    single=defaultdict(F)
    for a,pa in pg.items():
        for b,pb in fm.items():single[a+b]+=pa*pb
    low,high=min(single),max(single)
    den=lcm(*(p.denominator for p in single.values()))
    weights=[int(single[k]*den)for k in range(low,high+1)]
    assert weights==weights[::-1] and sum(weights)==den
    coefficients=[1]
    for _ in range(ell):
        out=[0]*(len(coefficients)+len(weights)-1)
        for j,w in enumerate(weights):
            for i,v in enumerate(coefficients):out[i+j]+=w*v
        coefficients=out
    full=den**ell;assert sum(coefficients)==full
    threshold=(q+1)//2
    tail=F(sum(coefficients[threshold-low*ell:]),full)
    pacc=(1-(1-2*f[1])**ell)/2*(1-g[0]**ell)
    bound=2*n*tail/pacc
    b=log2(bound.denominator)-log2(bound.numerator)
    result=dict(n=n,q=q,internal_message_bits=n//4,message_law=list(map(str,m)),
        accepted_key_average_zero_wrap_bound_exponent=b,target=target,
        exact_integer_inequality_passes=bound*2**target<=1,
        acceptance_probability=float(pacc),
        certificate_method='17-atom enumeration; exact integer one-coordinate convolution;2n union bound; exact acceptance correction',
        correction_benefit_used=False)
    return result

if __name__=='__main__':
    m=(F(1,2),F(0),F(1,2))
    cases={
      'I269_same_key_r_laws':(512,269,((F(1,2),F(1,16),F(7,16)),)*2+((F(1,2),F(1,8),F(3,8)),m),166),
      'V373_same_key_r_laws':(1024,373,((F(110,256),F(34,256),F(112,256)),(F(128,256),F(14,256),F(114,256)),(F(128,256),F(31,256),F(97,256)),m),163)
    }
    rows={key:certificate(*data)for key,data in cases.items()}
    for key,row in rows.items():print(key,row['accepted_key_average_zero_wrap_bound_exponent'])
    Path(__file__).with_name('double_certificates.json').write_text(json.dumps(rows,indent=2)+'\n')
