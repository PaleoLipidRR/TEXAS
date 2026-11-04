"""Compare forward posteriors fitted to the old (scaledRI-screened) and new (Scaled RI-screened)
training sets: every scalar parameter's median and 90% interval, and the shift in units of the
baseline posterior SD."""
import sys
from pathlib import Path

import numpy as np
import xarray as xr

GH = Path(r"C:\Users\ratta\Documents\GitHub")
A = GH / "TEXAS-baseline/data/cache/TEXAS_posterior_cache"
B = GH / "TEXAS-cren3/data/cache/TEXAS_posterior_cache"
names = sys.argv[1:] or sorted(p.name for p in B.glob("*.fwd.nc"))

for n in names:
    if not (A / n).exists() or not (B / n).exists():
        continue
    a, b = xr.open_dataset(A / n), xr.open_dataset(B / n)
    na, nb = (a.attrs.get(k) for k in ("N_crtp", "N_cul")), (b.attrs.get(k) for k in ("N_crtp", "N_cul"))
    print(f"\n== {n}   N_crtp/N_cul: {tuple(na)} -> {tuple(nb)}   max R-hat {a.attrs.get('stan_diag_max_rhat')} / "
          f"{b.attrs.get('stan_diag_max_rhat')}")
    print(f"   {'parameter':24s} {'old median [5, 95]':>28s} {'new median [5, 95]':>28s} {'shift':>8s} {'shift/SD':>8s}")
    for v in a.data_vars:
        if v not in b or set(a[v].dims) != {"chain", "draw"}:
            continue
        x, y = a[v].values.ravel(), b[v].values.ravel()
        qa, qb = np.percentile(x, [50, 5, 95]), np.percentile(y, [50, 5, 95])
        sd = x.std()
        print(f"   {v:24s} {qa[0]:9.4f} [{qa[1]:8.4f},{qa[2]:8.4f}] {qb[0]:9.4f} [{qb[1]:8.4f},{qb[2]:8.4f}] "
              f"{qb[0] - qa[0]:+8.4f} {(qb[0] - qa[0]) / sd if sd else np.nan:+8.2f}")
