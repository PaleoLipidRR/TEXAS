# TEXAS/stan/compiler.py

import logging
import os
import subprocess
import sys
import unicodedata
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional, Union

from cmdstanpy import CmdStanModel

from ..utils.paths import STAN_MODELS_DIR, STAN_BUILD_DIR, STAN_ARCHIVE_DIR

logger = logging.getLogger(__name__)

# ── ASCII sanitization for build copies ──────────────────────────────────────
# cmdstanpy reads the .stan file with ``open(path, 'r')`` and no explicit
# encoding (see cmdstanpy/model.py), so it decodes with the platform locale
# codec — cp1252 on a default Windows install. Any non-ASCII byte then raises
# ``UnicodeDecodeError``, even when the character only appears in a comment
# (box-drawing banners, Greek symbols, subscripts, degree signs, arrows, ...).
# To make compilation independent of the reader's locale we copy an ASCII-only
# version of each model into the build dir. The *source* file keeps its original
# Unicode; only the disposable build copy is transliterated.

# Greek letters -> spelled-out names (common in stats/model comments).
_GREEK_ASCII = {}
for _cp in range(0x0391, 0x03CA):  # capital Alpha .. small omega
    _ch = chr(_cp)
    try:
        _name = unicodedata.name(_ch)
    except ValueError:
        continue
    if "GREEK SMALL LETTER" in _name:
        _GREEK_ASCII[_ch] = _name.rsplit(" ", 1)[-1].lower()
    elif "GREEK CAPITAL LETTER" in _name:
        _GREEK_ASCII[_ch] = _name.rsplit(" ", 1)[-1].capitalize()
del _cp, _ch, _name

_STAN_ASCII_MAP = {
    # box drawing -> ASCII rules
    "─": "-", "━": "-", "═": "=",
    "│": "|", "┃": "|", "║": "|",
    **{c: "+" for c in "┌┐└┘├┤┬┴┼"
                       "╔╗╚╝╠╣╦╩╬"},
    # dashes / minus
    "‐": "-", "‑": "-", "‒": "-", "–": "-",
    "—": "--", "―": "--", "−": "-",
    # quotes / punctuation
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...", "·": "*", "•": "*", " ": " ",
    # math / relations
    "°": "deg", "±": "+/-", "×": "x", "÷": "/",
    "µ": "mu", "≈": "~=", "≠": "!=", "≤": "<=",
    "≥": ">=", "≡": "==", "∞": "inf", "∝": "prop-to",
    "∑": "sum", "∏": "prod", "∫": "int", "√": "sqrt",
    "∂": "d", "∇": "grad", "∈": "in", "∉": "not-in",
    "∀": "forall", "∃": "exists",
    # arrows
    "←": "<-", "→": "->", "↔": "<->",
    "⇐": "<=", "⇒": "=>", "⇔": "<=>",
    **_GREEK_ASCII,
}


def _stan_text_to_ascii(text: str) -> str:
    """Return an ASCII-only rendering of Stan source *text*.

    Known formatting/math symbols are transliterated for readability;
    sub/superscripts and accented letters are reduced via NFKD decomposition
    (e.g. ``T₀`` -> ``T0``); anything still non-ASCII becomes ``?``. Pure
    ASCII input is returned unchanged.
    """
    mapped = "".join(_STAN_ASCII_MAP.get(ch, ch) for ch in text)
    decomposed = unicodedata.normalize("NFKD", mapped)
    return decomposed.encode("ascii", "replace").decode("ascii")


def _copy_stan_ascii(src: Path, dest: Path) -> None:
    """Copy *src* to *dest*, sanitizing to ASCII so any locale can read it.

    Line endings are preserved. For already-ASCII sources this writes
    byte-identical content, so it is a drop-in replacement for a plain copy.
    """
    raw = src.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")  # never fails; last-resort readability
    ascii_text = _stan_text_to_ascii(text)
    dest.write_bytes(ascii_text.encode("ascii"))
    if any(ord(c) > 127 for c in text):
        logger.debug(
            "Stan source %s contains non-ASCII characters; wrote an "
            "ASCII-sanitized build copy so cmdstanpy can read it under any "
            "locale (e.g. cp1252 on Windows).",
            src.name,
        )

