# -*- coding: utf-8 -*-
"""Curated content for the interactive call map — see ``build_callmap.py``.

Everything here is hand-written; the call graph itself is extracted from the
source. Two things live in this file:

``PIPELINES``
    The stage-by-stage layout of the forward and inverse workflows. Each entry
    in ``stages[*]["nodes"]`` is a qualified name *without* the ``TEXAS.``
    prefix, e.g. ``"stan.sampler.get_posterior"``. ``dynamic`` lists real call
    edges the AST cannot see (a callable passed as an argument, then invoked);
    they render dashed.

``EXPLAIN``
    Prose shown above the docstring in the detail panel, keyed the same way.
    Only add an entry where you have something to say that the docstring does
    not already say.

The build script fails if any name here no longer exists in the package, so a
rename in ``src/TEXAS`` surfaces as a build error rather than a silent gap.
"""

FORWARD = {
    "id": "forward",
    "title": "Forward calibration",
    "kicker": "temperature -> proxy",
    "blurb": (
        "Stage 1 of the workflow. Screened culture / mesocosm / coretop data are packed into a "
        "Stan data dict, a hierarchical generalized-logistic model is sampled with HMC, and the "
        "posterior draws are annotated and written to a compressed .nc file. The same posterior "
        "then drives pure-Python forward prediction (no Stan) at the bottom of the flow."
    ),
    "stages": [
        {
            "name": "Screen & clean",
            "note": "Mahalanobis outlier removal and array hygiene before anything reaches Stan.",
            "nodes": [
                "data.screening.MahalanobisOutlierDetector.fit",
                "data.screening.MahalanobisOutlierDetector.detect_outliers_manual",
                "data.screening.MahalanobisOutlierDetector.transform",
                "data.screening.MahalanobisOutlierDetector.detect_outliers",
                "data.screening.MahalanobisOutlierDetector.fit_transform",
                "data.screening.MahalanobisOutlierDetector._compute_distances",
                "data.screening.MahalanobisOutlierDetector._resolve_features",
                "data.filter.filter_stan_compatible",
                "data.filter.ensure_numpy",
                "data.ocean_lookup.lookup_no3_from_woa",
            ],
        },
        {
            "name": "Build the Stan data dict",
            "note": "One entry point. It validates shapes, names keys proxyObs_*, sets use_* flags, "
                    "and can derive the NO3 cutoff and culmeso hyperpriors on its own.",
            "nodes": [
                "data.builder.build_fwd_data",
                "data.builder._extract_culmeso_hyperpriors",
                "data.builder._auto_no3_cutoff",
                "data.builder._fit_gen_logi_to_get_residuals",
                "models.multivariate.find_optimal_no3_threshold",
                "data.builder.build_fwd_data._range_str",
            ],
        },
        {
            "name": "Sample",
            "note": "get_posterior() is the functional face of StanSampler; predictor flags and CPU "
                    "settings are inferred rather than hand-set.",
            "nodes": [
                "stan.sampler.get_posterior",
                "stan.sampler.auto_detect_predictors",
                "stan.sampler.find_index_with_priority",
                "stan.sampler._ensure_lenN_vector",
                "utils.system_info.suggest_stan_sampling_kwargs",
                "stan.sampler.StanSampler.__init__",
                "stan.sampler.StanSampler.sample",
                "stan.sampler.StanSampler.sample_from_model",
                "stan.sampler.StanSampler._to_xarray",
            ],
        },
        {
            "name": "Compile",
            "note": "Reached from StanSampler.sample. Caches binaries in memory and on disk; "
                    "carries the Windows toolchain and ASCII workarounds.",
            "nodes": [
                "stan.compiler.StanCompiler.__init__",
                "stan.compiler.StanCompiler.get_model",
                "stan.compiler.StanCompiler.resolve_stan_path",
                "stan.compiler.StanCompiler._build_path",
                "stan.compiler._copy_stan_ascii",
                "stan.compiler._stan_text_to_ascii",
                "stan.compiler._windows_compile_path",
                "utils.paths.find_cmdstan",
            ],
        },
        {
            "name": "Annotate & diagnose",
            "note": "Everything downstream reads these attrs, so this stage is what makes a .nc file "
                    "self-describing.",
            "nodes": [
                "stan.metadata.extract_and_update_metadata",
                "stan.metadata._summarize_array",
                "stan.metadata.extract_priors_from_stan",
                "stan.metadata.extract_param_bounds_from_stan",
                "diagnostics.summarize_sampler_diagnostics",
                "diagnostics.create_summary_table",
            ],
        },
        {
            "name": "Persist",
            "note": "Filename encodes model, temptype, predictor flags and proxy_name.",
            "nodes": [
                "stan.io.save_posterior",
                "stan.io._sanitize_attrs_for_netcdf",
                "stan.io.load_posterior",
                "stan.io.list_posteriors",
                "utils.download.download_posteriors",
            ],
        },
        {
            "name": "Forward prediction",
            "note": "Pure Python, no Stan. Draws self-consistent parameter sets from the posterior "
                    "and evaluates the calibration curve.",
            "nodes": [
                "predict.predict_proxy_from_T",
                "ensemble.generator.generate_ensemble_auto",
                "ensemble.detection.detect_model_and_params",
                "ensemble.detection.choose_suffix",
                "ensemble.detection.available_suffixes",
                "ensemble.generator.generate_ensemble",
                "models.logistics.generalized_logistic_fixed_upper",
                "models.multivariate.generalized_logistic_fixed_upper_multivariate",
                "models.multivariate._broadcast_predictor",
                "predict.compute_scaledRI",
            ],
        },
    ],
    # edges the AST cannot see (callable passed as a value, then invoked)
    "dynamic": [
        ("ensemble.generator.generate_ensemble",
         "models.logistics.generalized_logistic_fixed_upper",
         "model_func is resolved by detect_model_and_params and called dynamically"),
        ("ensemble.generator.generate_ensemble",
         "models.multivariate.generalized_logistic_fixed_upper_multivariate",
         "model_func is resolved by detect_model_and_params and called dynamically"),
    ],
}

