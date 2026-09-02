#!/usr/bin/env python3
"""Stage the Zenodo data-record deposit for the revised manuscript (v0.3.0).

Replaces ``prepare_review_archive.sh`` (v0.1.8/v0.2.0, initial submission),
which staged the superseded additive posteriors under legacy long names. This
script stages the revised manuscript's refits under their case ids:

    review_archive_v<VERSION>/
        posteriors/forward/    9 forward calibrations (<case>.fwd.nc)
        posteriors/invT/coretop/
                               6 compiled global-coretop reconstructions —
                               batches b01..b07 concatenated in row order
                               (join key: data/coretop_maps_sites.csv)
        posteriors/invT/paleo/ every paleo-site reconstruction behind the
                               revised figures (GHEB + GHPU), plus the two
                               full-draws files behind Fig. 13
        data/                  training database, screened compilation,
                               NO3 uncertainty field, coretop site table
        MANIFEST.csv           per-run warm-up/budget/diagnostics rows from
                               the revision run manifests (the "archive
                               manifest" of SI Text S3.3)
        README.md              usage-first manifest mirroring Appendix C

Dry-run by default: prints the plan and exits. ``--apply`` copies/builds and
verifies (every staged .nc is re-opened; forward files must carry the case id
they are named for). Exits 1 without writing anything if a source is missing.

Then upload with ``scripts/zenodo_upload.py``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FWD_CACHE = REPO / "data/cache/TEXAS_posterior_cache"
INVT_CACHE = REPO / "data/cache/TEXAS_invT_posterior_cache"
REFIT_DIR = REPO / "data/revision1/groupA/manuscript_refit"

# ── What ships ───────────────────────────────────────────────────────────────

FWD_CASES = [
    # default calibration: full multivariate T0-shift (complete archival
    # copies, EIV per-site latents included)
    "tx.GHEB.sst.sri03.G23-N1p0",
    "tx.GHEB.thm.sri03.G23-N1p0",
    # single-predictor T0-shift variants
    "tx.GHEB.sst.sri03.G23",
    "tx.GHEB.thm.sri03.G23",
    "tx.GHEB.sst.sri03.N1p0",
    "tx.GHEB.thm.sri03.N1p0",
    # temperature-only
    "tx.GHPU.sst.sri03.p0",
    "tx.GHPU.thm.sri03.p0",
    # stage-1 culture+mesocosm
    "tx.GCDU.cul.sri03.p0",
]

# global-coretop reconstructions: compiled from batches b01..b07
CORETOP_CONFIGS = [
    "tx.GHEB.sst.sri03.G23",
    "tx.GHEB.sst.sri03.G23-N1p0",
    "tx.GHEB.thm.sri03.G23",
    "tx.GHEB.thm.sri03.G23-N1p0",
    "tx.GHPU.sst.sri03.p0",
    "tx.GHPU.thm.sri03.p0",
]
CORETOP_BATCHES = [f"b{i:02d}" for i in range(1, 8)]
CORETOP_N_SITES = 1513

# full-draws files behind the extreme-RI examples (Fig. 13)
DRAWS_FILES = [
    "draws/tx.GHEB.sst.sri03.G23-N1p0.inv.Co1010.ud_draws.nc",
    "draws/tx.GHEB.sst.sri03.G23-N1p0.inv.ODP1259.ud_draws.nc",
]

DATA_FILES = [
    REPO / "data/spreadsheets/combined_coretop_culture_mesocosm_rev20260210.csv",
    REPO / "data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv",
    REPO / "data/spreadsheets/cmems_no3_uncertainty_field.nc",
    REFIT_DIR / "coretop_maps_sites.csv",
    # NOTE: ocean_prop_ds (ds06_calculated_ocean_properties.nc) is NOT staged
    # here -- it isn't a TEXAS-record file. utils/download.py pins it to the
    # companion GRL paper's own Zenodo record, so it's never uploaded here.
]

# run manifests folded into MANIFEST.csv (source label -> path)
RUN_MANIFESTS = {
    "forward_refit": REFIT_DIR / "manifest.csv",
    "forward_single_predictor": REFIT_DIR / "single_predictor_manifest.csv",
    "coretop_invT_t0shift": REFIT_DIR / "coretop_maps_t0shift_manifest.csv",
    "coretop_invT_univ": REFIT_DIR / "coretop_maps_univ_manifest.csv",
}


def _version() -> str:
    # pyproject.toml, not importlib.metadata: the archive must track the repo,
    # and an editable install's recorded version goes stale between reinstalls.
    import re
    m = re.search(r'^version = "(.+)"', (REPO / "pyproject.toml").read_text(),
                  re.M)
    return m.group(1)


def paleo_invt_files() -> list[Path]:
    """Every case-named paleo-site reconstruction of the revised arms.

    GHEB (T0-shift multivariate) + GHPU (temperature-only) only — the
    superseded additive GHEA reconstructions stay on the v0.2.0 record.
    """
    out = []
    for pat in ("tx.GHEB.*.inv.*.nc", "tx.GHPU.*.inv.*.nc"):
        for f in sorted(INVT_CACHE.glob(pat)):
            if "global_coretop" in f.name:
                continue
            out.append(f)
    return out


def build_plan() -> tuple[list[tuple[Path, Path]], list[tuple[str, Path]], Path]:
    """Return (copies [(src, rel_dest)], compiles [(case, rel_dest)], archive)."""
    archive = REPO / f"review_archive_v{_version()}"
    copies: list[tuple[Path, Path]] = []
    for case in FWD_CASES:
        copies.append((FWD_CACHE / f"{case}.fwd.nc",
                       Path("posteriors/forward") / f"{case}.fwd.nc"))
    for f in paleo_invt_files():
        copies.append((f, Path("posteriors/invT/paleo") / f.name))
    for rel in DRAWS_FILES:
        src = INVT_CACHE / rel
        copies.append((src, Path("posteriors/invT/paleo") / src.name))
    for f in DATA_FILES:
        copies.append((f, Path("data") / f.name))
    compiles = [(case, Path("posteriors/invT/coretop") / f"{case}.inv.global_coretop.ud.nc")
                for case in CORETOP_CONFIGS]
    return copies, compiles, archive


def compile_coretop(case: str, dest: Path) -> None:
    """Concatenate the b01..b07 batch reconstructions in row order."""
    import xarray as xr
    parts = []
    names = []
    for b in CORETOP_BATCHES:
        p = INVT_CACHE / f"{case}.inv.global_coretop_{b}.ud.nc"
        parts.append(xr.open_dataset(p))
        names.append(p.name)
    ds = xr.concat(parts, dim="t_est_dim_0", combine_attrs="drop_conflicts")
    n = ds.sizes["t_est_dim_0"]
    if n != CORETOP_N_SITES:
        sys.exit(f"ERROR: {case} compiled to {n} sites, expected {CORETOP_N_SITES}")
    ds.attrs.update(
        compiled_from=", ".join(names),
        n_sites=n,
        site_order=("row order matches data/coretop_maps_sites.csv "
                    "(column 'row'); batches concatenated in batch order"),
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(dest)
    for p in parts:
        p.close()


def build_manifest(dest: Path) -> int:
    """Fold the revision run manifests into one MANIFEST.csv."""
    import pandas as pd
    frames = []
    for source, path in RUN_MANIFESTS.items():
        df = pd.read_csv(path)
        df.insert(0, "source_manifest", source)
        # strip machine-local absolute paths down to the file name
        if "path" in df.columns:
            df["path"] = df["path"].map(
                lambda p: Path(str(p)).name if pd.notna(p) else p)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True, sort=False)
    out.to_csv(dest, index=False)
    return len(out)


def write_readme(dest: Path, version: str) -> None:
    dest.write_text(README_TEMPLATE.format(version=version), encoding="utf-8")


def verify_forward(path: Path, case: str) -> None:
    import xarray as xr
    from TEXAS.utils.naming import case_from_attrs
    with xr.open_dataset(path) as ds:
        derived = str(case_from_attrs(ds.attrs))
    # spelling-tolerant: N10 in old attrs still parses to the same case
    from TEXAS.utils.naming import swap_no3_token
    if derived not in (case, swap_no3_token(case)):
        sys.exit(f"ERROR: {path.name} carries case id {derived!r}, "
                 f"expected {case!r}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="copy/build the archive (default: dry run)")
    args = ap.parse_args(argv)

    version = _version()
    copies, compiles, archive = build_plan()

    missing = [str(src) for src, _ in copies if not src.exists()]
    for case in CORETOP_CONFIGS:
        for b in CORETOP_BATCHES:
            p = INVT_CACHE / f"{case}.inv.global_coretop_{b}.ud.nc"
            if not p.exists():
                missing.append(str(p))
    for path in RUN_MANIFESTS.values():
        if not path.exists():
            missing.append(str(path))
    if missing:
        print("ERROR: missing sources:\n  " + "\n  ".join(missing))
        return 1

    n_paleo = sum(1 for _, d in copies if d.parts[:3] == ("posteriors", "invT", "paleo"))
    print(f"Archive: {archive}  (package version {version})")
    print(f"  forward posteriors : {len(FWD_CASES)}")
    print(f"  coretop compiles   : {len(compiles)} (from "
          f"{len(CORETOP_CONFIGS) * len(CORETOP_BATCHES)} batch files)")
    print(f"  paleo invT files   : {n_paleo}")
    print(f"  data files         : {len(DATA_FILES)}")
    print("  + MANIFEST.csv, README.md")
    if not args.apply:
        print("\nDry run. Files that would be staged:")
        for src, rel in copies:
            mb = src.stat().st_size / 1_048_576
            print(f"  {mb:8.1f} MB  {rel}")
        for case, rel in compiles:
            print(f"  (compile)    {rel}")
        print("\nRe-run with --apply to build.")
        return 0

    if archive.exists():
        shutil.rmtree(archive)
    for src, rel in copies:
        dest = archive / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"  copied  {rel}")
    for case, rel in compiles:
        compile_coretop(case, archive / rel)
        print(f"  compiled {rel}")

    n_rows = build_manifest(archive / "MANIFEST.csv")
    print(f"  wrote MANIFEST.csv ({n_rows} runs)")
    write_readme(archive / "README.md", version)
    print("  wrote README.md")

    # verification pass
    import xarray as xr
    for case in FWD_CASES:
        verify_forward(archive / "posteriors/forward" / f"{case}.fwd.nc", case)
    for f in sorted(archive.rglob("*.nc")):
        with xr.open_dataset(f):
            pass
    print("\nVerified: every .nc opens; forward files carry their case ids.")
    total = sum(f.stat().st_size for f in archive.rglob("*") if f.is_file())
    print(f"Archive ready: {archive}  ({total / 1_073_741_824:.2f} GB)")
    print("Next: ZENODO_TOKEN=<token> python scripts/zenodo_upload.py")
    return 0


README_TEMPLATE = """\
# TEXAS: GDGT calibration database and Bayesian posteriors

