"""Independent Python integers and frozen implementation comparison."""
from __future__ import annotations
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

class Plan(C.Structure):
    _fields_ = [(k, C.c_uint32) for k in
                ('n', 'q', 'encoded_bytes', 'limbs', 'digits', 'chunks', 'shift')] + [
        (k, C.c_uint64) for k in
        ('divisor', 'normalized_divisor', 'reciprocal', 'digit_reciprocal')] + [
        ('pack_limbs', C.c_uint16 * 1024), ('unpack_limbs', C.c_uint16 * 1024)]

def run(library: Path, cases: int) -> dict:
    new = C.CDLL(str(library.resolve()))
    new.ct_radix_plan_init.argtypes = [C.POINTER(Plan), C.c_uint32, C.c_uint32]
    new.ct_radix_pack.argtypes = [C.c_void_p, C.c_void_p, C.POINTER(Plan)]
    new.ct_radix_unpack.argtypes = [C.c_void_p, C.c_void_p, C.POINTER(Plan)]
    rng = random.Random(0x37FEAC095821D46B)
    reports = []
    for n, q in ((512, 211), (1024, 307), (1024, 331), (1024, 373)):
        old_path = (REPO/'benchmarks/build/q211-ref/libcntru.so' if n == 512 else
                    REPO/f'benchmarks/build/q{q}-ref/libcntru.so')
        old = C.CDLL(str(old_path))
        prefix = 'cntru' if n == 512 else f'cntru1024q{q}'
        pack = getattr(old, prefix+'_pack'); unpack = getattr(old, prefix+'_unpack')
        pack.argtypes = [C.c_void_p, C.c_void_p]
        unpack.argtypes = [C.c_void_p, C.c_void_p]
        p = Plan(); assert new.ct_radix_plan_init(C.byref(p), n, q) == 0
        size = ((q**n-1).bit_length()+7)//8
        assert p.encoded_bytes == size
        A = C.c_int16*n; B = C.c_uint8*size
        vectors = [[0]*n, [q-1]*n, [i % q for i in range(n)],
                   [q-1 if i % 2 else 0 for i in range(n)]]
        vectors.extend([[rng.randrange(q) for _ in range(n)] for _ in range(cases)])
        for vector in vectors:
            coefficients=A(*vector); output=B(); previous=B()
            assert new.ct_radix_pack(output, coefficients, C.byref(p)) == 0
            assert pack(previous, coefficients) == 0
            value=0
            for coefficient in reversed(vector): value=value*q+coefficient
            assert bytes(output) == bytes(previous) == value.to_bytes(size, 'little')
            decoded=A(); assert new.ct_radix_unpack(decoded,output,C.byref(p)) == 0
            assert list(decoded) == vector
        # Each invalid coefficient position, both signed and upper boundaries.
        for index in range(n):
            for invalid in (-32768, -1, q, 32767):
                coefficients=A(); coefficients[index]=invalid
                output=B(*([165]*size)); previous=B(*([90]*size))
                assert new.ct_radix_pack(output,coefficients,C.byref(p)) == -1
                assert pack(previous,coefficients) == -1
                assert bytes(output) == bytes(previous) == bytes(size)
        limit=q**n
        values=[0, 1, q-1, q, limit-2, limit-1, limit, limit+1,
                (1 << (8*size))-1]
        values.extend(rng.getrandbits(8*size) for _ in range(cases))
        # Every single-bit transport value, canonical or malformed.
        values.extend(1 << bit for bit in range(8*size))
        for value in values:
            encoded=B.from_buffer_copy(value.to_bytes(size,'little'))
            decoded=A(); previous=A()
            status=new.ct_radix_unpack(decoded,encoded,C.byref(p))
            assert status == unpack(previous,encoded) == (0 if value < limit else -1)
            expected=[]; remainder=value
            for _ in range(n): remainder,digit=divmod(remainder,q); expected.append(digit)
            assert list(decoded) == list(previous) == expected
        reports.append(dict(n=n,q=q,bytes=size,canonical_vectors=len(vectors),
                            decode_vectors=len(values),invalid_pack_vectors=4*n,
                            digits=p.digits,chunks=p.chunks,
                            pack_visits=sum(p.pack_limbs[:p.chunks]),
                            unpack_visits=sum(p.unpack_limbs[:p.chunks])))
    return dict(status='passed', cases=reports,
                library_sha256=hashlib.sha256(library.read_bytes()).hexdigest())

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--cases',type=int,default=256)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    result=run(args.library,args.cases)
    output=json.dumps(result,indent=2)+'\n'
    if args.out: args.out.write_text(output)
    print(output,end='')
