# TEXAS/stan/compiler.py

from pathlib import Path
import os
from cmdstanpy import CmdStanModel, compile_stan_file
from typing import Union, Optional

_MODEL_CACHE = {}

class StanCompiler:
    """
    Compile and cache Stan models via CmdStanPy.

    Use `get_model(stan_file, recompile=True)` to force recompilation.
    """

    def __init__(
        self,
        cmdstan_path: Optional[str] = None,
        stan_models_dir: Optional[Union[str, Path]] = None,
    ):
        if cmdstan_path:
            os.environ["CMDSTAN"] = os.path.expanduser(cmdstan_path)

        self.stan_models_dir = (
            Path(stan_models_dir).expanduser().resolve()
            if stan_models_dir
            else Path(__file__).parent.parent / "stan_models"
        )

        if not self.stan_models_dir.exists():
            raise FileNotFoundError(f"Stan models directory not found: {self.stan_models_dir}")

    def get_model(
        self,
        stan_file: Union[str, Path],
        recompile: bool = False,
        n_jobs: int = 4
    ) -> CmdStanModel:
        """
        Return a compiled CmdStanModel for the given .stan file, compiling if necessary.
        """
        path = Path(stan_file)
        if path.suffix != ".stan":
            path = self.stan_models_dir / f"{stan_file}.stan"
        path = path.expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"Stan file not found: {path}")

        if recompile or path not in _MODEL_CACHE:
            stem = path.stem
            for ext in [".hpp", ".o", ""]:  # "" → executable
                try:
                    p = path.with_suffix(ext)
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass

            print(f"🔧 Compiling Stan model: {path.name}")
            os.environ["MAKEFLAGS"] = f"-j{n_jobs}"
            
            # --- FIX: Add this line ---
            # This tells CmdStan's makefile that the C++ compiler is a 'gcc' type,
            # which is required for TBB (threading) support in Conda environments.
            if 'TBB_CXX_TYPE' not in os.environ:
                os.environ['TBB_CXX_TYPE'] = 'gcc'
            exe_path = compile_stan_file(str(path), force=True)
            model = CmdStanModel(stan_file=str(path), exe_file=exe_path)
            _MODEL_CACHE[path] = model
            print(f"✅ Compiled: {path.name}")

        return _MODEL_CACHE[path]

    def resolve_stan_path(self, name: str) -> Path:
        """Return the absolute .stan filepath for a given model name."""
        p = self.stan_models_dir / f"{name}.stan"
        if not p.exists():
            raise FileNotFoundError(f"Stan file not found: {p}")
        return p
