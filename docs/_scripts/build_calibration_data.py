#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate the calibration-data explorer -> docs/_static/calibration-data.html.

The page plots the global calibration dataset that the bundled TEXAS posteriors
were fitted to: every coretop, culture and mesocosm sample, as a scatter plot of
temperature against Scaled RI (or TEX86) beside a map of the coretop sites. The
colors are the manuscript's data-type colors (``datatype_color_dict`` in the SI
notebooks). The styling and JavaScript live in ``calibration_data_template.html``;
this script fills its data slot.

    python docs/_scripts/build_calibration_data.py
    python docs/_scripts/build_calibration_data.py --csv path/to/ds_gridded_screened_global_compilation_finalized.csv

**What is committed.** ``docs/_static/calibration-data.html`` and
``docs/_static/calibration-data.data.json``. ``.gitignore`` excludes the training
CSVs, so when the CSV is absent (CI, a fresh clone) the page is rebuilt from the
snapshot, and the script never overwrites a good page with an empty one. Get the
CSV with ``TEXAS.download_training_data()``.

**Checks.** The number of coretops must equal ``N_crtp`` recorded in the bundled
default posterior, so the page shows the samples the calibration was actually
fitted to; the script stops if they differ. Counts on the page are computed from
the data, never typed.

The coastlines are Natural Earth 1:110m land (public domain), read from a local
copy (``--land``, or the first ``ne_110m_land.shp`` found in the usual places).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TEMPLATE = HERE / "calibration_data_template.html"
OUT = HERE.parent / "_static" / "calibration-data.html"
SNAPSHOT = HERE.parent / "_static" / "calibration-data.data.json"
# Written by gdgt-db-workspace's analyses/texasdocs/export_calibration_data.py: the original
# studies and "used by" of every sample, and the earlier calibrations' data and lines.
PROVENANCE = HERE.parent / "_static" / "calibration-data.provenance.json"
POSTERIORS = {"sst": "tx.GHEB.sst.sri03.G23-N1p0", "thm": "tx.GHEB.thm.sri03.G23-N1p0"}
# Corrections to the TEXAS file applied on this page only (the CSV and Zenodo record are untouched)
OVERRIDES = {("reference_name", "Elling et al. (2017) Environmnental Microbiology"):
             "Elling et al. (2017) Environmental Microbiology"}
CSV_NAME = "ds_gridded_screened_global_compilation_finalized.csv"
POSTERIOR = "tx.GHEB.sst.sri03.G23-N1p0"
TYPES = {"coretop": "c", "culture": "u", "mesocosm": "m"}


def _find_csv(arg):
    candidates = [Path(arg)] if arg else []
    candidates += [REPO / "data" / "spreadsheets" / CSV_NAME]
    # a worktree under .claude/worktrees/ shares the main checkout's data/
    for parent in REPO.parents:
        candidates.append(parent / "data" / "spreadsheets" / CSV_NAME)
        if (parent / ".git").is_dir():
            break
    try:
        from TEXAS.utils.paths import get_data_dir  # type: ignore
        candidates.append(Path(get_data_dir()) / "spreadsheets" / CSV_NAME)
    except Exception:
        pass
    return next((c for c in candidates if c.is_file()), None)


def _find_land(arg):
    if arg:
        return Path(arg) if Path(arg).is_file() else None
    roots = [Path.home() / ".local" / "share" / "cartopy", Path(sys.prefix), Path.home() / "miniforge3",
             Path.home() / "anaconda3", Path.home() / "miniconda3"]
    for root in roots:
        if root.is_dir():
            hit = next(iter(sorted(root.rglob("ne_110m_land.shp"))), None)
            if hit:
                return hit
    return None


