from pathlib import Path
import numpy as np
import xarray as xr
from cmdstanpy import CmdStanModel

def get_posteriors(data: dict,
                   stan_filename: str,
                   stan_models_dir: Path | str = None
                  ) -> xr.Dataset:
    """
    Compile & sample a CmdStan .stan file, then return the draws
    as an xarray.Dataset with a single 'draw' dimension.
    """
    if stan_models_dir is None:
        stan_models_dir = Path(__file__).parent / "stan_models"
    stan_models_dir = Path(stan_models_dir)

    model = CmdStanModel(stan_file=str(stan_models_dir / stan_filename))
    fit = model.sample(
        data=data,
        chains=4,
        iter_warmup=500,
        iter_sampling=1000,
        seed=42,
        parallel_chains=4,
        show_console=True,
    )

    ds = xr.Dataset()
    for var in fit.stan_variables().keys():
        arr = fit.stan_variable(var)  # shape (n_draws, ...)
        ds[var] = xr.DataArray(arr,
                               dims=("draw",) + arr.shape[1:],
                               name=var)
    return ds


def _ensure_numpy(x):
    if hasattr(x, "values"):
        return x.values
    return np.asarray(x)


def pred_logistic(x: np.ndarray,
                  x0: np.ndarray,
                  k:  np.ndarray,
                  L:  np.ndarray,
                  b:  np.ndarray
                 ) -> np.ndarray:
    x = _ensure_numpy(x)
    x0, k, L, b = map(_ensure_numpy, (x0, k, L, b))
    z = x[:, None] - x0
    return L / (1 + np.exp(-k * z)) + b


def pred_logistic_multivariate(x: np.ndarray,
                               x0: np.ndarray,
                               k:  np.ndarray,
                               L:  np.ndarray,
                               b:  np.ndarray,
                               beta0: np.ndarray,
                               beta1: np.ndarray
                              ) -> np.ndarray:
    x = _ensure_numpy(x)
    x0, k, L, b, beta0, beta1 = map(_ensure_numpy,
                                    (x0, k, L, b, beta0, beta1))
    z = x[:, None] - x0
    base   = L / (1 + np.exp(-k * z)) + b
    linear = beta0 * x[:, None] + beta1
    return base + linear


def inv_logistic(y: np.ndarray,
                 x0: np.ndarray,
                 k:  np.ndarray,
                 L:  np.ndarray,
                 b:  np.ndarray
                ) -> np.ndarray:
    y = _ensure_numpy(y)
    x0, k, L, b = map(_ensure_numpy, (x0, k, L, b))
    arg = L / (y[:, None] - b) - 1
    return x0 - (1.0 / k) * np.log(arg)


def inv_logistic_multivariate(y: np.ndarray,
                              x0: np.ndarray,
                              k:  np.ndarray,
                              L:  np.ndarray,
                              b:  np.ndarray,
                              beta0: np.ndarray,
                              beta1: np.ndarray
                             ) -> np.ndarray:
    y = _ensure_numpy(y)
    x0, k, L, b, beta0, beta1 = map(_ensure_numpy,
                                    (x0, k, L, b, beta0, beta1))
    arg = L / (y[:, None] - b) - 1
    return (y[:, None] - beta1 - b) / (beta0 + arg)


def temperature_ensemble_from_scaledRI(scaledRI: np.ndarray,
                                       posterior_ds: xr.Dataset,
                                       model_name: str = "logistic_free_upper"
                                      ) -> np.ndarray:
    np.random.seed(42)
    draws = posterior_ds.dims["draw"]
    sel   = np.random.choice(draws, size=1000, replace=True)

    if model_name == "logistic_free_upper":
        P = posterior_ds.isel(draw=sel)[["x0","k","L","b"]]
        return inv_logistic(
            y=scaledRI, x0=P["x0"], k=P["k"],
            L=P["L"], b=P["b"]
        )

    elif model_name == "logistic_fixed_upper":
        P = posterior_ds.isel(draw=sel)[["x0","k","b"]]
        L = 1 - P["b"]
        return inv_logistic(
            y=scaledRI, x0=P["x0"], k=P["k"],
            L=L, b=P["b"]
        )

    elif model_name == "logistic_fixed_upper_multivariate":
        P = posterior_ds.isel(draw=sel)[["x0","k","b","beta0","beta1"]]
        L = 1 - P["b"]
        return inv_logistic_multivariate(
            y=scaledRI, x0=P["x0"], k=P["k"],
            L=L, b=P["b"],
            beta0=P["beta0"], beta1=P["beta1"]
        )

    else:
        raise ValueError(f"Unrecognized model_name {model_name!r}")


def scaledRI_ensemble_from_temperature(temperature: np.ndarray,
                                       posterior_ds: xr.Dataset,
                                       model_name: str = "logistic_free_upper"
                                      ) -> np.ndarray:
    np.random.seed(42)
    draws = posterior_ds.dims["draw"]
    sel   = np.random.choice(draws, size=1000, replace=True)

    if model_name == "logistic_free_upper":
        P = posterior_ds.isel(draw=sel)[["x0","k","L","b"]]
        return pred_logistic(
            x=temperature, x0=P["x0"], k=P["k"],
            L=P["L"], b=P["b"]
        )

    elif model_name == "logistic_fixed_upper":
        P = posterior_ds.isel(draw=sel)[["x0","k","b"]]
        L = 1 - P["b"]
        return pred_logistic(
            x=temperature, x0=P["x0"], k=P["k"],
            L=L, b=P["b"]
        )

    elif model_name == "logistic_fixed_upper_multivariate":
        P = posterior_ds.isel(draw=sel)[["x0","k","b","beta0","beta1"]]
        L = 1 - P["b"]
        return pred_logistic_multivariate(
            x=temperature, x0=P["x0"], k=P["k"],
            L=L, b=P["b"],
            beta0=P["beta0"], beta1=P["beta1"]
        )

    else:
        raise ValueError(f"Unrecognized model_name {model_name!r}")