# Substrings (case-insensitive) of PATH entries that ship a MinGW g++ known to
# break CmdStan linking on Windows: they are picked up ahead of RTools and their
# newer libstdc++ ABI clashes with CmdStan's RTools-built static libs, producing
# "undefined reference to std::istream::seekg(std::fpos<int>)" link errors.
_CONFLICTING_TOOLCHAIN_HINTS = ("strawberry",)


@contextmanager
def _windows_compile_path():
    """Make CmdStan's RTools toolchain win on PATH for the duration of a compile.

    cmdstanpy adds RTools to PATH, but another MinGW earlier on PATH (e.g.
    Strawberry Perl's g++) can still be chosen by ``mingw32-make``, yielding
    ``undefined reference to std::istream::seekg`` link errors because CmdStan's
    prebuilt libraries were built with RTools' g++. For the duration of the
    compile, prepend the RTools toolchain dirs and drop known-conflicting MinGW
    dirs, then restore the original PATH so the caller's environment is unchanged.

    No-op off Windows or when the RTools toolchain cannot be located (e.g. a
    conda-forge CmdStan, which uses its own compiler and needs no reordering).
    """
    if sys.platform != "win32":
        yield
        return

    try:
        from cmdstanpy.utils import cxx_toolchain_path

        rtools_dirs = [d for d in cxx_toolchain_path() if d and os.path.isdir(d)]
    except Exception:  # noqa: BLE001 — best-effort; never block a compile
        rtools_dirs = []

    if not rtools_dirs:
        yield
        return

    original = os.environ.get("PATH", "")
    entries = original.split(os.pathsep)
    rset = {d.lower() for d in rtools_dirs}
    conflicts = [
        e for e in entries
        if any(h in e.lower() for h in _CONFLICTING_TOOLCHAIN_HINTS)
    ]
    kept = [
        e for e in entries
        if e.lower() not in rset
        and not any(h in e.lower() for h in _CONFLICTING_TOOLCHAIN_HINTS)
    ]
    os.environ["PATH"] = os.pathsep.join(rtools_dirs + kept)
    if conflicts:
        logger.info(
            "Windows: prioritized RTools toolchain over %s for Stan compilation.",
            ", ".join(conflicts),
        )
    try:
        yield
    finally:
        # Undo our reordering, but KEEP any entries added during the block.
        # cmdstanpy puts the CmdStan TBB dll directory on PATH during model
        # construction so the compiled exe can load tbb.dll at run time
        # (STAN_THREADS); dropping it causes 0xC0000135 (DLL not found) when
        # sampling runs the exe. So restore the original PATH with those
        # additions prepended rather than blindly overwriting.
        entry_set = set(entries)
        added = [e for e in os.environ.get("PATH", "").split(os.pathsep)
                 if e not in entry_set]
        os.environ["PATH"] = os.pathsep.join(added + entries)


