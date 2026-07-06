# TEXAS/constants.py

# CmdStan version TEXAS is developed and tested against. Single source of truth:
# referenced by the CmdStan-not-found warning/error in utils/paths.py, the
# TEXAS.doctor() diagnostic, and the installation docs. Bump here only.
RECOMMENDED_CMDSTAN_VERSION = "2.36.0"

# Optional predictors
OPTIONAL_PREDICTORS = ["gdgt23ratio", "no3"]

# Suffixes for logistic model parameter variants
DEFAULT_SUFFIXES = ["crtp", "culmesocore", "culmeso", "meso", "cul", "downcore"]

# Maps predictor data-variable name → Stan/posterior coefficient name
PREDICTOR_BETA_NAMES = {
    "gdgt23ratio": "beta_G23",
    "no3": "beta_NO3",
}

# Stan direct keys (if used across multiple places)
DIRECT_KEYS = ["proxyObs", "prior_mu_t", "prior_sigma_t",
    "calibration_model_name", "N_cul", "N_meso", "N_crtp", "N",
    "prior_mu_t", "prior_sigma_t", "M"
]