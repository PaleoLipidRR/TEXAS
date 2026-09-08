# TEXAS/constants.py

# CmdStan version TEXAS is developed and tested against. Single source of truth:
# referenced by the CmdStan-not-found warning/error in utils/paths.py, the
# TEXAS.doctor() diagnostic, and the installation docs. Bump here only.
RECOMMENDED_CMDSTAN_VERSION = "2.36.0"

# Default forward calibration, by temperature target. These are the full
# multivariate T0-shift calibrations (Scaled RI0-3, G23 + NO3), the
# specification the manuscript uses for its reconstructions, and they ship
# inside the wheel (see utils/paths.BUNDLED_POSTERIOR_DIR) so a reconstruction
# needs no download. Used when predict_T_from_proxyObs is called without
# fwd_posterior.
DEFAULT_FWD_POSTERIOR = {
    "SST": "tx.GHEB.sst.sri03.G23-N1p0",
    "thermoT": "tx.GHEB.thm.sri03.G23-N1p0",
}

# Thermal-only counterparts, used when predict_T_from_proxyObs is called with a
# proxy and no predictors at all. These are a DIFFERENT calibration, not the
# multivariate one with its corrections switched off: the nonthermal effects are
# present in the coretop data either way, and a univariate fit absorbs them into
# the thermal parameters rather than removing them. They ship in the wheel too.
DEFAULT_FWD_POSTERIOR_UNIVARIATE = {
    "SST": "tx.GHPU.sst.sri03.p0",
    "thermoT": "tx.GHPU.thm.sri03.p0",
}

# Optional (non-thermal) predictors. The two named constants are the single
# source of truth for the key spelling; OPTIONAL_PREDICTORS is the canonical
# order in which they are iterated (data/builder.py, stan/metadata.py). Code
# that looks *up* one predictor uses the name; code that loops over both uses
# the list. Neither spells the string again.
GDGT23RATIO_KEY = "gdgt23ratio"
NO3_KEY = "no3"
OPTIONAL_PREDICTORS = [GDGT23RATIO_KEY, NO3_KEY]

# Suffixes for logistic model parameter variants
DEFAULT_SUFFIXES = ["crtp", "culmesocore", "culmeso", "meso", "cul", "downcore"]

# Maps predictor data-variable name → Stan/posterior coefficient name
PREDICTOR_BETA_NAMES = {
    "gdgt23ratio": "beta_G23",
    "no3": "beta_NO3",
}

# Stan direct keys (if used across multiple places)
# R2_thermal is included here (rather than given its own block in
# extract_and_update_metadata, the way no3_cutoff is) because the direct-keys
# loop already does exactly what provenance requires: it is only in the Stan
# data dict when build_fwd_data(..., R2_thermal=...) was actually called (see
# data/builder.py), so a univariate or non-EIV fit -- which never receives the
# argument -- gets no R2_thermal attr at all rather than an invented 0.0. It
# scales the sigma_proxyObs_crtp prior in the _eiv models (see
# gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift.stan); without it on
# the posterior, nothing shipped with a fitted file records what set that
# prior's scale.
DIRECT_KEYS = ["proxyObs", "prior_mu_t", "prior_sigma_t",
    "calibration_model_name", "N_cul", "N_meso", "N_crtp", "N",
    "prior_mu_t", "prior_sigma_t", "M", "R2_thermal"
]