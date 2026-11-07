"""Independent exact-law Python oracle for the NEW local family byte contract.

Importing does not run an encryption or a test.
This is an oracle, not a constant-time/production cryptographic implementation.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct
import sys
import numpy as np

HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parents[2]/'implementations/python'))
from ntru import poly


def orbit():
    result=[(0,0,0,0)]
    for seed in ((1,0,0,0),(1,1,0,0)):
        a=seed
        for _ in range(8):result.append(a);a=(-a[3],*a[:3])
    return result

@dataclass
class Secret:
    f:np.ndarray
    fp_inverse:int
    public_key:bytes
    rejection_seed:bytes

class Family:
    def __init__(self,number):
        self.profile=next(x for x in json.loads((HERE/'profiles.json').read_text())['profiles'] if x['number']==number)
        p=self.profile;s=p['semantic'];self.n=s['n'];self.q=s['q'];self.double=s['mode']=='double'
        self.half=self.n//2;self.blocks=self.n//4;self.mbytes=s['external_message_bits']//8;self.ubytes=s['internal_residue_bits']//8
        self.pkbytes=p['pk_bytes'];self.ctbytes=p['ct_bytes'];self.wordbytes=p['word_bytes'];self.samplebytes=self.blocks*self.wordbytes
        self.rhobytes=self.samplebytes+self.blocks;self.fbytes=p['f_trials']*self.samplebytes;self.gbytes=2*self.samplebytes
        self.atoms=orbit();self.laws=[[Fraction(v) for v in law] for law in s['laws']]
        self.classes={c:[a for a in self.atoms if ((a[0]+a[2])&1)+2*((a[1]+a[3])&1)==c] for c in range(4)}

    def sample(self,which,data):
        if len(data)!=self.samplebytes:raise ValueError('Coefficient tape length')
        z,u,a=self.laws[which];masses=[z]+[u/8]*8+[a/8]*8
        resolution=max(x.denominator for x in masses) # All exact denominators are powers of two.
        coefficients=[]
        for j in range(self.blocks):
            x=int.from_bytes(data[j*self.wordbytes:(j+1)*self.wordbytes],'little')&(resolution-1)
            cumulative=0
            for atom,p in zip(self.atoms,masses):
                cumulative+=int(p*resolution)
                if x<cumulative:coefficients.append(atom);break
        return np.array(coefficients,dtype=np.int64).T.reshape(self.n)

    def sample_rm(self,u,rho):
        if len(u)!=self.ubytes or len(rho)!=self.rhobytes:raise ValueError('Residue/tape length')
        r=self.sample(2,rho[:self.samplebytes]).reshape(4,self.blocks)
        r*=np.array([1,-1,1,-1])[:,None];bits=int.from_bytes(u,'little');columns=[]
        for j in range(self.blocks):
            v=rho[self.samplebytes+j]
            if self.double:atom=self.atoms[9+(v&7)] if (bits>>j)&1 else self.atoms[0]
            else:
                c=((bits>>j)&1)|(((bits>>(j+self.blocks))&1)<<1)
                atom=self.classes[c][v&(len(self.classes[c])-1)]
            columns.append(tuple(a*(1 if k%2==0 else -1) for k,a in enumerate(atom)))
        return r.reshape(self.n),np.array(columns,dtype=np.int64).T.reshape(self.n)

    def keygen(self,data):
        if len(data)!=self.fbytes+self.gbytes+self.mbytes:raise ValueError('Key tape length')
        f=fp=None
        for i in range(self.profile['f_trials']):
            candidate=self.sample(0,data[i*self.samplebytes:(i+1)*self.samplebytes])
            inverse=poly.f2_inv(poly.packbits(poly.residue(candidate,self.half)),self.half)
            if inverse is not None:f,fp=candidate,inverse;break
        g=None
        for i in range(2):
            start=self.fbytes+i*self.samplebytes;candidate=self.sample(1,data[start:start+self.samplebytes])
            if poly.invq(candidate,self.q) is not None:g=candidate;break
        if f is None or g is None:raise ValueError('Pool exhausted')
        fq=poly.invq(f,self.q)
        if fq is None:raise AssertionError('Unit shortcut violated')
        pk=poly.pack(poly.mul(g,fq,self.q),self.q)
        return pk,Secret(f,fp,pk,data[-self.mbytes:])

    def base_encrypt(self,pk,u,rho):
        h=poly.unpack(pk,self.n,self.q);r,m=self.sample_rm(u,rho)
        inverse=np.zeros(self.n,dtype=np.int64);inverse[0]=(self.q+1)//2;inverse[self.half]=-(self.q+1)//2
        return poly.pack((poly.mul(h,r,self.q)+poly.mul(inverse,m,self.q))%self.q,self.q)

    def base_decrypt(self,sk,ct):
        try:c=poly.unpack(ct,self.n,self.q)
        except ValueError:return None
        product=poly.mul(sk.f,c,self.q)
        v=np.concatenate((product[:self.half]-product[self.half:],product[:self.half]+product[self.half:]))%self.q
        v=poly.center(v,self.q);bits=v%2
        if self.double:
            syndrome=poly.residue(v,self.blocks);positions=np.flatnonzero(syndrome)
            if len(positions)>1:return None
            if len(positions)==1:
                group=[int(positions[0])+k*self.blocks for k in range(4)]
                chosen=max(group,key=lambda j:abs(int(v[j]))) # Python max preserves first ties.
                bits[chosen]^=1
        residue=poly.packbits(poly.residue(bits,self.half));out=poly.f2_ringmul(sk.fp_inverse,residue,self.half)
        if self.double and (out&((1<<self.blocks)-1))!=(out>>self.blocks):return None
        return int(out&((1<<(8*self.ubytes))-1)).to_bytes(self.ubytes,'little')

    def hash(self,tag,pk,parts,length):
        def frame(x):return struct.pack('<Q',len(x))+x
        s=self.profile['semantic'];context=frame(s['version'].encode())+frame(self.profile['parameter_id'].encode())+frame(pk)
        return hashlib.shake_256(frame(tag)+frame(context)+b''.join(frame(x) for x in parts)).digest(length)

    def deterministic_encrypt(self,pk,message):
        if len(message)!=self.mbytes:raise ValueError('External message length')
        coins=self.hash(b'G',pk,[message],self.ubytes+self.rhobytes);u=coins[:self.ubytes]
        c=self.base_encrypt(pk,u,coins[self.ubytes:]);mask=self.hash(b'F',pk,[u],self.mbytes)
        return c+bytes(a^b for a,b in zip(message,mask))

    def encaps(self,pk,message):
        ct=self.deterministic_encrypt(pk,message);return ct,self.hash(b'H',pk,[ct,message],32)

    def decaps(self,sk,ct):
        selected=sk.rejection_seed
        if len(ct)==self.ctbytes:
            u=self.base_decrypt(sk,ct[:self.pkbytes])
            if u is not None:
                mask=self.hash(b'F',sk.public_key,[u],self.mbytes)
                message=bytes(a^b for a,b in zip(ct[self.pkbytes:],mask))
                if self.deterministic_encrypt(sk.public_key,message)==ct:selected=message
        return self.hash(b'H',sk.public_key,[ct,selected],32)
