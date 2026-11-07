# Mathematical experiments

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
