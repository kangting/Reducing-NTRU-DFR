"""Independent physical-polynomial verification of D pair-MGF and decoder events."""
from pathlib import Path
from fractions import Fraction as F
from itertools import product
from math import lcm,gcd
import sys,json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'double'))
import pair_mgf as pm

def negamul(a,b):
    n=len(a);c=[0]*n
    for i,x in enumerate(a):
        if x:
            for j,y in enumerate(b):
                if y:c[(i+j)%n]+=x*y*(-1 if i+j>=n else 1)
    return c

def embed(atom,i,n,J=False):
    v=[0]*n;L=n//4
    for k,x in enumerate(atom):v[i+k*L]=x*(-1 if J and k%2 else 1)
    return v

def combine(c,P):
    if not P:return c
    n=len(c);half=n//2
    return [c[k]+c[(k-half)%n]*(-1 if k<half else 1)for k in range(n)]

def physical_mgf(n,d,left,right,P,a,sign):
    """Enumerate every left vector; integrate independent right blocks exactly.

    Contributions are generated from actual length-n negacyclic multiplication,
    not pair_mgf's matching/twist formula. This checks cycles of length up to4.
    """
    L=n//4;aa=pm.atoms(left);bb=pm.atoms(right)
    Da=lcm(*(p.denominator for _,p in aa));Db=lcm(*(p.denominator for _,p in bb))
    av=[x for x,p in aa];aw=[int(p*Da)for x,p in aa]
    bv=[x for x,p in bb];bw=[int(p*Db)for x,p in bb]
    E=8;num,den=a.numerator,a.denominator
    ep={e:num**(e+E)*den**(E-e)for e in range(-E,E+1)}
    tables=[];positions=[]
    for j in range(L):
        i0=(-j)%L;id=(d-j)%L;positions.append((i0,id))
        c0=[[combine(negamul(embed(x,i0,n),embed(y,j,n,True)),P)[0]for y in bv]for x in av]
        cd=[[combine(negamul(embed(x,id,n),embed(y,j,n,True)),P)[d]for y in bv]for x in av]
        tables.append([[sum(w*ep[c0[x][b]+sign*cd[y][b]]for b,w in enumerate(bw))for y in range(len(av))]for x in range(len(av))])
    total=0
    for ix in product(range(len(av)),repeat=L):
        w=1
        for i in ix:w*=aw[i]
        for j,(i0,id)in enumerate(positions):w*=tables[j][ix[i0]][ix[id]]
        total+=w
    return F(total,Da**L*Db**L*(num*den)**(E*L))

def key(n,d):
    L=n//4;low,k=d%L,d//L
    if low==0:return(1,L,(-k)%8)
    copies=gcd(L,low);ell=L//copies
    return(ell,copies,(-k*ell-low//copies)%8)

def checks():
    rows=[];a=F(5,4)
    law=(F(1,2),F(1,4),F(1,4));right=(F(1,2),F(0),F(1,2))
    for n,ds in [(8,range(1,8)),(16,[1,2,4,5])]:
        for P in (False,True):
            s=pm.setup(law,right,P);mg=pm.mgfs(s,n,a=a)
            for d in ds:
                for sign in (1,-1):
                    direct=physical_mgf(n,d,law,right,P,a,sign)
                    expected=mg[sign][key(n,d)]
                    assert direct==expected,(n,P,d,sign,float(direct),float(expected))
                    rows.append(dict(n=n,P=P,d=d,sign=sign,full_left17=True,right_adjacent9=True,exact_pass=True))
                    print('physical MGF exact pass',n,P,d,sign,flush=True)
    return rows

if __name__=='__main__':
    rows=checks()
    (ROOT/'physical_mgf_checks.json').write_text(json.dumps(rows,indent=2)+'\n')
