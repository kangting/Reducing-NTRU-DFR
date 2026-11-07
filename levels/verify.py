"""Independent exact-law, arithmetic and full-KEM checks for each C profile."""
from __future__ import annotations
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
from profiles import HERE, REPO, load_profile
from reference import KEM, FixedTape
from ntru import poly

U8 = C.c_uint8
Polynomial = C.c_int16*1024
Bytes32, Bytes64 = U8*32, U8*64
RNG = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_size_t)


def array(data): return (U8*len(data)).from_buffer_copy(data)


class Tape(FixedTape):
    def __init__(self, data):
        super().__init__(data)
        self.callback = RNG(self._read)

    def _read(self, ctx, out, size):
        del ctx
        try: C.memmove(out, self.read(size), size)
        except ValueError: return -1
        return 0


def load(path, q):
    profile = load_profile(q)
    PK, CT = U8*profile['pk_bytes'], U8*profile['ct_bytes']

    class Secret(C.Structure):
        _fields_ = [('f', Polynomial), ('fp_inverse', C.c_uint64*8),
                    ('h', Polynomial), ('public_key', PK), ('rejection_seed', Bytes32)]

    library = C.CDLL(str(path.resolve()))
    ptr = C.c_void_p
    signatures = dict(keygen=[ptr, ptr, RNG, ptr], base_encrypt=[ptr, ptr, ptr, RNG, ptr],
                      base_decrypt=[ptr, ptr, ptr], encrypt=[ptr, ptr, ptr, RNG, ptr],
                      decrypt=[ptr, ptr, ptr, C.c_size_t], deterministic_encrypt=[ptr, ptr, ptr],
                      encaps=[ptr, ptr, ptr, RNG, ptr], decaps=[ptr, ptr, ptr, C.c_size_t],
                      pack=[ptr, ptr], unpack=[ptr, ptr], poly_mul=[ptr, ptr, ptr], poly_inv=[ptr, ptr],
                      sample_poly=[ptr, C.c_uint, RNG, ptr], sample_rm=[ptr, ptr, ptr, RNG, ptr],
                      shake256=[ptr, C.c_size_t, ptr, C.c_size_t])
    lib = SimpleNamespace(PK=PK, CT=CT, Secret=Secret, library=library)
    for name, signature in signatures.items():
        fn = getattr(library, f'cntru1024q{q}_{name}')
        fn.argtypes = signature
        fn.restype = None if name in ('poly_mul', 'shake256') else C.c_int
        setattr(lib, name, fn)
    return lib


def keycheck(lib, kem, data, failure=False):
    pk, sk = lib.PK(), lib.Secret()
    C.memset(pk, 0xA5, C.sizeof(pk)); C.memset(C.byref(sk), 0xA5, C.sizeof(sk))
    tape = Tape(data)
    status = lib.keygen(pk, C.byref(sk), tape.callback, None)
    if tape.requests != [131072, 1024, 32] or tape.cursor != 132128:
        raise AssertionError(('keygen source schedule', tape.requests))
    if failure:
        assert status == -1 and not any(bytes(pk)) and not any(bytes(sk))
        try: kem.keygen(FixedTape(data).read)
        except ValueError: return None
        raise AssertionError('C rejected a reference-accepted pool')
    expected_pk, expected_sk, indices = kem.keygen(FixedTape(data).read)
    assert status == 0 and bytes(pk) == expected_pk
    assert list(sk.f) == list(expected_sk.f)
    assert sum(int(w) << (64*i) for i, w in enumerate(sk.fp_inverse)) == expected_sk.fp_inverse
    assert list(sk.h) == list(poly.unpack(expected_pk, 1024, kem.q))
    assert bytes(sk.public_key) == expected_pk and bytes(sk.rejection_seed) == expected_sk.rejection_seed
    return pk, sk, expected_sk, indices


