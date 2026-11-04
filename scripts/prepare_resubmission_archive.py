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

# ── Tier 1 (RESUME.md section G): first-party inputs behind every figure ──
# that weren't previously archived anywhere. Added 2026-11 so the Open
# Research promise ("a fresh clone + the two Zenodo records reproduces every
# figure") is actually true. See the README's own provenance table.

# Fig. 12 (SI_code03): Tierney et al. 2022 PNAS PETM data assimilation,
# regridded, + Zhu et al. 2019 Science iCESM1.2 PETM simulations, regridded
# to full depth -- both co-author products. Plus the 2 small Muller et al.
# 2019 plate-model files Fig. 12's paleogeography needs (the rest of that
# model -- rotations for other times, polygon files -- stays a cite+fetch,
# not re-hosted; these two are small enough to ship directly).
EXTERNAL_FILES = [
    REPO / "data/external/ncfiles/Tierney22_PNAS_PETMDA/PETMDA_OCN_annual_regridded.nc",
    REPO / "data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM01x.nc",
    REPO / "data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM03x.nc",
    REPO / "data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM06x.nc",
    REPO / "data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM09x.nc",
    REPO / "data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Muller2019-Young2019-Cao2020_COBs.gpmlz",
    REPO / "data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Muller2019-Young2019-Cao2020_CombinedRotations.rot",
]

# SI_code00 raw inputs (the ingredients behind combined_coretop_culture_mesocosm
# already on the record) + RR-compiled derivatives of published (CC-BY) sources,
# used across SI_code01-04. One provenance row each in the README.
PUBLISHED_DATA_FILES = [
    REPO / "data/spreadsheets/ds01_updated_global_coretop_tex_revised_011226.csv",
    REPO / "data/spreadsheets/culture_mesocosm_combined_rev_092325.xlsx",
    REPO / "data/spreadsheets/published_data/ds07_TasmanSea_paleorecords.xlsx",
    REPO / "data/spreadsheets/published_data/Babila_SST_results_finalized_compiled.xlsx",
    REPO / "data/spreadsheets/published_data/ODP1259_d18O_planktic_Bornemann08_OBrien17compl.xlsx",
    REPO / "data/spreadsheets/published_data/U1482_MgCa_SST.xlsx",
    REPO / "data/spreadsheets/published_data/PhanTEX_GIG_df.csv",
    REPO / "data/spreadsheets/published_data/PhanTEX_v001_modified_032626.csv",
    REPO / "data/spreadsheets/published_data/PhanSST_v001_extendedRR_121025.csv",
]

# Converted to csv at staging time, never shipped as the pickle itself --
# pickles pin a library version (sklearn already warns loading this one
# across a patch release) and "ship csv" is RESUME's own rule for this tier.
PICKLE_FILES = [
    REPO / "data/spreadsheets/ols_tex_thermoT_thisStudy.pkl",
]

PARAM_SENSITIVITY_DIR = REPO / "data/revision1/groupA/param_sensitivity"

# The 5 run manifests + case_ids.json SI_code02a reads directly (Figs. S12,
# S18, S19) -- shipped as their own files here, in addition to being folded
# into the combined MANIFEST.csv below.
REFIT_PROVENANCE_FILES = [
    REFIT_DIR / "manifest.csv",
    REFIT_DIR / "single_predictor_manifest.csv",
    REFIT_DIR / "coretop_maps_t0shift_manifest.csv",
    REFIT_DIR / "coretop_maps_univ_manifest.csv",
    REFIT_DIR / "coretop_maps_eiv_manifest.csv",
    REFIT_DIR / "case_ids.json",
]