**Version**: {version} (revised manuscript, in review)
**Package**: `texas-psm` — https://github.com/PaleoLipidRR/TEXAS
**Documentation, guides, and interactive tutorial**: https://paleolipidrr.github.io/TEXAS/

This archive contains the GDGT training database and the Bayesian calibration
posteriors and reconstructions of Rattanasriampaipong, Tierney, Elling &
Inglis, *TEXAS: A proxy system model for TEX86 paleothermometry* (revised
manuscript, AGU Paleoceanography and Paleoclimatology, 2026PA005459).

**What changed from v0.2.0.** The revised manuscript replaces the initial
submission's additive multivariate formulation with the **T0-shift
parameterization**: the nonthermal predictors (GDGT-2/GDGT-3 ratio and
[NO3-]) act on the calibration curve's location parameter T0, so predicted
Scaled RI stays inside its physical bounds by construction. Every posterior
here is a refit under that model; the superseded additive posteriors remain
available in version 0.2.0 of this record. Files are now named by **case id**
(see below).

---

## What you need to use TEXAS on your own data ("ingredients")

1. **GDGT measurements** — fractional abundances or integrated peak areas of
   GDGT-0 through GDGT-3 and crenarchaeol; `TEXAS.compute_scaledRI()`
   (default `cren_weight=3`) computes the Scaled Ring Index from them.
