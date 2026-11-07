"""Exact accepted-key coefficient law; union bound needs no output independence.

The old bound divides an unconditional tail by key acceptance. Here we keep
f's parity in a signed generating function and subtract the g=0 subspace.
This applies only to power-of-two n and the exact-unit modulus condition.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
from math import lcm,log2,isqrt
import json

def atoms(law):
    z,u,a=law
    out=[((0,0,0,0),z,0)]
    for v,p,parity in [((1,0,0,0),u,1),((1,1,0,0),a,0)]:
        for _ in range(8):
            out.append((v,p/8,parity));v=(-v[3],v[0],v[1],v[2])
    return out

def product(left,right,with_P=False,signed_f=False):
    out=defaultdict(F)
    for a,pa,odd in atoms(left):
        for b,pb,_ in atoms(right):
            b=tuple((-1 if i%2 else 1)*x for i,x in enumerate(b))
            v=[0]*4
            for i,x in enumerate(a):
                for j,y in enumerate(b):v[(i+j)%4]+=x*y*(-1 if i+j>=4 else 1)
            out[v[0]-v[2] if with_P else v[0]]+=pa*pb*(-1 if signed_f and odd else 1)
    return {k:v for k,v in out.items() if v}

def conv(left,right):
    out=defaultdict(F)
    for x,px in left.items():
        for y,py in right.items():out[x+y]+=px*py
    return {k:v for k,v in out.items() if v}

def power(law,ell):
    lo,hi=min(law),max(law);den=lcm(*(x.denominator for x in law.values()))
    w=[int(law.get(k,F(0))*den) for k in range(lo,hi+1)]
    coeff=[1]
    for _ in range(ell):
        nxt=[0]*(len(coeff)+len(w)-1)
        for j,y in enumerate(w):
            if y:
                for i,x in enumerate(coeff):nxt[i+j]+=x*y
        coeff=nxt
    return lo*ell,coeff,den**ell

def tail(powered,threshold):
    lo,coeff,den=powered
    return F(sum(coeff[max(0,threshold-lo):]),den)

def order(q,m):
    k=1;a=q%m
    while a!=1:a=a*q%m;k+=1
    return k

def certificate(n,q,laws,target=None):
    laws=tuple(tuple(F(x)for x in row)for row in laws)
    assert n>=8 and n&(n-1)==0 and q%2==1
    assert all(q%d for d in range(2,isqrt(q)+1))
    ell=n//4
    assert order(q,2*n)==ell*order(q,8)
    assert all(sum(row)==1 and min(row)>=0 for row in laws)
    f,g,r,m=laws
    pg=product(g,r,True);fm=product(f,m);sm=product(f,m,signed_f=True)
    total=power(conv(pg,fm),ell);signed=power(conv(pg,sm),ell)
    plain_fm=power(fm,ell);signed_fm=power(sm,ell)
    odd=(1-(1-2*f[1])**ell)/2;acc=odd*(1-g[0]**ell)
    threshold=(q+1)//2
    old_tail=tail(total,threshold)
    numerator=(old_tail-tail(signed,threshold)-g[0]**ell*(tail(plain_fm,threshold)-tail(signed_fm,threshold)))/2
    assert numerator>=0
    bound=min(F(1),2*n*numerator/acc)
    old=min(F(1),2*n*old_tail/acc)
    assert bound<=old
    exponent=None if not bound else log2(bound.denominator)-log2(bound.numerator)
    ans=dict(n=n,q=q,laws=[[str(x)for x in row]for row in laws],
       acceptance_probability=str(acc),bound_exponent=exponent,
       old_bound_exponent=None if not old else log2(old.denominator)-log2(old.numerator),
       bound_rational=str(bound),exact_conditioning=True,
       method='signed f-parity PGFs; subtract g=0; exact integer convolution; 2n coordinate union bound',
       output_coordinate_independence_assumed=False)
    if target is not None:ans.update(target=target,integer_inequality_passes=bound*2**target<=1)
    return ans

def selfcheck():
    # Independent local DP retaining f parity and the all-g-zero event.
    laws=((F(1,2),F(3,8),F(1,8)),)*3+((F(1,4),F(1,2),F(1,4)),)
    f,g,r,m=laws;ell=2
    pg={False:product(g,r,True),True:{0:g[0]}}
    # For one block: total g vs the g=0 subset. f parity tracked directly.
    fm=[product((f[0],F(0),f[2]),m),product((F(0),f[1],F(0)),m)]
    states={(0,0,True):F(1)}
    local=defaultdict(F)
    # obtain g-nonzero contribution by subtracting g=0 from total law
    nz=dict(pg[False]);nz[0]=nz.get(0,F(0))-g[0]
    for gp,gg in [(True,pg[True]),(False,nz)]:
        for par in (0,1):
            for k,p in conv(gg,fm[par]).items():local[k,par,gp]+=p
    for _ in range(ell):
        nxt=defaultdict(F)
        for (k,par,z),p in states.items():
            for (kk,pp,zz),v in local.items():nxt[k+kk,par^pp,z and zz]+=p*v
        states=dict(nxt)
    pga=product(g,r,True);fma=product(f,m);fms=product(f,m,signed_f=True)
    def mapping(v):
        lo,c,d=v;return {lo+i:F(x,d)for i,x in enumerate(c)}
    T,S,A,B=[mapping(power(x,ell))for x in (conv(pga,fma),conv(pga,fms),fma,fms)]
    for k in range(min(T),max(T)+1):
        signed=(T.get(k,0)-S.get(k,0)-g[0]**ell*(A.get(k,0)-B.get(k,0)))/2
        assert signed==states.get((k,1,False),F(0))
    return dict(independent_local_parity_zero_state_dp_passed=True,n=8)

if __name__=='__main__':
    ROOT=Path(__file__).resolve().parent
    src=ROOT.parent/'baseline/profiles/selected.json'
    rows=json.loads(src.read_text());out=[]
    for row in rows:
        c=certificate(row['n'],row['q'],row['laws'],row['targets']['dfr'])
        c['id']=row['id'];out.append(c)
        print(c['id'],c['old_bound_exponent'],c['bound_exponent'],flush=True)
    (ROOT/'sharp_certificates.json').write_text(json.dumps(dict(selfcheck=selfcheck(),rows=out),indent=2)+'\n')
