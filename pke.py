"""Base encryption of a 256-bit internal residue, without the KEM wrapper."""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import json
import secrets

import numpy as np

import poly
from sample import Table


@dataclass
class SecretKey:
    f: np.ndarray
    fp_inverse: int


class BasePKE:
    def __init__(self, params=None):
        path = Path(params) if params is not None else Path(__file__).with_name('par.json')
        data = json.loads(path.read_text())
        self.n, self.q = data['n'], data['q']
        if (self.n, self.q) != (512, 211):
            raise ValueError('this example uses n=512, q=211')
        self.tables = [Table(tab['rows']) for tab in data['tables']]
        self.lifts = []
        for residue in range(4):
            rows = [row for row in data['tables'][3]['rows']
                    if self.residue_class(row['atom']) == residue]
            if sum(Fraction(r['numerator'], r['denominator']) for r in rows) != Fraction(1, 4):
                raise ValueError('message residues must be uniform')
            self.lifts.append(Table(rows))
        self.signs = np.array([1, -1, 1, -1], dtype=np.int64)
        self.P = np.zeros(self.n, dtype=np.int64)
        self.P[0] = self.P[self.n // 2] = 1
        self.Pinv = self.P.copy()
        self.Pinv[self.n // 2] = -1
        self.Pinv = self.Pinv * pow(2, -1, self.q) % self.q
        self.bytes = poly.encoded_length(self.n, self.q)

    @staticmethod
    def residue_class(a):
        return (a[0] + a[2]) % 2 + 2 * ((a[1] + a[3]) % 2)

    def sample_poly(self, which, source):
        blocks = [self.tables[which].sample(source) for _ in range(self.n // 4)]
        # Block j occupies j, j+128, j+256, j+384.
        return np.array(blocks, dtype=np.int64).T.reshape(self.n)

    def keygen(self, source=secrets.token_bytes):
        while True:
            f = self.sample_poly(0, source)
            fp = poly.f2_inv(poly.packbits(poly.residue(f, 256)), 256)
            if fp is None:
                continue
            fq = poly.invq(f, self.q)
            if fq is not None:
                break
        while True:
            g = self.sample_poly(1, source)
            if poly.invq(g, self.q) is not None:
                break
        h = poly.mul(g, fq, self.q)
        return poly.pack(h, self.q), SecretKey(f, fp)

    def encrypt(self, pk, u, source=secrets.token_bytes):
        if len(u) != 32:
            raise ValueError('the internal residue must be 32 bytes')
        h = poly.unpack(pk, self.n, self.q)
        bits = np.unpackbits(np.frombuffer(u, dtype=np.uint8), bitorder='little')
        r = self.sample_poly(2, source).reshape(4, 128)
        r = (r * self.signs[:, None]).reshape(self.n)
        classes = bits[:128] + 2 * bits[128:]
        blocks = [self.lifts[int(k)].sample(source) * self.signs for k in classes]
        m = np.array(blocks, dtype=np.int64).T.reshape(self.n)
        c0 = (poly.mul(h, r, self.q) + poly.mul(self.Pinv, m, self.q)) % self.q
        return poly.pack(c0, self.q)

    def decrypt(self, sk, ciphertext):
        try:
            c0 = poly.unpack(ciphertext, self.n, self.q)
        except ValueError:
            return None
        v = poly.center(poly.mul(self.P, poly.mul(sk.f, c0, self.q), self.q), self.q)
        residue = poly.packbits(poly.residue(v, 256))
        u = poly.unpackbits(poly.f2_ringmul(sk.fp_inverse, residue, 256), 256)
        return np.packbits(u.astype(np.uint8), bitorder='little').tobytes()
