# Recorded results

| Folder | Contents |
|---|---|
| [raw/](raw/) | Compact numeric records of all accepted/rejected PMU batches |
| [summary/](summary/) | Performance/parameter CSVs, selected metadata and original model/test results |
| [tables/](tables/) | TeX/SVG sources, full Markdown tables and a vector PDF |

**[Six-page PDF](tables/publication-tables.pdf)** ·
**[Performance CSV](summary/performance.csv)** ·
**[All S/D parameters](summary/all_profiles_parameters.csv)** ·
**[All S/D performance](summary/all_profiles_performance.csv)**

## Recorded cohorts

| Raw file | Construction | Processes | Ranked targets | Operation groups |
|---|---|---:|---:|---:|
| `raw/ntru512.json.gz` | n=512,q=211 plus BAT/END | 707 | 7 | 21 |
| `raw/ntru1024.json.gz` | q=307/331/373 plus BAT/END-1024 | 808 | 8 | 24 |
| `raw/single_double.json.gz` | Sixteen S/D profiles plus peers | 3737 | 37 | 111 |

The primary S/D tables report four configurations. The extended repository
tables list all sixteen.
`summary/single_double_performance.csv` retains raw cycles, exact kcycles,
bootstrap intervals and counts; `summary/performance.csv` joins three distinct
cohorts with 156 measured rows and 21 blank exclusions. Internal study/profile
identifiers are preserved. Raw data and numerical values are unchanged by moves.

Recompute with `python3 benchmarks/analyze.py` from the repository root; see
[the benchmark guide](../benchmarks/README.md). Dataset fields omit machine-local
paths, process identifiers, duplicate stdout and build/audit digests while retaining
all scientific timing/selection fields and PMU endpoints.

## Interpretation

Units are actual task hardware CPU cycles / 1,000. Reported values are medians of
accepted batch means with bootstrap 95% intervals. KeyGen includes OS randomness;
Encaps uses an external seed/message. Interruption filtering can favor shorter
variable-time KeyGen realizations. Different schemes have different M/u/K lengths
and security/hardening models. END failures are explicit blank cells, not zero cost.

C/Q values in the parameter tables record the historical profile-screening
calculations. See the [paper reproducibility package](../experiments/paper_reproduction/README.md)
for the recovery diagnostics reported in Tables III and VI. The exponent b
describes a mathematical bound, and the recovery diagnostics describe work
under the specified model.
Comparator metadata use heterogeneous methods. BAT API sizes include one-byte
headers; source-only sizes retain the header-free convention. No unspecified
compression denominator is inferred.
