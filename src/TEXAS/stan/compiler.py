# TEXAS/stan/compiler.py (Corrected with force recompilation)

from pathlib import Path
from typing import Dict, Optional, Union
import os
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
        p = Path(stan_file)
        if p.suffix != '.stan':
            p = p.with_suffix('.stan')
        return self.model_dir / p

    def get_model(
        self,
        stan_file: Union[str, Path],
        cpp_options: Optional[Dict] = None,
        force: bool = False,  # ← ADD: force recompilation parameter
    ) -> CmdStanModel:
        """
        Compile a Stan model, using a cache to avoid re-compilation.
        
        Args:
            stan_file (str): The name of the .stan file in the model directory.
            cpp_options (dict, optional): Options for the Stan compiler.
            force (bool): If True, delete cached model and recompile from scratch.
        """
        stan_path = self.resolve_stan_path(stan_file)
        cache_key = str(stan_path) + str(sorted(cpp_options.items()) if cpp_options else "{}")

        # ← ADD: Force recompilation logic
        if force:
            # Remove from in-memory cache
            if cache_key in self.cache:
                print(f"🗑️  Clearing cached model: {stan_path.name}")
                del self.cache[cache_key]
            
            # Remove compiled binary from disk
            binary_path = stan_path.with_suffix('')  # Remove .stan extension
            if binary_path.exists():
                print(f"🗑️  Removing old binary: {binary_path}")
                os.remove(binary_path)

        # Check cache
        if cache_key in self.cache:
            print(f"♻️  Using cached model: {stan_path.name}")
            return self.cache[cache_key]

        # Compile
        print(f"🔧 Compiling Stan model: {stan_path.name}")
        model = CmdStanModel(stan_file=stan_path, cpp_options=cpp_options)
        self.cache[cache_key] = model
        print(f"✅ Compiled: {stan_path.name}")
        return model