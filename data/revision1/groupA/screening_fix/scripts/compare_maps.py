"""Compare the T0-shift core-top maps of the two arms: per arm, the inverse skill against the
measured temperature (bias, RMSE, 68% coverage, mean 68% width), and per shared cell the change
in the residual and the interval width."""
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

GH = Path(r"C:\Users\ratta\Documents\GitHub")
ARMS = {"baseline": GH / "TEXAS-baseline", "corrected": GH / "TEXAS-cren3"}
CASES = [("SST", "SST", "tx.GHEB.sst.sri03.G23"), ("SST", "SST", "tx.GHEB.sst.sri03.G23-N1p0"),
         ("thermoT", "t_sf2tc_avg", "tx.GHEB.thm.sri03.G23"),
         ("thermoT", "t_sf2tc_avg", "tx.GHEB.thm.sri03.G23-N1p0")]


def load(root, case, n):
    inv = root / "data/cache/TEXAS_invT_posterior_cache"
    nb = int(np.ceil(n / 250))
    return pd.concat([xr.open_dataset(inv / f"{case}.inv.global_coretop_b{b:02d}.ud.nc")["t_est"].to_pandas().T
                      for b in range(1, nb + 1)], ignore_index=True)


skill, cells = [], []
for tt, col, case in CASES:
    per = {}
    for arm, root in ARMS.items():
        s = pd.read_csv(root / "data/revision1/groupA/manuscript_refit/coretop_maps_sites.csv")
        q = load(root, case, len(s))
        assert len(q) == len(s)
        d = pd.DataFrame({"lat": s.match_lat_04deg.round(3), "lon": s.match_lon_04deg.round(3),
                          "obs": s[col], "p50": q[0.5], "w68": q[0.84] - q[0.16],
                          "inside": (s[col] >= q[0.16]) & (s[col] <= q[0.84])})
        d["res"] = d.p50 - d.obs
        per[arm] = d
        skill.append(dict(case=case, arm=arm, n=len(d), bias=d.res.mean(), rmse=np.sqrt((d.res ** 2).mean()),
                          cov68=d.inside.mean(), mean_w68=d.w68.mean()))
    m = per["baseline"].merge(per["corrected"], on=["lat", "lon"], suffixes=("_a", "_b"))
    same_obs = np.isclose(m.obs_a, m.obs_b)
    cells.append(dict(case=case, shared=len(m), same_measured_T=int(same_obs.sum()),
                      only_baseline=len(per["baseline"]) - len(m), only_corrected=len(per["corrected"]) - len(m),
                      dres_rms=float(np.sqrt(((m.res_b - m.res_a)[same_obs] ** 2).mean())),
                      dres_absmax=float((m.res_b - m.res_a)[same_obs].abs().max()),
                      dw68_mean=float((m.w68_b - m.w68_a)[same_obs].mean())))
print(pd.DataFrame(skill).round(3).to_string(index=False))
print()
print(pd.DataFrame(cells).round(3).to_string(index=False))
