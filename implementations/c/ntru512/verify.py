"""Independent Python oracle for the safety-first C contract.

The Python crypto sources are unmodified. Key selection alone models the new
fixed pool; encryption, decoding, inverse and implicit rejection use upstream.
"""
from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO/'implementations/python'))
from ntru import poly
from ntru.kem import KEM, SecretKey
from ntru.pke import SecretKey as BaseSecretKey

# Reuse only ctypes declarations and byte-tape plumbing, never expected values.
spec = importlib.util.spec_from_file_location("legacy_ctypes", HERE / "bindings.py")
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)
U8, Polynomial, Tape = binding.U8, binding.Polynomial, binding.Tape
Bytes32, Bytes495, Bytes527 = binding.Bytes32, binding.Bytes495, binding.Bytes527
array, load = binding.array, binding.load

class Secret(C.Structure):
    _fields_ = [("f", Polynomial), ("fp_inverse", C.c_uint64*4),
                ("h", Polynomial), ("public_key", Bytes495), ("rejection_seed", Bytes32)]


def fixed_pool_reference(kem, data):
    assert len(data) == 66080
    f = fp = g = None
    selected = []
    for i in range(256):
        candidate = kem.base.sample_poly(0, Tape(data[256*i:256*(i+1)]).read)
        inverse = poly.f2_inv(poly.packbits(poly.residue(candidate, 256)), 256)
        if inverse is not None:
            f, fp = candidate, inverse
            selected.append(i)
            break
    for i in range(2):
        candidate = kem.base.sample_poly(1, Tape(data[65536+256*i:65536+256*(i+1)]).read)
        # Use the original unit test, independently of the C nonzero shortcut.
        if poly.invq(candidate, 211) is not None:
            g = candidate
            selected.append(i)
            break
    if f is None or g is None:
        return None
    fq = poly.invq(f, 211)
    assert fq is not None
    pk = poly.pack(poly.mul(g, fq, 211), 211)
    return pk, SecretKey(BaseSecretKey(f, fp), pk, data[-32:]), selected


def check_key(lib, kem, data):
    expected = fixed_pool_reference(kem, data)
    pk, sk = Bytes495(), Secret()
    C.memset(pk, 0xA5, C.sizeof(pk))
    C.memset(C.byref(sk), 0xA5, C.sizeof(sk))
    tape = Tape(data)
    result = lib.cntru_keygen(pk, C.byref(sk), tape.callback, None)
    assert tape.requests == [65536, 512, 32] and tape.cursor == 66080
    if expected is None:
        assert result == -1 and not any(bytes(pk)) and not any(bytes(sk))
        return None
    epk, esk, selected = expected
    assert result == 0 and bytes(pk) == epk
    assert list(sk.f) == list(esk.base.f)
    assert list(sk.h) == list(poly.unpack(epk, 512, 211))
    assert sum(int(w) << (64*i) for i, w in enumerate(sk.fp_inverse)) == esk.base.fp_inverse
    assert bytes(sk.public_key) == epk and bytes(sk.rejection_seed) == esk.rejection_seed
    return pk, sk, esk, selected


