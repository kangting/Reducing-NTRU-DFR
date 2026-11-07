# Tests

From the repository root after `python -m pip install -e .`:

```sh
python -m tests.test_kem
python -m tests.test_affine
python -m unittest discover -s tests -t .
```

`benchmarks/` checks raw-data reaggregation, cohort/geometry/RNG contracts, PMU
broker protocol, fake-sysfs restoration and failed-admission behavior without
sudo or host CPU changes. C functional/oracle tests live with the relevant
implementation; `python3 benchmarks/build.py --suites all --test --check` builds
and runs their C checks. See [benchmark instructions](../benchmarks/README.md)
for independent Python oracles. Passing tests are not a proof of constant time,
rare DFR or full KEM security.
