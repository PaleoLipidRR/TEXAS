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

import os
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


def _cmdstan_diagnosis() -> list[str]:
    """Explain *why* CmdStan was not discovered.

    Covers the common "the directory exists but the toolchain is missing or
    unusable" failures that a bare "not found" message hides: ``CMDSTAN`` set to
    a non-existent path, set to a real directory whose ``bin/stanc`` is missing
    (never built), or a ``stanc`` that exists but is not executable.
    """
    stanc = "stanc.exe" if os.name == "nt" else "stanc"
    notes: list[str] = []

    def _probe(label: str, root: Path) -> None:
        binp = root / "bin" / stanc
        if not root.is_dir():
            notes.append(f"{label} -> '{root}' does not exist.")
        elif not binp.exists():
            notes.append(
                f"{label} -> '{root}' exists but '{binp.relative_to(root)}' is "
                "missing: the CmdStan C++ toolchain was never built there. "
                "Rebuild it (see below) or point CMDSTAN elsewhere."
            )
        elif not os.access(binp, os.X_OK):
            notes.append(
                f"{label} -> '{binp}' exists but is not executable "
                "(check file permissions / that it is not a partial download)."
            )

    env = os.environ.get("CMDSTAN")
    if env:
        _probe("CMDSTAN env var", Path(env))
    return notes


def _cmdstan_info() -> dict:
    """Locate CmdStan via the TEXAS safeguard and read its version."""
    info: dict = {
        "found": False,
        "path": None,
        "version": None,
        "recommended": RECOMMENDED_CMDSTAN_VERSION,
        "env": os.environ.get("CMDSTAN"),
        "notes": [],
    }
    try:
        from .paths import find_cmdstan

        path = find_cmdstan()
    except Exception:
        info["notes"] = _cmdstan_diagnosis()
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
    """A working C++ compiler + make is required to compile Stan models.

    On Windows the Stan toolchain is normally cmdstanpy-managed RTools (mingw
    ``g++`` + ``mingw32-make``) living under ``~/.cmdstan/RTools*``. cmdstanpy
    prepends it to PATH only at compile time, not persistently — so a plain PATH
    scan reports "no compiler" even when models compile fine. Look inside the
    RTools install (and on PATH) so the report matches actual capability. On
    POSIX the system ``g++``/``clang++`` + ``make`` on PATH is authoritative.
    """
    search_dirs: list[Path] = []
    if sys.platform == "win32":
        cmdstan_home = Path(
            os.environ.get("CMDSTAN_HOME", str(Path.home() / ".cmdstan"))
        )
        for rt in sorted(cmdstan_home.glob("RTools*"), reverse=True):
            for sub in ("mingw64/bin", "mingw32/bin", "usr/bin"):
                d = rt / sub
                if d.is_dir():
                    search_dirs.append(d)

    def _find(name: str) -> str | None:
        exe = f"{name}.exe" if sys.platform == "win32" else name
        for d in search_dirs:
            cand = d / exe
            if cand.exists():
                return str(cand)
        return shutil.which(name)

    cxx_names = ["g++", "clang++", "cl"] if sys.platform == "win32" else ["g++", "clang++"]
    make_names = ["mingw32-make", "make", "nmake"] if sys.platform == "win32" else ["make"]

    found = {n: _find(n) for n in cxx_names + make_names}
    have_cxx = any(found.get(n) for n in cxx_names)
    have_make = any(found.get(n) for n in make_names)
    return {"found": have_cxx and have_make, "which": found}


