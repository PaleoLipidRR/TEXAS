# TEXAS Repo — Publication Readiness Plan

> Created: 2026-04-03. Last updated: 2026-04-04.

This document tracks the plan for preparing the TEXAS repo for public release alongside manuscript submission.

---

## Open Questions (answers needed before implementation)

1. **Data archive**: Zenodo/Figshare for raw data, or everything self-contained in repo?
2. **Demo notebooks**: ship with pre-run cell outputs, or cleared (run-it-yourself)?
3. ~~**Cache path backward compat**: keep `data/cache/` as a fallback for existing users, or clean break with migration note?~~ → resolved: repo users keep `data/cache/` unchanged; pip users get `~/.texas/cache/`; old `~/.texas/data/cache/` triggers a deprecation warning.
4. **PyPI push**: credentials available on this machine, or user pushes manually after prep?

---

## 1. Repo Public Structure

### Keep public
- `src/TEXAS/` — full package source (required for pip reproducibility)
- `notebooks/manuscripts/SI_code1/2/3_*.ipynb` — SI reproducibility notebooks
- `data/published/` *(new folder)* — minimum data needed to run SI notebooks + demos
- `docker/`, `streamlit_app/`, `tests/`, `docs/`, config files

### Exclude / keep gitignored
- `data/cache/` — heavy Stan posteriors; provide Zenodo/download instructions instead (already gitignored)
- `data/external/` — already gitignored
- `data/spreadsheets/` — 24 MB, 60+ files; migrate only needed files to `data/published/`
- `figures/`, `outputs/` — already gitignored

### First step
Audit SI_code1/2/3 notebooks to identify which data files they read, move those to `data/published/`, and update notebook paths accordingly.

---

## 2. Demo Notebooks (new)

Create under `notebooks/demos/`:

| Notebook | Content |
|---|---|
| `00_installation.ipynb` | Environment setup, pip/docker verification, CmdStan check |
| `01_forward_calibration.ipynb` | `build_fwd_data()` → `get_posterior()` → `save_posterior()` using published coretop data |
| `02_inverse_reconstruction.ipynb` | `build_invT_inputData()` → `sampler_invT_posterior()` → plot T estimates with uncertainty |

All demos reference only data in `data/published/`.

---

## 3. Cache File Fix ✅ Done (2026-04-04)

~~**Problem:** `src/TEXAS/utils/paths.py` hardcodes cache paths relative to the repo root (`data/cache/TEXAS_posterior_cache/`). This silently breaks for pip-installed users who have no repo checkout.~~

**Implemented in `src/TEXAS/utils/paths.py`:**

- `_resolve_cache_root()` resolves priority: `TEXAS_CACHE_DIR` env var → `{repo}/data/cache/` (git checkout) → `~/.texas/cache/` (pip/Colab)
- `CACHE_ROOT`, `CACHE_DIR` (alias), `POSTERIOR_CACHE_DIR`, `INVT_CACHE_DIR` defined from `CACHE_ROOT`
- `set_cache_dir(path)` exported from top-level `TEXAS` — updates module globals and propagates into `io.DEFAULT_FORWARD_DIR` / `io.DEFAULT_INVT_DIR`
- Old `~/.texas/data/cache/` layout (pre-fix pip installs) triggers a `UserWarning` with migration instructions
- `README.md` updated: corrected cache path, added `TEXAS_CACHE_DIR` / `set_cache_dir` usage block and API table entry

**Still needed (Docker):**
- Extend `run.sh` to prompt for a local cache dir and mount it as `-v /local/path:/root/.texas/cache`

---

## 4. pip Version Update

- Bump `pyproject.toml`: `0.1.2` → `0.2.0` (cache path change is a behavioral breaking change)
- Verify Stan models are bundled correctly as package data
- Test from a clean environment before pushing to PyPI
- Tag the git release

---

## Implementation Sequence

1. Answer the open questions above
2. Audit SI notebooks → identify data files → populate `data/published/`
3. ~~Fix cache paths in `src/TEXAS/utils/paths.py`~~ ✅
4. Update `run.sh` to support cache volume mounting for Docker
5. Write the three demo notebooks
6. Update `.gitignore` to explicitly include `data/published/`
7. Bump version in `pyproject.toml` and push to PyPI
8. Final check: fresh clone → `pip install texas-psm` → run demo notebooks end-to-end
