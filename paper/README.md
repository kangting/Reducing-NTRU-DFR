# Paper experiments and data

The final PMU datasets retain scientific numeric fields from the completed runs.
Local paths, process identifiers, duplicate stdout and build/audit digests are
omitted. No numeric timing, selection decision, interval or count is changed.

## Recorded cohorts

| Dataset | Construction | Processes | Ranked targets | Operation groups |
|---|---|---:|---:|---:|
| `data/q211-raw.json.gz` | n=512,q=211 and BAT/END-512 | 707 | 7 | 21 |
| `data/levels-raw.json.gz` | n=1024,q=307/331/373 and BAT/END-1024 | 808 | 8 | 24 |
| `data/family-raw.json.gz` | Sixteen revised S/D profiles and peers | 3737 | 37 | 111 |

Every cohort has 101 rounds. Raw files retain target/operation order, accepted and
rejected batches, PMU value/enabled/running endpoints, work counts, CPU migration,
context-switch/page-fault observations, RNG requests, input offsets and 31 empty
counter-read-pair samples per process. Wall-nanosecond observations are separate.

```sh
python3 paper/analyze.py
```

This recomputes medians and 10,000-resample bootstrap 95% intervals and compares
them with recorded summaries. `data/cycles-summary.csv` has 156 measured rows and
21 blank exclusion rows across the three cohorts. This analysis needs no C
binaries, old build records, network, sudo or external Python packages.

## Tables

- [Six-page vector PDF](tables/publication-tables.pdf)
- [Full family tables](tables/TABLES.md)
- [All family parameters](data/family-appendix-parameters.csv)
- [Exact family performance, intervals and counts](data/family-performance.csv)
- [All cohorts in kcycles](data/cycles-summary.csv)

The main family table has four primary profiles; the appendix has all sixteen.
TeX and SVG sources are under `tables/`. Standalone TeX needs `booktabs`, `graphicx`
and `geometry`. Comparator metadata use separate security/DFR models. BAT API
sizes include one-byte key/ciphertext headers; source-only sizes retain the
header-free convention. No common security certification or unspecified
compression denominator is assigned.

## Environment and protocol

Intel Core i9-14900KF, Linux x86-64, GCC 15.2.0, and common flags
`-std=gnu11 -O3 -DNDEBUG -fPIC -mtune=generic`. REF uses `-march=x86-64`;
AVX2 uses `-march=x86-64-v3` plus the vector NTT. Scalar-v3 rows use the wider ISA
without selecting the vector implementation. The latest run used Ubuntu 26.04.1
LTS and Linux 7.0.0-42-generic. Each raw file records its exact kernel/compiler.

One thread was pinned to logical CPU 4; SMT sibling 5 was offline, Turbo disabled,
the performance governor selected, and both frequency bounds set to 3 GHz.
Other cores/interrupts were not fully isolated. Settings were restored after each
study. Frequency bounds do not rule out thermal throttling.

Each batch has one KeyGen or 32 Encaps/Decaps calls. There are eight warm keys,
32 warm KEM pairs, and an eight-key/256-ciphertext correctness pool in every
process. Offsets rotate by 32 each round. Counter-read overhead is retained,
never subtracted. Wrong CPU, involuntary context switches, major faults and
unscheduled/multiplexed counters are rejected; voluntary waits remain. Every
group exceeds the fixed minimum of 30 accepted batches. KeyGen medians are
conditional on this filter, not unconditional/tail latency estimates.

KeyGen includes OS entropy. Encaps uses an external seed/message, excluding its
initial OS draw but retaining all internal work. Task cycles include on-CPU user
and kernel execution; off-CPU waits contribute no task cycles. Wall time is never
multiplied by frequency to obtain cycle counts.

## Build and check

```sh
python3 paper/build.py --suites all --test --check
python3 paper/build.py --targets p03-ref p15-avx2 q211-ref q373-avx2 --test --check
```

Core objects are shared by each library, C test and timing executable. Generated
outputs are ignored build files. q541 includes the ten-bit inverse exponent and
constant-two regression. Known END failures are explicit: END512 AVX2 and all
END1024 variants fail the shared-key preflight through the preserved adapters.

With root requirements installed, independent oracle examples are:

```sh
.venv/bin/python family_20261107/verify.py --profiles 1 2 3 4 15 --isa portable
.venv/bin/python family_20261107/verify.py --profiles 1 2 3 4 15 --isa avx2
.venv/bin/python publication/verify_reference.py --library paper/build/q211-ref/libcntru.so --out paper/local-results/q211-oracle.json
.venv/bin/python levels/verify.py --q 373 --library paper/build/q373-avx2/libcntru.so --out paper/local-results/q373-oracle.json
```

## Fresh controlled measurement

Choose an allowed logical CPU and supported frequency for your machine. Run as
the ordinary user. The wrapper invokes sudo locally only for temporary CPU controls
and scoped PMU setup; global perf permissions stay unchanged. This controller
requires Linux Intel `intel_pstate` controls.

```sh
bash paper/run_controlled.sh family NEW_RUN_NAME 4 3000000
bash paper/run_controlled.sh q211 ANOTHER_RUN_NAME 4 3000000
bash paper/run_controlled.sh levels THIRD_RUN_NAME 4 3000000
```

Fresh names are mandatory. Output goes to ignored `paper/local-results/`;
restoration and statistical selection are checked before reporting. Failed or
partial runs retain evidence and cannot produce a successful timing table.
