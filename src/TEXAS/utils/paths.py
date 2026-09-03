# TEXAS/utils/paths.py
from __future__ import annotations
import os, subprocess, warnings
from pathlib import Path
from cmdstanpy import set_cmdstan_path, cmdstan_path
from ..constants import RECOMMENDED_CMDSTAN_VERSION

def find_cmdstan(min_version: str = "2.23.0") -> Path:
    """Locate a working CmdStan installation and configure cmdstanpy to use it.

    Accepts any CmdStan version >= min_version (default 2.23.0, when
    reduce_sum was introduced).  For well-known directories the highest
    installed version is preferred so users are not penalised for upgrading.

    Search order:
      1. ``CMDSTAN`` env var — set by conda on activation; also honoured when
         set manually (``export CMDSTAN=/path/to/cmdstan-X.Y.Z``)
      2. ``CONDA_PREFIX/bin/cmdstan`` — conda/mamba env activated interactively
      3. ``sys.prefix/bin/cmdstan`` — active Python env (covers Docker/mamba
         where activation scripts didn't run but PATH was set directly)
      4. ``/opt/cmdstan/``, ``~/.cmdstan/``, ``/usr/local/cmdstan/`` —
         highest cmdstan-* version found across all three directories
      5. Whatever cmdstanpy is already configured to use

    ``set_cmdstan_path()`` is always called so cmdstanpy's internal state stays
    consistent with the returned path, regardless of which branch matched.

    Raises:
        RuntimeError: if no working CmdStan installation is found anywhere.
    """
    import sys
    stanc = "stanc.exe" if os.name == "nt" else "stanc"

    def ok(p: Path) -> bool:
        stanc_path = p / "bin" / stanc
        return p.is_dir() and stanc_path.exists() and os.access(stanc_path, os.X_OK)

    def _use(p: Path) -> Path:
        set_cmdstan_path(str(p))
        return p

    def _ver_tuple(p: Path):
        """Parse (major, minor, patch) from a cmdstan-X.Y.Z directory name."""
        try:
            return tuple(int(x) for x in p.name.replace("cmdstan-", "").split("."))
        except ValueError:
            return (0, 0, 0)

    # 1. CMDSTAN env var — highest priority; conda sets this on `conda activate`
    env_cmdstan = os.environ.get("CMDSTAN")
    if env_cmdstan:
        p = Path(env_cmdstan)
        if ok(p):
            return _use(p)
        warnings.warn(
            f"CMDSTAN env var points to '{env_cmdstan}' but no stanc binary was "
            "found there. Ignoring and searching standard paths.",
            UserWarning, stacklevel=2,
        )

    # 2. Active conda/mamba environment (CONDA_PREFIX is set by both conda and mamba)
    prefix = os.environ.get("CONDA_PREFIX")
    if prefix:
        p = Path(prefix) / "bin" / "cmdstan"
        if ok(p):
            return _use(p)

    # 3. sys.prefix — covers Docker/mamba without activation scripts
    p = Path(sys.prefix) / "bin" / "cmdstan"
    if ok(p):
        return _use(p)

    # 4. Well-known installation directories — pick highest version found
    candidates = []
    for parent in [
        Path("/opt/cmdstan"),
        Path.home() / ".cmdstan",
        Path("/usr/local/cmdstan"),
    ]:
        if parent.is_dir():
            candidates.extend(parent.glob("cmdstan-*"))
    candidates = sorted((c for c in candidates if ok(c)), key=_ver_tuple, reverse=True)
    if candidates:
        return _use(candidates[0])

    # 5. Whatever cmdstanpy is already configured to use
    try:
        p = Path(cmdstan_path())
        if ok(p):
            return _use(p)
    except Exception:
        pass

    set_hint = (
        '$env:CMDSTAN="C:\\path\\to\\cmdstan"   (PowerShell)'
        if os.name == "nt"
        else "export CMDSTAN=/path/to/your/cmdstan   (bash/zsh)"
    )
    raise RuntimeError(
        "No working CmdStan installation found.\n"
        "  Searched : $CMDSTAN, $CONDA_PREFIX/bin/cmdstan, "
        f"{sys.prefix}/bin/cmdstan, "
        "/opt/cmdstan/cmdstan-*, ~/.cmdstan/cmdstan-*, "
        "/usr/local/cmdstan/cmdstan-*, cmdstanpy configured path\n"
        "  Install  : python -c \"import cmdstanpy; "
        f"cmdstanpy.install_cmdstan(version='{RECOMMENDED_CMDSTAN_VERSION}')\"\n"
        f"  Or set   : {set_hint}\n"
        "  Diagnose : texas-doctor  (or TEXAS.doctor())"
    )

