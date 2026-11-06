"""Check key generation, base encryption and recovery of uniform residues."""
import argparse
import random
import secrets

from ntru.pke import BasePKE


def run(keys=3, trials=16, seed=None):
    source = secrets.token_bytes
    if seed is not None:
        rng = random.Random(seed)
        source = lambda count: rng.getrandbits(8 * count).to_bytes(count, 'little')
    scheme = BasePKE()
    for _ in range(keys):
        pk, sk = scheme.keygen(source)
        for _ in range(trials):
            u = source(32)
            ciphertext = scheme.encrypt(pk, u, source)
            if scheme.decrypt(sk, ciphertext) != u:
                raise RuntimeError('internal residue recovery failed')
    print(f'Base encryption: {keys} keys, {keys * trials} round trips passed.')
    print(f'Public key {len(pk)} B; base ciphertext {len(ciphertext)} B.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keys', type=int, default=3)
    parser.add_argument('--trials', type=int, default=16)
    parser.add_argument('--seed', type=int, help='reproducible demo RNG, not a cryptographic RNG')
    args = parser.parse_args()
    if args.keys < 1 or args.trials < 1:
        parser.error('keys and trials must be positive')
    run(args.keys, args.trials, args.seed)
