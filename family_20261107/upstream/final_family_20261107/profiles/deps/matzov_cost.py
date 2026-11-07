"""Port of lattice-estimator 5ba00f5 RC.MATZOV reduction cost only.

Source: estimator/reduction.py, MATZOV inherits GJ21/Kyber.__call__.
This is not a port of the full estimator or its attack portfolio.
"""
from math import log, log2, pi, e
import numpy as np

A = 0.29613500308205365
B = 20.387885985467914
C = 1 / (1 - 2**(-A))
QUANTUM_A = 0.2663676536352464
QUANTUM_B = 25.299541499216627

def log2_cost(beta, dimension, a=A, b=B):
    """Classical gate-model log2 reduction cost; beta>=20, d>=beta."""
    beta=np.asarray(beta,dtype=float)
    dimension=np.asarray(dimension,dtype=float)
    if np.any(beta<20) or np.any(dimension<beta):
        raise ValueError('requires d >= beta >= 20')
    d4f=np.maximum(beta*np.log(4/3)/np.log(beta/(2*pi*e)),0)
    cc=1/(1-2**(-a))
    lattice=a*(beta-d4f)+b+2*log2(cc)+np.log2(np.maximum(dimension-beta,1))
    lll=3*np.log2(dimension)
    return np.logaddexp2(lll,lattice)

def first_beta(target_bits, dimension):
    """First beta meeting target; NOT a universal monotone inverse near beta=d."""
    for beta in range(40,int(dimension)+1):
        if log2_cost(beta,dimension)>=target_bits:
            return beta
    return None

def maximum_affordable_betas(target_bits, dimensions):
    """Largest beta strictly below target cost for each dimension.

    Exhaustive discrete scan avoids assuming monotonic cost near beta=d.
    GSA margin monotonicity in beta is a separate modelling assumption.
    """
    ds=np.asarray(dimensions,dtype=int)
    result=[]
    for d in ds:
        bs=np.arange(40,d+1)
        valid=bs[log2_cost(bs,d)<target_bits]
        result.append(int(valid[-1]) if len(valid) else 0)
    return np.asarray(result)

if __name__=='__main__':
    import json
    # Official exact-commit docstring: RC.Kyber(500,1024) = 2^176.55419197058822.
    kyber=float(log2_cost(500,1024,.2988026130564745,26.011121212891872))
    assert abs(kyber-176.55419197058822)<1e-11
    # Official exact-commit docstring for list_decoding-ge19.
    ge19=float(log2_cost(500,1024,.2695210400018704,35.47132142280775))
    assert abs(ge19-172.89020262269491)<1e-11
    print(json.dumps({'official_docstring_checks':{'Kyber':kyber,'ge19':ge19},
      'MATZOV_500_1024':float(log2_cost(500,1024)),
      'inversions':{str(d):{str(t):first_beta(t,d) for t in (196,207,262,266.5,269.9,272)}
                    for d in (1024,1280,1536,1792,2048)}},indent=2))