def get_repo_root(target_dir_name: str = "TEXAS") -> Path | None:
    cwd = Path.cwd()
    try:
        top = subprocess.check_output(
            ["git","rev-parse","--show-toplevel"], cwd=str(cwd)
        ).decode().strip()
        return Path(top)
    except Exception:
        pass
    for parent in [cwd, *cwd.parents]:
        if parent.name == target_dir_name:
            return parent
        cand = parent/target_dir_name
        if cand.is_dir():
            return cand
    return None

def get_project_root() -> Path:
    """Top-level repo folder (contains .git or pyproject.toml).

    Falls back to ~/.texas/ when the package is pip-installed outside a repo
    (e.g. Google Colab, pip install texas-psm).
    """
    cwd = Path.cwd()
    try:
        top = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=str(cwd)
        ).decode().strip()
        return Path(top)
    except Exception:
        pass
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent
    # Pip-installed (no repo): use ~/.texas/ as the project root for caches
    fallback = Path.home() / ".texas"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback

# PACKAGE_ROOT: always the installed TEXAS/ package directory, regardless of
# whether the package was pip-installed or run from source.
PACKAGE_ROOT = Path(__file__).parent.parent  # utils/ -> TEXAS/
PROJECT_ROOT = get_project_root()
REPO_ROOT = PROJECT_ROOT                      # back-compat alias
STAN_MODELS_DIR = (PACKAGE_ROOT / "stan_models").resolve()

# Superseded Stan models, kept in the repository for reproducibility but not
# shipped in the wheel (`pyproject.toml` globs `stan_models/*.stan`, which is
# non-recursive). Only exists in a source checkout; None for a pip install, in
# which case the resolver's archive fallback is simply inert.
_archive = (PROJECT_ROOT / "archive" / "submission-2026-04" / "stan_models")
STAN_ARCHIVE_DIR = _archive.resolve() if _archive.is_dir() else None
del _archive

# Calibration posteriors that ship inside the wheel, so that a reconstruction
# works on a bare `pip install texas-psm` with no network access. These are the
# full multivariate T0-shift calibrations with the per-site EIV latents dropped
# (81 MB -> 0.4 MB); rebuild with scripts/make_bundled_posteriors.py.
BUNDLED_POSTERIOR_DIR = (PACKAGE_ROOT / "bundled_posteriors").resolve()

# Stan build artifacts (.hpp, binaries) go here — outside the source/bind-mount
# tree so container users (different UID) can always write compilation output.
# Override with TEXAS_STAN_BUILD_DIR env var.
def _resolve_stan_build_dir() -> Path:
    env = os.environ.get("TEXAS_STAN_BUILD_DIR")
    if env:
        return Path(env)
    return Path.home() / ".texas" / "stan_cache"

STAN_BUILD_DIR = _resolve_stan_build_dir()

HOME = Path.home()
try:
    CMDSTAN_DIR = find_cmdstan()
except RuntimeError as _e:
    CMDSTAN_DIR = None
    warnings.warn(
        "CmdStan not found — Stan sampling (forward calibration and inverse "
        "reconstruction) will not be available until CmdStan is installed.\n"
        "  Install : TEXAS.install_cmdstan()   (one call; also repairs a broken "
        "install)\n"
        "  Diagnose: texas-doctor   (or TEXAS.doctor())",
        UserWarning, stacklevel=1,
    )
