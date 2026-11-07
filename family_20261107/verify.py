"""Independent runtime oracle checks for the selected family."""
from __future__ import annotations
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
from reference import Family

HERE=Path(__file__).resolve().parent
RNG=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_size_t)
class Tape:
    def __init__(self,data):self.data=data;self.cursor=0;self.requests=[];self.callback=RNG(self.read)
    def read(self,unused,out,count):
        self.requests.append(count)
        if count>len(self.data)-self.cursor:return -1
        C.memmove(out,self.data[self.cursor:self.cursor+count],count);self.cursor+=count;return 0

def array(data):return (C.c_uint8*len(data)).from_buffer_copy(data)

def verify(number,isa):
    ref=Family(number);p=ref.profile;root=HERE/'build'/f'p{number:02d}-{isa}';library=root/'libcntru_family.so'
    lib=C.CDLL(str(library));Polynomial=C.c_int16*ref.n;PK=C.c_uint8*ref.pkbytes;CT=C.c_uint8*ref.ctbytes;Key=C.c_uint8*32
    class Secret(C.Structure):
        _fields_=[('f',Polynomial),('fp_inverse',C.c_uint64*(ref.half//64)),('h',Polynomial),
                  ('public_key',PK),('rejection_seed',C.c_uint8*ref.mbytes)]
    functions={}
    for name,args in {'keygen':[C.c_void_p,C.c_void_p,RNG,C.c_void_p],
                      'encaps':[C.c_void_p,C.c_void_p,C.c_void_p,RNG,C.c_void_p],
                      'decaps':[C.c_void_p,C.c_void_p,C.c_void_p,C.c_size_t]}.items():
        fn=getattr(lib,p['symbol_prefix']+name);fn.argtypes=args;fn.restype=C.c_int;functions[name]=fn
    seed=f'family20261107-oracle-{number}'.encode();size=ref.fbytes+ref.gbytes+ref.mbytes
    data=hashlib.shake_256(seed).digest(size);expected_pk,expected_sk=ref.keygen(data)
    pk,sk=PK(),Secret();tape=Tape(data)
    if functions['keygen'](pk,C.byref(sk),tape.callback,None) or bytes(pk)!=expected_pk:raise AssertionError('KeyGen')
    if tape.requests!=[ref.fbytes,ref.gbytes,ref.mbytes]:raise AssertionError('Key RNG schedule')
    if list(sk.f)!=list(expected_sk.f) or bytes(sk.rejection_seed)!=expected_sk.rejection_seed:raise AssertionError('Expanded key')
    digest=hashlib.sha256();checked=0
    for i in range(8):
        message=hashlib.shake_256(seed+bytes([i])).digest(ref.mbytes);expected_ct,expected_key=ref.encaps(expected_pk,message)
        ct,key=CT(),Key();mt=Tape(message)
        if functions['encaps'](ct,key,pk,mt.callback,None) or bytes(ct)!=expected_ct or bytes(key)!=expected_key:raise AssertionError('KEM bytes')
        for received in (expected_ct,bytes([expected_ct[0]^1])+expected_ct[1:],expected_ct[:-1],expected_ct+b'\0',b'',b'\xff'*ref.ctbytes):
            out=Key()
            if functions['decaps'](out,C.byref(sk),array(received),len(received)) or bytes(out)!=ref.decaps(expected_sk,received):raise AssertionError('FO valid/rejection')
            checked+=1
        digest.update(expected_ct+expected_key)
    return {'status':'passed','profile':p['semantic']['id'],'isa':isa,'checks':checked,
            'library_sha256':hashlib.sha256(library.read_bytes()).hexdigest(),'local_kat_digest':digest.hexdigest(),
            'scope':'Runtime check of the new local byte contract; not archive PRNG compatibility/security/DFR/constant-time certification'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--profiles',nargs='+',type=int,default=[1,2,3,4]);parser.add_argument('--isa',choices=['portable','avx2'],default='portable');args=parser.parse_args()
    for number in args.profiles:print(json.dumps(verify(number,args.isa),indent=2),flush=True)

if __name__=='__main__':main()