def _land_rings(shp):
    """Natural Earth land polygons as rings of [lon, lat], for the page to project."""
    import shapefile  # pyshp

    rings = []
    for shape in shapefile.Reader(str(shp)).shapes():
        idx = list(shape.parts) + [len(shape.points)]
        for a, b in zip(idx[:-1], idx[1:]):
            pts, last = [], None
            for lon, lat in shape.points[a:b]:
                p = [round(lon, 1), round(lat, 1)]
                if p != last:
                    pts.append(p)
                    last = p
            if len(pts) >= 4:
                rings.append(pts)
    return rings


def _texas_curves(g23):
    """Median and 5-95 % Scaled RI of each default posterior over temperature, at the coretops'
    median GDGT-2/3 with the nitrate term off (NO3 above the cutoff)."""
    import numpy as np
    import xarray as xr
    import TEXAS  # type: ignore

    out = {}
    T = np.arange(-4.0, 50.01, 0.5)
    for key, case in POSTERIORS.items():
        f = Path(TEXAS.__file__).parent / "bundled_posteriors" / f"{case}.fwd.nc"
        with xr.open_dataset(f) as ds:
            d = {v: ds[v].values.reshape(-1) for v in ("t0_crtp", "k_crtp", "b_crtp", "v_crtp", "gamma_G23_crtp")}
        t0 = d["t0_crtp"] + d["gamma_G23_crtp"] * g23
        ri = d["b_crtp"][:, None] + (1 - d["b_crtp"][:, None]) / (
            1 + np.exp(-d["k_crtp"][:, None] * (T[None, :] - t0[:, None]))) ** (1 / d["v_crtp"][:, None])
        q = np.percentile(ri, [5, 50, 95], axis=0)
        out[key] = {"case": case, "T": T.round(2).tolist(), "lo": q[0].round(4).tolist(),
                    "mid": q[1].round(4).tolist(), "hi": q[2].round(4).tolist()}
    return {"g23": round(float(g23), 2), "curves": out}


def _num(v, nd):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else round(f, nd)


def _posterior_n_crtp():
    try:
        from TEXAS.stan.io import load_posterior  # type: ignore
        post = load_posterior(POSTERIOR)
        attrs = getattr(post, "attrs", {}) or {}
        return int(attrs["N_crtp"]) if "N_crtp" in attrs else None
    except Exception:
        try:
            import xarray as xr
            import TEXAS  # type: ignore
            f = Path(TEXAS.__file__).parent / "bundled_posteriors" / f"{POSTERIOR}.fwd.nc"
            with xr.open_dataset(f) as ds:
                return int(ds.attrs["N_crtp"])
        except Exception:
            return None