INVERSE = {
    "id": "inverse",
    "title": "Inverse prediction",
    "kicker": "proxy -> temperature",
    "blurb": (
        "Stage 2. Observed proxy values are inverted to temperature by a second Stan model that "
        "marginalises over M parameter sets drawn from the forward posterior, so calibration "
        "uncertainty propagates into the reconstruction. The forward posterior is an input here, "
        "not something this path fits."
    ),
    "stages": [
        {
            "name": "Entry point",
            "note": "The user-facing call. Accepts a posterior name or a loaded Dataset, and can "
                    "look up modern NO3 from coordinates.",
            "nodes": [
                "predict.predict_T_from_proxyObs",
                "predict.compute_scaledRI",
                "data.ocean_lookup.lookup_no3_from_woa",
                "stan.io.load_posterior",
            ],
        },
        {
            "name": "Wrapper",
            "note": "Thin layer that runs the model and turns draws into percentile summaries.",
            "nodes": [
                "stan.invT.predict_temperature_from_proxyObs",
            ],
        },
        {
            "name": "Bridge forward -> inverse",
            "note": "This is where calibration uncertainty enters: M parameter sets are sampled "
                    "from the forward posterior and handed to Stan as data.",
            "nodes": [
                "data.builder.build_invT_inputData",
                "data.filter.ensure_numpy",
            ],
        },
        {
            "name": "Choose the model & patch the data",
            "note": "Model file depends on direct/ensemble sampling, which predictors are active, "
                    "and the temperature constraint scheme.",
            "nodes": [
                "stan.invT._select_invT_stan_file",
                "stan.utils.patch_optional_predictors",
                "utils.system_info.simple_memory_check",
                "utils.system_info.get_system_info",
                "utils.system_info.suggest_stan_sampling_kwargs",
            ],
        },
        {
            "name": "Sample",
            "note": "The orchestrator for the whole inverse run.",
            "nodes": [
                "stan.invT.get_invT_posterior",
                "stan.sampler.sampler_invT_posterior",
                "stan.sampler.StanSampler.sample_from_model",
                "stan.sampler.StanSampler.sample",
                "stan.compiler.StanCompiler.get_model",
            ],
        },
        {
            "name": "Summarize",
            "note": "t_est has a different shape in ensemble vs marginal models; the quantile "
                    "helper handles both.",
            "nodes": [
                "stan.invT.get_invT_post_quantiles",
                "stan.invT._attach_invT_metadata",
                "stan.metadata.extract_priors_from_stan",
                "models.logistics.inverse_generalized_logistic_fixed_upper",
                "models.multivariate.inverse_generalized_logistic_fixed_upper_multivariate",
            ],
        },
        {
            "name": "Persist",
            "note": "Three separate artefacts: the summary posterior, the raw draws, and a tidy "
                    "results table.",
            "nodes": [
                "stan.io._save_invT_posterior",
                "stan.io._save_invT_draws",
                "stan.io._save_invT_results",
                "stan.io._generate_filename_base",
                "stan.io._slug",
                "stan.io._sanitize_attrs_for_netcdf",
                "stan.io.save_invT_posterior",
            ],
        },
    ],
    "dynamic": [],
}

