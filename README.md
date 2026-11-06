# Complementary Gaussian Sampling for NTRU

Minimal code for **Reducing NTRU Decryption Noise with Complementary Gaussian Sampling**.

The package contains the polynomial encryption example and the experiments reported
in the paper. The Gaussian experiment evaluates rounded continuous Gaussian laws.
The encryption example uses the paper's finite 17-pattern block distributions at
`n = 512`, `q = 211`, and `P = 1 + x^256`.

## Run

Use Python 3.10 or later.

```bash
python -m pip install -r requirements.txt
python demo.py
python exp/dfr.py
```

`demo.py` generates three keys and checks 48 encrypt/decrypt round trips. An optional
`--seed 1` makes the demo reproducible; the default uses operating-system randomness.

## Files

| Path | Purpose |
| --- | --- |
| `pke.py` | Key generation, base encryption, internal residue recovery |
| `sample.py` | Exact integer sampling and conditional message lifts |
| `poly.py` | Polynomial arithmetic and radix-q encoding |
| `par.json` | The four finite block distributions used at q = 211 |
| `demo.py` | A short working example |
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

Here `u` is the 256-bit **internal residue** and `c0` is the base polynomial
ciphertext. The example transmits a 495-byte public key and a 495-byte base
ciphertext. The paper's ACWC0/FO KEM additionally uses a 32-byte mask, giving
495/527 bytes. That wrapper is omitted from this package. This Python code is a
research implementation; the loops and branches are not constant time.
