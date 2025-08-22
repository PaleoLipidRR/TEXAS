# TEXAS/stan/compiler.py (Corrected)

from pathlib import Path
from typing import Dict, Optional, Union
from ..utils.paths import STAN_MODELS_DIR
from cmdstanpy import CmdStanModel
from TEXAS.utils import get_repo_root

class StanCompiler:
    """A simple wrapper for compiling Stan models with caching."""
    def __init__(self, model_dir: Optional[Union[str, Path]] = None):
        if model_dir is None:
            self.model_dir = STAN_MODELS_DIR
        else:
            self.model_dir = Path(model_dir)
        self.cache = {}

    def resolve_stan_path(self, stan_file: Union[str, Path]) -> Path:
        """
        Resolves the full path to a Stan model file, ensuring it has the .stan extension.
        """
        # --- THIS IS THE FIX ---
        p = Path(stan_file)
        if p.suffix != '.stan':
            p = p.with_suffix('.stan')
        return self.model_dir / p
        # --- END FIX ---

    def get_model(
        self,
        stan_file: Union[str, Path],
        cpp_options: Optional[Dict] = None,
    ) -> CmdStanModel:
        """
        Compile a Stan model, using a cache to avoid re-compilation.
        
        Args:
            stan_file (str): The name of the .stan file in the model directory.
            cpp_options (dict, optional): Options for the Stan compiler.
        """
        stan_path = self.resolve_stan_path(stan_file)
        # Create a unique cache key based on filename and options
        cache_key = str(stan_path) + str(sorted(cpp_options.items()) if cpp_options else "{}")

        if cache_key in self.cache:
            return self.cache[cache_key]

        print(f"🔧 Compiling Stan model: {stan_path.name}")
        model = CmdStanModel(stan_file=stan_path, cpp_options=cpp_options)
        self.cache[cache_key] = model
        print(f"✅ Compiled: {stan_path.name}")
        return model