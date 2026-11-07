# Reducing NTRU Decryption Noise with Complementary Gaussian Sampling

Implementations, mathematical experiments and measured results for the paper.

**[Result tables (PDF)](results/tables/publication-tables.pdf)** ·
**[Performance data (CSV)](results/summary/performance.csv)** ·
**[Reproduction guide](benchmarks/README.md)**

## Where to look

```text
implementations/   Python reference and C implementations
experiments/       Noise, DFR, parameter selection and attack-cost calculations
benchmarks/        Build, measure and analyze performance; comparison sources
results/           Recorded raw data, summary CSVs and manuscript tables
tests/             Python and benchmark-infrastructure checks
examples/          Small runnable encryption example
```

| Task | Location |
|---|---|
| Use the original Python PKE/KEM | [implementations/python/ntru](implementations/python/ntru) |
| Inspect the n=512,q=211 C code | [implementations/c/ntru512](implementations/c/ntru512) |
| Inspect n=1024,q=307/331/373 | [implementations/c/ntru1024](implementations/c/ntru1024) |
| Inspect the 16 selected S/D profiles | [implementations/c/single_double](implementations/c/single_double/README.md) |
| Reproduce the mathematical calculations | [experiments](experiments/README.md) |
| Build or measure C implementations | [benchmarks](benchmarks/README.md) |
| Find raw data and paper-ready tables | [results](results/README.md) |

## Recompute the recorded performance table

From the repository root, using Python 3.10 or later:

```sh
python3 benchmarks/analyze.py
```

This needs only Python's standard library. It checks all three recorded cohorts
and regenerates `results/summary/performance.csv`: 156 measured operation rows
and 21 explicitly excluded rows. Timings, distributions and cryptographic byte
contracts are unchanged by the folder organization.

## Build and check C code

Linux x86-64 and GCC are required; executing vector variants requires AVX2.

```sh
python3 benchmarks/build.py --suites all --test --check
```

All generated binaries stay under ignored `benchmarks/build/`. The command
reports known END shared-key failures explicitly and assigns them no timing rank.
See [benchmark instructions](benchmarks/README.md) for a fresh controlled run.

## Python examples and mathematical experiments

Install the local package and its NumPy/SciPy dependencies in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m examples.demo --seed 1
.venv/bin/python -m tests.test_kem
.venv/bin/python -m tests.test_affine
```

The `ntru` import name remains the same; its source and parameter JSON are in
`implementations/python/ntru/`. Run commands from the repository root.

## Reading the results

Performance uses actual task hardware CPU cycles, divided by 1,000 for kcycles.
REF is C; Python is the independent oracle. The original n=512, older n=1024 and
revised S/D measurements are separate cohorts. DFR entries are mathematical
bounds, not observed rare-failure rates. Structural C/Q cost diagnostics are not
full-KEM security proofs or NIST classifications. Message, residue and shared-key
output lengths are recorded separately. Details are in [results](results/README.md).
