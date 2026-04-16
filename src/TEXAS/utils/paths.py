# TEXAS/utils/paths.py
from __future__ import annotations
import os, subprocess, warnings
from pathlib import Path
from cmdstanpy import set_cmdstan_path, cmdstan_path

def find_cmdstan(version: str = "2.36.0") -> Path:
    """Locate a working CmdStan installation and configure cmdstanpy to use it.

    Search order:
      1. ``CMDSTAN`` environment variable (auto-set by conda; also honoured when
         set manually, e.g. ``export CMDSTAN=~/.cmdstan/cmdstan-{version}``)
      2. ``/opt/cmdstan/cmdstan-{version}``
      3. ``~/.cmdstan/cmdstan-{version}``   (installed via cmdstanpy.install_cmdstan())
      4. ``/usr/local/cmdstan/cmdstan-{version}``
      5. Whatever cmdstanpy is already configured to use

    ``set_cmdstan_path()`` is always called so cmdstanpy's internal state stays
    consistent with the returned path, regardless of which branch matched.

    Raises:
        RuntimeError: if no working CmdStan installation is found anywhere.
    """
    stanc = "stanc.exe" if os.name == "nt" else "stanc"

    def ok(p: Path) -> bool:
        return (p / "bin" / stanc).exists()

    def _use(p: Path) -> Path:
        set_cmdstan_path(str(p))
        return p

    # 1. CMDSTAN env var — highest priority so conda/Docker/user-set overrides work
    env = os.environ.get("CMDSTAN")
    if env:
        env_path = Path(env)
        if ok(env_path):
            return _use(env_path)
        warnings.warn(
            f"CMDSTAN env var points to '{env}' but no stanc binary was found "
            "there. Ignoring env var and searching standard paths.",
            UserWarning, stacklevel=2,
        )

    # 2–4. Well-known installation directories
    for p in [
        Path("/opt/cmdstan") / f"cmdstan-{version}",
        Path.home() / ".cmdstan" / f"cmdstan-{version}",
        Path("/usr/local/cmdstan") / f"cmdstan-{version}",
    ]:
        if ok(p):
            return _use(p)

    # 5. Whatever cmdstanpy is already configured to use (e.g. a pre-configured
    #    system install or an earlier set_cmdstan_path() call in the same session)
    try:
        fallback = Path(cmdstan_path())
        if ok(fallback):
            return _use(fallback)
    except Exception:
        pass

    raise RuntimeError(
        f"No working CmdStan {version} installation found.\n"
        f"  Searched : $CMDSTAN, /opt/cmdstan/cmdstan-{version}, "
        f"~/.cmdstan/cmdstan-{version}, /usr/local/cmdstan/cmdstan-{version}\n"
        f"  Install  : python -c \"import cmdstanpy; "
        f"cmdstanpy.install_cmdstan(version='{version}')\"\n"
        f"  Or set   : export CMDSTAN=/path/to/cmdstan-{version}"
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

HOME = Path.home()
CMDSTAN_DIR = find_cmdstan("2.36.0")
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
