"""Independent byte-for-byte oracle checks against the untouched Python KEM."""
from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))
from ntru import poly  # noqa: E402
from ntru.kem import KEM  # noqa: E402

U8 = C.c_uint8
I16 = C.c_int16
Bytes32 = U8 * 32
Bytes495 = U8 * 495
Bytes527 = U8 * 527
Polynomial = I16 * 512
RNG = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_size_t)


class Secret(C.Structure):
    _fields_ = [("f", Polynomial), ("fp_inverse", C.c_uint64 * 4),
                ("public_key", Bytes495), ("rejection_seed", Bytes32)]


class Tape:
    def __init__(self, data: bytes):
        self.data = data
        self.cursor = 0
        self.requests: list[int] = []
        self.callback = RNG(self._read_c)

    def read(self, n: int) -> bytes:
        if self.cursor + n > len(self.data):
            raise ValueError("tape exhausted")
        result = self.data[self.cursor:self.cursor + n]
        self.cursor += n
        self.requests.append(n)
        return result

    def _read_c(self, ctx: int, out: int, n: int) -> int:
        del ctx
        try:
            C.memmove(out, self.read(n), n)
        except ValueError:
            return -1
        return 0


def array(data: bytes):
    return (U8 * len(data)).from_buffer_copy(data)


def load(path: Path):
    lib = C.CDLL(str(path.resolve()))
    ptr = C.c_void_p
    signatures = {
        "cntru_keygen": [ptr, ptr, RNG, ptr],
        "cntru_base_encrypt": [ptr, ptr, ptr, RNG, ptr],
        "cntru_base_decrypt": [ptr, ptr, ptr],
        "cntru_deterministic_encrypt": [ptr, ptr, ptr],
        "cntru_encaps": [ptr, ptr, ptr, RNG, ptr],
        "cntru_decaps": [ptr, ptr, ptr, C.c_size_t],
        "cntru_pack": [ptr, ptr], "cntru_unpack": [ptr, ptr],
        "cntru_poly_mul": [ptr, ptr, ptr], "cntru_poly_inv": [ptr, ptr],
        "cntru_sample_poly": [ptr, C.c_uint, RNG, ptr],
        "cntru_sample_rm": [ptr, ptr, ptr, RNG, ptr],
        "cntru_shake256": [ptr, C.c_size_t, ptr, C.c_size_t],
    }
    if hasattr(lib, "cntru_encrypt"):
        signatures["cntru_encrypt"] = [ptr, ptr, ptr, RNG, ptr]
        signatures["cntru_decrypt"] = [ptr, ptr, ptr, C.c_size_t]
    for name, args in signatures.items():
        fn = getattr(lib, name)
        fn.argtypes = args
        fn.restype = None if name in ("cntru_poly_mul", "cntru_shake256") else C.c_int
    return lib


