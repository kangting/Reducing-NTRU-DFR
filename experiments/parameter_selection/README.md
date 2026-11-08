# Selected S/D parameter calculations

`refined/` contains the selected single/double-encoding bounds and cost routines.
`baseline/` supplies their arithmetic, ideal-sampler and cost-model dependencies.
The folders have descriptive names; original scientific profile IDs remain intact.
The C byte-contract generator reads `refined/parameters_refined.json`.
The `validation.source_files` field records note filenames from the parameter
analysis archive. The calculations below use the checked-in scripts and inputs.

With the repository's NumPy/SciPy environment activated, run:

```sh
cd experiments/parameter_selection/refined
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

Generated calculation output is ignored by Git. The sharp S bound tracks accepted
f-parity and excludes g=0 before the coordinate union bound. D uses exact rational
joint transfer matrices and correction-aware event inclusion. Strict S inputs can
also be evaluated with `single/deps/correct.exact_certificate(n,q,laws,256)`.

Cost commands need `--all` for the selected IDs. The two `new_double` JSON
files supply the selected moduli, laws and message lengths for cost calculations.
The commands evaluate GSA/MATZOV paths and conditional-event coverage.
For the manuscript estimates, see the [paper reproducibility package](../paper_reproduction/README.md).
Rounded b
is an approximate negative binary logarithm of a bound. Ideal-sampler functional
checks do not replace [the C/oracle checks](../../implementations/c/single_double/README.md).
