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


def _land_path(shp):
    """Natural Earth land polygons as one SVG path in degrees (x = lon, y = -lat)."""
    import shapefile  # pyshp

    parts_out = []
    for shape in shapefile.Reader(str(shp)).shapes():
        idx = list(shape.parts) + [len(shape.points)]
        for a, b in zip(idx[:-1], idx[1:]):
            ring = shape.points[a:b]
            pts, last = [], None
            for lon, lat in ring:
                p = (round(lon, 1), round(-lat, 1))
                if p != last:
                    pts.append(p)
                    last = p
            if len(pts) >= 4:
                parts_out.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
    return "".join(parts_out)


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
    import pandas as pd

    df = pd.read_csv(csv)
    df = df[df["datatype"].isin(TYPES)].reset_index(drop=True)
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
        })

    refs = (df.groupby(["datatype", "reference_name"]).size().reset_index(name="n")
              .sort_values(["datatype", "n"], ascending=[True, False]))
    sources = [{"t": TYPES[r.datatype], "ref": r.reference_name, "n": int(r.n)} for r in refs.itertuples()]

    return {
        "csv": CSV_NAME,
        "posterior": POSTERIOR,
        "n_crtp_posterior": n_crtp,
        "land_source": "Natural Earth 1:110m land (public domain)",
        "land": _land_path(land) if land else "",
        "points": pts,
        "sources": sources,
    }


def main(argv=None):
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
