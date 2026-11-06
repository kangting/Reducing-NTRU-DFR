"""Reproduce the pre-key-acceptance q curves from rounded Gaussian cell integrals."""
import itertools
import math
from pathlib import Path
import csv
import argparse
import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq, minimize_scalar
from scipy.special import ndtr, logsumexp


SQRT2=math.sqrt(2)


def rounded_var(tau):
    return 2*sum((2*k-1)*ndtr(-(k-.5)/tau) for k in range(1,60))


def cdf_interval(lo,hi,tau):
    if hi<=lo:return 0.0
    if lo>=0:return float(ndtr(-lo/tau)-ndtr(-hi/tau))
    return float(ndtr(hi/tau)-ndtr(lo/tau))


def cell_prob(k,s,l,t,tau):
    al,ah=k-.5,k+.5
    lows=[(0.,l-.5),(-1.,SQRT2*(s-.5)),(1.,SQRT2*(t-.5))]
    highs=[(0.,l+.5),(-1.,SQRT2*(s+.5)),(1.,SQRT2*(t+.5))]
    lines=lows+highs
    breaks={al,ah}
    for (a,b),(c,d) in itertools.combinations(lines,2):
        if a==c:continue
        v=(d-b)/(a-c)
        if al<v<ah:breaks.add(v)
    breaks=sorted(breaks)
    ans=err=0.0
    normalizer=1/(tau*math.sqrt(2*math.pi))
    for a,b in zip(breaks,breaks[1:]):
        mid=(a+b)/2
        lower=max(lows,key=lambda z:z[0]*mid+z[1])
        upper=min(highs,key=lambda z:z[0]*mid+z[1])
        if upper[0]*mid+upper[1] <= lower[0]*mid+lower[1]:continue
        def integrand(x):
            return (normalizer*math.exp(-.5*(x/tau)**2)*
                    cdf_interval(lower[0]*x+lower[1],upper[0]*x+upper[1],tau))
        value,error=quad(integrand,a,b,epsabs=1e-280,epsrel=2e-11,limit=100)
        ans+=value;err+=error
    return ans,err


def block_law(tau,K):
    entries=[]
    errors=[]
    for k in range(-K,K+1):
        for l in range(-K,K+1):
            slow=math.ceil((k+l-1)/SQRT2-.5)
            shigh=math.floor((k+l+1)/SQRT2+.5)
            tlow=math.ceil((l-k-1)/SQRT2-.5)
            thigh=math.floor((l-k+1)/SQRT2+.5)
            # Retain a box in all four latent coefficient coordinates.  It
            # is invariant under signed y rotations, unlike truncating only
            # the two independent latent coordinates A,B.
            for s in range(max(-K,slow),min(K,shigh)+1):
                for t in range(max(-K,tlow),min(K,thigh)+1):
                    p,err=cell_prob(k,s,l,t,tau)
                    if p>0:
                        entries.append(((k,s,l,t),p));errors.append(err)
    coeff=np.array([a for a,p in entries],dtype=np.int16)
    weights=np.array([p for a,p in entries])
    return coeff,weights,sum(errors)


def product_law(coeff,weights):
    # D_minus = diag(1,-1,1,-1) D_plus.
    # coeff_0(a * D_minus(b)) = a0*b0+a1*b3-a2*b2+a3*b1.
    perm=coeff[:,[0,3,2,1]]*np.array([1,1,-1,1],dtype=np.int16)
    bound=int(4*np.max(np.abs(coeff))**2)
    probs=np.zeros(2*bound+1)
    for start in range(0,len(coeff),128):
        a=coeff[start:start+128]
        product=a@perm.T
        joint=weights[start:start+128,None]*weights[None,:]
        probs += np.bincount((product+bound).ravel(),joint.ravel(),minlength=len(probs))
    keep=np.flatnonzero(probs)
    xs=keep-bound
    return xs,probs[keep]


def bound_curve(pmf, repetitions, qs, trunc_log2=-math.inf):
    xs = np.array([int(x) for x in pmf], dtype=float)
    logp = np.log(np.array(list(pmf.values()), dtype=float))
    rows = []
    for q in qs:
        T = (int(q) + 1) // 2
        def objective(t):
            return -t*T + repetitions * (logsumexp(logp+3*t*xs)+logsumexp(logp+t*xs))
        opt = minimize_scalar(objective, bounds=(0, 3), method='bounded',
                              options={'xatol': 1e-12})
        lg = (math.log(1024) + opt.fun) / math.log(2)
        total = np.logaddexp(lg*math.log(2), trunc_log2*math.log(2)) / math.log(2)
        rows.append(float(min(0, total)))
    return np.array(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="optional output CSV path")
    args = parser.parse_args()
    K=10
    tau=brentq(lambda v:rounded_var(v)-.5,.5,.8,xtol=1e-14)
    atoms,weights,_=block_law(tau,K)
    xs,probs=product_law(atoms,weights)
    product=dict(zip(xs,probs))
    scalar={k:cdf_interval(k-.5,k+.5,tau) for k in range(-K,K+1)}
    iid={}
    for a,pa in scalar.items():
        for b,pb in scalar.items():
            iid[a*b]=iid.get(a*b,0)+pa*pb
    trunc=math.log2(8*512*float(ndtr(-(K+.5)/tau)))
    qs=sorted(set(range(449,1100,8))|{577,1061})
    Ec=-bound_curve(product,128,qs,trunc)
    Ei=-bound_curve(iid,512,qs,trunc)
    if args.out:
        with args.out.open("w",newline="") as out:
            rows=csv.writer(out);rows.writerow(["q","independent","complementary"])
            rows.writerows(zip(qs,Ei,Ec))
    covariance = np.dot(atoms[:,0] * atoms[:,1], weights)
    print(f"tau={tau:.12f}; c0={covariance:.12f}")
    print(f"Noise variance: independent 1280; complementary {(1280*np.dot(xs*xs,probs)):.9f}")
    print(f"At q=577, complementary exponent {Ec[qs.index(577)]:.8f}.")
    print(f"At q=1061, independent exponent {Ei[qs.index(1061)]:.8f}.")
    # Monotonicity allows us to verify the first passing primes by checking
    # each marked prime and its immediate prime predecessor.
    assert -bound_curve(product,128,[571],trunc)[0] < 128 <= Ec[qs.index(577)]
    assert -bound_curve(iid,512,[1051],trunc)[0] < 128 <= Ei[qs.index(1061)]
