"""Enumerate product magnitudes in the paper's finite control experiment."""
from fractions import Fraction as F
from itertools import product,combinations

def rot(a):return (-a[3],a[0],a[1],a[2])
def orbit(a):
 out=[]
 for _ in range(8):out.append(a);a=rot(a)
 return out
U=orbit((1,0,0,0));A=orbit((1,1,0,0))
D=[]
for i,j in combinations(range(4),2):
 for s,t in product([-1,1],repeat=2):
  a=[0]*4;a[i]=s;a[j]=t;D.append(tuple(a))
def mul(a,b):
 c=[0]*4
 for i in range(4):
  for j in range(4):c[(i+j)%4]+=a[i]*b[j]*(1 if i+j<4 else -1)
 return c
P=(1,0,1,0)
def model(pair_atoms):
 # coefficients constant,alpha,beta,alpha*beta
 out={}
 for ak,aa in enumerate([U,pair_atoms]):
  for bk,bb in enumerate([U,pair_atoms]):
   for a,b in product(aa,bb):
    b=[v*(1 if i%2==0 else -1) for i,v in enumerate(b)]
    x=abs(mul(a,mul(P,b))[0]);v=out.setdefault(x,[F(0) for _ in range(4)])
    co=[[1,-1,-1,1],[0,0,1,-1],[0,1,0,-1],[0,0,0,1]][2*ak+bk]
    for i in range(4):v[i]+=F(co[i],len(aa)*len(bb))
 return out
c=model(A);i=model(D)
assert c[2]==[0,0,0,F(1,4)]
assert i[2]==[0,F(1,12),F(1,12),F(1,3)]
assert max(c)==max(i)==2
assert c[1]==[F(1,2),F(1,2),F(1,2),F(-3,2)]
assert i[1]==[F(1,2),F(1,6),F(1,6),F(-5,6)]
print("Coefficients in order 1, a, b, ab")
print("Complementary mass at |X|=2:", *c[2])
print("Isotropic mass at |X|=2:    ", *i[2])