def build_snapshot(csv, land):
    """Read the CSV (and the coastlines) into the dict the page embeds."""
    import pandas as pd

    df = pd.read_csv(csv)
    for (col, old), new in OVERRIDES.items():
        n = int((df[col] == old).sum())
        if n:
            df.loc[df[col] == old, col] = new
            print(f"override: {col} {old!r} -> {new!r} ({n} rows)")
    df = df[df["datatype"].isin(TYPES)].reset_index(drop=True)
    prov = json.loads(PROVENANCE.read_text()) if PROVENANCE.is_file() else None
    if prov:
        n_c, n_l = int((df.datatype == "coretop").sum()), int((df.datatype != "coretop").sum())
        if len(prov["cells"]) != n_c or len(prov["labs"]) != n_l:
            sys.exit(f"{PROVENANCE.name} has {len(prov['cells'])} cells / {len(prov['labs'])} labs, "
                     f"the CSV {n_c} / {n_l}: re-export it from gdgt-db-workspace")
        it_c, it_l = iter(prov["cells"]), iter(prov["labs"])
        studies_of, used_of = [], []
        for t in df.datatype:
            if t == "coretop":
                c = next(it_c)
                studies_of.append(c["s"])
                used_of.append(c["u"])
            else:
                lab = next(it_l)
                studies_of.append([lab] if lab else [])
                used_of.append("")
        df = df.assign(_s=studies_of, _u=used_of)
    n_crtp = _posterior_n_crtp()
    n_core = int((df["datatype"] == "coretop").sum())
    if n_crtp is not None and n_crtp != n_core:
        sys.exit(f"coretop count {n_core} != N_crtp {n_crtp} in {POSTERIOR}: "
                 f"this CSV is not the data the bundled calibration was fitted to.")

    pts = []
    order = {"coretop": 0, "mesocosm": 1, "culture": 2}
    df = df.assign(_o=df["datatype"].map(order)).sort_values(["_o", "reference_name"], kind="stable")
    for _, r in df.iterrows():
        pts.append({
            "t": TYPES[r["datatype"]],
            "lat": _num(r.get("Latitude"), 3), "lon": _num(r.get("Longitude"), 3),
            "sst": _num(r.get("SST"), 2), "thm": _num(r.get("t_sf2tc_avg"), 2),
            "ri": _num(r.get("scaledRI_cren3"), 4), "tex": _num(r.get("TEX86"), 4),
            "g23": _num(r.get("gdgt23ratio"), 3), "no3": _num(r.get("no3_sf2tc_avg"), 3),
            "ref": str(r.get("reference_name") or ""),
            "org": "" if pd.isna(r.get("organism_commonName")) else str(r.get("organism_commonName")),
            "reg": "" if pd.isna(r.get("regionName")) else str(r.get("regionName")),
            **({"s": r["_s"], "u": r["_u"]} if prov else {}),
        })

    sources = []
    if prov:
        agg = {}
        for p_ in pts:
            for sk in p_["s"]:
                a = agg.setdefault(sk, {"key": sk, "n": 0, "t": set(), "u": set()})
                a["n"] += 1
                a["t"].add(p_["t"])
                a["u"].update(p_["u"])
        for a in agg.values():
            st = prov["studies"].get(a["key"], {})
            sources.append({"key": a["key"], "cite": st.get("cite", a["key"]), "doi": st.get("doi"),
                            "year": st.get("year"), "n": a["n"], "t": "".join(sorted(a["t"], key="cumc".index)),
                            "u": "".join(sorted(a["u"], key="LHB".index))})
        sources.sort(key=lambda x: (-(x["year"] or 0), x["cite"]))

    return {
        "csv": CSV_NAME,
        "posterior": POSTERIOR,
        "n_crtp_posterior": n_crtp,
        "land_source": "Natural Earth 1:110m land (public domain)",
        "land": _land_rings(land) if land else [],
        "points": pts,
        "sources": sources,
        "texas": _texas_curves(df.loc[df.datatype == "coretop", "gdgt23ratio"].median()),
        "legacy": ({k: prov[k] for k in ("schouten", "kim", "bayspar")} if prov else None),
        "studies": (prov["studies"] if prov else {}),
        "provenance": (prov["provenance"] if prov else None),
    }


def main(argv=None):
    """Rebuild the snapshot when the CSV is present, then write the page from it."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", help=f"path to {CSV_NAME}")
    ap.add_argument("--land", help="path to Natural Earth ne_110m_land.shp")
    args = ap.parse_args(argv)

    csv = _find_csv(args.csv)
    if csv is not None:
        land = _find_land(args.land)
        snap = build_snapshot(csv, land)
        if not snap["land"] and SNAPSHOT.is_file():
            snap["land"] = json.loads(SNAPSHOT.read_text())["land"]   # keep committed coastlines
        SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"wrote {SNAPSHOT.relative_to(REPO)} from {csv}")
    elif SNAPSHOT.is_file():
        snap = json.loads(SNAPSHOT.read_text())
        print(f"{CSV_NAME} not found; rebuilding from the committed snapshot")
    else:
        print(f"{CSV_NAME} not found and no snapshot; leaving the page alone")
        return 0

    html = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(snap, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    OUT.write_text(html.replace("/*__DATA__*/null", payload), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