2. **A temperature prior** per sample (`prior_mu_t`, `prior_sigma_t`) — e.g.
   an independent proxy estimate or a broad oceanographic prior.
3. **Optional nonthermal predictors** — the GDGT-2/GDGT-3 ratio
   (`gdgt23ratio`, computed from the same measurements) and bottom-water
   [NO3-] in umol/L (`no3`; modern climatology or scenario values; the
   correction switches off above the 1.0 umol/L threshold).

Quickstart (the default calibration ships inside the package — no download
needed):

```python
pip install texas-psm

import TEXAS
ri  = TEXAS.compute_scaledRI(my_gdgt_dataframe)            # 1. index
res = TEXAS.predict_T_from_proxyObs(                        # 2. reconstruct
    proxyObs=ri, prior_mu_t=15.0, prior_sigma_t=10.0,
    gdgt23ratio=my_g23, no3=my_no3)
res["p50"], res["p16"], res["p84"]                          # 3. temperatures
```

Screening (recommended; same 90% chi-square criterion the calibration was
built with):

```python
from TEXAS.data import MahalanobisOutlierDetector
detector = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"],
                                      confidence=0.90)
df["flagged"] = detector.fit_predict(df)
```

## Case id naming

`tx.<compset>.<temperature>.<proxy>.<predictors>` — e.g.
`tx.GHEB.sst.sri03.G23-N1p0` is the default calibration: generalized logistic
(**G**), hierarchical coretop training (**H**), errors-in-variables estimator
(**E**), T0-shift predictor structure (**B**), SST target, Scaled RI with
crenarchaeol counted as 3 rings (`sri03`), GDGT-2/3 ratio plus [NO3-] with
its 1.0 umol/L threshold (`N1p0`, `p` = decimal point). `p0` = no predictors;
compset `GHPU` = temperature-only; `GCDU` = the stage-1 culture+mesocosm fit.

