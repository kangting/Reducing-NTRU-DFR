"""Functional KEM tests: three keys, 48 fixed-seed messages, three encapsulations."""
import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import random

from ntru.kem import FixedTape, KEM, frame


def flip(data, index):
    out = bytearray(data)
    out[index] ^= 1
    return bytes(out)


def run(keys=3, trials=16, out=None):
    rng = random.Random(1)
    source = lambda n: rng.getrandbits(8*n).to_bytes(n, 'little')
    kem = KEM()
    checks = Counter()
    for _ in range(keys):
        pk, sk = kem.keygen(source)
        assert len(pk) == 495
        changed_z = replace(sk, rejection_seed=flip(sk.rejection_seed, 0))
        for j in range(trials):
            message = b'\x00'*32 if j == 0 else b'\xff'*32 if j == 1 else source(32)
            ciphertext = kem.deterministic_encrypt(pk, message)
            assert len(ciphertext) == 527
            assert kem.decrypt(sk, ciphertext) == message
            key = kem.key_hash(pk, ciphertext, message)
            assert kem.decapsulate(sk, ciphertext) == key
            checks['honest'] += 1
            assert kem.deterministic_encrypt(pk, message) == ciphertext
            checks['reencryption'] += 1
            # Changing either 128-bit half of M changes deterministic encryption.
            for index in (0, 16):
                assert kem.deterministic_encrypt(pk, flip(message, index))[:495] != ciphertext[:495]
            checks['both_message_halves'] += 1
            for name, index in [('core_mutation', 0), ('mask_mutation', 495)]:
                altered = flip(ciphertext, index)
                fallback = kem.key_hash(pk, altered, sk.rejection_seed)
                assert kem.decapsulate(sk, altered) == fallback
                assert kem.decapsulate(sk, altered) == fallback
                assert kem.decapsulate(changed_z, altered) != fallback
                checks[name] += 1
            noncanonical = (kem.base.q**kem.base.n).to_bytes(495, 'little') + ciphertext[495:]
            for bad in (b'', ciphertext[:-1], ciphertext+b'\x00', noncanonical):
                assert kem.decrypt(sk, bad) is None
                assert kem.decapsulate(sk, bad) == kem.key_hash(pk, bad, sk.rejection_seed)
            checks['malformed_ciphertexts'] += 1
            assert kem.decapsulate(changed_z, ciphertext) == key
            checks['valid_independent_of_fallback'] += 1
        # Reusing only internal coins changes the mask, never the core.
        coins = source(416)
        c0 = kem.encrypt(pk, bytes(32), FixedTape(coins).read)
        c1 = kem.encrypt(pk, b'\xff'*32, FixedTape(coins).read)
        assert c0[:495] == c1[:495]
        assert bytes(a ^ b for a, b in zip(c0[495:], c1[495:])) == b'\xff'*32
        assert kem.base.decrypt(sk.base, c0[:495]) == coins[:32]
        checks['mask_xor'] += 1
        # All-one internal residue reaches the stated maximum random-tape use.
        tape = FixedTape(b'\xff'*32 + source(384))
        assert kem.decrypt(sk, kem.encrypt(pk, bytes(32), tape.read)) == bytes(32)
        assert tape.cursor == 416
        checks['maximum_coin_budget'] += 1
        for bad_pk in (pk[:-1], pk+b'\x00', (211**512).to_bytes(495, 'little')):
            try:
                kem.encapsulate(bad_pk, source)
            except ValueError:
                checks['malformed_public_key'] += 1
            else:
                raise AssertionError('malformed public key accepted')
        ciphertext, key = kem.encapsulate(pk, source)
        assert len(key) == 32 and kem.decapsulate(sk, ciphertext) == key
        checks['encapsulations'] += 1
    assert frame(b'a', b'bc') != frame(b'ab', b'c')
    try:
        FixedTape(bytes(384)).read(385)
    except ValueError:
        checks['tape_exhaustion'] += 1
    else:
        raise AssertionError('finite randomness tape overrun')
    result = dict(status='passed', keys=keys, messages=keys*trials,
                  public_key_bytes=495, ciphertext_bytes=527, shared_key_bytes=32,
                  base_randomness_bytes=384, masked_randomness_bytes=416,
                  checks=dict(checks))
    text = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(text+'\n')
    print(text)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keys', type=int, default=3)
    parser.add_argument('--trials', type=int, default=16)
    parser.add_argument('--out', help='optional result JSON')
    args = parser.parse_args()
    if args.keys < 1 or args.trials < 1:
        parser.error('keys and trials must be positive')
    run(args.keys, args.trials, args.out)
