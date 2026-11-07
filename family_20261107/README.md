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
[parameter table](../paper/data/family-appendix-parameters.csv).

## C and Python checks

```sh
python3 family_20261107/generate.py --check
python3 paper/build.py --suites family --test --check
.venv/bin/python family_20261107/verify.py --profiles 1 2 3 4 15 --isa portable
.venv/bin/python family_20261107/tests/verify_extended.py --profile 3 --isa portable
```

The versioned ACWC0/FO port uses fixed public suffix slots, exact CDFs, bounded
public candidate pools and full actual-ciphertext implicit rejection. D uses W
adjacent encoding/correction, full syndrome, first absolute argmax, inversion over
n/2 bits and repeated-half validation. Scalar/AVX2 paths center both NTT inputs.
q541 includes exponent bit9. Parameter IDs inside FO frames are part of the
executable byte contract; ideal-sampler prototypes have a different random tape.

## Mathematical reproduction

The minimal research modules and finite selected inputs are retained in upstream/.
Keep the refined/final folders side by side. With NumPy/SciPy installed, run from
the refined folder:

```sh
source .venv/bin/activate
cd family_20261107/upstream/refined_family_20261107
python single/selected_refined.py
python single_functional.py
python double/profile_checks.py
python double_audit/exact_bound.py
python double/pair_mgf.py --id D512_M128_W_experimental --q 157 --a 3
python double/pair_mgf.py --id D1024_M256_W_experimental --q 251 --a 5/2
python cost_audit/audit.py single/selected_refined.json --all --out cost_audit/recomputed_single.json
python cost_audit/audit.py single/strict/selected_strict.json --all --out cost_audit/recomputed_strict.json
python cost_audit/audit.py cost_audit/new_double_input.json --all --out cost_audit/recomputed_double.json
python cost_audit/audit.py cost_audit/new_double_q251_input.json --all --out cost_audit/recomputed_double_q251.json
```

selected_refined.py computes the current sharp S bounds by tracking accepted-key
parity and excluding g=0 before the coordinate union bound. exact_bound.py checks
the correction-aware D bound with exact rational arithmetic and displacement
cycle counts. pair_mgf.py uses joint transfer matrices, not output-coordinate
independence. Strict S laws can also be evaluated through
single/deps/correct.exact_certificate(n,q,laws,256).

Cost commands need --all for new IDs. Their GSA/MATZOV paths and conditional-event
coverage are diagnostics, not a complete attack suite or KEM security proof.
Rounded b is an approximate negative binary logarithm of a bound, not actual DFR.
Archived ideal-sampler checks do not replace current C/oracle tests. Search dumps,
unselected branches and audit-only manifests are unnecessary for these commands.
