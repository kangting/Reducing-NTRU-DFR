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
python -m examples.demo
python -m tests.test_kem --out results/kem.json
python -m experiments.dfr
```

`examples/demo.py` generates three keys and checks 48 encrypt/decrypt round trips. An optional
`--seed 1` makes the demo reproducible; the default uses operating-system randomness.
`tests/test_kem.py` checks the KEM with three keys, 48 fixed-seed messages, and three additional
encapsulations. It checks deterministic re-encryption, changes to both halves of the
external message, modifications of the core and mask, malformed encodings, and
implicit rejection. `results/kem.json` records a successful run.

## Repository layout

```text
.
├── ntru/          # Encryption, KEM, polynomial arithmetic, and parameter tables
├── examples/      # Runnable encryption example
├── experiments/   # Paper reproduction scripts
├── tests/         # KEM functional tests
├── results/       # Recorded test results and exported experiment output
├── README.md
└── requirements.txt
```

## Files

| Path | Purpose |
| --- | --- |
| `ntru/pke.py` | Key generation, base encryption, internal residue recovery |
| `ntru/sample.py` | Exact integer sampling and conditional message lifts |
| `ntru/poly.py` | Polynomial arithmetic and radix-q encoding |
| `ntru/par.json` | The four finite block distributions used at q = 211 |
| `ntru/kem.py` | ACWC0 masking, FO encapsulation and implicit rejection |
| `tests/test_kem.py` | KEM functional tests |
| `examples/demo.py` | Base encryption example |
| `experiments/` | Reproduction scripts listed below |

## Experiments

Run these module commands from the repository root. Parameter files are resolved
relative to the package, independently of the working directory.

| Command | Paper result |
| --- | --- |
| `python -m experiments.gauss` | Gaussian coefficient variance 1280 → 388.536795; numerical tail curves at q = 577 and 1061 |
| `python -m experiments.dfr` | Exact internal average-error upper bound ≤ 2^-129 at q = 211 |
| `python -m experiments.match` | Finite-product magnitude counts for the equal-variance exponential-moment comparison |
| `python -m experiments.orient` | Noise variance 52.722656 → 74.769531 when the alternating sign change is removed |
| `python -m experiments.wrap` | Actual internal recovery-error lower bound > 2^-100 for that control |
| `python -m experiments.balance` | q = 349 full-noise comparison at equal variance; bound exponents 129.291698 and 127.216750 |
| `python -m experiments.cost` | Coefficient-variance and block-covariance lattice-cost estimates |

To export the Gaussian curve:

```bash
python -m experiments.gauss --out results/curve.csv
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
from ntru.pke import BasePKE

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
from ntru.kem import KEM

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

`ntru/kem.py` defines the fixed public version and parameter identifier. Change the
identifier when changing the parameter tables or encoding conventions. Hash
inputs use eight-byte little-endian length prefixes and separate `F`, `G`, `H`
tags. SHAKE256 is provided by Python's standard `hashlib`; no extra hash
implementation is needed.

This Python code is a research implementation with data-dependent loops and
branches. Functional tests check executable behavior; the rare-failure bound
comes from `experiments/dfr.py`, rather than the number of successful test messages.
