"""One-call CmdStan installer for TEXAS.

``TEXAS.install_cmdstan()`` is an opt-in, TEXAS-aware wrapper around
``cmdstanpy.install_cmdstan()``. It exists because the bare cmdstanpy call has
two sharp edges for our users:

1. It does not know TEXAS's recommended version, nor does it point TEXAS at the
   result or confirm the toolchain afterwards.
2. If a *half-built* ``cmdstan-X.Y.Z`` directory already exists (interrupted
   download, or only the sources unpacked so ``bin/stanc`` was never compiled),
   ``cmdstanpy.install_cmdstan()`` refuses to touch it unless you happen to know
   to pass ``overwrite=True`` — so users get stuck exactly where they started.

This helper detects both situations and self-heals: it no-ops if a working
CmdStan already resolves, it steps aside for conda-managed installs, and it
auto-enables ``overwrite`` when the target directory exists but TEXAS rejects it.
After installing it re-resolves the path and prints ``doctor()`` so success is
never ambiguous.

Nothing here runs automatically — TEXAS never installs CmdStan on import or on
first sample. The user (or the ``texas-install-cmdstan`` console script) must
call it.
"""
from __future__ import annotations

import os
from pathlib import Path

from ..constants import RECOMMENDED_CMDSTAN_VERSION
from .paths import find_cmdstan


def _compiler_present() -> bool:
    """True if a C++ compiler + make are already on PATH (Windows check)."""
    import shutil

    have_make = shutil.which("mingw32-make") or shutil.which("make")
    have_cxx = shutil.which("g++") or shutil.which("cl") or shutil.which("clang++")
    return bool(have_make and have_cxx)


def _existing_target_is_broken(version: str) -> bool:
    """True if ``~/.cmdstan/cmdstan-<version>`` exists but is not a usable install.

    This is the state ``cmdstanpy.install_cmdstan()`` will not overwrite on its
    own — the directory is present so it assumes the job is done, but TEXAS's
    ``find_cmdstan`` rejects it because ``bin/stanc`` is missing/unusable.
    """
    stanc = "stanc.exe" if os.name == "nt" else "stanc"
    target = Path.home() / ".cmdstan" / f"cmdstan-{version}"
    if not target.is_dir():
        return False
    binp = target / "bin" / stanc
    return not (binp.exists() and os.access(binp, os.X_OK))


def install_cmdstan(
    version: str = RECOMMENDED_CMDSTAN_VERSION,
    *,
    overwrite: bool = False,
    verbose: bool = True,
    **kwargs,
) -> Path | None:
    """Install CmdStan and point TEXAS at it (opt-in; never runs automatically).

    A thin, TEXAS-aware wrapper over :func:`cmdstanpy.install_cmdstan`. On
    Windows, cmdstanpy also installs the RTools C++ toolchain as part of this
    call, so no separate compiler step is needed.

    Args:
        version: CmdStan version to install. Defaults to the version TEXAS is
            tested against (:data:`~TEXAS.constants.RECOMMENDED_CMDSTAN_VERSION`).
        overwrite: Force reinstall even if the target directory already exists.
            Auto-enabled when the target exists but is a broken/partial install.
        verbose: Print a summary and the :func:`~TEXAS.doctor` report afterwards.
        **kwargs: Forwarded to :func:`cmdstanpy.install_cmdstan` (e.g. ``cores``,
            ``progress``, ``dir``).

    Returns:
        Path to the resolved CmdStan installation, or ``None`` if the install
        ran but the toolchain still does not resolve (see the printed report).

    Raises:
        ImportError: if cmdstanpy is not installed.
    """
    try:
        import cmdstanpy
    except ImportError as exc:  # pragma: no cover - trivial
        raise ImportError(
            "cmdstanpy is required to install CmdStan. Install it first: "
            "pip install cmdstanpy"
        ) from exc

    def _log(msg: str) -> None:
        if verbose:
            print(msg)

    # 1. Already working? Do nothing — importantly, don't fight a conda/Docker
    #    install by recompiling over it.
    try:
        existing = find_cmdstan()
        if not overwrite:
            _log(f"CmdStan already available at {existing} — nothing to do.")
            _log("  (pass overwrite=True to reinstall anyway.)")
            return existing
    except RuntimeError:
        pass  # not found — proceed to install

    # 2. Warn conda users, who almost never want a from-source install layered on
    #    top of the conda-forge `cmdstan` package.
    if os.environ.get("CONDA_PREFIX") and os.environ.get("CMDSTAN"):
        _log(
            "Note: you are in a conda env with CMDSTAN set. If CmdStan came from "
            "conda-forge, prefer `conda install -c conda-forge cmdstan` over this "
            "helper — installing from source on top of it can conflict."
        )

    # 3. Self-heal the half-built-directory case that blocks cmdstanpy's default.
    if _existing_target_is_broken(version) and not overwrite:
        _log(
            f"Found an incomplete ~/.cmdstan/cmdstan-{version} (no runnable "
            "bin/stanc) — reinstalling over it (overwrite=True)."
        )
        overwrite = True

    import sys

    # On Linux (incl. Google Colab), CmdStan's bundled Intel TBB can fail to
    # build unless the compiler type is pinned — this is why the docs prepend
    # `TBB_CXX_TYPE=gcc` to the manual install. Default it here (only if the user
    # hasn't set it, and only on Linux) so the one-call helper is as robust as the
    # documented manual path. macOS uses clang and needs no hint.
    if sys.platform.startswith("linux") and "TBB_CXX_TYPE" not in os.environ:
        os.environ["TBB_CXX_TYPE"] = "gcc"
        _log("Set TBB_CXX_TYPE=gcc for the CmdStan build (Linux default).")

    # On Windows, `make build` needs the RTools MinGW toolchain (mingw32-make +
    # g++). cmdstanpy installs it as part of install_cmdstan ONLY when
    # compiler=True; without it the build fails with "mingw32-make ... No such
    # file or directory" on a machine that has no compiler. Default it on so the
    # one-call helper is self-sufficient. Linux/macOS ignore this flag.
    if sys.platform == "win32":
        kwargs.setdefault("compiler", True)
        if not _compiler_present():
            _log("No C++ compiler detected — installing the RTools toolchain too "
                 "(compiler=True). This adds a few minutes on the first run.")

    _log(f"Installing CmdStan {version} via cmdstanpy… (this can take a few minutes)")
    cmdstanpy.install_cmdstan(version=version, overwrite=overwrite, **kwargs)

    # 4. Re-resolve and confirm.
    try:
        resolved = find_cmdstan()
    except RuntimeError:
        resolved = None

    if verbose:
        from .doctor import doctor

        doctor()

    return resolved


def _cli_main(argv: list[str] | None = None) -> int:
    """Console-script entry point (``texas-install-cmdstan``).

    Returns 0 if CmdStan resolves after the attempt, 1 otherwise.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="texas-install-cmdstan",
        description="Install CmdStan for TEXAS and verify the Stan toolchain.",
    )
    parser.add_argument(
        "--version",
        default=RECOMMENDED_CMDSTAN_VERSION,
        help=f"CmdStan version to install (default: {RECOMMENDED_CMDSTAN_VERSION}).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Force reinstall even if a CmdStan install already exists.",
    )
    args = parser.parse_args(argv)

    resolved = install_cmdstan(version=args.version, overwrite=args.overwrite)
    return 0 if resolved is not None else 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(_cli_main(sys.argv[1:]))
