# TEXAS/stan/compiler.py

import shutil
import subprocess
import warnings
from pathlib import Path
from typing import Dict, Optional, Union

from cmdstanpy import CmdStanModel

from ..utils.paths import STAN_MODELS_DIR, STAN_BUILD_DIR


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
    """

    def __init__(self, model_dir: Optional[Union[str, Path]] = None):
        self.model_dir = Path(model_dir) if model_dir is not None else STAN_MODELS_DIR
        self.build_dir = STAN_BUILD_DIR
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, CmdStanModel] = {}

    # ── Path helpers ────────────────────────────────────────────────────────

    def resolve_stan_path(self, stan_file: Union[str, Path]) -> Path:
        """Return the absolute path to the .stan source file."""
        p = Path(stan_file)
        if p.suffix != ".stan":
            p = p.with_suffix(".stan")
        return self.model_dir / p

    def _build_path(self, stan_source: Path) -> Path:
        """Return the path under STAN_BUILD_DIR that we compile from.

        Copies the source file if the build copy is absent or stale.
        """
        dest = self.build_dir / stan_source.name
        src_mtime = stan_source.stat().st_mtime
        if not dest.exists() or dest.stat().st_mtime < src_mtime:
            shutil.copy2(stan_source, dest)
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
        model = CmdStanModel(stan_file=build_path, cpp_options=cpp_options)
        self.cache[cache_key] = model
        print(f"✅ Compiled: {stan_path.name}")
        return model