# ---- hand-written explainers (short, specific; docstrings fill the rest) -----
EXPLAIN = {
    "predict.predict_proxy_from_T":
        "The forward half of the public API. Give it temperatures and a forward posterior and it "
        "returns proxy percentiles. It does no sampling of its own: it loads the posterior if you "
        "passed a name, then hands everything to generate_ensemble_auto. If the posterior was fitted "
        "with the multivariate model you must also supply gdgt23ratio / no3 arrays, one value per "
        "temperature point.",
    "predict.predict_T_from_proxyObs":
        "The inverse half of the public API, and the function most paleo users actually call. It "
        "accepts proxy observations plus a temperature prior (mu, sigma), optionally resolves modern "
        "NO3 from site coordinates against a WOA23-derived dataset, and delegates to "
        "predict_temperature_from_proxyObs. prior_sigma_t should be diffuse (~10 degC) when you have "
        "little prior information.",
    "predict.compute_scaledRI":
        "Converts raw GDGT fractional abundances into the scaled Ring Index used as the proxy "
        "throughout. Kept variable-name-agnostic so it is not tied to one spreadsheet's column names.",
    "data.builder.build_fwd_data":
        "The single recommended way to build a forward Stan data dict. It enforces proxyObs_* key "
        "naming, validates array shapes, auto-sets use_gdgt23ratio / use_no3 from whether the arrays "
        "are present and non-NaN, and auto-computes no3_cutoff when you omit it. For two-stage "
        "priorApprox models, pass culmeso_posterior= and it extracts the t0/k/b/v hyperpriors for you. "
        "It always emits sd_gdgt23ratio_crtp, sd_no3_crtp and sd_proxyObs (defaulting to zeros / 0.03) "
        "so the EIV model can be run without changing the call.",
    "data.builder._extract_culmeso_hyperpriors":
        "Pulls raw mean and standard deviation for t0, k, b and v out of a culture+mesocosm posterior. "
        "These become the informative priors in the second-stage priorApprox coretop model, which is "
        "how the hierarchy is approximated without refitting stage one.",
    "data.builder._auto_no3_cutoff":
        "Finds the nitrate threshold below which the NO3 correction should apply, by fitting a "
        "thermal-only generalized logistic, taking residuals, and scanning cutoffs for the strongest "
        "Spearman rank correlation between residual and NO3. NaN rows are dropped across all arrays "
        "before scoring. Only runs when no3_cutoff is not supplied.",
    "data.builder._fit_gen_logi_to_get_residuals":
        "Least-squares fit of a thermal-only generalized logistic, used purely to produce residuals "
        "for the NO3 cutoff search. Not a Bayesian fit and never used for calibration itself.",
    "data.builder.build_invT_inputData":
        "The bridge between the two stages. It loads (or accepts) the forward posterior, randomly "
        "samples M parameter sets from it, extracts t0/k/b/v/sigma, packages any optional predictors, "
        "and returns both the Stan data dict and the sampler kwargs. Sampling M whole parameter sets "
        "rather than M independent marginals is what keeps posterior correlations intact.",
    "stan.sampler.get_posterior":
        "Runs a forward calibration and returns (posterior, diagnostic string). It wraps StanSampler "
        "with automatic predictor detection and CPU configuration, then attaches metadata. proxy_name "
        "is required at call time because it is written into the .nc attrs and into the filename.",
    "stan.sampler.auto_detect_predictors":
        "Inspects the data dict, decides whether GDGT-2/3 and NO3 are actually in play, and sets the "
        "integer use_* flags Stan expects. Also translates legacy scaledRI_* keys to proxyObs_* with a "
        "DeprecationWarning, which is why old notebooks still run.",
    "stan.sampler.StanSampler.sample":
        "The real workhorse: compile, sample, time the run, diagnose, convert draws to xarray, then "
        "attach metadata, priors and diagnostics as attrs. Application-specific kwargs (temptype, "
        "proxy_name, site_name, version, recompile) are popped off before the rest go to CmdStanPy.",
    "stan.sampler.StanSampler.sample_from_model":
        "Samples from an already-compiled CmdStanModel. Its notable job is recovering from exit code "
        "127, which means the cached binary is incompatible with the current runtime (typically a TBB "
        "mismatch between a Docker image and the host env). It deletes the stale binary, recompiles, "
        "evicts the compiler's in-memory cache entry, and retries once.",
    "stan.sampler.sampler_invT_posterior":
        "The inverse-side counterpart to get_posterior: a thin functional wrapper that builds a "
        "compiler and sampler and calls sample().",
    "stan.compiler.StanCompiler.get_model":
        "Returns a compiled CmdStanModel, hitting an in-memory cache first and the on-disk binary "
        "second. force=True clears the binary and recompiles. This is where the Windows-specific "
        "compile path and the ASCII source copy are applied.",
    "stan.compiler._stan_text_to_ascii":
        "Rewrites non-ASCII characters in Stan source to ASCII equivalents. Needed because stanc and "
        "the Windows toolchain choke on UTF-8 in .stan files that were edited with typographic "
        "characters.",
    "stan.compiler._windows_compile_path":
        "Resolves the RTools-vs-Strawberry g++ conflict on Windows and restores PATH afterwards "
        "without clobbering cmdstanpy's TBB dll directory. This is the fix that made Stan usable on "
        "the Windows uv-venv setup.",
    "stan.invT.get_invT_posterior":
        "The orchestrator of the inverse run and the busiest function in the package. It builds the "
        "invT data (or accepts one), picks the Stan file, patches predictors, sizes the run against "
        "available memory, samples, computes quantiles, attaches metadata, and optionally writes the "
        "posterior and the raw draws. Note that cache_dir (where results are written) and "
        "fwd_cache_dir (where the forward posterior is read) are deliberately separate.",
    "stan.invT._select_invT_stan_file":
        "Picks the .stan file from the shape of the problem: which optional predictors are "
        "active, and the temperature constraint scheme (unconstrained, "
        "truncated_prior). truncated_prior is the one that keeps P50 unbiased near a lower "
        "bound; hard_constraint was Jacobian-biased there and was archived in 2026-09, "
        "along with reparameterized and soft, which never had Stan models.",
    "stan.invT.get_invT_post_quantiles":
        "Reduces draws to percentiles, with shape handling that differs by model family: ensemble "
        "models give t_est as (chain, draw, N, M) and must also reduce over M, marginal models give "
        "(chain, draw, N).",
    "stan.invT.predict_temperature_from_proxyObs":
        "High-level wrapper around get_invT_posterior that returns temperature percentiles and, "
        "optionally, writes a tidy results table.",
    "stan.utils.patch_optional_predictors":
        "Defensive normalisation before Stan sees the data: makes sure gdgt23ratio and no3 arrays, "
        "use_* flags and beta terms all exist with the right shapes, converts NaN to 0.0, and handles "
        "both single-group (N) and multi-group (N_crtp) key layouts. Some Stan models expect "
        "unsuffixed use_* flags as well, so it creates both.",
    "stan.metadata.extract_and_update_metadata":
        "Attaches run metadata to the posterior Dataset: model name, temptype, priors, duration, data "
        "summaries and diagnostics. This is what makes downstream auto-detection possible, so a "
        "posterior missing these attrs will not work with generate_ensemble_auto.",
    "stan.metadata.extract_priors_from_stan":
        "Parses the .stan source to recover the prior expressions actually used, so the priors stored "
        "in the .nc are the ones in the model file rather than a hand-maintained copy.",
    "stan.io.save_posterior":
        "Writes the posterior as compressed NetCDF into the forward cache. The filename is built from "
        "model, temptype, optional predictor flags, and proxy_name, so a filename identifies a run.",
    "stan.io.load_posterior":
        "Loads {model_name}.nc from the forward or invT cache, or from an explicit cache_dir. Raises "
        "FileNotFoundError rather than silently returning empty.",
    "stan.io._sanitize_attrs_for_netcdf":
        "NetCDF attrs only accept a narrow set of types. This coerces everything else (dicts, None, "
        "nested lists) into storable strings so metadata survives the round trip.",
    "ensemble.generator.generate_ensemble_auto":
        "The auto-dispatching front end for forward curves. It reads the posterior's data_vars and "
        "attrs to infer the model function, parameter suffix and predictor flags, then delegates to "
        "generate_ensemble. It refuses invT posteriors, which is the common mistake.",
    "ensemble.generator.generate_ensemble":
        "Draws n_draws posterior indices and evaluates model_func at every x value, returning "
        "percentiles and optionally the full ensemble. All parameters for a given draw come from the "
        "same posterior index, which preserves their correlations. model_func arrives as a callable, "
        "so this edge is invisible to static analysis.",
    "ensemble.detection.detect_model_and_params":
        "Infers which curve function and which parameter names to use from the posterior itself. It "
        "reads use_gdgt23ratio / use_no3 / no3_cutoff from attrs and infers the model form from "
        "data_vars, deliberately not from stan_model_name.",
    "ensemble.detection.choose_suffix":
        "Applies the suffix priority order (crtp > culmesocore > culmeso > meso > cul) so the most "
        "data-rich parameter set available in a posterior is the one used.",
    "models.logistics.generalized_logistic_fixed_upper":
        "The forward calibration curve itself: a generalized logistic in temperature with a fixed "
        "upper asymptote. Since the Q asymmetry parameter was dropped, Q = 1 and the inflection point "
        "sits at t0.",
    "models.logistics.inverse_generalized_logistic_fixed_upper":
        "Closed-form inversion of the calibration curve. Useful for point estimates and plotting, but "
        "it is not the inverse reconstruction: that is Bayesian and lives in stan/invT.py.",
    "models.multivariate.generalized_logistic_fixed_upper_multivariate":
        "The multivariate forward curve, adding the GDGT-2/3 and below-cutoff NO3 correction terms to "
        "the thermal generalized logistic.",
    "models.multivariate.find_optimal_no3_threshold":
        "Scans candidate NO3 cutoffs and scores each by Spearman rank correlation between the cutoff-"
        "gated NO3 and the thermal residuals. Supplies the value build_fwd_data uses when no3_cutoff "
        "is omitted.",
    "data.screening.MahalanobisOutlierDetector.fit_transform":
        "Fit, score and screen in one call. Convenient, but note that the manuscript notebooks do not "
        "use it: they call fit() and then detect_outliers_manual() so the per-variable bounds can be "
        "set explicitly.",
    "data.screening.MahalanobisOutlierDetector.fit":
        "Estimates the mean vector and covariance of the chosen feature set, which defines the "
        "Mahalanobis metric everything downstream is measured in.",
    "data.screening.MahalanobisOutlierDetector.detect_outliers_manual":
        "The screening actually used to build the finalized global compilation. Unlike "
        "detect_outliers(), which thresholds on Mahalanobis distance alone, this applies explicit "
        "per-variable bounds so domain knowledge (e.g. plausible SST or RI ranges) can override the "
        "purely statistical call.",
    "data.ocean_lookup.lookup_no3_from_woa":
        "Nearest-valid-cell lookup of modern nitrate from a WOA23-derived dataset given site lat/lon. "
        "Lets you run the NO3-corrected model on cores that have no measured nitrate.",
    "diagnostics.summarize_sampler_diagnostics":
        "Condenses divergences, R-hat, ESS and E-BFMI into a dict that gets attached to the posterior "
        "as stan_diag_* attrs, so a saved run carries its own health check.",
    "utils.paths.find_cmdstan":
        "Resolves CmdStan in priority order (CMDSTAN env var, conda prefix, sys.prefix, well-known "
        "install roots, cmdstanpy's default) and only accepts a candidate whose bin/stanc actually "
        "exists and is executable. Always calls set_cmdstan_path() on the winner so cmdstanpy stays "
        "consistent. TEXAS never installs CmdStan implicitly.",
    "utils.system_info.suggest_stan_sampling_kwargs":
        "Reads the machine (cores, memory, container limits) and proposes chains / parallel_chains / "
        "threads_per_chain, so a notebook does not have to be tuned per machine.",
    "utils.system_info.simple_memory_check":
        "Guard rail before an inverse run: ensemble invT models allocate N x M temperature values and "
        "can exhaust memory on large cores.",
}