def _toolchain_conflict() -> str | None:
    """On Windows, warn if a non-RTools ``g++`` shadows an installed RTools one.

    Strawberry Perl (or another MinGW) earlier on PATH gets picked up by
    CmdStan's ``make`` ahead of RTools; its newer libstdc++ ABI clashes with
    CmdStan's RTools-built static libs, giving "undefined reference to
    std::istream::seekg" link errors. ``StanCompiler`` reorders PATH per-compile
    to avoid this, but surfacing it here lets a user fix the root cause.
    Returns a message when a conflict is detected, else ``None``.
    """
    if sys.platform != "win32":
        return None
    active = shutil.which("g++")
    if not active or ("rtools" in active.lower() and ".cmdstan" in active.lower()):
        return None  # nothing on PATH, or RTools already wins
    cmdstan_home = Path(os.environ.get("CMDSTAN_HOME", str(Path.home() / ".cmdstan")))
    rtools_gpp: Path | None = None
    for rt in sorted(cmdstan_home.glob("RTools*"), reverse=True):
        for sub in ("mingw64/bin", "mingw32/bin"):
            cand = rt / sub / "g++.exe"
            if cand.exists():
                rtools_gpp = cand
                break
        if rtools_gpp:
            break
    if rtools_gpp is None:
        return None  # no RTools to shadow; _compiler_info handles "no compiler"
    return (
        f"non-RTools g++ first on PATH ({active}) shadows RTools ({rtools_gpp}); "
        "can cause Stan link errors. TEXAS reorders PATH per-compile, but "
        "removing the other MinGW (e.g. Strawberry Perl) from PATH is cleaner."
    )


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
        "toolchain_conflict": _toolchain_conflict(),
        "cache_dir": str(paths.POSTERIOR_CACHE_DIR),
        "data_dir": str(paths.SPREADSHEETS_DIR),
        "sampling_ready": bool(cmdstan["found"] and compiler["found"]),
    }
    return report


def _unicode_ok() -> bool:
    """True if stdout can encode the check/cross glyphs.

    Windows consoles default to cp1252, which cannot encode ``✓``/``✗`` and
    would raise ``UnicodeEncodeError`` on print. Fall back to ASCII markers
    there so ``texas-doctor`` runs in PowerShell, CMD, and Anaconda Prompt.
    """
    enc = getattr(sys.stdout, "encoding", None) or ""
    try:
        "✓✗".encode(enc)
        return True
    except (LookupError, UnicodeEncodeError):
        return False


def _fmt(ok: bool, unicode: bool = True) -> str:
    if unicode:
        return "✓" if ok else "✗"
    return "OK " if ok else "X  "


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
    uni = _unicode_ok()

    lines = [
        "TEXAS environment check",
        "=" * 40,
        f"  TEXAS               {r['texas_version']}",
        f"  Python              {r['python_version']}  ({r['platform']})",
        f"  {_fmt(cp['installed'], uni)} cmdstanpy         "
        f"{cp['version'] or 'not installed (pip install cmdstanpy)'}",
        f"  {_fmt(cs['found'], uni)} CmdStan           "
        + (f"{cs['version'] or '?'}  @ {cs['path']}" if cs["found"] else "not found"),
        f"  {_fmt(co['found'], uni)} C++ compiler      "
        + (
            ", ".join(t for t, p in co["which"].items() if p)
            if co["found"]
            else "no working compiler + make on PATH"
        ),
    ]
    if r.get("toolchain_conflict"):
        lines.append(f"  {_fmt(False, uni)} toolchain warning  {r['toolchain_conflict']}")
    lines += [
        "",
        f"  cache dir           {r['cache_dir']}",
        f"  data dir            {r['data_dir']}",
        "=" * 40,
    ]

    if r["sampling_ready"]:
        lines.append(f"  Stan sampling: READY {_fmt(True, uni)}")
    else:
        lines.append(f"  Stan sampling: NOT READY {_fmt(False, uni)}")
        if not cs["found"]:
            # Surface *why* discovery failed (e.g. CMDSTAN points at a directory
            # whose toolchain was never built) before the generic install hint.
            for note in cs.get("notes", []):
                lines.append(f"    ! {note}")
            lines.append(
                "    Install CmdStan:  TEXAS.install_cmdstan()   "
                "(one call; repairs a broken install too)"
            )
            lines.append(
                f"      -> installs CmdStan {cs['recommended']} to ~/.cmdstan/; "
                "conda users instead: conda install -c conda-forge "
                f"cmdstan={cs['recommended']}"
            )
            lines.append("    Point TEXAS at an existing install:")
            lines.append(
                "      POSIX (bash/zsh):  export "
                f"CMDSTAN=~/.cmdstan/cmdstan-{cs['recommended']}"
            )
            lines.append(
                "      PowerShell:        $env:CMDSTAN="
                f"\"$HOME\\.cmdstan\\cmdstan-{cs['recommended']}\""
            )
        if not co["found"]:
            lines.append(
                "    Install a compiler:  (Linux) apt install build-essential  |  "
                "(macOS) xcode-select --install  |  (Windows) "
                "python -m cmdstanpy.install_cxx_toolchain "
                "or conda-forge cmdstan (pre-built)"
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