## Contents

### posteriors/forward/ — forward calibrations

| File | Model | Target |
|---|---|---|
| tx.GHEB.sst.sri03.G23-N1p0.fwd.nc | full multivariate T0-shift (**default**) | SST |
| tx.GHEB.thm.sri03.G23-N1p0.fwd.nc | full multivariate T0-shift (**default**) | Thermo-T |
| tx.GHEB.sst.sri03.G23.fwd.nc | G2/3-only T0-shift | SST |
| tx.GHEB.thm.sri03.G23.fwd.nc | G2/3-only T0-shift | Thermo-T |
| tx.GHEB.sst.sri03.N1p0.fwd.nc | NO3-only T0-shift | SST |
| tx.GHEB.thm.sri03.N1p0.fwd.nc | NO3-only T0-shift | Thermo-T |
| tx.GHPU.sst.sri03.p0.fwd.nc | temperature-only | SST |
| tx.GHPU.thm.sri03.p0.fwd.nc | temperature-only | Thermo-T |
| tx.GCDU.cul.sri03.p0.fwd.nc | culture+mesocosm (stage 1) | culture T |

The multivariate files are the **complete archival copies** (EIV per-site
latent variables included, ~78-81 MB). The package wheel bundles a
latent-stripped 0.4 MB copy of the default pair; `TEXAS.download_posteriors()`
fetches any of the above by case id. Per-fit MCMC diagnostics (max R-hat,
bulk ESS, divergences) are stored as attributes inside each file; warm-up
lengths for every run are in `MANIFEST.csv`.

### posteriors/invT/coretop/ — global coretop reconstructions

One compiled file per configuration (1513 sites; batches b01-b07
concatenated). Row order matches `data/coretop_maps_sites.csv`.

### posteriors/invT/paleo/ — paleo-site reconstructions

Every reconstruction shown in the revised manuscript's figures (DSDP 591,
MD98-2152, U1482, U1510, ODP 959, SDB, Co1010, ODP 1259), including the
nitrate-scenario variants (`no3_001`, `no3_01`, `no3_10`, `no3_modern`) and
the two full-draws files behind the extreme-RI examples (Fig. 13).

### data/

| File | Description |
|---|---|
| combined_coretop_culture_mesocosm_rev20260210.csv | master GDGT training database (culture + mesocosm + coretop) |
| ds_gridded_screened_global_compilation_finalized.csv | screened, gridded global coretop compilation (calibration training set) |
| cmems_no3_uncertainty_field.nc | CMEMS [NO3-] uncertainty field used by the EIV calibration |
| coretop_maps_sites.csv | coretop site table; join key for the compiled reconstructions |

Note: `ocean_prop_ds` (`ds06_calculated_ocean_properties.nc`), used for the
`site_lat`/`site_lon` NO3 lookup at inference time, is NOT part of this
archive -- it's hosted on the companion GRL paper's own Zenodo record and
downloaded from there directly (see `utils/download.py`).

### MANIFEST.csv

The run log of the revision: one row per Stan run (117), giving the sampler
budget (warm-up, sampling draws, and M forward draws for reconstructions),
training size, wall-clock time, convergence diagnostics, and the output file
the run produced. `source_manifest` names which of the four run manifests the
row came from. This is the archive manifest referred to in SI Text S3.3, where
warm-up length is recorded for runs whose posteriors predate that attribute.

Two caveats. It logs the **whole revision**, so some rows describe the additive
(`GHEA`) comparison arm whose posteriors are on version 0.2.0 of this record
rather than here. And `max_rhat` / `divergences` are blank for a few early
rows, where those manifests did not record them; for those runs the values are
in the posterior's own attributes.

---

## Citation

Rattanasriampaipong, R., Tierney, J. E., Elling, F. J., & Inglis, G. N.
(2026). TEXAS: A proxy system model for TEX86 paleothermometry (revised
manuscript). Software: 10.5281/zenodo.19671664. Data: 10.5281/zenodo.19666744.
"""


if __name__ == "__main__":
    raise SystemExit(main())
