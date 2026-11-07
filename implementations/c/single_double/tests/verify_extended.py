"""Supplemental exact-law, D-correction and FO checks; never benchmarks."""
from __future__ import annotations
import argparse
from collections import Counter
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[2]
sys.path.insert(0,str(HERE))
from reference import Family,Secret
from verify import Tape,array,RNG
from ntru import poly

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(number,isa):
    ref=Family(number);p=ref.profile
    directory=REPO/'benchmarks/build'/f'p{number:02d}-{"ref" if isa in ("portable","ref") else "avx2"}';path=directory/'libcntru_family.so'
    before=sha(path)
    lib=C.CDLL(str(path));A=C.c_int16*ref.n;PK=C.c_uint8*ref.pkbytes;CT=C.c_uint8*ref.ctbytes;K=C.c_uint8*32
    class SK(C.Structure):
        _fields_=[('f',A),('fp_inverse',C.c_uint64*(ref.half//64)),('h',A),('public_key',PK),('rejection_seed',C.c_uint8*ref.mbytes)]
    definitions={
        'keygen':[C.c_void_p,C.c_void_p,RNG,C.c_void_p],
        'sample_poly':[C.c_void_p,C.c_uint,RNG,C.c_void_p],
        'sample_rm':[C.c_void_p,C.c_void_p,C.c_void_p,RNG,C.c_void_p],
        'poly_mul':[C.c_void_p,C.c_void_p,C.c_void_p],
        'pack':[C.c_void_p,C.c_void_p], 'unpack':[C.c_void_p,C.c_void_p],
        'base_decrypt':[C.c_void_p,C.c_void_p,C.c_void_p],
        'decrypt':[C.c_void_p,C.c_void_p,C.c_void_p,C.c_size_t],
        'encaps':[C.c_void_p,C.c_void_p,C.c_void_p,RNG,C.c_void_p],
        'decaps':[C.c_void_p,C.c_void_p,C.c_void_p,C.c_size_t],
        'double_residue':[C.c_void_p,C.c_void_p]}
    fn={}
    for name,args in definitions.items():
        f=getattr(lib,p['symbol_prefix']+name);f.argtypes=args;f.restype=None if name=='poly_mul' else C.c_int;fn[name]=f
    counts=Counter();seed=f'family-supplement-{number}'.encode()
    def check(condition,case):
        if not condition:raise AssertionError(case)
        counts[case]+=1
    def random_bytes(tag,size):return hashlib.shake_256(seed+tag).digest(size)
    # Independent exact probabilities, including 32-bit sampler words at p15.
    for which,law in enumerate(ref.laws[:3]):
        masses=[law[0]]+[law[1]/8]*8+[law[2]/8]*8
        resolution=max(x.denominator for x in masses);cumulative=0;words=[0,resolution-1,resolution,resolution+1,(1<<(8*ref.wordbytes))-1]
        for mass in masses:
            cumulative+=int(mass*resolution)
            words.extend((max(0,cumulative-1),cumulative))
        data=b''.join(words[i%len(words)].to_bytes(ref.wordbytes,'little') for i in range(ref.blocks))
        t=Tape(data);actual=A()
        status=fn['sample_poly'](actual,which,t.callback,None);expected=ref.sample(which,data)
        if status!=0 or list(actual)!=list(expected):
            indices=np.flatnonzero(np.array(actual)!=expected)
            raise AssertionError(dict(case='sampler_boundary_tape',which=which,status=status,
                requests=t.requests,wordbytes=ref.wordbytes,resolution=resolution,
                mismatches=[(int(i),int(actual[i]),int(expected[i])) for i in indices[:16]]))
        counts['sampler_boundary_tape']+=1
    for pattern in range(8):
        u=random_bytes(b'u'+bytes([pattern]),ref.ubytes)
        rho=random_bytes(b'rho'+bytes([pattern]),ref.rhobytes)
        r,m=ref.sample_rm(u,rho);cr,cm=A(),A();t=Tape(rho)
        check(fn['sample_rm'](cr,cm,array(u),t.callback,None)==0 and list(cr)==list(r) and list(cm)==list(m),'conditional_sampler_exact')
    bound=ref.q-1
    vectors=[[bound]*ref.n,[-bound]*ref.n,[bound if i&1 else -bound for i in range(ref.n)]]
    for i,a in enumerate(vectors):
        for j,b in enumerate(vectors):
            actual=A();fn['poly_mul'](actual,A(*a),A(*b))
            check(list(actual)==list(poly.mul(a,b,ref.q)),'full_range_product')
    # Full-integer codec boundaries and exact low digits on malformed input.
    limit=ref.q**ref.n
    for value in (0,1,limit-1,limit,limit+1,(1<<(8*ref.pkbytes))-1):
        actual=A();status=fn['unpack'](actual,array(value.to_bytes(ref.pkbytes,'little')))
        remainder=value;expected=[]
        for _ in range(ref.n):remainder,digit=divmod(remainder,ref.q);expected.append(digit)
        check(status==(0 if value<limit else -1) and list(actual)==expected,'codec_boundary')
    # Independently force f=g=1, with a nonzero rejection seed.
    tape_data=bytearray(ref.fbytes+ref.gbytes+ref.mbytes)
    for which,start in ((0,0),(1,ref.fbytes)):
        masses=[ref.laws[which][0]]+[ref.laws[which][1]/8]*8+[ref.laws[which][2]/8]*8
        resolution=max(v.denominator for v in masses);word=int(masses[0]*resolution)
        tape_data[start:start+ref.wordbytes]=word.to_bytes(ref.wordbytes,'little')
    z=random_bytes(b'z',ref.mbytes);tape_data[-ref.mbytes:]=z
    t=Tape(bytes(tape_data));pk,sk=PK(),SK()
    check(fn['keygen'](pk,C.byref(sk),t.callback,None)==0 and bytes(pk)==b'\1'+bytes(ref.pkbytes-1),'forced_unit_key')
    check(list(sk.f)==[1]+[0]*(ref.n-1) and list(sk.h)==[1]+[0]*(ref.n-1) and sk.fp_inverse[0]==1 and all(v==0 for v in sk.fp_inverse[1:]),'expanded_unit_key')
    oracle_sk=Secret(np.array([1]+[0]*(ref.n-1),dtype=np.int64),1,bytes(pk),z)
    sk_before=bytes(sk)
    for i in range(3):
        message=random_bytes(b'M'+bytes([i]),ref.mbytes);expected_ct,expected_key=ref.encaps(bytes(pk),message)
        ct,key=CT(),K();mt=Tape(message)
        check(fn['encaps'](ct,key,pk,mt.callback,None)==0 and bytes(ct)==expected_ct and bytes(key)==expected_key,'kem_exact_encapsulation')
        variants=[expected_ct,expected_ct[:-1],expected_ct+b'\0',expected_ct+bytes(range(256)),b'',b'\xff'*ref.ctbytes,
                  limit.to_bytes(ref.pkbytes,'little')+expected_ct[ref.pkbytes:],
                  expected_ct[:ref.pkbytes]+bytes([expected_ct[ref.pkbytes]^1])+expected_ct[ref.pkbytes+1:],
                  bytes([expected_ct[0]^1])+expected_ct[1:]]
        for index,received in enumerate(variants):
            output=K();status=fn['decaps'](output,C.byref(sk),array(received),len(received))
            expected=ref.decaps(oracle_sk,received)
            check(status==0 and bytes(output)==expected,'fo_exact_case')
            if index==0:check(bytes(output)==expected_key,'valid_shared_key')
        check(bytes(sk)==sk_before,'decapsulation_key_immutable')
    # Invalid public keys must reject before requesting the message source.
    ct,key=CT(*([165]*ref.ctbytes)),K(*([165]*32));mt=Tape(bytes(ref.mbytes))
    check(fn['encaps'](ct,key,array(limit.to_bytes(ref.pkbytes,'little')),mt.callback,None)==-1 and not mt.requests and not any(ct) and not any(key),'invalid_pk_no_rng_zero_output')
    if ref.double:
        Bits=C.c_uint64*(ref.half//64)
        fixtures=json.loads((HERE/'tests/double_decode_vectors.json').read_text())
        for case in fixtures['common_cases']+[x for x in fixtures['dimension_cases'] if x['n']==ref.n]:
            values=A()
            for group,slot,value in case['entries']:values[group+slot*ref.blocks]=value
            output=Bits();status=fn['double_residue'](output,values)
            expected=sum(1<<(group+lane*ref.blocks) for group,lane in case['expected_set_bits'])
            check(status==case['valid'] and sum(v<<(64*i) for i,v in enumerate(output))==expected,'d_static_fixture')
        values=A()
        for group in range(ref.blocks):
            for slot in range(4):
                for sign in (-1,1):
                    index=group+slot*ref.blocks;values[index]=3*sign;output=Bits()
                    check(fn['double_residue'](output,values)==1 and not any(output),'d_every_position_signed_single')
                    values[index]=0
        for case,entries in enumerate(([(7,0,3),(7,1,-3),(7,2,1)],[(9,0,1),(9,1,1)],[(1,0,1),(2,0,1)])):
            v=[0]*ref.n
            for group,slot,value in entries:v[group+slot*ref.blocks]=value
            inv2=(ref.q+1)//2
            c=[inv2*(v[j]+v[j+ref.half])%ref.q for j in range(ref.half)]+[inv2*(v[j+ref.half]-v[j])%ref.q for j in range(ref.half)]
            core=poly.pack(c,ref.q);u=ref.base_decrypt(oracle_sk,core)
            output=(C.c_uint8*ref.ubytes)(*([165]*ref.ubytes));status=fn['base_decrypt'](output,C.byref(sk),array(core))
            check(status==(0 if u is not None else -1) and bytes(output)==(u if u is not None else bytes(ref.ubytes)),'d_canonical_base_case')
            message=random_bytes(b'D'+bytes([case]),ref.mbytes)
            body=bytes(a^b for a,b in zip(message,ref.hash(b'F',bytes(pk),[u],ref.mbytes))) if u is not None else bytes(ref.mbytes)
            received=core+body;plain=(C.c_uint8*ref.mbytes)(*([165]*ref.mbytes));status=fn['decrypt'](plain,C.byref(sk),array(received),len(received))
            check(status==(0 if u is not None else -1) and bytes(plain)==(message if u is not None else bytes(ref.mbytes)),'d_canonical_acwc_case')
            output=K();status=fn['decaps'](output,C.byref(sk),array(received),len(received))
            check(status==0 and bytes(output)==ref.decaps(oracle_sk,received)==ref.hash(b'H',bytes(pk),[received,z],32),'d_canonical_fo_reject')
    after=sha(path);check(before==after,'library_hash_unchanged')
    return dict(status='passed',profile_number=number,profile=p['semantic']['id'],isa=isa,
                library_sha256_before=before,library_sha256_after=after,cases=dict(counts),
                scope='Functional supplement only; not security/DFR/CT certification')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--profile',type=int,required=True)
    parser.add_argument('--isa',choices=('portable','ref','avx2'),required=True);args=parser.parse_args()
    print(json.dumps(verify(args.profile,args.isa),indent=2))

if __name__=='__main__':main()
