"""Independently count displacement cycles and verify exact rational bounds."""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
from math import log2,isqrt
import json,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'double'))
import pair_mgf as pm

def graph_key(n,d):
    L=n//4;step,k=d%L,d//L
    visited=set();cycles=[]
    for first in range(L):
        if first in visited:continue
        j=first;length=0;twist=0
        while j not in visited:
            visited.add(j);length+=1;twist-=k
            if j+step>=L:twist-=1
            j=(j+step)%L
        cycles.append((length,twist%8))
    assert len(set(cycles))==1
    ell,twist=cycles[0]
    return ell,len(cycles),twist

def order(q,m):
    a=q%m;k=1
    while a!=1:a=a*q%m;k+=1
    return k

def check(row,q,a,target):
    n=row['n'];L=n//4;laws=tuple(tuple(F(x)for x in law)for law in row['laws'])
    assert q>2 and all(q%d for d in range(2,isqrt(q)+1))
    assert order(q,2*n)==L*order(q,8)
    gr=pm.setup(laws[1],laws[2],True);fm=pm.setup(laws[0],laws[3],False)
    Mgr=pm.mgfs(gr,n,a=a);Mfm=pm.mgfs(fm,n,a=a)
    classes=Counter(graph_key(n,d)for d in range(1,n))
    assert classes==pm.pair_classes(n)
    assert sum(classes.values())==n-1
    def pair(key):return 2*(Mgr[1][key]*Mfm[1][key]+Mgr[-1][key]*Mfm[-1][key])
    two=F(n,2)*sum(pair(graph_key(n,d))for d in range(1,n))/a**(q+1)
    within=F(n,2)*sum(pair(graph_key(n,k*L))for k in (1,2,3))/a**q
    # Independently enumerate marginal product law for extreme coefficient.
    def marginal(s):
        numerator=F(0)
        for i,row in enumerate(s['vals']):
            for j,value in enumerate(row):numerator+=F(s['aw'][i]*s['bw'][j],s['dena']*s['denb'])*a**int(value)
        return numerator**L
    extreme=2*n*marginal(gr)*marginal(fm)/a**q
    acceptance=(1-(1-2*laws[0][1])**L)/2*(1-laws[1][0]**L)
    B=(two+within+extreme)/acceptance
    assert B==pm.bound(n,q,laws,a=a)
    b=log2(B.denominator)-log2(B.numerator)
    report=dict(id=row['id'],n=n,q=q,a=str(a),target=target,bound_exponent=b,
      integer_inequality_passed=B*2**target<=1,
      prime_and_exact_unit_order_passed=True,
      direct_graph_cycle_counts_passed=True,
      exact_rational_recomputation_passed=True,
      bound_numerator_bits=B.numerator.bit_length(),bound_denominator_bits=B.denominator.bit_length(),
      two=float(two/acceptance),within=float(within/acceptance),extreme=float(extreme/acceptance))
    print(report,flush=True)
    return report

if __name__=='__main__':
    rows=json.loads((ROOT.parents[1]/'baseline/profiles/selected.json').read_text())
    D={row['n']:row for row in rows if row['mode']=='double'}
    result=[check(D[512],157,F(3),133),check(D[1024],269,F(3),163),check(D[1024],251,F(5,2),166)]
    assert all(x['integer_inequality_passed']for x in result)
    (ROOT/'exact_bound_checks.json').write_text(json.dumps(result,indent=2)+'\n')
