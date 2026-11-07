"""Exact pair transfer matrices for the correction-on W-code bound.
No output-coordinate independence assumption is used.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict,Counter
from math import gcd,lcm,log2,exp,log
import json,sys
import numpy as np
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parents[1]/'baseline'
sys.path.insert(0,str(OLD/'encoding'))
from double_layer import atoms

def rot(v,k=1):
 v=tuple(v)
 for _ in range(k%8):v=(-v[3],v[0],v[1],v[2])
 return v

def mul(a,b):
 c=[0]*4
 for i,x in enumerate(a):
  for j,y in enumerate(b):c[(i+j)%4]+=x*y*(-1 if i+j>=4 else 1)
 return c

def value(a,b,P):
 c=mul(a,b)
 return c[0]-c[2] if P else c[0]

def setup(left,right,P):
 aa=atoms(left);bb=atoms(right)
 dena=lcm(*(p.denominator for _,p in aa));denb=lcm(*(p.denominator for _,p in bb))
 av=[x for x,p in aa];aw=[int(p*dena)for x,p in aa]
 bv=[tuple((-1 if j%2 else 1)*v for j,v in enumerate(x))for x,p in bb];bw=[int(p*denb)for x,p in bb]
 # Opposite orientation leaves the atom law unchanged.
 vals=np.array([[value(a,b,P)for b in bv]for a in av],dtype=int)
 rotations=[[av.index(rot(a,k))for a in av]for k in range(8)]
 return dict(vals=vals,av=av,bv=bv,aw=aw,bw=bw,dena=dena,denb=denb,rotations=rotations)

def kernel_float(s,t,sign):
 v=s['vals'];p=np.array(s['aw'],float)/s['dena'];pr=np.array(s['bw'],float)/s['denb']
 k=np.array([[np.sum(pr*np.exp(t*(v[i]+sign*v[j])))*p[j]for j in range(len(p))]for i in range(len(p))])
 return k

def kernel_exact(s,a,sign):
 v=s['vals'];E=int(2*np.max(np.abs(v)));p,d=a.numerator,a.denominator
 den=s['dena']*s['denb']*(p*d)**E
 exps={e:p**(e+E)*d**(E-e)for e in range(-E,E+1)}
 k=np.array([[sum(w*exps[int(x+sign*y)]for w,x,y in zip(s['bw'],v[i],v[j]))*s['aw'][j]for j in range(len(s['aw']))]for i in range(len(s['aw']))],dtype=object)
 # Rotation invariance implies K commutes with the 8-cycle permutation.
 rr=s['rotations'][1]
 assert all(k[rr[i],rr[j]]==k[i,j]for i in range(len(rr))for j in range(len(rr)))
 return k,den

def pair_classes(n):
 L=n//4;out=Counter()
 # Ordered forward displacement; unordered-pair sum is n/2 times this sum.
 for d in range(1,n):
  low,k=d%L,d//L
  if low==0:ell,copies,a=1,L,0
  else:copies=gcd(L,low);ell=L//copies;a=low//copies
  # K1(g,g') = K0(g,rot(g',-1)); target component k contributes -k.
  twist=(-k*ell-a)%8
  out[(ell,copies,twist)]+=1
 return out

def trace_twist(power,s,r):
 # trace(K P_r), where P columns map index j to rotated atom.
 # Sum K[i, rot(i,r)] (sign convention can be swapped by r -> -r).
 return sum(power[i,s['rotations'][r][i]]for i in range(len(s['aw'])))

def mgfs(s,n,t=None,a=None):
 L=n//4;result={};exact=a is not None
 for sign in (1,-1):
  if exact:k,den=kernel_exact(s,a,sign)
  else:k=kernel_float(s,t,sign);den=1
  powers={1:k}
  ell=2
  while ell<=L:powers[ell]=powers[ell//2]@powers[ell//2];ell*=2
  vals={}
  for ell,copies,r in pair_classes(n):
   v=trace_twist(powers[ell],s,r)
   if exact:v=F(int(v),den**ell)**copies
   else:v=float(v)**copies
   vals[(ell,copies,r)]=v
  result[sign]=vals
 return result

def bound(n,q,laws,t=None,a=None,details=False):
 exact=a is not None;L=n//4
 assert n>=8 and n&(n-1)==0 and q%2==1
 assert all(q%d for d in range(2,int(q**.5)+1))
 def order(v,mod):
  z=v%mod;j=1
  while z!=1:z=z*v%mod;j+=1
  return j
 assert order(q,2*n)==L*order(q,8)
 assert laws[3]==(F(1,2),F(0),F(1,2))
 assert all(sum(law)==1 and min(law)>=0 for law in laws)
 gr=setup(laws[1],laws[2],True);fm=setup(laws[0],laws[3],False)
 mg=mgfs(gr,n,t,a);mf=mgfs(fm,n,t,a)
 def pair(key):return 2*sum(mg[s][key]*mf[s][key]for s in (1,-1))
 classes=pair_classes(n)
 if exact:base=a
 else:base=exp(t)
 # All-coordinate pair term bounds >=two wraps via |Zi|+|Zj| >= q+1.
 two=F(n,2)*sum(count*pair(key)for key,count in classes.items())/base**(q+1)
 # Within-quartet wrong-location event uses pair sum >=q, unordered 6 per quartet.
 within=F(n,2)*sum(pair((1,L,(-k)%8))for k in (1,2,3))/base**q
 # Extreme single wrap, |Zj|>=q, needs separate coverage.
 def single(s):
  v=s['vals'];return sum(F(w, s['dena'])*F(u,s['denb'])*base**int(z)for w,row in zip(s['aw'],v)for u,z in zip(s['bw'],row))**L
 extreme=2*n*single(gr)*single(fm)/base**q
 pacc=(1-(1-2*laws[0][1])**L)/2*(1-laws[1][0]**L)
 out=(two+within+extreme)/pacc
 if details:return dict(two=two/pacc,within=within/pacc,extreme=extreme/pacc,bound=out,acceptance=pacc)
 return out

def brutemgf(s,n,d,a,sign):
 from itertools import product
 L=n//4;assert L==2
 weightsa=list(zip(s['av'],s['aw']));weightsb=list(zip(s['bv'],s['bw']))
 total=F(0)
 P=s.get('P',False)
 # z0=sum T(g_i,R_i); zd_k=sum T_k(g_i,rot(R_i-d,-1 if i<d else0)).
 low,k=d%L,d//L
 for ga in product(weightsa,repeat=L):
  for rb in product(weightsb,repeat=L):
   z0=sum(value(ga[i][0],rb[i][0],P)for i in range(L))
   zd=sum(value(rot(ga[i][0],-k),rot(rb[(i-low)%L][0],-1 if i<low else 0),P)for i in range(L))
   w=1
   for v,j in ga+rb:w*=j
   total+=w*a**(z0+sign*zd)
 return total/(s['dena']*s['denb'])**L

def verify():
 law=(F(1,2),F(1,2),F(0));a=F(5,4);n=8
 rows=[]
 for P in (False,True):
  s=setup(law,law,P);s['P']=P
  mg=mgfs(s,n,a=a)
  for d in range(1,n):
   low,k=d%2,d//2
   if low==0:key=(1,2,(-k)%8)
   else:key=(2,1,(-2*k-low)%8)
   for sign in (1,-1):
    direct=brutemgf(s,n,d,a,sign)
    assert direct==mg[sign][key],(P,d,sign,float(direct),float(mg[sign][key]))
    rows.append(dict(P=P,d=d,sign=sign,exact_pass=True))
 return rows

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');ap.add_argument('--id');ap.add_argument('--q',type=int);ap.add_argument('--a');args=ap.parse_args()
 if args.verify:
  checks=verify();(ROOT/'transfer_checks.json').write_text(json.dumps(checks,indent=2)+'\n');print('exact complete enumeration checks',len(checks));sys.exit()
 rows=json.loads((OLD/'profiles/selected.json').read_text())
 row=next(x for x in rows if x['id']==args.id);laws=tuple(tuple(F(v)for v in law)for law in row['laws']);n=row['n'];q=args.q or row['q']
 if args.a:
  a=F(args.a);out=bound(n,q,laws,a=a,details=True)
  report={k:float(v)for k,v in out.items()};B=out['bound'];report.update(bound_numerator_hex=hex(B.numerator),bound_denominator_hex=hex(B.denominator));report.update(n=n,q=q,id=args.id,a=str(a),bound_exponent=log2(B.denominator)-log2(B.numerator),pass133=B*2**133<=1,pass163=B*2**163<=1,pass166=B*2**166<=1)
  (ROOT/(args.id+'_q'+str(q)+'_certificate.json')).write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items()if not k.endswith('_hex')})
 else:
  def obj(t):
   try:b=bound(n,q,laws,t=t);return log(float(b))
   except (OverflowError,ValueError):return 1e100
  from scipy.optimize import minimize_scalar
  res=minimize_scalar(obj,bounds=(.01,1),method='bounded');print(dict(n=n,q=q,t=res.x,a=exp(res.x),b=-res.fun/log(2)))