def verify(lib, q):
    kem = KEM(q)
    rng = np.random.default_rng(0x1024+q)
    counts = {}
    digest = hashlib.sha256()
    for length in [0, 1, 135, 136, 137, 271, 272, 273, 832, 4096]:
        source = rng.bytes(length)
        for size in [0, 32, 64, 135, 136, 137, 832, 1600]:
            out = (U8*size)()
            lib.shake256(out, size, array(source), length)
            assert bytes(out) == hashlib.shake_256(source).digest(size)
    counts['shake_boundary_cases'] = 80
    for i in range(128):
        a, b = rng.integers(-(q-1), q, (2, 1024))
        if i < 4:
            a[:] = (q-1)*(-1 if i & 1 else 1)
            b[:] = (q-1)*(-1 if i & 2 else 1)
        if i == 4:
            a[::2] = -(q-1); a[1::2] = q-1
            b[::2] = q//2; b[1::2] = -(q//2)
        ca, cb, out = Polynomial(*a), Polynomial(*b), Polynomial()
        expected = poly.mul(a, b, q)
        lib.poly_mul(out, ca, cb)
        assert np.array_equal(expected, np.array(out)), ('product', q, i)
        lib.poly_mul(ca, ca, cb)
        assert bytes(ca) == bytes(out)
        ca = Polynomial(*a); lib.poly_mul(cb, ca, cb)
        assert bytes(cb) == bytes(out)
    counts['full_input_range_products_and_two_aliases'] = 128
    for i in range(128):
        a = rng.integers(0, q, 1024)
        if i < 2: a[:] = i*(q-1)
        encoded, decoded = lib.PK(), Polynomial()
        assert lib.pack(encoded, Polynomial(*a)) == 0
        assert bytes(encoded) == poly.pack(a, q)
        assert lib.unpack(decoded, encoded) == 0 and np.array_equal(a, np.array(decoded))
    for value in [q**1024, q**1024+1, (1 << (kem.pk_bytes*8))-1]:
        assert lib.unpack(Polynomial(), array(value.to_bytes(kem.pk_bytes, 'little'))) == -1
    for pos in [0, 1, 2, 3, 511, 1022, 1023]:
        for value in [-32768, -1, q, 32767]:
            a, encoded = Polynomial(), lib.PK(); a[pos] = value
            assert lib.pack(encoded, a) == -1 and not any(encoded)
    counts.update(codec_valid_cases=128, codec_invalid_cases=31)
    for which in range(3):
        for start in range(0, 65536, 256):
            source = b''.join(i.to_bytes(2, 'little') for i in range(start, start+256))
            expected = kem.sample_poly(which, FixedTape(source).read)
            out, tape = Polynomial(), Tape(source)
            assert lib.sample_poly(out, which, tape.callback, None) == 0
            assert tape.requests == [512]
            assert np.array_equal(expected, np.array(out)), ('sampler', q, which, start)
    counts.update(sampler_words_per_law=65536, sampler_laws=3)
    patterns = [np.full(256, cls, dtype=np.uint8) for cls in range(4)]
    for cursor in range(257):
        patterns += [np.array([0]*cursor+[1+(i % 3) for i in range(256-cursor)], dtype=np.uint8),
                     np.array([1+(i % 3) for i in range(cursor)]+[0]*(256-cursor), dtype=np.uint8)]
    patterns += [np.arange(256, dtype=np.uint8) % 4, np.array([3, 0, 2, 0, 1, 0, 0, 0]*32, dtype=np.uint8)]
    for number, classes in enumerate(patterns):
        u = np.packbits(np.concatenate((classes & 1, classes >> 1)), bitorder='little').tobytes()
        source = rng.bytes(512)+bytes(range(256))
        er, em = kem.sample_rm(u, FixedTape(source).read)
        r, m, tape = Polynomial(), Polynomial(), Tape(source)
        assert lib.sample_rm(r, m, array(u), tape.callback, None) == 0
        assert tape.requests == [768]
        assert np.array_equal(er, np.array(r)) and np.array_equal(em, np.array(m)), ('message', q, number)
    counts['conditional_patterns_all_prefix_cursors'] = len(patterns)
    for i in range(8):
        a = rng.integers(-1, 2, 1024)
        if i == 0: a[:] = 0
        if i == 1: a[:] = 0; a[513] = 1
        if i == 7:
            a[:] = 0
            if q % 4 == 1:
                s = next(x for x in range(q) if x*x % q == q-1)
                a[0] = -s; a[512] = 1
            else:
                s = next(x for x in range(q) if x*x % q == q-2)
                a[0] = -1; a[256] = s; a[512] = 1
        expected, out = poly.invq(a, q), Polynomial()
        status = lib.poly_inv(out, Polynomial(*a))
        assert (status == -1) if expected is None else (status == 0 and np.array_equal(expected, np.array(out)))
    counts['inverse_cases_including_nonzero_nonunit'] = 8

    def word(which, nonzeros):
        table = kem.tables[which]
        row = next(i for i, atom in enumerate(table.atoms) if np.count_nonzero(atom) == nonzeros)
        return int(0 if row == 0 else table.cdf[row-1]).to_bytes(2, 'little')

    fzero, gzero = word(0, 0)*256, word(1, 0)*256
    funit = word(0, 1)+word(0, 0)*255
    fpair = word(0, 2)+word(0, 0)*255
    gunit = word(1, 1)+word(1, 0)*255
    z = bytes(range(32))
    assert keycheck(lib, kem, fpair*255+funit+gzero+gunit+z)[-1] == [255, 1]
    keycheck(lib, kem, fzero*256+gunit*2+z, failure=True)
    keycheck(lib, kem, funit*256+gzero*2+z, failure=True)
    counts['forced_pool_last_selection_and_exhaustions'] = 3
    malformed = cases = 0
    vectors = []
    for i in range(3):
        seed = b'independent-levels-key-v1-'+q.to_bytes(2, 'little')+bytes([i])
        data = hashlib.shake_256(seed).digest(132128)
        pk, sk, expected_sk, selected = keycheck(lib, kem, data)
        digest.update(bytes(pk)+bytes(sk.rejection_seed))
        for j in range(6):
            message = hashlib.sha256(seed+bytes([j])).digest()
            expected_ct, expected_key = kem.encapsulate(bytes(pk), FixedTape(message).read)
            ct, key, recovered = lib.CT(), Bytes32(), Bytes32()
            tape = Tape(message)
            assert lib.encaps(ct, key, pk, tape.callback, None) == 0 and tape.requests == [32]
            assert bytes(ct) == expected_ct and bytes(key) == expected_key
            assert lib.decaps(recovered, C.byref(sk), ct, kem.ct_bytes) == 0 and bytes(recovered) == expected_key
            digest.update(bytes(ct)+bytes(key)); cases += 1
            if i == j == 0:
                vectors.append(dict(keygen_source_seed_hex=seed.hex(), public_key_hex=bytes(pk).hex(),
                                    external_message_hex=message.hex(), ciphertext_hex=bytes(ct).hex(), shared_key_hex=bytes(key).hex()))
            coins = hashlib.shake_256(message).digest(832)
            u = hashlib.shake_256(message+b'internal').digest(64)
            core, internal, tape = lib.PK(), Bytes64(), Tape(coins)
            assert lib.base_encrypt(core, pk, array(u), tape.callback, None) == 0 and tape.requests == [768]
            assert bytes(core) == kem.base_encrypt(bytes(pk), u, FixedTape(coins).read)
            assert lib.base_decrypt(internal, C.byref(sk), core) == 0 and bytes(internal) == u
            tape = Tape(coins)
            assert lib.encrypt(ct, pk, array(message), tape.callback, None) == 0 and tape.requests == [64, 768]
            assert bytes(ct) == kem.encrypt(bytes(pk), message, FixedTape(coins).read)
            assert lib.decrypt(recovered, C.byref(sk), ct, kem.ct_bytes) == 0 and bytes(recovered) == message
            tampered = bytearray(expected_ct); tampered[(j*181) % kem.ct_bytes] ^= 1 << (j % 8)
            for bad in [bytes(tampered), b'', expected_ct[:-1], expected_ct+b'\0', b'\xff'*kem.ct_bytes,
                        (q**1024).to_bytes(kem.pk_bytes, 'little')+expected_ct[kem.pk_bytes:], expected_ct+rng.bytes(4096)]:
                assert lib.decaps(recovered, C.byref(sk), array(bad), len(bad)) == 0
                assert bytes(recovered) == kem.decapsulate(expected_sk, bad), ('fallback', q, i, j, len(bad))
                malformed += 1
            assert lib.decaps(recovered, C.byref(sk), None, 0) == 0
            assert bytes(recovered) == kem.decapsulate(expected_sk, b'')
        for value in [q**1024, q**1024+1, (1 << (kem.pk_bytes*8))-1]:
            bad = value.to_bytes(kem.pk_bytes, 'little')
            C.memset(internal, 0xA5, 64)
            assert lib.base_decrypt(internal, C.byref(sk), array(bad)) == -1 and not any(internal)
            C.memset(recovered, 0xA5, 32)
            assert lib.decrypt(recovered, C.byref(sk), array(bad+bytes(32)), kem.ct_bytes) == -1 and not any(recovered)
    counts.update(reference_fixed_pool_keygens=3, byte_identical_kem_roundtrips=cases,
                  malformed_reference_comparisons=malformed, zeroed_base_and_masked_failure_cases=18,
                  kat_digest_sha256=digest.hexdigest())
    return counts, vectors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--q', type=int, choices=[307, 331, 373], required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    checks, vectors = verify(load(args.library, args.q), args.q)
    paths = [Path(__file__), HERE/'profiles.py', HERE/'reference.py', HERE/'params'/f'q{args.q}.json',
             REPO/'ntru/poly.py', REPO/'ntru/sample.py', REPO/'ntru/kem.py']
    result = dict(status='passed', q=args.q, checks=checks, vectors=vectors, python=sys.version, numpy=np.__version__,
                  library=str(args.library.resolve()), library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
                  oracle_sources_sha256={str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(status=result['status'], q=args.q, checks=checks), indent=2))


if __name__ == '__main__': main()
