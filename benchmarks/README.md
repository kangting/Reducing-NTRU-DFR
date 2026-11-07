# Performance reproduction

Build and measurement tools are here; recorded results are under
[results/](../results/README.md). Comparison adapters are in `adapters/`, the
PMU driver in `include/`, and author BAT/END sources/notices in `vendor/`.

## Recompute recorded data

```sh
python3 benchmarks/analyze.py
```

The standard-library analyzer reads `results/raw/{ntru512,ntru1024,single_double}.json.gz`,
checks complete cohorts, geometry, RNG schedules, PMU endpoints, input/order
coverage and rejection rules, and recomputes medians with 10,000-resample
bootstrap 95% intervals. Output is `results/summary/performance.csv`.

## Build and correctness checks

```sh
python3 benchmarks/build.py --suites all --test --check
python3 benchmarks/build.py --targets p03-ref p15-avx2 q211-ref q373-avx2 --test --check
```

Linux x86-64, GCC and AVX2 support are required for all variants. Core objects
are shared by each library, C test and benchmark. All 51 targets build: 41 proposed
variants and 10 peers. Six peers pass; END512 AVX2 and all END1024 variants have
known shared-key preflight failures through the preserved adapters and receive
no timing rank. Scalar-v3 targets select the wider ISA without the explicit
vector implementation.

After installing the repository Python package, independent oracle examples are:

```sh
.venv/bin/python implementations/c/single_double/verify.py --profiles 1 2 3 4 15 --isa portable
.venv/bin/python implementations/c/single_double/verify.py --profiles 1 2 3 4 15 --isa avx2
.venv/bin/python implementations/c/ntru512/verify.py --library benchmarks/build/q211-ref/libcntru.so --out benchmarks/local-results/q211-oracle.json
.venv/bin/python implementations/c/ntru1024/verify.py --q 373 --library benchmarks/build/q373-avx2/libcntru.so --out benchmarks/local-results/q373-oracle.json
```

## Fresh controlled measurements

Run from the repository root as the ordinary user. Choose an allowed logical
CPU and a frequency supported by the host. The controller requires Linux Intel
`intel_pstate`; sudo is used only for temporary CPU controls and scoped PMU setup.
Global perf permissions stay unchanged. Example on the measured host:

```sh
bash benchmarks/run_controlled.sh single-double NEW_RUN_NAME 4 3000000
bash benchmarks/run_controlled.sh ntru512 ANOTHER_RUN_NAME 4 3000000
bash benchmarks/run_controlled.sh ntru1024 THIRD_RUN_NAME 4 3000000
```

Fresh names are mandatory. Data, controller records and journals go to ignored
`benchmarks/local-results/`; CPU restoration is verified before reporting. New
runs do not overwrite the recorded paper data. The internal legacy cohort names
`family`, `q211`, `levels` remain accepted and are retained in the existing raw
records to preserve their scientific identity.

## Recorded environment and boundaries

Intel Core i9-14900KF; Linux x86-64; GCC 15.2.0;
`-std=gnu11 -O3 -DNDEBUG -fPIC -mtune=generic`, with `-march=x86-64` for REF and
`-march=x86-64-v3` plus vector NTT for AVX2. Latest run: Ubuntu 26.04.1 LTS,
Linux 7.0.0-42-generic. Exact kernels/compiler flags are in each raw dataset.

One thread was pinned to logical CPU 4, SMT sibling 5 offline, Turbo disabled,
performance governor, and 3 GHz minimum/maximum bounds. Other cores/interrupts
were not fully isolated. Settings were restored; bounds do not rule out throttling.
Each of 101 rounds has KG1/KEM32 batches, eight warm keys, 32 warm KEM pairs and
an eight-key/256-ciphertext correctness pool. Target/operation order and offsets
rotate. Migration, involuntary switches, major faults and multiplexed/unscheduled
counter intervals are rejected; voluntary waits remain. Counter-read overhead
is retained without subtraction. Groups need at least 30 accepted batches.

KeyGen includes OS entropy; seeded Encaps excludes only its initial OS draw.
Cycles include on-CPU user/kernel work; off-CPU waits contribute no task cycles.
KeyGen medians are conditional on the filter and do not estimate tails. Wall time
is not converted into CPU cycles. Different message/security models are described
in [the result guide](../results/README.md).
