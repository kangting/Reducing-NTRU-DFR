"""Independent, variable-time Python oracle for the frozen n=1024 profiles.

This is test/reference code. The C implementation must not copy its branches,
large Python integers, direct CDF indexing or Euclidean inverse routines.
"""
from __future__ import annotations
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import hmac
from pathlib import Path
import secrets
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]/'implementations/python'))
from ntru import poly
from ntru.sample import Table
from ntru.kem import frame
from profiles import load_profile


class FixedTape:
    def __init__(self, data):
        self.data = bytes(data)
        self.cursor = 0
        self.requests = []

    def read(self, size):
        if size < 0 or self.cursor+size > len(self.data): raise ValueError('Random tape exhausted')
        start = self.cursor; self.cursor += size; self.requests.append(size)
        return self.data[start:self.cursor]


def exact_read(source, size):
    result = source(size)
    if len(result) != size: raise ValueError('Random source returned wrong length')
    return result


@dataclass
class SecretKey:
    q: int
    f: np.ndarray
    fp_inverse: int
    public_key: bytes
    rejection_seed: bytes


class KEM:
    def __init__(self, q):
        self.profile = profile = load_profile(q)
        self.n, self.q = profile['n'], profile['q']
        self.pk_bytes, self.ct_bytes = profile['pk_bytes'], profile['ct_bytes']
        self.version, self.parameter_id = profile['version'].encode(), profile['parameter_id'].encode()
        self.tables = [Table(tab['rows']) for tab in profile['tables']]
        self.lifts = []
        for cls in range(4):
            rows = [row for row in profile['tables'][3]['rows'] if self.residue_class(row['atom']) == cls]
            if sum(Fraction(row['numerator'], row['denominator']) for row in rows) != Fraction(1, 4):
                raise ValueError('Message residue classes must be uniform')
            self.lifts.append(Table(rows))
        self.signs = np.array([1, -1, 1, -1], dtype=np.int64)
        self.P = np.zeros(self.n, dtype=np.int64); self.P[0] = self.P[self.n//2] = 1
        self.Pinv = self.P.copy(); self.Pinv[self.n//2] = -1
        self.Pinv = self.Pinv*pow(2, -1, q) % q

    @staticmethod
    def residue_class(atom):
        return (atom[0]+atom[2]) % 2 + 2*((atom[1]+atom[3]) % 2)

    def sample_poly(self, which, source):
        """Every block consumes two bytes, even when normalized total <256."""
        table = self.tables[which]
        total = int(table.cdf[-1])
        if total & (total-1): raise ValueError('CDF total must be a power of two')
        blocks = [table.atoms[bisect_right(table.cdf, int.from_bytes(exact_read(source, 2), 'little') & (total-1))]
                  for _ in range(256)]
        return np.array(blocks, dtype=np.int64).T.reshape(self.n)

    def sample_rm(self, u, source):
        if len(u) != 64: raise ValueError('Internal residue must be64 bytes')
        # Public fixed consumption; the local oracle implements compact logical
        # consumption inside rho, independently of the C oblivious full scan.
        tape = FixedTape(exact_read(source, 768))
        r = (self.sample_poly(2, tape.read).reshape(4, 256)*self.signs[:, None]).reshape(self.n)
        bits = np.unpackbits(np.frombuffer(u, dtype=np.uint8), bitorder='little')
        classes = bits[:256]+2*bits[256:]
        m = np.array([self.lifts[int(cls)].sample(tape.read)*self.signs for cls in classes], dtype=np.int64).T.reshape(self.n)
        return r, m

    def keygen(self, source=secrets.token_bytes):
        fpool = exact_read(source, 131072)
        gpool = exact_read(source, 1024)
        z = exact_read(source, 32)
        f = fp = g = None
        selected = []
        for index in range(256):
            candidate = self.sample_poly(0, FixedTape(fpool[index*512:(index+1)*512]).read)
            inverse = poly.f2_inv(poly.packbits(poly.residue(candidate, 512)), 512)
            if inverse is not None:
                f, fp = candidate, inverse; selected.append(index); break
        for index in range(2):
            candidate = self.sample_poly(1, FixedTape(gpool[index*512:(index+1)*512]).read)
            # Use actual q-invertibility as an independent check of the C
            # support-specific nonzero shortcut; never assume it here.
            if poly.invq(candidate, self.q) is not None:
                g = candidate; selected.append(index); break
        if f is None or g is None: raise ValueError('Fixed key pool exhausted')
        fq = poly.invq(f, self.q)
        if fq is None: raise ValueError('Accepted f is not a q-unit')
        pk = poly.pack(poly.mul(g, fq, self.q), self.q)
        return pk, SecretKey(self.q, f, fp, pk, z), selected

    def context(self, pk):
        return frame(self.version, self.parameter_id, pk)

    def mask_hash(self, pk, u):
        if len(u) != 64: raise ValueError('Internal residue must be64 bytes')
        return hashlib.shake_256(frame(b'F', self.context(pk), u)).digest(32)

    def key_hash(self, pk, ciphertext, secret):
        if len(secret) != 32: raise ValueError('Key preimage must be32 bytes')
        return hashlib.shake_256(frame(b'H', self.context(pk), ciphertext, secret)).digest(32)

    def base_encrypt(self, pk, u, source=secrets.token_bytes):
        h = poly.unpack(pk, self.n, self.q)
        r, m = self.sample_rm(u, source)
        c = (poly.mul(h, r, self.q)+poly.mul(self.Pinv, m, self.q)) % self.q
        return poly.pack(c, self.q)

    def base_decrypt(self, sk, ciphertext):
        if sk.q != self.q: raise ValueError('Secret-key profile mismatch')
        try: c = poly.unpack(ciphertext, self.n, self.q)
        except ValueError: return None
        v = poly.center(poly.mul(self.P, poly.mul(sk.f, c, self.q), self.q), self.q)
        residue = poly.packbits(poly.residue(v, 512))
        value = poly.f2_ringmul(sk.fp_inverse, residue, 512)
        return int(value).to_bytes(64, 'little')

    def encrypt(self, pk, message, source=secrets.token_bytes):
        if len(message) != 32: raise ValueError('External message must be32 bytes')
        u = exact_read(source, 64)
        core = self.base_encrypt(pk, u, source)
        return core+bytes(a ^ b for a, b in zip(message, self.mask_hash(pk, u)))

    def decrypt(self, sk, ciphertext):
        if len(ciphertext) != self.ct_bytes: return None
        u = self.base_decrypt(sk, ciphertext[:self.pk_bytes])
        if u is None: return None
        return bytes(a ^ b for a, b in zip(ciphertext[self.pk_bytes:], self.mask_hash(sk.public_key, u)))

    def deterministic_encrypt(self, pk, message):
        if len(message) != 32: raise ValueError('External message must be32 bytes')
        coins = hashlib.shake_256(frame(b'G', self.context(pk), message)).digest(832)
        return self.encrypt(pk, message, FixedTape(coins).read)

    def encapsulate(self, pk, source=secrets.token_bytes):
        poly.unpack(pk, self.n, self.q)
        message = exact_read(source, 32)
        ciphertext = self.deterministic_encrypt(pk, message)
        return ciphertext, self.key_hash(pk, ciphertext, message)

    def decapsulate(self, sk, ciphertext):
        message = self.decrypt(sk, ciphertext)
        valid = message is not None and hmac.compare_digest(ciphertext, self.deterministic_encrypt(sk.public_key, message))
        return self.key_hash(sk.public_key, ciphertext, message if valid else sk.rejection_seed)
