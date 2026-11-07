"""Functional underlying-PKE/ACWC0 checks, not a production KEM or benchmark."""
from pathlib import Path
from fractions import Fraction as F
import json,sys,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'baseline'
sys.path.insert(0,str(OLD/'encoding'))
import double_layer as dl
poly=dl.poly

def encode_single(u,rng):
    n=2*len(u);L=n//4
    orbit=dl.atoms((F(1,4),F(1,2),F(1,4)))
    classes={k:[a for a,p in orbit if dl.residue_class(a)==k] for k in [(0,0),(1,0),(0,1),(1,1)]}
    blocks=[]
    for i in range(L):
        items=classes[(int(u[i]),int(u[L+i]))]
        a=items[int(rng.integers(len(items)))]
        blocks.append(tuple(v*(-1 if j%2 else 1)for j,v in enumerate(a)))
    m=np.array(blocks,dtype=np.int64).T.reshape(n)
    assert np.array_equal(poly.residue(m,n//2),u)
    return m

def check(row,rng):
    n,q=row['n'],row['q'];laws=tuple(tuple(F(v)for v in law)for law in row['laws'])
    f,g,h,finv=dl.keygen(n,q,laws[0],laws[1],rng)
    P=np.zeros(n,dtype=np.int64);P[0]=P[n//2]=1
    Pinv=np.zeros(n,dtype=np.int64);Pinv[0]=pow(2,-1,q);Pinv[n//2]=-pow(2,-1,q)
    for trial in range(12):
        u=rng.integers(2,size=n//2);m=encode_single(u,rng)
        r=dl.sample_vector(n,laws[2],rng,True)
        c=(poly.mul(h,r,q)+poly.mul(Pinv,m,q))%q
        wire=poly.pack(c,q);c=poly.unpack(wire,n,q)
        v=poly.center(poly.mul(P,poly.mul(f,c,q),q),q)
        uu=poly.unpackbits(poly.f2_ringmul(finv,poly.packbits(poly.residue(v,n//2)),n//2),n//2)
        assert np.array_equal(u,uu)
        message=rng.bytes(32)
        mask=hashlib.shake_256(poly.pack(h,q)+np.packbits(u,bitorder='little').tobytes()).digest(32)
        component=bytes(x^y for x,y in zip(message,mask))
        mask2=hashlib.shake_256(poly.pack(h,q)+np.packbits(uu,bitorder='little').tobytes()).digest(32)
        assert bytes(x^y for x,y in zip(component,mask2))==message
    return dict(id=row['id'],n=n,q=q,roundtrips=12,base_and_acwc0_roundtrips_passed=True,
        scope='functional seeded ideal-sampler checks; no FO proof, cryptographic PRNG, constant-time or timing claim')

if __name__=='__main__':
    rows=json.loads((ROOT/'single/selected_refined.json').read_text())
    ids={'S512_q251_C140_sharp','S512_q251_C1395_sharp','S1024_q347_den128_sharp'}
    chosen=[x for x in rows if x['id'] in ids]
    strict=json.loads((ROOT/'single/strict/selected_strict.json').read_text())
    chosen += [x for x in strict if x['id']in {'S1024_M256_D256_simple','S1024_M256_D256_541'}]
    rng=np.random.default_rng(2026110702)
    out=[check(x,rng)for x in chosen]
    (ROOT/'single_functional.json').write_text(json.dumps(out,indent=2)+'\n')
    for x in out:print(x['id'],x['q'],'12 passed',flush=True)