# run manifests folded into MANIFEST.csv (source label -> path)
RUN_MANIFESTS = {
    "forward_refit": REFIT_DIR / "manifest.csv",
    "forward_single_predictor": REFIT_DIR / "single_predictor_manifest.csv",
    "coretop_invT_t0shift": REFIT_DIR / "coretop_maps_t0shift_manifest.csv",
    "coretop_invT_univ": REFIT_DIR / "coretop_maps_univ_manifest.csv",
    "coretop_invT_eiv": REFIT_DIR / "coretop_maps_eiv_manifest.csv",
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


def coretop_batch_files() -> list[Path]:
    """The 42 raw per-batch coretop invT files SI_code02 actually globs.

    The 6 compiled files (one concatenated .nc per configuration, built by
    ``compile_coretop`` below) stay in the archive too, for users who just
    want to read a reconstruction without caring how it was batched.
    """
    return [INVT_CACHE / f"{case}.inv.global_coretop_{b}.ud.nc"
            for case in CORETOP_CONFIGS for b in CORETOP_BATCHES]


def sensitivity_files() -> list[Path]:
    """param_sensitivity/ (Figs. S12, S18, S19) + the refit manifests/case
    ids SI_code02a reads directly as provenance -- data/revision1/ in the
    archive."""
    out = sorted(PARAM_SENSITIVITY_DIR.glob("*")) if PARAM_SENSITIVITY_DIR.exists() else []
    return [*out, *REFIT_PROVENANCE_FILES]


def _pickle_to_csv(src: Path, dest: Path) -> None:
    """Convert a pickled object to csv so the archive never ships a pickle.

    Pickles pin a library version -- unpickling ``ols_tex_thermoT_thisStudy.pkl``
    already warns across a scikit-learn patch release -- while csv does not
    rot. Handles the two shapes seen in this repo: a pandas object (dumped
    as-is) and a fitted scikit-learn estimator with ``coef_``/``intercept_``
    (dumped as its fitted parameters, one row).
    """
    # Safe: these pickles are first-party repo artifacts this script's own
    # author produced (sklearn fit results / DataFrames), never third-party
    # or user-supplied input -- this is the one place they get unpickled,
    # specifically to retire the pickle in favor of csv.
    import pickle
    import pandas as pd
    with open(src, "rb") as f:
        obj = pickle.load(f)
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        obj.to_csv(dest, index=isinstance(obj, pd.Series))
        return
    if hasattr(obj, "coef_") and hasattr(obj, "intercept_"):
        import numpy as np
        row = {f"coef_{i}": float(c) for i, c in enumerate(np.atleast_1d(obj.coef_))}
        row["intercept"] = float(np.ravel(obj.intercept_)[0])
        row["model_class"] = type(obj).__name__
        pd.DataFrame([row]).to_csv(dest, index=False)
        return
    raise TypeError(f"{src.name}: don't know how to convert a "
                    f"{type(obj).__name__} to csv -- add a case to _pickle_to_csv")


def build_plan() -> tuple[list[tuple[Path, Path]], list[tuple[str, Path]],
                          list[tuple[Path, Path]], Path]:
    """Return (copies [(src, rel_dest)], compiles [(case, rel_dest)],
    pickle_conversions [(src_pkl, rel_dest_csv)], archive)."""
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
    for f in coretop_batch_files():
        copies.append((f, Path("posteriors/invT/coretop/batches") / f.name))
    for f in DATA_FILES:
        copies.append((f, Path("data") / f.name))
    for f in EXTERNAL_FILES:
        copies.append((f, Path("data/external") / f.name))
    for f in PUBLISHED_DATA_FILES:
        copies.append((f, Path("data/published_data") / f.name))
    for f in sensitivity_files():
        copies.append((f, Path("data/revision1") / f.name))
    pickle_conversions = [(f, Path("data/published_data") / f"{f.stem}.csv")
                          for f in PICKLE_FILES]
    compiles = [(case, Path("posteriors/invT/coretop") / f"{case}.inv.global_coretop.ud.nc")
                for case in CORETOP_CONFIGS]
    return copies, compiles, pickle_conversions, archive


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
    copies, compiles, pickle_conversions, archive = build_plan()

    missing = [str(src) for src, _ in copies if not src.exists()]
    missing += [str(src) for src, _ in pickle_conversions if not src.exists()]
    for path in RUN_MANIFESTS.values():
        if not path.exists():
            missing.append(str(path))
    if missing:
        print("ERROR: missing sources:\n  " + "\n  ".join(missing))
        return 1

    n_paleo = sum(1 for _, d in copies if d.parts[:3] == ("posteriors", "invT", "paleo"))
    n_batches = sum(1 for _, d in copies if d.parts[:3] == ("posteriors", "invT", "coretop")
                    and d.parts[3:4] == ("batches",))
    n_external = sum(1 for _, d in copies if d.parts[:2] == ("data", "external"))
    n_published = (sum(1 for _, d in copies if d.parts[:2] == ("data", "published_data"))
                   + len(pickle_conversions))
    n_sensitivity = sum(1 for _, d in copies if d.parts[:2] == ("data", "revision1"))
    print(f"Archive: {archive}  (package version {version})")
    print(f"  forward posteriors : {len(FWD_CASES)}")
    print(f"  coretop compiles   : {len(compiles)} (from {n_batches} batch files, "
          f"which also ship individually)")
    print(f"  paleo invT files   : {n_paleo}")
    print(f"  data files         : {len(DATA_FILES)}")
    print(f"  external files     : {n_external}  (Fig. 12 model grids + plate model)")
    print(f"  published-data     : {n_published}  (RR-compiled derivatives of CC-BY sources)")
    print(f"  sensitivity/refit  : {n_sensitivity}  (param_sensitivity + refit manifests)")
    print("  + MANIFEST.csv, README.md")
    if not args.apply:
        print("\nDry run. Files that would be staged:")
        for src, rel in copies:
            mb = src.stat().st_size / 1_048_576
            print(f"  {mb:8.1f} MB  {rel}")
        for case, rel in compiles:
            print(f"  (compile)    {rel}")
        for src, rel in pickle_conversions:
            print(f"  (pkl->csv)   {rel}")
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
    for src, rel in pickle_conversions:
        dest = archive / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        _pickle_to_csv(src, dest)
        print(f"  pkl->csv {rel}")

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
    for src, rel in pickle_conversions:
        import pandas as pd
        pd.read_csv(archive / rel)
    print("\nVerified: every .nc opens; forward files carry their case ids; "
          "every converted csv re-reads.")
    total = sum(f.stat().st_size for f in archive.rglob("*") if f.is_file())
    print(f"Archive ready: {archive}  ({total / 1_073_741_824:.2f} GB)")
    print("Next: ZENODO_TOKEN=<token> python scripts/zenodo_upload.py")
    return 0


README_TEMPLATE = """\
# TEXAS: GDGT calibration database and Bayesian posteriors

**Version**: {version} (revised manuscript, accepted)
**Package**: `texas-psm` — https://github.com/PaleoLipidRR/TEXAS
**Documentation and guides**: https://paleolipidrr.github.io/TEXAS/

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
`posteriors/invT/coretop/batches/` additionally ships the 42 raw per-batch
files these are concatenated from (what `notebooks/manuscripts/SI_code02`
itself globs) — the compiled copies above are for anyone who just wants to
read a reconstruction without caring how it was batched.

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

### data/external/ — first-party model/plate-model grids behind Fig. 12

| File | Source | Derivation |
|---|---|---|
| PETMDA_OCN_annual_regridded.nc | Tierney et al. 2022, PNAS (PETM data assimilation) | regridded with `TEXAS.utils.regrid` |
| Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM0{{1,3,6,9}}x.nc | Zhu et al. 2019, Science (iCESM1.2 PETM simulations) | regridded to full depth with `TEXAS.utils.regrid` |
| Muller2019-Young2019-Cao2020_COBs.gpmlz, ..._CombinedRotations.rot | Muller et al. 2019 (EarthByte plate model), CC-BY 4.0 | unmodified; re-hosted here (small) rather than linked, unlike the rest of that plate model |

### data/published_data/ — compiled inputs to the training database

| File | Source | Derivation |
|---|---|---|
| ds01_updated_global_coretop_tex_revised_011226.csv, culture_mesocosm_combined_rev_092325.xlsx | this study | raw SI_code00 inputs behind `combined_coretop_culture_mesocosm_rev20260210.csv` above |
| ds07_TasmanSea_paleorecords.xlsx, Babila_SST_results_finalized_compiled.xlsx, ODP1259_d18O_planktic_Bornemann08_OBrien17compl.xlsx, U1482_MgCa_SST.xlsx, PhanTEX_GIG_df.csv, PhanTEX_v001_modified_032626.csv, PhanSST_v001_extendedRR_121025.csv | compiled by the authors from published (CC-BY) sources | see SI_code01-04 for per-source citations; compiled, not raw |
| ols_tex_thermoT_thisStudy.csv | this study | the fitted TEX86-vs-thermoT linear regression's parameters (`coef_`, `intercept_`); shipped as csv, not the original pickle, since a pickle pins a library version |

### data/revision1/ — sampler-budget sensitivity + refit provenance

`param_sensitivity/` contents (Figs. S12, S18, S19 — MCMC/invT budget grids,
proxy-definition and parameter-comparison tables) plus the 5 run manifests
and `case_ids.json` `notebooks/manuscripts/SI_code02a` reads directly, in
addition to their being folded into `MANIFEST.csv` below.

### MANIFEST.csv

The run log of the revision: one row per Stan run, giving the sampler
budget (warm-up, sampling draws, and M forward draws for reconstructions),
training size, wall-clock time, convergence diagnostics, and the output file
the run produced. `source_manifest` names which of the five run manifests the
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
