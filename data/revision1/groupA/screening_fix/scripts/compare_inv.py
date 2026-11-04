"""Compare the paleo reconstructions of the two arms, file by file: per sample, the shift of the
posterior median and of the 68% interval width (corrected minus baseline), summarised per run."""
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

GH = Path(r"C:\Users\ratta\Documents\GitHub")
A = GH / "TEXAS-baseline/data/cache/TEXAS_invT_posterior_cache"
B = GH / "TEXAS-cren3/data/cache/TEXAS_invT_posterior_cache"
OUT = Path(r"C:\Users\ratta\AppData\Local\Temp\claude\c--Users-ratta-Documents-GitHub-gdgt-db-workspace"
           r"\3c8c5502-d42c-4b65-a627-51268a3d59fc\scratchpad\inv_compare.csv")

rows = []
for fb in sorted(B.glob("*.nc")):
    if "global_coretop" in fb.name:
        continue
    fa = A / fb.name
    if not fa.exists():
        rows.append(dict(file=fb.name, note="no baseline"))
        continue
    a = xr.open_dataset(fa)["t_est"].to_pandas().T
    b = xr.open_dataset(fb)["t_est"].to_pandas().T
    if a.shape != b.shape:
        rows.append(dict(file=fb.name, note=f"shape {a.shape} vs {b.shape}"))
        continue
    d50 = b[0.5] - a[0.5]
    w = lambda q: q[0.84] - q[0.16]
    dw = w(b) - w(a)
    parts = fb.name.split(".")
    rows.append(dict(model=parts[1], temptype=parts[2], site=parts[6] if len(parts) > 6 else "",
                     scenario=parts[7] if len(parts) > 8 else "", n=len(a),
                     p50_base=a[0.5].mean(), dmed_mean=d50.mean(), dmed_absmax=d50.abs().max(),
                     dmed_rms=float(np.sqrt((d50 ** 2).mean())), dwidth68_mean=dw.mean(), file=fb.name))
df = pd.DataFrame(rows)
df.to_csv(OUT, index=False)
ok = df.dropna(subset=["dmed_mean"])
print(f"{len(ok)} runs compared ({len(df) - len(ok)} not comparable)")
print(ok.groupby("model")[["dmed_mean", "dmed_rms", "dmed_absmax", "dwidth68_mean"]]
      .agg(["mean", "min", "max"]).round(2).to_string())
print("\nlargest per-run mean shifts:")
print(ok.reindex(ok.dmed_mean.abs().sort_values(ascending=False).index)
      [["model", "temptype", "site", "scenario", "n", "p50_base", "dmed_mean", "dmed_absmax", "dwidth68_mean"]]
      .head(10).round(2).to_string(index=False))
