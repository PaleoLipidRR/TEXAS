# TEXAS/diagnostics.py

import numpy as np
import pandas as pd

def summarize_sampler_diagnostics(fit) -> dict:
    """
    Extract divergent__, treedepth__, E-BFMI, R_hat, and ESS_bulk
    from a CmdStanPy fit and return them as stan_diag_* attrs.
    """
    diag = {}
    # 1) method variables
    mv = fit.method_variables()
    total_draws = mv["divergent__"].size

    # divergent transitions
    n_div = int(np.sum(mv["divergent__"]))
    pct_div = 100 * n_div / total_draws
    diag["stan_diag_n_divergent"] = n_div
    diag["stan_diag_pct_divergent"] = pct_div
    diag["stan_diag_divergent_status"] = "PASS" if pct_div < 1.0 else "FAIL"

    # treedepth
    td = mv["treedepth__"]
    max_td = 10
    n_td = int(np.sum(td >= max_td))
    pct_td = 100 * n_td / total_draws
    diag["stan_diag_n_max_treedepth"] = n_td
    diag["stan_diag_pct_max_treedepth"] = pct_td
    diag["stan_diag_treedepth_status"] = "PASS" if pct_td < 5.0 else "FAIL"

    # E-BFMI
    try:
        bfmi_vals = fit.bfmi if hasattr(fit, "bfmi") else fit.bfmi_
    except Exception:
        bfmi_vals = None
    min_ebfmi = float(np.min(bfmi_vals)) if bfmi_vals is not None else -1.0
    if min_ebfmi == -1.0:
        ebfmi_status = "UNKNOWN"
    else:
        ebfmi_status = "PASS" if min_ebfmi > 0.2 else "FAIL"
    diag["stan_diag_min_ebfmi"] = min_ebfmi
    diag["stan_diag_ebfmi_status"] = ebfmi_status

    # R-hat & ESS
    summary_df = fit.summary()
    max_rhat = float(summary_df["R_hat"].max())
    n_high_rhat = int((summary_df["R_hat"] > 1.01).sum())
    min_ess = float(summary_df["ESS_bulk"].min())
    diag["stan_diag_max_rhat"] = max_rhat
    diag["stan_diag_n_high_rhat"] = n_high_rhat
    diag["stan_diag_rhat_status"] = "PASS" if max_rhat < 1.01 else "FAIL"
    diag["stan_diag_min_ess_bulk"] = min_ess
    diag["stan_diag_ess_status"] = "PASS" if min_ess > 100 else "FAIL"

    # overall
    checks = [
        diag[k]
        for k in [
            "stan_diag_divergent_status",
            "stan_diag_treedepth_status",
            "stan_diag_rhat_status",
            "stan_diag_ess_status",
        ]
        if diag[k] != "UNKNOWN"
    ]
    diag["stan_diag_overall_status"] = "PASS" if all(c == "PASS" for c in checks) else "FAIL"

    return diag


def create_summary_table(datasets: list) -> pd.DataFrame:
    """
    Build a DataFrame summarizing the stan_diag_* attrs from each xarray.Dataset.
    """
    rows = []
    for ds in datasets:
        row = {"model": ds.attrs.get("filename", "unknown")}
        for k, v in ds.attrs.items():
            if k.startswith("stan_diag_"):
                row[k.replace("stan_diag_", "")] = v
        rows.append(row)
    return pd.DataFrame(rows)