def verify(lib):
    kem = KEM()
    rng = np.random.default_rng(0xC0711511)
    counts = {}
    digest = hashlib.sha256()
    for n in [0, 1, 7, 135, 136, 137, 271, 272, 273, 4096]:
        data = rng.bytes(n)
        for m in [0, 1, 32, 135, 136, 137, 416, 1000]:
            out = (U8*m)()
            lib.cntru_shake256(out, m, array(data), n)
            assert bytes(out) == hashlib.shake_256(data).digest(m)
    counts['shake_boundary_cases'] = 80

    for i in range(128):
        a, b = rng.integers(-210, 211, (2, 512))
        if i < 4:
            a[:] = [-210, 210, 210, -210][i]
            b[:] = [-210, 210, -210, 210][i]
        if i == 4:
            a[::2] = -210; a[1::2] = 210
            b[::2] = 210; b[1::2] = -210
        expected = poly.mul(a, b, 211)
        ca, cb, out = Polynomial(*a), Polynomial(*b), Polynomial()
        lib.cntru_poly_mul(out, ca, cb)
        assert np.array_equal(expected, np.array(out)), ('mul', i)
        lib.cntru_poly_mul(ca, ca, cb)
        assert bytes(ca) == bytes(out), ('alias_a', i)
        ca = Polynomial(*a)
        lib.cntru_poly_mul(cb, ca, cb)
        assert bytes(cb) == bytes(out), ('alias_b', i)
    counts['multiplication_extreme_random_two_alias_cases'] = 128

    for i in range(256):
        a = rng.integers(0, 211, 512)
        if i < 2: a[:] = 210*i
        out, decoded = Bytes495(), Polynomial()
        assert lib.cntru_pack(out, Polynomial(*a)) == 0
        assert bytes(out) == poly.pack(a, 211)
        assert lib.cntru_unpack(decoded, out) == 0
        assert np.array_equal(a, np.array(decoded))
    for value in [211**512, 211**512+1, (1 << 3960)-1]:
        assert lib.cntru_unpack(Polynomial(), array(value.to_bytes(495, 'little'))) == -1
    for index in [0, 1, 3, 4, 255, 508, 511]:
        for value in [-32768, -1, 211, 32767]:
            invalid, encoded = Polynomial(), Bytes495()
            invalid[index] = value
            assert lib.cntru_pack(encoded, invalid) == -1 and not any(encoded)
    counts['codec_valid_cases'] = 256
    counts['codec_invalid_cases'] = 31

    for which in range(3):
        for start in range(0, 65536, 128):
            data = b''.join(i.to_bytes(2, 'little') for i in range(start, start+128))
            expected = kem.base.sample_poly(which, Tape(data).read)
            out, tape = Polynomial(), Tape(data)
            assert lib.cntru_sample_poly(out, which, tape.callback, None) == 0
            assert np.array_equal(expected, np.array(out)), ('sampler', which, start)
            assert tape.requests == [256]
    counts['sampler_words_per_law'] = 65536
    counts['sampler_laws'] = 3

    class_patterns = [np.full(128, c, dtype=np.uint8) for c in range(4)]
    for k in range(129):
        class_patterns.append(np.array([0]*k + [1+(j % 3) for j in range(128-k)], dtype=np.uint8))
        class_patterns.append(np.array([1+(j % 3) for j in range(k)] + [0]*(128-k), dtype=np.uint8))
    class_patterns += [np.arange(128, dtype=np.uint8) % 4,
                       np.array(([3, 0, 2, 0, 1, 0, 0, 0]*16), dtype=np.uint8)]
    for pattern_no, classes in enumerate(class_patterns):
        u = np.packbits(np.concatenate((classes & 1, classes >> 1)), bitorder='little').tobytes()
        for start in [0, 128]:
            data = rng.bytes(256) + bytes(range(start, start+128))
            tape, py = Tape(data), Tape(data)
            r, m = Polynomial(), Polynomial()
            assert lib.cntru_sample_rm(r, m, array(u), tape.callback, None) == 0
            er = (kem.base.sample_poly(2, py.read).reshape(4, 128)*kem.base.signs[:, None]).reshape(512)
            em = np.array([kem.base.lifts[int(c)].sample(py.read)*kem.base.signs for c in classes]).T.reshape(512)
            assert np.array_equal(er, np.array(r)) and np.array_equal(em, np.array(m)), pattern_no
            assert tape.requests == [384]
    counts['conditional_class_patterns'] = len(class_patterns)
    counts['conditional_suffix_halves_per_pattern'] = 2

    for i in range(11):
        a = rng.integers(-1, 2, 512)
        if i == 0: a[:] = 0
        if i == 1: a[:] = 0; a[127] = 1
        if i == 10:
            s = next(k for k in range(211) if k*k % 211 == 209)
            a[:] = 0; a[0] = -1; a[128] = s; a[256] = 1
        expected, out = poly.invq(a, 211), Polynomial()
        result = lib.cntru_poly_inv(out, Polynomial(*a))
        assert (result == -1) if expected is None else (result == 0 and np.array_equal(expected, np.array(out)))
    counts['inverse_cases_including_nonzero_nonunit'] = 11

    def atom_word(which, nonzeros):
        table = kem.base.tables[which]
        row = next(i for i, atom in enumerate(table.atoms) if np.count_nonzero(atom) == nonzeros)
        return (0 if row == 0 else table.cdf[row-1]).to_bytes(2, 'little')

    fzero, gzero = atom_word(0, 0)*128, atom_word(1, 0)*128
    funit = atom_word(0, 1) + atom_word(0, 0)*127
    gunit = atom_word(1, 1) + atom_word(1, 0)*127
    fpair = atom_word(0, 2) + atom_word(0, 0)*127
    z = bytes(range(32))
    late = check_key(lib, kem, fpair*255 + funit + gzero + gunit + z)
    assert late[-1] == [255, 1]
    assert check_key(lib, kem, fzero*256 + gunit*2 + z) is None
    assert check_key(lib, kem, funit*256 + gzero*2 + z) is None
    counts['pool_last_candidate_and_exhaustion_cases'] = 3

    ciphertexts = malformed = 0
    for i in range(4):
        seed = b'fixed-pool-independent-reference-' + bytes([i])
        data = hashlib.shake_256(seed).digest(66080)
        pk, sk, esk, selected = check_key(lib, kem, data)
        digest.update(bytes(pk) + bytes(sk.rejection_seed))
        for j in range(8):
            message = hashlib.sha256(seed + bytes([j])).digest()
            expected_ct, expected_key = kem.encapsulate(bytes(pk), Tape(message).read)
            ct, key, recovered = Bytes527(), Bytes32(), Bytes32()
            tape = Tape(message)
            assert lib.cntru_encaps(ct, key, pk, tape.callback, None) == 0
            assert bytes(ct) == expected_ct and bytes(key) == expected_key
            assert tape.requests == [32]
            assert lib.cntru_decaps(recovered, C.byref(sk), ct, 527) == 0
            assert bytes(recovered) == expected_key
            digest.update(bytes(ct) + bytes(key)); ciphertexts += 1
            coins = hashlib.shake_256(message).digest(416)
            core, tape = Bytes495(), Tape(coins)
            assert lib.cntru_base_encrypt(core, pk, array(message), tape.callback, None) == 0
            assert bytes(core) == kem.base.encrypt(bytes(pk), message, Tape(coins).read)
            assert tape.requests == [384]
            assert lib.cntru_base_decrypt(recovered, C.byref(sk), core) == 0 and bytes(recovered) == message
            tape = Tape(coins)
            assert lib.cntru_encrypt(ct, pk, array(message), tape.callback, None) == 0
            assert bytes(ct) == kem.encrypt(bytes(pk), message, Tape(coins).read)
            assert tape.requests == [32, 384]
            assert lib.cntru_decrypt(recovered, C.byref(sk), ct, 527) == 0 and bytes(recovered) == message
            if i == 0 and j == 0:
                for value in [211**512, 211**512+1, (1 << 3960)-1]:
                    bad_core = value.to_bytes(495, 'little')
                    assert kem.base.decrypt(esk.base, bad_core) is None
                    C.memset(recovered, 0xA5, 32)
                    assert lib.cntru_base_decrypt(recovered, C.byref(sk), array(bad_core)) == -1
                    assert not any(recovered)
                    bad_masked = bad_core+bytes(32)
                    assert kem.decrypt(esk, bad_masked) is None
                    C.memset(recovered, 0xA5, 32)
                    assert lib.cntru_decrypt(recovered, C.byref(sk), array(bad_masked), 527) == -1
                    assert not any(recovered)
            tampered = bytearray(expected_ct); tampered[(j*71) % 527] ^= 1 << (j % 8)
            for bad in [bytes(tampered), expected_ct[:495] + bytes(b ^ 0x55 for b in expected_ct[495:]),
                        b'', expected_ct[:494], expected_ct[:-1], expected_ct+b'\0', b'\xff'*527,
                        (211**512).to_bytes(495, 'little') + expected_ct[495:], expected_ct+rng.bytes(4096)]:
                assert lib.cntru_decaps(recovered, C.byref(sk), array(bad), len(bad)) == 0
                assert bytes(recovered) == kem.decapsulate(esk, bad), (i, j, len(bad))
                malformed += 1
            assert lib.cntru_decaps(recovered, C.byref(sk), None, 0) == 0
            assert bytes(recovered) == kem.decapsulate(esk, b'')
    counts.update(reference_fixed_pool_keygens=4, byte_identical_kem_roundtrips=ciphertexts,
                  malformed_reference_comparisons=malformed, null_empty_cases=ciphertexts,
                  base_pke_invalid_output_zero_cases=3, masked_pke_invalid_output_zero_cases=3,
                  kat_digest_sha256=digest.hexdigest())
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=REPO/'benchmarks/build/q211-ref/libcntru.so')
    parser.add_argument('--out', type=Path, default=REPO/'benchmarks/build/q211-ref/reference.json')
    args = parser.parse_args()
    result = {'status': 'passed', 'library': str(args.library.resolve()),
              'library_sha256': hashlib.sha256(args.library.read_bytes()).hexdigest(),
              'python': sys.version, 'numpy': np.__version__, 'checks': verify(load(args.library)),
              'oracle_sources_sha256': {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in [Path(__file__), HERE/'bindings.py',
                                                  *sorted((REPO/'implementations/python/ntru').glob('*.py')), REPO/'implementations/python/ntru/par.json']}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
