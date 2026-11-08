# NTRU paper reproducibility package

Version 1.0.1, 2026-11-08. This package reproduces the recovery-cost
estimates, correctness controls, and rank checks for S512-q251, S1024-q347,
D512-q157, and D1024-q251.

The paper cites the implementation and benchmark records at commit
[`b9ac24ea2edfa377b7282ba0d96659bf7e88ce82`](https://github.com/kangting/Reducing-NTRU-DFR/tree/b9ac24ea2edfa377b7282ba0d96659bf7e88ce82).

## Run

From the repository or the extracted archive root:

```sh
cd experiments/paper_reproduction
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python verify.py --out rerun
```

Use Python 3.11 or later with NumPy 2.3.5. The archived check used Python
3.12.14. Once the dependency is installed, the calculations run offline.
`verify.py` regenerates all three JSONs in a temporary directory and
checks the exact fields and floating point results against `expected/`.
It compares the paper's displayed values against `paper_values.json`.
`--out` copies the checked outputs to a new directory and is optional.
The individual calculations can also be run from `reproduction/`:

```sh
python security_audit.py
python rank_check.py --out rank_check.json
python ablation_check.py
```

| Paper location | Calculation in `reproduction/` | Reference output in `expected/` |
| --- | --- | --- |
| Main Table III and §VI-B, including Eq. (18) | `security_audit.py` with `security_inputs.json` and `cost_model.py` | `security_results.json`, `rows[].summary` and `rows[].routes.affine_f` |
| Supplementary Table VI | Same cost calculation | `security_results.json`, `rows[].routes`, using the route IDs in `paper_values.json` |
| Supplementary Appendix C | `ablation_check.py` | `ablation_check.json`, exact rational bounds and their approximate log exponents |
| Supplementary Appendix D-C | `rank_check.py` | `rank_check.json`, modular ranks, rank-loss probabilities, and exhaustive counts |

The cost calculation uses the GSA criterion and the MATZOV constants from
the estimator commit cited in the paper. It minimizes classical work
over feasible dimension and block-size pairs. The reported quantum work
uses the classical optimum, while `Q_min` gives the independent quantum
minimum. These values are model estimates. The event probabilities and
guess conventions are stored separately. The calculations do not measure
lattice recovery success.

The minimum route IDs appear in `rows[].summary.<group>.route`.
For all four profiles the ordinary key and ciphertext minima are
`covariance_g_f` and `covariance_r_m`. For D the factored-message
minimum is `factor_bm_r_cov`. The single-condition minimum is
`affine_r` for S and `affine_g` for D. Table VI reports `C`,
`Q_at_C`, `d`, `beta`, and `coverage.log2` for each listed route.
The first four event probabilities are before removing the rank-zero
exception, as specified in the caption.

The Appendix C script checks the threshold inequalities using integers
and rational numbers. It gives S512's J-off lower-bound exponent
114.401166 and D1024's correction-off upper-bound exponent 95.415335.
The bounds concern internal message recovery. The rank script checks
eight conditional pairs and two deliberate signed rotations per profile.
At n = 8 it enumerates 20,736 pairs for each of q = 3 and q = 157, with
18,432 rank-four and 2,304 rank-zero pairs per modulus. The finite checks
corroborate the algebraic argument in Appendix D-C.

## Parameter selection

The initial local S search used the covariance proxy in four orders
(`covariance_f_g`, `covariance_g_f`, `covariance_r_m`,
`covariance_m_r`) and five single-condition routes
(`affine_f`, `affine_g`, `affine_r`, `even_g`, `even_r`).
The final recorded S and D cost checks also used the four corresponding
coefficient-variance routes. Those checks minimized classical and quantum
work separately and treated the affine-r guesses as supplied.
The paper's recovery diagnostics also include the factored-message,
factored-r, and joint-key routes. See the archived [parameter selection guide](https://github.com/kangting/Reducing-NTRU-DFR/blob/9548e2942cb776b98ae6e7170f16e64937706f51/experiments/parameter_selection/README.md)
and [historical cost calculation](https://github.com/kangting/Reducing-NTRU-DFR/blob/9548e2942cb776b98ae6e7170f16e64937706f51/experiments/parameter_selection/refined/cost_audit/audit.py).

## Existing implementation and cycle results

For the implementation and recorded PMU measurements, start at
[`paper/README.md` at commit `b9ac24e`](https://github.com/kangting/Reducing-NTRU-DFR/blob/b9ac24ea2edfa377b7282ba0d96659bf7e88ce82/paper/README.md).
From that checkout, `python3 paper/analyze.py` processes the archived
records for main Table V and supplementary Table VII.
The family raw data are `paper/data/family-raw.json.gz`. The later
repository layout moves them to `results/raw/single_double.json.gz`
and moves the analyzer to `benchmarks/analyze.py`
([later guide](https://github.com/kangting/Reducing-NTRU-DFR/blob/9548e2942cb776b98ae6e7170f16e64937706f51/benchmarks/README.md)).
Both raw file paths resolve to Git blob
`2c5c7d4fcc523f11e20c2b60cce92a143c25d547` in their respective
commits. The parameter selection guide links the correctness scripts for
Table II.

## Package identification

The archive is named `NTRU_paper_reproduction_1.0.1.zip`. Its entry
point is `experiments/paper_reproduction/README.md`. The manifest lists
the file checksums, and `verification.log` records the verification run.
