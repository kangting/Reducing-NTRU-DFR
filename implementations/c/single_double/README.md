# Selected single/double-encoding family

The sixteen selectors in `profiles.json` preserve the finite 17-atom laws and
exact public byte schedules. `src/profile_ids.h` names the C selectors. G28 is
excluded. Four primary profiles are:

| Selector | Profile | n | q | M/u/K bits | PK/CT bytes |
|---:|---|---:|---:|---|---|
| 1 | S512 | 512 | 251 | 256/256/256 | 511/543 |
| 2 | S1024 | 1024 | 347 | 256/512/256 | 1081/1113 |
| 3 | D512 | 512 | 157 | 128/128/256 | 467/483 |
| 4 | D1024 | 1024 | 251 | 256/256/256 | 1021/1053 |

M is the external message, u the internal residue, and K the shared-key output.
All alternatives, laws and attributed bounds are in the
[parameter table](../../../results/summary/all_profiles_parameters.csv).

## C and Python checks

```sh
python3 implementations/c/single_double/generate.py --check
python3 benchmarks/build.py --suites family --test --check
.venv/bin/python implementations/c/single_double/verify.py --profiles 1 2 3 4 15 --isa portable
.venv/bin/python implementations/c/single_double/tests/verify_extended.py --profile 3 --isa portable
```

The versioned ACWC0/FO port uses fixed public suffix slots, exact CDFs, bounded
public candidate pools and full actual-ciphertext implicit rejection. D uses W
adjacent encoding/correction, full syndrome, first absolute argmax, inversion over
n/2 bits and repeated-half validation. Scalar/AVX2 paths center both NTT inputs.
q541 includes exponent bit9. Parameter IDs inside FO frames are part of the
executable byte contract; ideal-sampler prototypes have a different random tape.

## Mathematical reproduction

The selected finite inputs and bound/cost routines are under
[experiments/parameter_selection](../../../experiments/parameter_selection/README.md).
Recorded geometry, performance and model diagnostics are under
[results/](../../../results/README.md). Parameter/domain IDs inside FO frames are
unchanged by this reorganization.
