"""Exact finite-sampler DFR certificates for power-of-two degree.

Each law is an aggregate triple (zero mass, total signed-monomial mass,
total signed-adjacent-pair mass). Every nonzero orbit has eight elements.
The fixed message law (1/4, 1/2, 1/4) is forced by uniform residues on
this support. This module does not evaluate cryptanalytic attack costs.
"""
from collections import defaultdict
from fractions import Fraction as F
from functools import lru_cache
from math import exp, log, log2, lcm, isqrt, gcd
from pathlib import Path
from itertools import permutations
import argparse
import json

DEFAULT_LAWS = (
    (F(1,2), F(9,256), F(119,256)),
    (F(15,32), F(85,256), F(51,256)),
    (F(7,16), F(27,64), F(9,64)),
    (F(1,4), F(1,2), F(1,4)),
)
NAMES = ('f','g','r','m')

def canonical_laws(laws=DEFAULT_LAWS):
    if isinstance(laws, dict):
        laws = [laws[k] for k in NAMES]
    # Floats are interpreted as their exact binary values. Supply Fraction
    # or rational strings for a deliberate exact probability specification.
    result = tuple(tuple(F(p) for p in row) for row in laws)
    if len(result) != 4 or any(len(row)!=3 or min(row)<0 or sum(row)!=1 for row in result):
        raise ValueError('expected four normalized nonnegative aggregate triples')
    if result[3] != (F(1,4),F(1,2),F(1,4)):
        raise ValueError('uniform residues on this 17-atom support fix the message law')
    return result

def is_prime(q):
    if q < 2: return False
    if q % 2 == 0: return q == 2
    return all(q % p for p in range(3, isqrt(q)+1, 2))

