"""Reproduce the coefficient-variance and block-covariance GSA estimates."""
from math import e, exp, log, pi, sqrt
from pathlib import Path
import json
import numpy as np


def block_variances(tables, whiten):
    variances = []
    for k, law in enumerate(tables):
        rows = law["rows"]
        a = np.array([x["atom"] for x in rows])
        p = np.array([int(x["numerator"])/int(x["denominator"]) for x in rows])
        if k == 0:  # key generation accepts odd total coefficient sum
            signs = 1 - 2*(a.sum(axis=1) % 2)
            bias = float(signs @ p)
            p = p*(1-signs*bias**127)/(1-bias**128)
        # Conditioning g on a nonzero polynomial changes variances by less
        # than binary64 resolution. A sign change in r,m preserves both scalars.
        cov = (a.T*p) @ a
        variances.append(np.linalg.det(cov)**.25 if whiten else np.trace(cov)/4)
    return variances


def estimate(first, second, affine):
    logxi = log(second/first)/2
    height = log(second)/2 if affine else 0
    for beta in range(40, 1025+affine):
        shape = log(1.01295) if beta == 40 else (
            log(beta/(2*pi*e)) + log(pi*beta)/beta)/(2*(beta-1))
        best = (-float("inf"), None)
        for keep in range(4, 513, 4):
            dim = 512+keep+affine
            if dim < beta:
                continue
            det = keep*log(211) + 512*logxi + height
            margin = (2*beta-dim-1)*shape + det/dim - log(beta*second)/2
            best = max(best, (margin, dim))
        if best[0] >= 0:
            return beta, best[1]
    raise RuntimeError("no qualifying block size")


if __name__ == "__main__":
    data = json.loads((Path(__file__).resolve().parents[1] / "ntru" / "par.json").read_text())
    assert data["n"] == 512 and data["q"] == 211
    for whiten in (False, True):
        v = block_variances(data["tables"], whiten)
        rows = [estimate(v[i], v[j], a) for i,j,a in
                [(0,1,False),(1,0,False),(2,3,True),(3,2,True)]]
        beta = min(x[0] for x in rows)
        print("covariance" if whiten else "coefficient variance", "beta/dim:", rows,
              "min classical / quantum log2-cost:", f"{.292*beta:.3f}", f"{.257*beta:.3f}")
