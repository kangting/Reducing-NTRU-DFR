"""Independent full beta-by-d matrix audit of the proposed sampler parameters.

Does not import route_cost or security. The assumed GSA success inequalities
are the manuscript model; this is an arithmetic audit, not a security proof.
"""
from pathlib import Path
from fractions import Fraction as F
from functools import lru_cache
import json,math
import numpy as np


@lru_cache(None)
def grids(n,fd,embedded):
    keeps=np.arange(4,n+1,4,dtype=float)[None,:]
    ds=fd+keeps+embedded
    bs=np.arange(40,fd+n+embedded+1,dtype=float)[:,None]
    logdelta=(np.log(bs/(2*math.pi*math.e))+np.log(math.pi*bs)/bs)/(2*(bs-1))
    logdelta=np.where(bs==40,math.log(1.01295),logdelta)
    shape=(2*bs-ds-1)*logdelta-.5*np.log(bs)
    matrices={}
    for name,a,b in [('classical',.29613500308205365,20.387885985467914),
                     ('quantum',.2663676536352464,25.299541499216627)]:
        d4f=np.maximum(bs*np.log(4/3)/np.log(bs/(2*math.pi*math.e)),0)
        cc=1/(1-2**(-a))
        svp=a*(bs-d4f)+b+2*np.log2(cc)+np.log2(np.maximum(ds-bs,1))
        matrices[name]=np.logaddexp2(3*np.log2(ds),svp)
    return keeps,ds,bs,shape,matrices

def single(n,q,v1,v2,embedded=False,fd=None):
    fd=n if fd is None else fd
    keeps,ds,bs,shape,costs=grids(n,fd,int(embedded))
    logdet=keeps*math.log(q)+fd*.5*math.log(v2/v1)+(math.log(v2)/2 if embedded else 0)
    margins=shape+logdet/ds-.5*math.log(v2)
    feasible=(ds>=bs)&(margins>=0)
    out={}
    for name,cost in costs.items():
        feasible_cost=np.where(feasible,cost,np.inf)
        i,j=np.unravel_index(np.argmin(feasible_cost),feasible_cost.shape)
        assert np.isfinite(feasible_cost[i,j])
        out[name]={'bits':float(feasible_cost[i,j]),'beta':int(bs[i,0]),
                   'dimension':int(ds[0,j]),'keep':int(keeps[0,j]),
                   'log_margin':float(margins[i,j])}
    return out

def derived_moments(n,laws):
    ell=n//4;out=[]
    for i,(z,u,a) in enumerate(laws):
        if i==0:
            b=1-2*u
            u,a=u*(1+b**(ell-1))/(1-b**ell),a*(1-b**(ell-1))/(1-b**ell)
        elif i==1:u,a=u/(1-z**ell),a/(1-z**ell)
        variance=u/4+a/2;cov=a/4
        out.append((float(variance),math.sqrt(float(variance*variance-2*cov*cov))))
    return out

def conditional_entropy(ell,z,u,a):
    """Diagnostic only. Shannon entropy is not a concrete attack cost."""
    density=float(a/(1-u))
    binary=-sum(p*math.log2(p) for p in (density,1-density) if p>0)
    return (ell-1)*(binary+3*density)

