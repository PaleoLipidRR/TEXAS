# TEXAS/utils/paths.py
from __future__ import annotations
import os, subprocess
from pathlib import Path
from cmdstanpy import set_cmdstan_path, cmdstan_path

def find_cmdstan(version: str = "2.36.0") -> Path:
    stanc = "stanc.exe" if os.name == "nt" else "stanc"
    def ok(p: Path) -> bool: return (p / "bin" / stanc).exists()

    env = os.environ.get("CMDSTAN")
    if env and ok(Path(env)):
        return Path(env)

    for p in [Path("/opt/cmdstan")/f"cmdstan-{version}",
              Path.home()/".cmdstan"/f"cmdstan-{version}",
              Path("/usr/local/cmdstan")/f"cmdstan-{version}"]:
        if ok(p):
            set_cmdstan_path(str(p))
            return p

    return Path(cmdstan_path())

def get_repo_root(target_dir_name: str = "TEXAS") -> Path:
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
    raise RuntimeError(f"Could not locate '{target_dir_name}' above {cwd}")

def get_project_root() -> Path:
    """Top-level repo folder (contains .git or pyproject.toml)."""
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
    return get_repo_root("TEXAS").parent

PROJECT_ROOT = get_project_root()          # e.g., /home/micromamba/app
PACKAGE_ROOT  = PROJECT_ROOT / "TEXAS"     # e.g., /home/micromamba/app/TEXAS
REPO_ROOT = PROJECT_ROOT                   # back-compat alias
STAN_MODELS_DIR = (PACKAGE_ROOT / "stan_models").resolve()

HOME = Path.home()
CMDSTAN_DIR = find_cmdstan("2.36.0")
DOCUMENTS = HOME / "Documents"
ONEDRIVE = Path("/mnt/onedrive") if Path("/mnt/onedrive").exists() else HOME / "OneDrive"