DOCUMENTS = HOME / "Documents"
ONEDRIVE = Path("/mnt/onedrive") if Path("/mnt/onedrive").exists() else HOME / "OneDrive"

# ── Cache root resolution ────────────────────────────────────────────────────
# Priority:
#   1. TEXAS_CACHE_DIR environment variable
#   2. data/cache/ inside the repo (when running from a git checkout)
#   3. ~/.texas/cache/ (pip-installed / Colab / no repo)

def _resolve_cache_root() -> Path:
    env = os.environ.get("TEXAS_CACHE_DIR")
    if env:
        return Path(env)

    # In a git checkout — keep posteriors inside the repo
    cwd = Path.cwd()
    try:
        top = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=str(cwd),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return Path(top) / "data" / "cache"
    except Exception:
        pass
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent / "data" / "cache"

    # pip-installed / no repo
    user_cache = Path.home() / ".texas" / "cache"

    # Backward-compat: warn once if old pip-install layout exists
    old_cache = Path.home() / ".texas" / "data" / "cache"
    if old_cache.exists() and any(old_cache.iterdir()):
        warnings.warn(
            f"TEXAS cache found at old location {old_cache}. "
            f"Move files to {user_cache} or set TEXAS_CACHE_DIR to suppress this warning.",
            UserWarning, stacklevel=2,
        )

    return user_cache


CACHE_ROOT = _resolve_cache_root()
CACHE_DIR = CACHE_ROOT          # backward-compat alias
POSTERIOR_CACHE_DIR = CACHE_ROOT / "TEXAS_posterior_cache"
INVT_CACHE_DIR      = CACHE_ROOT / "TEXAS_invT_posterior_cache"

# Training data spreadsheets — inside the repo when running from a git checkout,
# otherwise ~/.texas/data/spreadsheets/ (pip-installed / Colab).
# SI notebooks use relative paths rooted at the repo, so git-checkout users get
# the right location automatically.  Colab users should mount Google Drive and
# call set_spreadsheets_dir() or set TEXAS_DATA_DIR.
def _resolve_spreadsheets_dir() -> Path:
    env = os.environ.get("TEXAS_DATA_DIR")
    if env:
        return Path(env) / "spreadsheets"
    # Same logic as cache root: prefer the repo's data/spreadsheets/
    cwd = Path.cwd()
    try:
        top = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=str(cwd),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return Path(top) / "data" / "spreadsheets"
    except Exception:
        pass
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent / "data" / "spreadsheets"
    return Path.home() / ".texas" / "data" / "spreadsheets"

SPREADSHEETS_DIR = _resolve_spreadsheets_dir()


def set_cache_dir(path: "str | Path") -> None:
    """Override TEXAS cache directories at runtime.

    Call this before any posterior I/O.  For a persistent override, set the
    ``TEXAS_CACHE_DIR`` environment variable instead.

    Args:
        path: Root directory for all TEXAS caches.  Two subdirectories will be
              used inside it: ``TEXAS_posterior_cache/`` and
              ``TEXAS_invT_posterior_cache/``.
    """
    import TEXAS.utils.paths as _paths
    root = Path(path)
    _paths.CACHE_ROOT           = root
    _paths.CACHE_DIR            = root
    _paths.POSTERIOR_CACHE_DIR  = root / "TEXAS_posterior_cache"
    _paths.INVT_CACHE_DIR       = root / "TEXAS_invT_posterior_cache"
    # Propagate into io.py module-level defaults (bound at import time)
    try:
        import TEXAS.stan.io as _io
        _io.DEFAULT_FORWARD_DIR = _paths.POSTERIOR_CACHE_DIR
        _io.DEFAULT_INVT_DIR    = _paths.INVT_CACHE_DIR
    except ImportError:
        pass
