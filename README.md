# Reducing NTRU Decryption Noise with Complementary Gaussian Sampling

Code, parameters and numerical data for the paper: the original Python construction,
scalar/AVX2 C implementations, finite-law DFR calculations, structural lattice-cost
diagnostics and measured KEM tables.

Start with **[the experiment guide](paper/README.md)**,
**[the result PDF](paper/tables/publication-tables.pdf)** or
**[the cycle data](paper/data/cycles-summary.csv)**.

## Repository contents

| Path | Purpose |
|---|---|
| `ntru/` | Original q=211 PKE, ACWC0/FO KEM, arithmetic and exact samplers |
| `examples/`, `tests/` | Encryption example and KEM/affine checks |
| `experiments/` | Gaussian/noise, exact DFR, orientation controls and GSA costs |
| `hardened/` | C implementation for n=512,q=211 |
| `hardened_levels/`, `levels/params/` | C implementation/distributions for n=1024,q=307/331/373 |
| `family_20261107/` | Sixteen selected S/D profiles, Python oracle and C implementation |
| `common/` | Exact radix codec, sampler helpers and PMU-cycle reader |
| `benchmarks/vendor/` | BAT/END sources used by local comparisons, with upstream notices |
| `paper/` | Portable build/measurement scripts, scientific raw data and tables |

The publication package contains source and scientific results. Compiled libraries,
machine-local environments, duplicate archives, audit digests and intermediate
failure checkpoints are unnecessary for reproduction. Parameter identifiers inside
the cryptographic byte contract remain part of the implementation.

## Quick start

Python 3.10+, NumPy and SciPy are required for the mathematical experiments/oracles.
C builds require Linux x86-64 and GCC; executing AVX2 variants requires AVX2 support.
Offline cycle-table analysis uses only the Python standard library.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m examples.demo --seed 1
.venv/bin/python -m tests.test_kem --out results/kem.json
.venv/bin/python -m tests.test_affine
python3 paper/analyze.py
python3 paper/build.py --suites all --test --check
```

The builder checks all proposed implementations and reports known END shared-key
failures explicitly. Failed targets receive no timing rank. Building/checking does
not change CPU controls or run privileged measurements.

## Original mathematical experiments

Run from the repository root after activating `.venv` (or use `.venv/bin/python`):

| Command | Calculation |
|---|---|
| `python -m experiments.gauss` | Rounded Gaussian variance and tail curves |
| `python -m experiments.dfr` | Exact q=211 internal average-error upper bound |
| `python -m experiments.match` | Finite-product exponential-moment comparison |
| `python -m experiments.orient` | Noise variance without the alternating sign map |
| `python -m experiments.wrap` | Recovery-error lower bound for that control |
| `python -m experiments.balance` | Equal-variance q=349 full-noise comparison |
| `python -m experiments.cost` | Coefficient/block-covariance GSA costs |
| `python -m experiments.affine --out results/affine.json` | Conditional normalized-key affine path |

The finite q=211 bounds use exact integer/rational arithmetic. Gaussian curves and
lattice-cost calculations are numerical. A bound exponent is the negative binary
logarithm of a mathematical bound, not a measured failure probability. The scripts
recompute selected configurations, not the historical search process.
See [the family guide](family_20261107/README.md) for the revised S/D calculations.

## Interpretation

Performance is actual task hardware CPU cycles, divided by 1,000 for kcycles.
Python is an independent oracle, not the timed reference. The original q=211,
older n=1024 and revised-family runs are separate cohorts. Exploratory wall-time/TSC
optimization traces are not mixed into these final cycle tables.

DFR entries are bounds under the stated distributions and accepted-key conditions.
C/Q entries are structural GSA/MATZOV diagnostics for specified paths, not a full
KEM security proof or NIST classification. External message, internal residue and
shared-key output lengths differ. Functional/leakage tests are not a proof of
constant-time execution or production security.
