"""Environment diagnostic for TEXAS.

``TEXAS.doctor()`` reports whether the current environment can run Stan sampling
and where TEXAS reads/writes its data — the checks a user (or a maintainer on a
fresh machine) would otherwise run by hand: cmdstanpy, the CmdStan toolchain, a
C++ compiler, and the resolved cache/data directories.

It leverages the existing ``find_cmdstan()`` safeguard for CmdStan discovery and
adds the two things that safeguard does not do: a C++ compiler probe (every Stan
model compiles to a native binary, so ``stanc`` alone is not enough) and a
human-readable summary.

Also exposed as the ``texas-doctor`` console script.
"""
from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path

from ..constants import RECOMMENDED_CMDSTAN_VERSION


def _cmdstanpy_version() -> str | None:
    try:
        import cmdstanpy

        return getattr(cmdstanpy, "__version__", "unknown")
    except ImportError:
        return None


def _cmdstan_info() -> dict:
    """Locate CmdStan via the TEXAS safeguard and read its version."""
    info: dict = {
        "found": False,
        "path": None,
        "version": None,
        "recommended": RECOMMENDED_CMDSTAN_VERSION,
    }
    try:
        from .paths import find_cmdstan

        path = find_cmdstan()
    except Exception:
        return info

    info["found"] = True
    info["path"] = str(path)
    # CmdStan writes its version into a `make/local`-adjacent file; the
    # directory name (cmdstan-X.Y.Z) is the most reliable source.
    name = Path(path).name
    if name.startswith("cmdstan-"):
        info["version"] = name.replace("cmdstan-", "")
    return info


def _compiler_info() -> dict:
    """A working C++ compiler + make is required to compile Stan models."""
    tools = ["make"] + (["cl"] if sys.platform == "win32" else ["g++", "clang++"])
    found = {t: shutil.which(t) for t in tools}
    have_make = found.get("make") is not None
    have_cxx = any(found.get(t) for t in tools if t != "make")
    return {"found": have_make and have_cxx, "which": found}


def check_environment() -> dict:
    """Return a structured report of the TEXAS runtime environment.

    Does not print anything — use :func:`doctor` for a formatted report.
    """
    from . import paths

    try:
        import TEXAS

        texas_version = TEXAS.__version__
    except Exception:
        texas_version = "unknown"

    cmdstanpy_version = _cmdstanpy_version()
    cmdstan = _cmdstan_info()
    compiler = _compiler_info()

    report = {
        "texas_version": texas_version,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cmdstanpy": {
            "installed": cmdstanpy_version is not None,
            "version": cmdstanpy_version,
        },
        "cmdstan": cmdstan,
        "compiler": compiler,
        "cache_dir": str(paths.POSTERIOR_CACHE_DIR),
        "data_dir": str(paths.SPREADSHEETS_DIR),
        "sampling_ready": bool(cmdstan["found"] and compiler["found"]),
    }
    return report


def _fmt(ok: bool) -> str:
    return "✓" if ok else "✗"  # ✓ / ✗


def doctor(verbose: bool = True) -> dict:
    """Report the TEXAS environment and whether Stan sampling will work.

    Args:
        verbose: If True (default), print a formatted report to stdout.

    Returns:
        The structured report dict from :func:`check_environment`.
    """
    r = check_environment()
    if not verbose:
        return r

    cp = r["cmdstanpy"]
    cs = r["cmdstan"]
    co = r["compiler"]

    lines = [
        "TEXAS environment check",
        "=" * 40,
        f"  TEXAS               {r['texas_version']}",
        f"  Python              {r['python_version']}  ({r['platform']})",
        f"  {_fmt(cp['installed'])} cmdstanpy         "
        f"{cp['version'] or 'not installed (pip install cmdstanpy)'}",
        f"  {_fmt(cs['found'])} CmdStan           "
        + (f"{cs['version'] or '?'}  @ {cs['path']}" if cs["found"] else "not found"),
        f"  {_fmt(co['found'])} C++ compiler      "
        + (
            ", ".join(t for t, p in co["which"].items() if p)
            if co["found"]
            else "no working compiler + make on PATH"
        ),
        "",
        f"  cache dir           {r['cache_dir']}",
        f"  data dir            {r['data_dir']}",
        "=" * 40,
    ]

    if r["sampling_ready"]:
        lines.append("  Stan sampling: READY ✓")
    else:
        lines.append("  Stan sampling: NOT READY ✗")
        if not cs["found"]:
            lines.append(
                "    Install CmdStan:  python -c \"import cmdstanpy; "
                f"cmdstanpy.install_cmdstan(version='{cs['recommended']}')\""
            )
        if not co["found"]:
            lines.append(
                "    Install a compiler:  (Linux) apt install build-essential  |  "
                "(macOS) xcode-select --install  |  (Windows) RTools"
            )
    print("\n".join(lines))
    return r


def _cli_main(argv: list[str] | None = None) -> int:
    """Console-script entry point (``texas-doctor``).

    Returns 0 if the environment is ready for Stan sampling, 1 otherwise.
    """
    report = doctor(verbose=True)
    return 0 if report["sampling_ready"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli_main(sys.argv[1:]))