class StanCompiler:
    """Wraps CmdStanModel with in-memory caching and a writable build directory.

    Stan writes a .hpp intermediate file and a compiled binary into the same
    directory as the .stan source file.  When the source tree lives on a
    bind-mounted volume (devcontainer) and was last written by a different OS
    user, stanc raises "Permission denied" on the .hpp write.

    This class avoids that by copying each .stan file to STAN_BUILD_DIR
    (~/.texas/stan_cache/ by default, always writable) and compiling from
    there.  The source file is used only for reading; build artifacts never
    touch the source tree.

    The build copy is also ASCII-sanitized so cmdstanpy — which reads the
    .stan file with the platform locale codec (cp1252 on Windows) — never
    crashes on non-ASCII characters in comments.  See :func:`_copy_stan_ascii`.
    """

    def __init__(self, model_dir: Optional[Union[str, Path]] = None):
        self.model_dir = Path(model_dir) if model_dir is not None else STAN_MODELS_DIR
        self.build_dir = STAN_BUILD_DIR
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, CmdStanModel] = {}

    # ── Path helpers ────────────────────────────────────────────────────────

    def resolve_stan_path(self, stan_file: Union[str, Path]) -> Path:
        """Return the absolute path to the .stan source file.

        An absolute ``stan_file`` is returned unchanged (``Path.__truediv__``
        discards the left operand), which is how a model outside the search
        directory is addressed explicitly.

        Otherwise the name is looked up in ``model_dir`` and, failing that, in
        ``STAN_ARCHIVE_DIR`` -- the superseded models kept in the repository but
        not shipped in the wheel. That fallback is what keeps the manuscript's
        additive-EIV comparison arm refittable by plain stem
        (``stan_file="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv"``) from
        the SI notebooks and the refit scripts, without any caller having to
        build a path -- and, importantly, without an absolute path leaking into
        the ``stan_model_name`` attr, which is written verbatim from this
        argument and has to stay a bare model name for case-id resolution.

        The fallback is announced rather than silent: resolving here means the
        model is superseded. It is inert for a pip install, where no archive
        directory exists.
        """
        p = Path(stan_file)
        if p.suffix != ".stan":
            p = p.with_suffix(".stan")
        primary = self.model_dir / p
        if primary.exists() or p.is_absolute():
            return primary
        if STAN_ARCHIVE_DIR is not None:
            archived = STAN_ARCHIVE_DIR / p.name
            if archived.exists():
                print(f"📦 '{p.name}' is a superseded model; resolving from "
                      f"{STAN_ARCHIVE_DIR}")
                return archived
        return primary

    def _build_path(self, stan_source: Path) -> Path:
        """Return the path under STAN_BUILD_DIR that we compile from.

        Copies the source file if the build copy is absent or stale. The copy
        is ASCII-sanitized (see :func:`_copy_stan_ascii`) so cmdstanpy's
        locale-encoded file read never fails on non-ASCII comment characters.
        """
        dest = self.build_dir / stan_source.name
        src_mtime = stan_source.stat().st_mtime
        if not dest.exists() or dest.stat().st_mtime < src_mtime:
            _copy_stan_ascii(stan_source, dest)
        return dest

    # ── Public API ──────────────────────────────────────────────────────────

    def get_model(
        self,
        stan_file: Union[str, Path],
        cpp_options: Optional[Dict] = None,
        force: bool = False,
    ) -> CmdStanModel:
        """Return a compiled CmdStanModel, using an in-memory cache.

        Args:
            stan_file: Name of the .stan file (with or without extension).
            cpp_options: Passed to CmdStanModel (e.g. {"STAN_THREADS": True}).
            force: Delete cached binary and recompile from scratch.
        """
        stan_path = self.resolve_stan_path(stan_file)
        # Cache key uses the source path so it's stable across sessions
        opts_str = str(sorted(cpp_options.items()) if cpp_options else "{}")
        cache_key = str(stan_path) + opts_str

        # Resolve the writable build copy
        build_path = self._build_path(stan_path)
        binary_path = build_path.with_suffix("")

        # Auto-detect stale/incompatible binary (e.g. compiled on another OS)
        if not force and binary_path.exists():
            try:
                result = subprocess.run(
                    [str(binary_path), "--version"],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    warnings.warn(
                        f"Stan model '{binary_path.name}' was compiled for a different "
                        "environment (e.g. Docker or another OS) and cannot run here "
                        "(exit code 127). The old binary has been removed and the model "
                        "will be recompiled for your current setup — this is normal when "
                        "switching between Docker and a local install.",
                        RuntimeWarning,
                        stacklevel=3,
                    )
                    binary_path.unlink(missing_ok=True)
                    self.cache.pop(cache_key, None)
            except (OSError, subprocess.TimeoutExpired):
                pass

        # Force recompilation
        if force:
            if cache_key in self.cache:
                print(f"🗑️  Clearing cached model: {stan_path.name}")
                del self.cache[cache_key]
            if binary_path.exists():
                print(f"🗑️  Removing old binary: {binary_path}")
                binary_path.unlink()

        # In-memory cache hit
        if cache_key in self.cache:
            print(f"♻️  Using cached model: {stan_path.name}")
            return self.cache[cache_key]

        # Compile from the writable build copy
        print(f"🔧 Compiling Stan model: {stan_path.name}")
        print(f"   (build dir: {self.build_dir})")
        with _windows_compile_path():
            model = CmdStanModel(stan_file=build_path, cpp_options=cpp_options)
        self.cache[cache_key] = model
        print(f"✅ Compiled: {stan_path.name}")
        return model
