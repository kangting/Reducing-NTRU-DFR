# Mathematical experiments

## Paper revision calculations

The [version 1.0.0 revision companion](paper_revision/README.md) reproduces
main Table III and Section VI-B, supplementary Table VI, the Appendix C
J-off/correction-off bounds, and Appendix D-C rank checks. It contains its own
inputs, pinned dependency, expected JSON outputs and paper-value comparison.
Use its separate environment:

```sh
cd experiments/paper_revision
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python verify.py --out rerun
```

These are later mathematical calculations. Their citation is separate from the
[original implementation/PMU baseline](https://github.com/kangting/Reducing-NTRU-DFR/tree/b9ac24ea2edfa377b7282ba0d96659bf7e88ce82).
No new BKZ recovery experiment or CPU-cycle measurement is performed by this
companion. Existing performance records remain under `results/` and are analyzed
with `benchmarks/analyze.py`. See the companion README for the paper-to-script map
and immutable references to the historical parameter-selection calculations.

## Original construction and parameter calculations

Install with `python -m pip install -e .`, then run from the repository root.
Use the activated environment's Python for NumPy/SciPy dependencies.

| Command | Calculation |
|---|---|
| `python -m experiments.gauss` | Rounded Gaussian variance and tail curves |
| `python -m experiments.dfr` | Exact q=211 internal average-error upper bound |
| `python -m experiments.match` | Finite-product exponential-moment comparison |
| `python -m experiments.orient` | Noise variance without the alternating sign map |
| `python -m experiments.wrap` | Recovery-error lower bound for that control |
| `python -m experiments.balance` | Equal-variance q=349 full-noise comparison |
| `python -m experiments.cost` | Coefficient/block-covariance GSA costs |
| `python -m experiments.affine --out results/summary/affine_model.json` | Conditional normalized-key affine model |

The original q=211 distribution is the installed `ntru/par.json` package resource.
Exact finite-law bounds use integer/rational arithmetic; Gaussian and lattice-cost
calculations are numerical. A bound exponent is not an empirical failure rate.
These commands recompute selected configurations, not historical searches.

[parameter_selection/](parameter_selection/README.md) contains the revised S/D
calculations. `refined/` is the selected analysis and `baseline/` supplies the
minimal arithmetic/reference dependencies. Performance experiments are separately
organized under [benchmarks/](../benchmarks/README.md).