PIPELINES = [FORWARD, INVERSE]

# ── Loose ends ───────────────────────────────────────────────────────────────
# Notes for functions the reachability pass flags as unreferenced. The flag
# itself is computed (nothing in src/, notebooks/, streamlit_app/ or tests/
# calls them); these notes say what to do about it. Delete an entry once the
# function is removed or wired up — the build fails on names that no longer
# exist, so this list cannot silently rot.
LOOSE_ENDS = {
    "data.screening.MahalanobisOutlierDetector.fit_transform":
        "Convenience wrapper. The manuscript notebooks deliberately do not use it — they call "
        "fit() then detect_outliers_manual() so per-variable bounds can be set explicitly. Safe to "
        "keep as sklearn-style sugar, but it is not the documented screening path.",
    "data.screening.MahalanobisOutlierDetector.get_params":
        "sklearn-estimator convention, useful only if the detector is dropped into an sklearn "
        "Pipeline or GridSearchCV. Nothing does that today.",
    "data.screening.MahalanobisOutlierDetector.plot_multiple_ellipses":
        "Exploratory plotting kept from development. Only plot_decision_boundary() feeds a "
        "manuscript figure; these four unused plotters are roughly 420 lines of screening.py and "
        "pull in the heaviest optional plotting dependencies.",
    "data.screening.MahalanobisOutlierDetector.plot_pairwise_ellipses":
        "Same as plot_multiple_ellipses — exploratory, unused by any notebook or figure.",
    "data.screening.MahalanobisOutlierDetector.plot_pca_projection":
        "Same as plot_multiple_ellipses — exploratory, unused by any notebook or figure.",
    "data.screening.MahalanobisOutlierDetector.plot_corner":
        "Same as plot_multiple_ellipses — exploratory, unused by any notebook or figure.",
    "models.calibration.CalibrationRegistry.add_calibration":
        "Registry write API. Nothing registers a calibration at runtime; the registry is populated "
        "statically and only CalibrationRegistry.get() is ever called.",
    "models.calibration.CalibrationRegistry.list_calibrations":
        "Discovery helper for the registry. Never called — a natural fit for the Streamlit app or "
        "the docs, if you want it exercised rather than removed.",
    "models.calibration.TEX86Calibration.predict_tex86":
        "The forward direction of the classical (non-Bayesian) calibrations. Only predict_sst() is "
        "used; this half of the pair has no caller.",
}
