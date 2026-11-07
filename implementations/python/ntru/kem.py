"""ACWC0 masking and FO encapsulation for the finite q=211 base PKE."""
from dataclasses import dataclass
import hashlib
import hmac
import secrets

from .pke import BasePKE, SecretKey as BaseSecretKey
from . import poly

VERSION = b'Complementary-NTRU-ACWC0-FO-v1'
PARAMETER_ID = b'n512-q211-P1+x256-block17-v1'


def frame(*parts):
    """Length-prefixed tuples; lengths are unsigned eight-byte LE integers."""
    return b''.join(len(p).to_bytes(8, 'little') + p for p in parts)


class FixedTape:
    def __init__(self, data):
        self.data = data
        self.cursor = 0

    def read(self, count):
        if count < 0 or self.cursor + count > len(self.data):
            raise ValueError('encryption randomness exhausted')
        start = self.cursor
        self.cursor += count
        return self.data[start:self.cursor]


@dataclass
class SecretKey:
    base: BaseSecretKey
    public_key: bytes
    rejection_seed: bytes


class KEM:
    def __init__(self):
        self.base = BasePKE()
        self.pk_bytes = self.base.bytes
        self.ct_bytes = self.base.bytes + 32

    @staticmethod
    def context(pk):
        return frame(VERSION, PARAMETER_ID, pk)

    def keygen(self, source=secrets.token_bytes):
        pk, base_key = self.base.keygen(source)
        z = source(32)
        if len(z) != 32:
            raise ValueError('random source returned wrong length')
        return pk, SecretKey(base_key, pk, z)

    def mask_hash(self, pk, u):
        if len(u) != 32:
            raise ValueError('internal message must be 32 bytes')
        return hashlib.shake_256(frame(b'F', self.context(pk), u)).digest(32)

    def encrypt(self, pk, message, source=secrets.token_bytes):
        """Randomized ACWC0 PKE; an external message uses fresh internal u."""
        if len(message) != 32:
            raise ValueError('external message must be 32 bytes')
        u = source(32)
        if len(u) != 32:
            raise ValueError('random source returned wrong length')
        core = self.base.encrypt(pk, u, source)
        mask = bytes(a ^ b for a, b in zip(message, self.mask_hash(pk, u)))
        return core + mask

    def decrypt(self, sk, ciphertext):
        """Masked PKE decryption; malformed ciphertexts return None."""
        if len(ciphertext) != self.ct_bytes:
            return None
        core, mask = ciphertext[:self.base.bytes], ciphertext[self.base.bytes:]
        u = self.base.decrypt(sk.base, core)
        if u is None:
            return None
        return bytes(a ^ b for a, b in zip(mask, self.mask_hash(sk.public_key, u)))

    def deterministic_encrypt(self, pk, message):
        if len(message) != 32:
            raise ValueError('external message must be 32 bytes')
        # G outputs u (32 bytes), then rho (384 bytes). Unused rho is ignored.
        coins = hashlib.shake_256(frame(b'G', self.context(pk), message)).digest(416)
        return self.encrypt(pk, message, FixedTape(coins).read)

    def key_hash(self, pk, ciphertext, secret):
        if len(secret) != 32:
            raise ValueError('key preimage must be 32 bytes')
        return hashlib.shake_256(
            frame(b'H', self.context(pk), ciphertext, secret)).digest(32)

    def encapsulate(self, pk, source=secrets.token_bytes):
        # Public-key parsing failure is reported as ValueError in this API.
        poly.unpack(pk, self.base.n, self.base.q)
        message = source(32)
        if len(message) != 32:
            raise ValueError('random source returned wrong length')
        ciphertext = self.deterministic_encrypt(pk, message)
        return ciphertext, self.key_hash(pk, ciphertext, message)

    def decapsulate(self, sk, ciphertext):
        message = self.decrypt(sk, ciphertext)
        valid = False
        if message is not None:
            candidate = self.deterministic_encrypt(sk.public_key, message)
            valid = hmac.compare_digest(ciphertext, candidate)
        secret = message if valid else sk.rejection_seed
        # Bind all received bytes even if length or canonical decoding failed.
        return self.key_hash(sk.public_key, ciphertext, secret)
