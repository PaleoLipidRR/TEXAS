# stan/runner.py
from .utils import check_tbb_env
from cmdstanpy import CmdStanModel

def compile_model(stan_file: str) -> CmdStanModel:
    check_tbb_env()
    model = CmdStanModel(stan_file=stan_file)
    return model

def run_model(model: CmdStanModel, data: dict, **kwargs):
    return model.sample(data=data, **kwargs)
