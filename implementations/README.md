# Implementations

| Folder | Construction |
|---|---|
| `python/ntru/` | Original Python PKE and ACWC0/FO KEM at n=512,q=211 |
| `c/ntru512/` | Portable C / AVX2 for that original parameter set |
| `c/ntru1024/` | C / AVX2 candidates at q=307,331,373; local `parameters/` stores their laws |
| `c/single_double/` | Sixteen selected single/double-encoding profiles, independent oracle and generator |
| `c/common/` | Shared exact radix codec and sampler helpers |

Use `python3 benchmarks/build.py --suites all --test --check` from the repository
root. Build outputs go to `benchmarks/build/<target>/`; measurement drivers and
BAT/END comparisons are under `benchmarks/`. Python oracle scripts are beside
the corresponding C implementation. Install the package with `pip install -e .`
for the public `ntru` Python API. Cryptographic versions and parameter/domain IDs
are unchanged; folder names are not part of the hash transcript.
