"""Research prototype for the W-code layer over the current 17-atom support.

The interface is the underlying PKE, before the existing ACWC0/FO wrappers.
It intentionally has no constant-time or full KEM implementation claim.
"""
from pathlib import Path
import sys,json
from fractions import Fraction as F
from collections import defaultdict
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'common'))
import poly

def atoms(law):
    z,u,a=map(F,law);out=[((0,0,0,0),z)]
    for first,mass in [((1,0,0,0),u),((1,1,0,0),a)]:
        x=first
        for _ in range(8):
            out.append((x,mass/8));x=(-x[3],x[0],x[1],x[2])
    return [(x,p) for x,p in out if p]

def residue_class(x):return ((x[0]+x[2])%2,(x[1]+x[3])%2)

def sample_vector(n,law,rng,opposite=False):
    rows=atoms(law);p=np.array([float(v)for _,v in rows]);p/=p.sum()
    block=np.array([rows[int(i)][0] for i in rng.choice(len(rows),size=n//4,p=p)],dtype=np.int64).T
    if opposite:block*=np.array([1,-1,1,-1])[:,None]
    return block.reshape(n)

def encode(message,rng):
    """Uniform bit u_i selects class00/11, giving law(1/2,0,1/2)."""
    message=np.asarray(message,dtype=np.int64);ell=len(message)
    pair=[x for x,p in atoms((0,0,1))]
    block=np.zeros((4,ell),dtype=np.int64)
    for i,bit in enumerate(message):
        if bit:block[:,i]=np.array(pair[int(rng.integers(8))])*[1,-1,1,-1]
    result=block.reshape(4*ell)
    assert np.array_equal(poly.residue(result,2*ell),np.tile(message,2))
    return result

def decode_v(v,finv):
    """DAWN-style position selection followed by inversion moduloP overF2."""
    v=np.asarray(v,dtype=np.int64);n=len(v);ell=n//4
    syndrome=poly.residue(v,ell)
    flips=np.flatnonzero(syndrome)
    if len(flips)>1:return None
    correction=None
    bits=v%2
    if len(flips):
        i=int(flips[0]);positions=np.array([i+k*ell for k in range(4)])
        correction=int(positions[np.argmax(np.abs(v[positions]))])
        bits[correction]^=1
    out=poly.unpackbits(poly.f2_ringmul(finv,poly.packbits(poly.residue(bits,2*ell)),2*ell),2*ell)
    if not np.array_equal(out[:ell],out[ell:]):return None
    return out[:ell],correction

def keygen(n,q,f_law,g_law,rng):
    while True:
        f=sample_vector(n,f_law,rng)
        finv=poly.f2_inv(poly.packbits(poly.residue(f,n//2)),n//2)
        if finv is None:continue
        fq=poly.invq(f,q)
        if fq is not None:break
    while True:
        g=sample_vector(n,g_law,rng)
        if poly.invq(g,q) is not None:break
    return f,g,poly.mul(g,fq,q),finv

def encrypt(h,message,r_law,q,rng):
    n=len(h);r=sample_vector(n,r_law,rng,True);m=encode(message,rng)
    Pinv=np.zeros(n,dtype=np.int64);Pinv[0]=pow(2,-1,q);Pinv[n//2]=-pow(2,-1,q)
    c=(poly.mul(h,r,q)+poly.mul(Pinv,m,q))%q
    return c,r,m

def decrypt(f,finv,c,q):
    n=len(f);P=np.zeros(n,dtype=np.int64);P[0]=P[n//2]=1
    v=poly.center(poly.mul(P,poly.mul(f,c,q),q),q)
    return decode_v(v,finv)

def selfcheck():
    rng=np.random.default_rng(20261107);n=32;q=7;ell=n//4
    laws=((F(1,2),F(3,8),F(1,8)),)*3
    f,g,h,finv=keygen(n,q,laws[0],laws[1],rng)
    P=np.zeros(n,dtype=np.int64);P[0]=P[n//2]=1
    counts=defaultdict(int)
    for _ in range(1000):
        u=rng.integers(2,size=ell);c,r,m=encrypt(h,u,laws[2],q,rng)
        z=poly.mul(P,poly.mul(g,r))+poly.mul(f,m)
        v=poly.center(z,q);e=(z-v)//q
        assert np.array_equal(v,poly.center(poly.mul(P,poly.mul(f,c,q),q),q))
        result=decrypt(f,finv,c,q);ok=result is not None and np.array_equal(result[0],u)
        nonzero=np.flatnonzero(e)
        if not len(nonzero):
            counts['zero_wrap']+=1;assert ok
        elif len(nonzero)==1 and abs(e[nonzero[0]])==1:
            counts['one_wrap']+=1
            j=int(nonzero[0]);positions=np.array([j%ell+k*ell for k in range(4)])
            if j==positions[np.argmax(np.abs(v[positions]))]:
                counts['one_wrap_position_correct']+=1;assert ok
            if ok:counts['one_wrap_recovered']+=1
        else:counts['multiple_or_large_wrap']+=1
    # Exhaustive clean codewords and deliberately single-wrap syndromes.
    for k in range(1<<ell):
        u=np.array([(k>>i)&1 for i in range(ell)])
        m=encode(u,rng)
        base=poly.mul(f,m)
        # A synthetically wrapped v differing in exactlyone paritycoefficient
        # whose magnitude dominates its four-position class.
        for j in range(n):
            v=base.copy();v[j]-=q
            pos=np.array([j%ell+t*ell for t in range(4)])
            if j==pos[np.argmax(np.abs(v[pos]))]:
                result=decode_v(v,finv)
                assert result is not None and np.array_equal(result[0],u)
                counts['synthetic_single_wrap_verified']+=1
    return dict(n=n,q=q,seed=20261107,counts=dict(counts),message_law=['1/2','0','1/2'],all_checks_pass=True)

if __name__=='__main__':
    out=selfcheck();print(json.dumps(out,indent=2))
    Path(__file__).with_name('prototype_checks.json').write_text(json.dumps(out,indent=2)+'\n')