def admissible(n,q,exact_units_only=True):
    return (n >= 8 and n & (n-1) == 0 and q%2==1 and is_prime(q)
            and (multiplicative_order(q,2*n)==(n//4)*multiplicative_order(q,8)
                 if exact_units_only else q>17))

def multiplicative_order(q,m):
    if m<2 or gcd(q,m)!=1:
        raise ValueError('multiplicative order requires modulus >=2 and an invertible residue')
    value=q%m
    order=1
    while value!=1:
        value=value*q%m
        order+=1
    return order

def acceptance_details(n,q,laws=DEFAULT_LAWS,allow_general=False):
    if not admissible(n,q,not allow_general):
        raise ValueError('unsupported degree/modulus for the unit certificate')
    f,g,_,_=canonical_laws(laws)
    blocks=n//4
    odd=(1-(1-2*f[1])**blocks)/2
    if multiplicative_order(q,2*n)==(n//4)*multiplicative_order(q,8):
        value=odd*(1-g[0]**blocks)
        return value,dict(kind='exact',f_odd_probability=float(odd),
                          g_nonunit_upper=float(g[0]**blocks),f_extra_rejection_upper=0.)
    # At every primitive eighth root, the 17 atom evaluations are distinct
    # for q>17. Exhaustive resultants over Z have prime factors only2,3,17.
    d=multiplicative_order(q,2*n)
    d0=multiplicative_order(q,8)
    L=d//d0
    factors=n//d
    mu_f=max(f[0],f[1]/8,f[2]/8)
    mu_g=max(g[0],g[1]/8,g[2]/8)
    reject_f=min(F(1),factors*mu_f**L)
    reject_g=min(F(1),factors*mu_g**L)
    value=max(F(0),odd-reject_f)*max(F(0),1-reject_g)
    return value,dict(kind='rigorous lower bound',order_2n=d,order_8=d0,
                      extension_degree=L,number_of_factors=factors,
                      f_odd_probability=float(odd),
                      f_extra_rejection_upper=float(reject_f),
                      g_nonunit_upper=float(reject_g),
                      max_atom_f=str(mu_f),max_atom_g=str(mu_g))

def acceptance(n,q,laws=DEFAULT_LAWS,allow_general=False):
    return acceptance_details(n,q,laws,allow_general)[0]

def block_pgfs(laws=DEFAULT_LAWS):
    f,g,r,m = canonical_laws(laws)
    _,uf,af=f; _,ug,ag=g; _,ur,ar=r; _,um,am=m
    p1 = ug*ur/2 + ug*ar + ag*ur
    p2 = ag*ar/4
    h1 = uf*um/4 + (uf*am+af*um+af*am)/2
    pg = {-2:p2/2,-1:p1/2,0:1-p1-p2,1:p1/2,2:p2/2}
    fm = {-1:h1/2,0:1-h1,1:h1/2}
    return pg,fm

def joint_weights(laws=DEFAULT_LAWS):
    pg,fm = block_pgfs(laws)
    law=defaultdict(F)
    for x,px in pg.items():
        for y,py in fm.items(): law[x+y] += px*py
    denominator=lcm(*(p.denominator for p in law.values()))
    weights=tuple(int(law[k]*denominator) for k in range(-3,4))
    assert sum(weights)==denominator and weights==weights[::-1]
    return weights,denominator

@lru_cache(maxsize=24)
def coefficient_distribution(n,laws=DEFAULT_LAWS):
    """Unconditioned one-coordinate law, as integer weights / denominator."""
    laws=canonical_laws(laws)
    weights,denominator=joint_weights(laws)
    coefficients=[1]
    for _ in range(n//4):
        out=[0]*(len(coefficients)+6)
        for j,w in enumerate(weights):
            if not w: continue
            for i,x in enumerate(coefficients): out[i+j]+=w*x
        coefficients=out
    full_denom=denominator**(n//4)
    assert sum(coefficients)==full_denom
    return tuple(coefficients),full_denom

def exact_certificate(n,q,laws=DEFAULT_LAWS,target_bits=None,allow_general=False):
    if target_bits is not None:
        if int(target_bits)!=target_bits or target_bits<0:
            raise ValueError('exact certification requires a nonnegative integer exponent')
        target_bits=int(target_bits)
    laws=canonical_laws(laws)
    pacc,unit_info=acceptance_details(n,q,laws,allow_general)
    if not pacc: raise ValueError('zero key acceptance')
    coefficients,denominator=coefficient_distribution(n,laws)
    threshold=(q+1)//2
    offset=3*(n//4)
    tail=F(sum(coefficients[offset+threshold:]),denominator)
    bound=2*n*tail/pacc
    cert = None if target_bits is None else bound * 2**target_bits <= 1
    exponent=float('inf') if not bound else log2(bound.denominator)-log2(bound.numerator)
    poly_bytes=((q**n-1).bit_length()+7)//8
    pg,fm=block_pgfs(laws)
    variance=(n//4)*(sum(k*k*p for k,p in pg.items())+sum(k*k*p for k,p in fm.items()))
    return {
      'n':n,'q':q,'blocks':n//4,'target_bits':target_bits,
      'integer_inequality_passes':cert,'bound_exponent':exponent,
      'acceptance_probability':float(pacc),'coefficient_variance':str(variance),
      'acceptance_analysis':unit_info,
      'internal_message_bits':n//2,'external_message_bits':256,'mask_bytes':32,
      'public_key_bytes':poly_bytes,'ciphertext_bytes':poly_bytes+32,'sum_bytes':2*poly_bytes+32,
      'laws':{name:list(map(str,law)) for name,law in zip(NAMES,laws)},
      'positive_wrap_threshold':threshold,'tail_offset':offset,
      'certificate_method':'exact integer one-coordinate convolution, union bound 2n, rational acceptance correction',
      'assumptions':'n power of two; prime q admitted by acceptance analysis; independent blocks before acceptance',
    }

def chernoff_exponent(n,q,laws=DEFAULT_LAWS,allow_general=False):
    """Numerical screening exponent, not a rigorous certificate."""
    laws=canonical_laws(laws)
    pacc=float(acceptance(n,q,laws,allow_general))
    if pacc<=0: return float('-inf')
    weights,denom=joint_weights(laws)
    support=[(k-3,float(F(w,denom))) for k,w in enumerate(weights) if w]
    B=n//4
    threshold=(q+1)//2
    maximum=max(k for k,p in support)
    if threshold > B*maximum: return float('inf')
    def cumulant(t):
        values=[(k,log(p)+t*k) for k,p in support]
        pivot=max(a for k,a in values)
        mass=sum(exp(a-pivot) for k,a in values)
        mean=sum(k*exp(a-pivot) for k,a in values)/mass
        return pivot+log(mass),mean
    lo,hi=0.,1.
    while cumulant(hi)[1]*B < threshold and hi<1024: hi*=2
    for _ in range(60):
        mid=(lo+hi)/2
        if cumulant(mid)[1]*B < threshold: lo=mid
        else: hi=mid
    t=(lo+hi)/2
    return (t*threshold-B*cumulant(t)[0]-log(2*n)+log(pacc))/log(2)

def minimum_q(n,target_bits,laws=DEFAULT_LAWS,qmax=4096,allow_general=False):
    """Exact first admissible prime. The polynomial law is cached per n."""
    laws=canonical_laws(laws)
    coefficients,denominator=coefficient_distribution(n,laws)
    for q in range(3,qmax+1,2):
        if not admissible(n,q,not allow_general): continue
        if acceptance(n,q,laws,allow_general)<=0: continue
        row=exact_certificate(n,q,laws,target_bits,allow_general)
        if row['integer_inequality_passes']:
            return row
    return None

def verify_type_formulas():
    """Independent enumeration of every pair in the 17-atom supports."""
    def rotate(a): return (-a[3],a[0],a[1],a[2])
    def orbit(a):
        out=[]
        for _ in range(8): out.append(a); a=rotate(a)
        return out
    def mul(a,b):
        out=[0]*4
        for i,x in enumerate(a):
            for j,y in enumerate(b): out[(i+j)%4]+=x*y*(-1 if i+j>=4 else 1)
        return tuple(out)
    groups=[[(0,0,0,0)],orbit((1,0,0,0)),orbit((1,1,0,0))]
    for i,A in enumerate(groups):
        for j,B in enumerate(groups):
            laws=[tuple(F(k==i) for k in range(3)),tuple(F(k==i) for k in range(3)),
                  tuple(F(k==j) for k in range(3)),DEFAULT_LAWS[3]]
            # Check category pair PGFs directly against the type formulas,
            # including fm with arbitrary category in both inputs.
            for with_P in (False,True):
                obs=defaultdict(F)
                for a in A:
                    for b in B:
                        c=mul(a,tuple(x*(-1 if k%2 else 1) for k,x in enumerate(b)))
                        v=c[0]-c[2] if with_P else c[0]
                        obs[v]+=F(1,len(A)*len(B))
                u1,a1=F(i==1),F(i==2); u2,a2=F(j==1),F(j==2)
                p1=u1*u2/2+u1*a2+a1*u2 if with_P else u1*u2/4+(u1*a2+a1*u2+a1*a2)/2
                p2=a1*a2/4 if with_P else F(0)
                expected={0:1-p1-p2,-1:p1/2,1:p1/2,-2:p2/2,2:p2/2}
                assert all(obs[k]==expected.get(k,F(0)) for k in set(obs)|set(expected))
    return True

def verify_atom_norms():
    """Certify the integer norm list used for the general-prime unit bound."""
    def rotate(a): return (-a[3],a[0],a[1],a[2])
    atoms=[(0,0,0,0)]
    for a in ((1,0,0,0),(1,1,0,0)):
        for _ in range(8): atoms.append(a); a=rotate(a)
    values=set()
    for i,a in enumerate(atoms):
        for b in atoms[:i]:
            c=tuple(x-y for x,y in zip(a,b))
            columns=[]
            for _ in range(4): columns.append(c); c=rotate(c)
            matrix=list(zip(*columns))
            det=0
            for p in permutations(range(4)):
                sign=(-1)**sum(p[i]>p[j] for i in range(4) for j in range(i+1,4))
                v=sign
                for i in range(4): v*=matrix[i][p[i]]
                det+=v
            values.add(abs(det))
    assert values=={1,2,4,8,9,16,17,32}
    return sorted(values)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--n',type=int,default=1024)
    p.add_argument('--q',type=int)
    p.add_argument('--target',type=int,default=192)
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    verify_type_formulas()
    verify_atom_norms()
    row=exact_certificate(args.n,args.q,target_bits=args.target) if args.q else minimum_q(args.n,args.target)
    s=json.dumps(row,indent=2)
    if args.out: args.out.write_text(s+'\n')
    print(s)
