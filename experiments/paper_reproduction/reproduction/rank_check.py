#!/usr/bin/env python3
"""Check the four zero-coordinate constraints in the conditional key route.

Run: python3 rank_check.py --out rank_check.json
Dependencies: Python >=3.10 and NumPy. No project modules are imported.

The algebraic proof is in Supplementary Material, Appendix D-C. These tests are corroboration,
not a substitute for that proof and not a lattice-recovery experiment.
Polynomial arithmetic below is a standalone form of the project's
negacyclic multiplication and Euclidean-inversion routines.
"""
from __future__ import annotations
import argparse
from collections import Counter
from fractions import Fraction as F
import itertools
import json
import math
from pathlib import Path
import numpy as np

PROFILES = [
    ('S512', 512, 251, (247,80,185,512), (256,71,185,512)),
    ('S1024',1024,347,(63,10,55,128),(64,9,55,128)),
    ('D512',512,157,(128,5,123,256),(32,15,17,64)),
    ('D1024',1024,251,(128,3,125,256),(128,17,111,256)),
]

def rotate(a): return (-a[3],a[0],a[1],a[2])
def orbit(a):
    out=[]
    for _ in range(8): out.append(a);a=rotate(a)
    return out
MONO=orbit((1,0,0,0)); ADJ=orbit((1,1,0,0)); NONMONO=[(0,0,0,0)]+ADJ

def trim(a):
    a=list(a)
    while a and a[-1]==0:a.pop()
    return a

def divpoly(a,b,q):
    a=trim([int(x)%q for x in a]);b=trim([int(x)%q for x in b])
    assert b
    quo=[0]*max(0,len(a)-len(b)+1);ib=pow(b[-1],-1,q)
    while len(a)>=len(b):
        d=len(a)-len(b);c=a[-1]*ib%q;quo[d]=c
        for j,x in enumerate(b):a[d+j]=(a[d+j]-c*x)%q
        a=trim(a)
    return trim(quo),a

def inverse(f,q):
    n=len(f);mod=[1]+[0]*(n-1)+[1]
    r0,r1=mod,trim([int(x)%q for x in f]);t0,t1=[],[1]
    while r1:
        quo,r=divpoly(r0,r1,q);r0,r1=r1,r
        p=[] if not quo or not t1 else (np.convolve(quo,t1)%q).tolist()
        t=trim([((t0[i] if i<len(t0) else 0)-(p[i] if i<len(p) else 0))%q for i in range(max(len(t0),len(p)))])
        t0,t1=t1,t
    assert len(r0)==1
    _,t=divpoly([int(x)*pow(r0[0],-1,q)%q for x in t0],mod,q)
    return np.array(t+[0]*(n-len(t)),dtype=np.int64)

def mul(a,b,q):
    n=len(a);v=np.convolve(a,b);r=v[:n].copy();r[:n-1]-=v[n:]
    return r%q

def signed_shift(a,k):
    n=len(a);k%=2*n
    if k>=n:return -signed_shift(a,k-n)
    if not k:return a.copy()
    return np.concatenate((-a[-k:],a[:-k]))

def rank_mod(a,q):
    a=np.array(a,dtype=np.int64,copy=True)%q;r=0
    for j in range(a.shape[1]):
        nz=np.flatnonzero(a[r:,j])
        if not len(nz):continue
        k=r+int(nz[0]);a[[r,k]]=a[[k,r]]
        a[r]=a[r]*pow(int(a[r,j]),-1,q)%q
        for i in range(r+1,a.shape[0]):a[i]=(a[i]-a[i,j]*a[r])%q
        r+=1
        if r==a.shape[0]:break
    return r

def mono_block(a):
    b=a.reshape(4,len(a)//4);nz=np.flatnonzero(np.count_nonzero(b,axis=0)==1)
    assert len(nz)==1
    return int(nz[0])

def evaluate(f,g,q,ginv=None):
    n=len(f);L=n//4;i_f=mono_block(f);i_g=mono_block(g)
    hi=mul(f,inverse(g,q) if ginv is None else ginv,q)
    rows=i_f+L*np.arange(4);cols=np.array([j for j in range(n) if j%L!=i_g])
    mat=hi[(rows[:,None]-cols[None,:])%n]*np.where(rows[:,None]<cols[None,:],-1,1)
    rank=rank_mod(mat,q)
    nz=np.flatnonzero(hi)
    signed_monomial=len(nz)==1 and int(hi[nz[0]]) in (1,q-1)
    assert rank==(0 if signed_monomial else 4), (n,q,rank,i_f,i_g)
    return rank

def sample_conditional(n,law,rng):
    z,u,a,den=law;L=n//4
    p=[z/(z+a)]+[a/(8*(z+a))]*8
    b=np.array([NONMONO[i] for i in rng.choice(9,size=L,p=p)],dtype=np.int64).T
    j=int(rng.integers(L));b[:,j]=MONO[int(rng.integers(8))]
    return b.reshape(n)

def small_exhaustive(q):
    n=8;L=2;polys=[]
    for pos in range(L):
        for m in MONO:
            for a in NONMONO:
                b=np.zeros((4,L),dtype=np.int64);b[:,pos]=m;b[:,1-pos]=a
                polys.append(b.reshape(n))
    invs=[inverse(g,q) for g in polys];hist=Counter()
    for g,gi in zip(polys,invs):
        for f in polys:hist[evaluate(f,g,q,gi)]+=1
    return {'n':n,'q':q,'polynomials':len(polys),'ordered_pairs':len(polys)**2,'rank_counts':dict(hist)}

def probability(n,lf,lg):
    zf,uf,af,df=lf;zg,ug,ag,dg=lg
    # Conditioning on exactly one monomial block normalizes the other blocks.
    collision=F(zf,df-uf)*F(zg,dg-ug)+F(af,df-uf)*F(ag,dg-ug)/8
    p=collision**(n//4-1)
    return {'collision_per_remaining_block':str(collision),'probability_exact':str(p),
            'minus_log2_probability':math.log2(p.denominator)-math.log2(p.numerator)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='rank_check.json');ap.add_argument('--samples',type=int,default=8);ap.add_argument('--skip-exhaustive',action='store_true');args=ap.parse_args()
    rng=np.random.default_rng(202611070317);result={'seed':202611070317,'scope':'exact rank arithmetic; no BKZ recovery performed','profile_tests':[],'small_exhaustive':[]}
    for name,n,q,lf,lg in PROFILES:
        hist=Counter();deg=Counter()
        for j in range(args.samples):
            f=sample_conditional(n,lf,rng);g=sample_conditional(n,lg,rng);gi=inverse(g,q)
            assert np.array_equal(mul(g,gi,q),np.array([1]+[0]*(n-1)))
            hist[evaluate(f,g,q,gi)]+=1
            if j<2:
                f0=signed_shift(g,int(rng.integers(2*n)))
                deg[evaluate(f0,g,q,gi)]+=1
        row={'profile':name,'n':n,'q':q,'independent_conditional_pairs':args.samples,'independent_rank_counts':dict(hist),'deliberately_rotated_pair_counts':dict(deg),'conditional_rank_loss_probability':probability(n,lf,lg)}
        result['profile_tests'].append(row);print(name,'random ranks',dict(hist),'rotated ranks',dict(deg),'-log2 probability',row['conditional_rank_loss_probability']['minus_log2_probability'],flush=True)
    if not args.skip_exhaustive:
        for q in (3,157):
            row=small_exhaustive(q);result['small_exhaustive'].append(row);print('small',q,row['rank_counts'],flush=True)
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
