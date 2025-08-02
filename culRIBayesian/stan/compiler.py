# culRIBayesian/stan/compiler.py

from pathlib import Path
import os
import warnings
from cmdstanpy import CmdStanModel
from typing import Union, Optional

_MODEL_CACHE = {}

class StanCompiler:
    """
    Compile and cache Stan models via CmdStanPy.
    """

    def __init__(
        self,
        cmdstan_path: Optional[str] = None,
        stan_models_dir: Optional[Union[str, Path]] = None,
    ):
        # where CmdStan is installed
        if cmdstan_path:
            os.environ["CMDSTAN"] = os.path.expanduser(cmdstan_path)
        # where your .stan files live
        if stan_models_dir:
            self.stan_models_dir = Path(stan_models_dir).expanduser().resolve()
        else:
            # default to a stan_models folder next to this file
            self.stan_models_dir = Path(__file__).parent.parent / "stan_models"

        if not self.stan_models_dir.exists():
            raise FileNotFoundError(f"Stan models directory not found: {self.stan_dir}")

    def get_model(self, stan_file: Union[str, Path]) -> CmdStanModel:
        """
        Return a CmdStanModel for the given .stan file, compiling if necessary.
        `stan_file` may be just the base name (no “.stan”) or a full path.
        """
        # allow passing in base names
        path = Path(stan_file)
        if path.suffix != ".stan":
            path = self.stan_models_dir / f"{stan_file}.stan"

        path = path.expanduser().resolve()
        if path not in _MODEL_CACHE:
            if not path.exists():
                raise FileNotFoundError(f"Stan file not found: {path}")
            _MODEL_CACHE[path] = CmdStanModel(stan_file=str(path))
        return _MODEL_CACHE[path]
    
    def resolve_stan_path(self, name: str) -> Path:
        """Return the absolute .stan filepath for a given model name."""
        p = self.stan_models_dir / f"{name}.stan"
        if not p.exists():
            raise FileNotFoundError(f"Stan file not found: {p}")
        return p
