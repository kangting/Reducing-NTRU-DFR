# Complementary Gaussian Sampling for NTRU

Minimal code for **Reducing NTRU Decryption Noise with Complementary Gaussian Sampling**.

The package contains the base encryption, ACWC0/FO KEM, and the experiments reported
in the paper. The Gaussian experiment evaluates rounded continuous Gaussian laws.
The encryption example uses the paper's finite 17-pattern block distributions at
`n = 512`, `q = 211`, and `P = 1 + x^256`.

## Run

Use Python 3.10 or later.

```bash
python -m pip install -r requirements.txt
python demo.py
python test.py --out results.json
python exp/dfr.py
```

`demo.py` generates three keys and checks 48 encrypt/decrypt round trips. An optional
`--seed 1` makes the demo reproducible; the default uses operating-system randomness.
`test.py` checks the KEM with three keys, 48 fixed-seed messages, and three additional
encapsulations. It checks deterministic re-encryption, changes to both halves of the
external message, modifications of the core and mask, malformed encodings, and
implicit rejection. `results.json` records a successful run.

## Files

| Path | Purpose |
| --- | --- |
| `pke.py` | Key generation, base encryption, internal residue recovery |
| `sample.py` | Exact integer sampling and conditional message lifts |
| `poly.py` | Polynomial arithmetic and radix-q encoding |
| `par.json` | The four finite block distributions used at q = 211 |
| `kem.py` | ACWC0 masking, FO encapsulation and implicit rejection |
| `test.py` | KEM functional tests |
| `demo.py` | Base encryption example |
| `exp/` | Reproduction scripts listed below |

## Experiments

Run these commands from the repository root. Script paths and parameter loading
also work when the commands are invoked from another directory.

| Command | Paper result |
| --- | --- |
| `python exp/gauss.py` | Gaussian coefficient variance 1280 → 388.536795; numerical tail curves at q = 577 and 1061 |
| `python exp/dfr.py` | Exact internal average-error upper bound ≤ 2^-129 at q = 211 |
| `python exp/match.py` | Finite-product magnitude counts for the equal-variance exponential-moment comparison |
| `python exp/orient.py` | Noise variance 52.722656 → 74.769531 when the alternating sign change is removed |
| `python exp/wrap.py` | Actual internal recovery-error lower bound > 2^-100 for that control |
| `python exp/balance.py` | q = 349 full-noise comparison at equal variance; bound exponents 129.291698 and 127.216750 |
| `python exp/cost.py` | Coefficient-variance and block-covariance lattice-cost estimates |

To export the Gaussian curve:

```bash
python exp/gauss.py --out curve.csv
```

The finite q = 211 upper/lower bounds use exact integer or rational arithmetic.
Gaussian curves and lattice-cost estimates are numerical. In the q = 349 comparison,
the complementary bound uses exact rational arithmetic and the isotropic control
uses 70-digit decimal arithmetic. An exponent is the negative base-two logarithm
of the stated bound, not a measured failure probability. The scripts evaluate the
selected parameters; they do not rerun the historical parameter search.

## Encryption example

```python
import secrets
from pke import BasePKE

scheme = BasePKE()
pk, sk = scheme.keygen()
u = secrets.token_bytes(32)
c0 = scheme.encrypt(pk, u)
assert scheme.decrypt(sk, c0) == u
```

Here `u` is the 256-bit **internal residue** and `c0` is the 495-byte base
polynomial ciphertext. The public key also occupies 495 bytes.

## KEM example

```python
from kem import KEM

scheme = KEM()
pk, sk = scheme.keygen()
ciphertext, key = scheme.encapsulate(pk)
assert scheme.decapsulate(sk, ciphertext) == key
assert (len(pk), len(ciphertext), len(key)) == (495, 527, 32)
```

ACWC0 samples an internal message `u` and appends the 32-byte mask
`M xor F(ctx,u)` for the external message `M`. FO derives `u` and the base
randomness from a 416-byte `G(ctx,M)` output. Decapsulation re-encrypts the
complete 527-byte ciphertext; a failed check derives a fallback key from the
secret rejection seed and all received bytes. Malformed public keys raise
`ValueError`. Base or masked PKE decryption returns `None` for malformed
ciphertexts, while KEM decapsulation always returns a 32-byte key.

`kem.py` defines the fixed public version and parameter identifier. Change the
identifier when changing the parameter tables or encoding conventions. Hash
inputs use eight-byte little-endian length prefixes and separate `F`, `G`, `H`
tags. SHAKE256 is provided by Python's standard `hashlib`; no extra hash
implementation is needed.

This Python code is a research implementation with data-dependent loops and
branches. Functional tests check executable behavior; the rare-failure bound
comes from `exp/dfr.py`, rather than the number of successful test messages.