def verify(lib) -> dict:
    kem = KEM()
    generator = np.random.default_rng(0xC0211)
    counts = {}
    digest = hashlib.sha256()
    # SHAKE absorb/squeeze rate boundaries, zero output, multiple output blocks.
    for n in [0, 1, 7, 135, 136, 137, 271, 272, 273, 4096]:
        data = generator.bytes(n)
        for m in [0, 1, 32, 135, 136, 137, 416, 1000]:
            out = (U8 * m)()
            lib.cntru_shake256(out, m, array(data), n)
            assert bytes(out) == hashlib.shake_256(data).digest(m), (n, m)
    counts["shake_boundary_cases"] = 80

    for i in range(128):
        a = generator.integers(-210, 211, 512)
        b = generator.integers(-210, 211, 512)
        if i == 0:
            a[:] = 210; b[:] = 210
        if i == 1:
            a[:] = -210; b[:] = 210
        if i == 2:
            a[:] = 1; b[:] = 210
        if i == 3:
            a[:] = -1; b[:] = -210
        if i >= 96:
            if i % 2:
                a = generator.integers(-1, 2, 512)
            else:
                b = generator.integers(-1, 2, 512)
        expected = poly.mul(a, b, 211)
        out, ca, cb = Polynomial(), Polynomial(*a), Polynomial(*b)
        lib.cntru_poly_mul(out, ca, cb)
        assert np.array_equal(expected, np.array(out)), i
        lib.cntru_poly_mul(ca, ca, cb)
        assert bytes(ca) == bytes(out), ("alias", i)
    counts["multiplication_random_extreme_and_alias_cases"] = 128

    for i in range(256):
        a = generator.integers(0, 211, 512)
        if i < 2:
            a[:] = i * 210
        out, decoded = Bytes495(), Polynomial()
        assert lib.cntru_pack(out, Polynomial(*a)) == 0
        assert bytes(out) == poly.pack(a, 211)
        assert lib.cntru_unpack(decoded, out) == 0
        assert np.array_equal(a, np.array(decoded))
    for value in [211**512, (1 << 3960) - 1]:
        assert lib.cntru_unpack(Polynomial(), array(value.to_bytes(495, "little"))) == -1
    for value in [-1, 211]:
        invalid = Polynomial(); invalid[0] = value
        assert lib.cntru_pack(Bytes495(), invalid) == -1
    counts["codec_random_and_boundary_cases"] = 260

    # Every 16-bit word is exercised exactly once for EACH law. Batch 128
    # words into a full polynomial; this also checks block position ordering.
    for which in range(3):
        for start in range(0, 65536, 128):
            data = b"".join(i.to_bytes(2, "little") for i in range(start, start + 128))
            py_tape, c_tape = Tape(data), Tape(data)
            expected = kem.base.sample_poly(which, py_tape.read)
            out = Polynomial()
            assert lib.cntru_sample_poly(out, which, c_tape.callback, None) == 0
            assert np.array_equal(expected, np.array(out)), (which, start)
            assert py_tape.requests == c_tape.requests
    counts["sampler_16bit_inputs_per_law"] = 65536
    counts["sampler_laws"] = 3
    # Conditional message classes exercise ALL byte values, bit ordering,
    # complementary signs and variable byte consumption, including zero class.
    for cls in range(4):
        u = bytes([255 if cls & 1 else 0] * 16 + [255 if cls & 2 else 0] * 16)
        for start in [0, 128]:
            data = bytes(256) + bytes(range(start, start + 128))
            ctape = Tape(data)
            r, m = Polynomial(), Polynomial()
            assert lib.cntru_sample_rm(r, m, array(u), ctape.callback, None) == 0
            pytape = Tape(data)
            expected_r = kem.base.sample_poly(2, pytape.read).reshape(4, 128)
            expected_r = (expected_r * kem.base.signs[:, None]).reshape(512)
            expected_m = np.array([kem.base.lifts[cls].sample(pytape.read) * kem.base.signs
                                   for _ in range(128)]).T.reshape(512)
            assert np.array_equal(expected_r, np.array(r))
            assert np.array_equal(expected_m, np.array(m)), (cls, start)
            assert ctape.requests == pytape.requests
    counts["conditional_sampler_byte_inputs_per_class"] = 256

    for i in range(11):
        a = generator.integers(-1, 2, 512)
        if i == 0: a[:] = 0
        if i == 1: a[:] = 0; a[127] = 1
        if i == 10:
            # x^512+1=(x^256+s*x^128-1)(x^256-s*x^128-1)
            # when s^2=-2 mod211: an explicit nonzero q-nonunit.
            s = next(k for k in range(211) if k*k % 211 == 209)
            a[:] = 0; a[0] = -1; a[128] = s; a[256] = 1
        expected = poly.invq(a, 211)
        out = Polynomial()
        ret = lib.cntru_poly_inv(out, Polynomial(*a))
        if expected is None:
            assert ret == -1
        else:
            assert ret == 0 and np.array_equal(expected, np.array(out))
    counts["inverse_cases"] = 11
    counts["explicit_nonzero_q_nonunit_inverse"] = True

    ciphertexts = 0
    malformed = 0
    forced_g_zero = False
    for i in range(4):
        seed = b"independent-cntru-reference-key-" + bytes([i])
        data = hashlib.shake_256(seed).digest(65536)
        ptape, ctape = Tape(data), Tape(data)
        pk, sk = kem.keygen(ptape.read)
        cpk, csk = Bytes495(), Secret()
        assert lib.cntru_keygen(cpk, C.byref(csk), ctape.callback, None) == 0
        assert bytes(cpk) == pk
        assert list(csk.f) == list(sk.base.f)
        fp = sum(int(w) << (64*j) for j, w in enumerate(csk.fp_inverse))
        assert fp == sk.base.fp_inverse
        assert bytes(csk.public_key) == pk
        assert bytes(csk.rejection_seed) == sk.rejection_seed
        assert ctape.requests == ptape.requests
        digest.update(pk + sk.rejection_seed)
        if i == 0:
            # Insert a rejected all-zero g immediately before the accepted g.
            split = ptape.cursor - 32 - 256
            g_table = kem.base.tables[1]
            zero_row = next(k for k, atom in enumerate(g_table.atoms) if not np.any(atom))
            zero_index = 0 if zero_row == 0 else g_table.cdf[zero_row - 1]
            zero_g_tape = zero_index.to_bytes(2, "little") * 128
            assert not np.any(kem.base.sample_poly(1, Tape(zero_g_tape).read))
            retry_data = data[:split] + zero_g_tape + data[split:]
            pyretry, cretry = Tape(retry_data), Tape(retry_data)
            retry_pk, retry_sk = kem.keygen(pyretry.read)
            out_pk, out_sk = Bytes495(), Secret()
            assert lib.cntru_keygen(out_pk, C.byref(out_sk), cretry.callback, None) == 0
            assert retry_pk == pk == bytes(out_pk)
            assert retry_sk.rejection_seed == bytes(out_sk.rejection_seed)
            assert pyretry.requests == cretry.requests
            assert pyretry.cursor == ptape.cursor + 256
            forced_g_zero = True
            f_table = kem.base.tables[0]
            zero_row = next(k for k, atom in enumerate(f_table.atoms) if not np.any(atom))
            pair_row = next(k for k, atom in enumerate(f_table.atoms)
                            if np.any(atom) and np.count_nonzero(atom) == 2)
            word = lambda row: (0 if row == 0 else f_table.cdf[row - 1]).to_bytes(2, "little")
            for rejected_f in [word(zero_row)*128, word(pair_row) + word(zero_row)*127]:
                f = kem.base.sample_poly(0, Tape(rejected_f).read)
                assert poly.f2_inv(poly.packbits(poly.residue(f, 256)), 256) is None
                pyretry, cretry = Tape(rejected_f + data), Tape(rejected_f + data)
                retry_pk, retry_sk = kem.keygen(pyretry.read)
                out_pk, out_sk = Bytes495(), Secret()
                assert lib.cntru_keygen(out_pk, C.byref(out_sk), cretry.callback, None) == 0
                assert bytes(out_pk) == retry_pk == pk
                assert bytes(out_sk.rejection_seed) == retry_sk.rejection_seed
                assert pyretry.requests == cretry.requests
                assert pyretry.cursor == ptape.cursor + 256

        for j in range(8):
            message = hashlib.sha256(seed + bytes([j])).digest()
            cct, ckey, dkey = Bytes527(), Bytes32(), Bytes32()
            mtape = Tape(message)
            expected_ct, expected_key = kem.encapsulate(pk, Tape(message).read)
            assert lib.cntru_encaps(cct, ckey, cpk, mtape.callback, None) == 0
            assert bytes(cct) == expected_ct and bytes(ckey) == expected_key
            assert lib.cntru_decaps(dkey, C.byref(csk), cct, 527) == 0
            assert bytes(dkey) == expected_key
            digest.update(bytes(cct) + bytes(ckey))
            ciphertexts += 1
            coins = hashlib.shake_256(message).digest(416)
            pytape, ctape = Tape(coins), Tape(coins)
            expected_core = kem.base.encrypt(pk, message, pytape.read)
            core, recovered = Bytes495(), Bytes32()
            assert lib.cntru_base_encrypt(core, cpk, array(message), ctape.callback, None) == 0
            assert bytes(core) == expected_core and ctape.requests == pytape.requests
            assert lib.cntru_base_decrypt(recovered, C.byref(csk), core) == 0
            assert bytes(recovered) == message
            if hasattr(lib, "cntru_encrypt"):
                pytape, ctape = Tape(coins), Tape(coins)
                masked = kem.encrypt(pk, message, pytape.read)
                assert lib.cntru_encrypt(cct, cpk, array(message), ctape.callback, None) == 0
                assert bytes(cct) == masked and ctape.requests == pytape.requests
                assert lib.cntru_decrypt(recovered, C.byref(csk), cct, 527) == 0
                assert bytes(recovered) == kem.decrypt(sk, masked) == message
            tampered = bytearray(expected_ct)
            tampered[(j*71) % 527] ^= 1 << (j % 8)
            other_mask = expected_ct[:495] + bytes(b ^ 0x55 for b in expected_ct[495:])
            bad_inputs = [bytes(tampered), other_mask, b"", expected_ct[:494],
                          expected_ct[:-1], expected_ct + b"\x00", b"\xff"*527,
                          (211**512).to_bytes(495, "little") + expected_ct[495:],
                          expected_ct + generator.bytes(4096)]
            for bad in bad_inputs:
                assert lib.cntru_decaps(dkey, C.byref(csk), array(bad), len(bad)) == 0
                assert bytes(dkey) == kem.decapsulate(sk, bad), (i, j, len(bad))
                malformed += 1
            assert lib.cntru_decaps(dkey, C.byref(csk), None, 0) == 0
            assert bytes(dkey) == kem.decapsulate(sk, b"")
    counts["reference_keygens"] = 4
    counts["forced_zero_g_rejection"] = forced_g_zero
    counts["forced_f2_nonunit_rejections"] = 2
    counts["byte_identical_kem_roundtrips"] = ciphertexts
    counts["malformed_or_tampered_reference_comparisons"] = malformed
    counts["null_empty_ciphertext_cases"] = ciphertexts
    counts["masked_pke_api_exercised"] = hasattr(lib, "cntru_encrypt")
    counts["kat_digest_sha256"] = digest.hexdigest()
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=REPO / "native/build/libcntru.so")
    parser.add_argument("--out", type=Path, default=HERE / "results/reference_checks.json")
    args = parser.parse_args()
    counts = verify(load(args.library))
    result = {"status": "passed", "library": str(args.library),
              "library_sha256": hashlib.sha256(args.library.read_bytes()).hexdigest(),
              "python": sys.version, "numpy": np.__version__, "checks": counts}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
