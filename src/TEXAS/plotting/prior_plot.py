# TEXAS/plotting/prior_plot.py

import re
import math
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats
from typing import Union, Optional, Dict, List, Sequence, Literal


def _format_stat(median: float, std: float) -> str:
    """Return 'median ± std' formatted to appropriate significant figures.

    The uncertainty drives the precision:
    - Round std to 1 sig fig (2 sig figs if its leading digit is 1 or 2,
      since one sig fig would be too coarse there).
    - Round median to the same decimal place.

    Examples
    --------
    >>> _format_stat(35.812, 0.845)   # σ leading digit 8 → 1 sig fig
    '35.8 ± 0.8'
    >>> _format_stat(0.02451, 0.00234)  # σ leading digit 2 → 2 sig figs
    '0.0245 ± 0.0023'
    >>> _format_stat(35.0, 1.52)      # σ leading digit 1 → 2 sig figs
    '35.0 ± 1.5'
    """
    if not np.isfinite(std) or std <= 0:
        return f"{median:.3g}"
    n_dec = _n_decimals(std)
    fmt = f".{n_dec}f"
    return f"{round(median, n_dec):{fmt}} ± {round(std, n_dec):{fmt}}"

def _n_decimals(scale: float) -> int:
    """Decimal places needed to show `scale` to 1–2 sig figs (GUM §7.2.6 rule)."""
    if not np.isfinite(scale) or scale <= 0:
        return 3
    mag = math.floor(math.log10(abs(scale)))
    first_digit = int(abs(scale) / 10 ** mag)
    return max(0, 1 - mag) if first_digit <= 3 else max(0, -mag)


def _format_ci(median: float, p5: float, p95: float) -> str:
    """Return 'median [p5, p95]' with sig figs driven by the interval half-width.

    Examples
    --------
    >>> _format_ci(31.2, 28.4, 34.1)
    '31.2 [28.4, 34.1]'
    >>> _format_ci(0.245, 0.18, 0.31)
    '0.245 [0.180, 0.310]'
    """
    half_width = (p95 - p5) / 2
    n_dec = _n_decimals(half_width)
    fmt = f".{n_dec}f"
    return f"{round(median, n_dec):{fmt}} [{round(p5, n_dec):{fmt}}, {round(p95, n_dec):{fmt}}]"


def _format_prior_expr(dist: str, a: float, b: float, trunc: Optional[str]) -> str:
    """Return a 'distributed as' string for a prior.

    Notation follows McElreath (Statistical Rethinking) / Stan convention:
    θ ~ Normal(μ, σ) where σ is the standard deviation.
    The '~' is written as plain text outside math mode so it renders
    as a tilde rather than the math-mode '∼' (similar-to) symbol.
    """
    def _fmt(v: float) -> str:
        return f"{v:.4g}"

    args = rf"({_fmt(a)},\;{_fmt(b)})"

    if trunc:
        bounds = [v.strip() for v in trunc.split(",")]
        lo = bounds[0] if bounds[0] else r"-\infty"
        hi = bounds[1] if len(bounds) > 1 and bounds[1] else r"+\infty"
        args += rf"\;\mathrm{{T}}[{lo},\;{hi}]"

    if dist == "normal":
        return rf"$\mathcal{{N}}\,{args}$"
    elif dist == "lognormal":
        return rf"$\mathrm{{LogNormal}}\,{args}$"
    elif dist == "beta":
        return rf"$\mathcal{{B}}\,{args}$"
    elif dist == "cauchy":
        return rf"$\mathrm{{Cauchy}}\,{args}$"
    else:
        return rf"$\mathrm{{{dist}}}\,{args}$"


from .range_utils import (
    compute_sample_range,
    compute_density_based_range,
    compute_suffix_specific_range,
    compute_dataset_specific_range,
)


def plot_prior_distributions(
    priors_list: Optional[Union[List[str], Dict[str,str]]] = None,
    posterior_datasets: Optional[List["xr.Dataset"]] = None,
    posterior_labels_list: Optional[List[str]] = None,
    show_suptitle: bool = True,
    kde_bw: float = 0.3,
    focus_on_posterior: bool = True,
    include_groups: Sequence[str] = ("t0","k","b","v","a","beta_G23","beta_NO3"),
    suffix_include: Optional[List[str]] = None,
    zoomin_suffix: Optional[Union[str,List[str]]] = None,
    zoomin_dataset_idx: Optional[int] = None,
    use_linestyle_by_param: bool = False,
    show_histogram: bool = True,
    show_annotation: bool = False,
    set_linewidth: float = 1.5,
    set_fig_width_factor: float = 3,
    set_fig_height_factor: float = 3.5,
    set_leg_max_ncol: int = 3,
    color_list: Optional[Sequence[str]] = None,
    param_source_map: Optional[Dict[str, int]] = None,
    annotation_style: Literal["ci95", "sigma"] = "ci95",
    show_subplot_legend: bool = True,
    show_figure_legend: bool = True,
    show_prior_expression: bool = True,
):
    """
    Plot priors + any number of posterior distributions in a grid,
    split by parameter group (t0, k, b, etc.).

    Args:
        param_source_map: Optional dict mapping a param group name to the index of
            the dataset in ``posterior_datasets`` that should be used as the sole
            source for that group.  All other datasets are skipped for that group.

            Use this when different parameters come from different posteriors — e.g.
            logistic params (t0, k, b…) from a ``culmeso`` run and beta coefficients
            from a multivariate ``crtp`` run::

                plot_prior_distributions(
                    posterior_datasets=[culmeso_ds, crtp_multiv_ds],
                    param_source_map={"beta_G23": 1, "beta_NO3": 1},
                )

            When a group is not in ``param_source_map``, all datasets are searched
            as usual.
    """
    # ── Resolve any string / Path entries in posterior_datasets ──────────────
    if posterior_datasets:
        from pathlib import Path as _Path
        from ..stan.io import load_posterior as _load_posterior
        resolved = []
        for item in posterior_datasets:
            if isinstance(item, (str, _Path)):
                resolved.append(_load_posterior(str(item)))
            else:
                resolved.append(item)
        posterior_datasets = resolved

    fig, axes = None, None
    parsed_priors = {}

    # If priors_list not supplied, pull prior strings from the posterior datasets'
    # attrs["priors"] (set automatically during sampling).  Merge across all
    # datasets and deduplicate so each prior name appears only once.
    if priors_list is None:
        seen = {}
        for ds in (posterior_datasets or []):
            for entry in ds.attrs.get("priors", []):
                name = entry.split(":")[0].strip()
                seen.setdefault(name, entry)   # first dataset wins on conflict
        priors_list = list(seen.values())

    for prior in priors_list:
        name, dist_expr = prior.split(":", 1)
        name = name.strip()
        dist_expr = dist_expr.strip()

        if any(sym in dist_expr for sym in ["mu_", "sigma_", "logit"]):
            continue

        match = re.match(r"(\w+)\(([^,]+),\s*([^)]+)\)(?:\s*T\[(.*)\])?", dist_expr)
        if not match:
            continue

        dist_name, a_str, b_str, trunc = match.groups()
        try:
            a = float(a_str)
            b = float(b_str)
        except ValueError:
            continue

        parsed_priors[name] = {
            "dist": dist_name,
            "a": a,
            "b": b,
            "trunc": trunc,
        }

    all_param_names = set(parsed_priors.keys())
    _use_gdgt23ratio_detection = 0
    _use_no3_detection = 0
    if posterior_datasets:
        for ds in posterior_datasets:
            all_param_names.update(ds.data_vars)
            
            # collect "use_gdgt23ratio" and "use_no3" from all datasets
            if ds.attrs.get("use_gdgt23ratio", 0) == 1:
                _use_gdgt23ratio_detection += 1

            if ds.attrs.get("use_no3", 0) == 1:
                _use_no3_detection += 1

    grouped = {key: [] for key in include_groups}
    for name in all_param_names:
        for prefix in include_groups:
            if name.startswith(prefix + "_"):
                grouped[prefix].append(name)
    param_groups = [g for g in include_groups if grouped[g]]

    ### pop param_groups
    if ('beta_G23' in param_groups) and (_use_gdgt23ratio_detection == 0):
        param_groups.pop(param_groups.index('beta_G23'))

    if ('beta_NO3' in param_groups) and (_use_no3_detection == 0):
        param_groups.pop(param_groups.index('beta_NO3'))

    # ncols/nrows computed AFTER popping so the grid is sized correctly.
    # Max layout is 2 rows × 3 cols (6 params: t0, k, b, v, beta_G23, beta_NO3).
    ncols = min(3, len(param_groups))
    nrows = int(np.ceil(len(param_groups) / ncols)) if ncols > 0 else 1

    # squeeze=False guarantees axes is always 2-D (nrows × ncols) so indexing
    # axes[row, col] is safe regardless of grid size.
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols,
                             figsize=(set_fig_width_factor * ncols, set_fig_height_factor * nrows),
                             squeeze=False, clear=True,
                             sharex=False, sharey=False)

    # Keyed by idx_ds → (line_handle, label); populated during plotting so the
    # figure-level legend always has exactly one entry per dataset in list order.
    _fig_legend_entries: Dict[int, tuple] = {}
    _prior_handle = None

    for idx, base in enumerate(param_groups):
        row_idx, col_idx = divmod(idx, ncols)
        ax = axes[row_idx, col_idx]
        ax.clear()
            

        param_names = sorted(grouped[base])   # sort for deterministic order
        if suffix_include:
            param_names = [p for p in param_names if any(p.endswith(suf) for suf in suffix_include)]
        all_samples = []
        x_min, x_max = None, None

        prior_key = next((k for k in parsed_priors if k.startswith(base)), None)
        x = None  # Initialize x variable
        
        if prior_key:
            prior_info = parsed_priors[prior_key]
            dist, a, b, trunc = prior_info["dist"], prior_info["a"], prior_info["b"], prior_info["trunc"]

            if dist == "normal":
                std_range = 4 if trunc is None else 2.5
                x_min = a - std_range * b
                x_max = a + std_range * b
                if trunc:
                    t_bounds = [float(v) if v else None for v in re.split(r",\s*", trunc)]
                    if t_bounds[0] is not None:
                        x_min = max(x_min, t_bounds[0])
                    if len(t_bounds) > 1 and t_bounds[1] is not None:
                        x_max = min(x_max, t_bounds[1])
                x = np.linspace(x_min, x_max, 5000)
                y = stats.norm.pdf(x, a, b)
                if trunc:
                    if t_bounds[0] is not None:
                        y[x < t_bounds[0]] = 0
                    if len(t_bounds) > 1 and t_bounds[1] is not None:
                        y[x > t_bounds[1]] = 0

            elif dist == "beta":
                x_min, x_max = 0.0, 1.0
                x = np.linspace(x_min, x_max, 5000)
                y = stats.beta.pdf(x, a, b)

            elif dist == "cauchy":
                x_min = a - 10 * b
                x_max = a + 10 * b
                x = np.linspace(x_min, x_max, 5000)
                y = stats.cauchy.pdf(x, a, b)
                
            elif dist == "lognormal":
                x_min = max(1e-6, np.exp(a - 4 * b))
                x_max = np.exp(a + 4 * b)
                x = np.linspace(x_min, x_max, 5000)
                y = stats.lognorm.pdf(x, s=b, scale=np.exp(a))

            else:
                continue

            (prior_line,) = ax.plot(x, y, color='black', lw=set_linewidth, label="Prior")
            if _prior_handle is None:
                _prior_handle = prior_line
            if show_prior_expression:
                expr = _format_prior_expr(dist, a, b, trunc)
                ax.text(0.98, 0.98, expr, transform=ax.transAxes,
                        fontsize=9, va='top', ha='right', color='black')

        # Collect all samples first to determine x range if no prior available.
        # If param_source_map specifies a source dataset for this group, only
        # pull samples from that dataset; otherwise search all datasets.
        _source_idx = param_source_map.get(base) if param_source_map else None
        for name in param_names:
            if posterior_datasets:
                for idx_ds, ds in enumerate(posterior_datasets):
                    if _source_idx is not None and idx_ds != _source_idx:
                        continue
                    if name not in ds.data_vars:
                        continue
                    samples = ds[name].values.flatten()
                    if posterior_labels_list is not None:
                        stan_model_labels = posterior_labels_list[idx_ds]
                    else:
                        # Fallback to dataset filename if labels not provided
                        stan_model_labels = ds.attrs.get('filename', 'Unknown Model')
                    use_gdgt23ratio_check = ds.attrs.get('use_gdgt23ratio', 0)
                    use_no3_check = ds.attrs.get('use_no3', 0)
                    all_samples.append((samples, idx_ds, name, stan_model_labels,
                                        use_gdgt23ratio_check, use_no3_check))
        
        # Sort by (idx_ds, param_name) so all lines for dataset 0 are plotted
        # before dataset 1, giving a consistent order in every subplot.
        all_samples.sort(key=lambda t: (t[1], t[2]))

        # If x was not defined by prior, create it from posterior data range
        if x is None and all_samples:
            # Get the combined range of all samples for this parameter group
            all_param_samples = np.concatenate([s for s, _, _, _, _, _ in all_samples])
            data_min, data_max = all_param_samples.min(), all_param_samples.max()
            
            # Robust padding calculation that works for any value range
            data_range = data_max - data_min
            if data_range > 0:
                # Use 15% padding relative to data range
                padding = 0.15 * data_range
            else:
                # If all values are identical, use absolute padding based on magnitude
                abs_magnitude = abs(data_min) if data_min != 0 else 1.0
                padding = 0.1 * abs_magnitude
            
            x_min = data_min - padding
            x_max = data_max + padding
            x = np.linspace(x_min, x_max, 5000)
        elif x is None:
            # Fallback: create a default range if no samples either
            x = np.linspace(-1, 1, 5000)
        
        # Determine number of distinct models (used to color by model)
        if posterior_datasets:
            num_models = len(posterior_datasets)
        else:
            num_models = 0

        # Validate and assign plotting colors
        if color_list is not None:
            if len(color_list) != num_models:
                raise ValueError(f"color_list must have exactly {num_models} colors to match the number of posterior datasets.")
            default_colors = color_list
        else:
            # Use default tab10 colors; repeat if not enough
            default_colors = plt.cm.tab10.colors
            if num_models > len(default_colors):
                from itertools import cycle, islice
                default_colors = list(islice(cycle(default_colors), num_models))
        
        linestyles = ['-', '--', '-.', ':', (0, (3, 1, 1, 1))]

        unique_param_names = sorted(set(pname for _, _, pname, _, _, _ in all_samples))
        _n_annotated = [0]  # counts lines actually drawn; drives annotation y-position

        for iiii, (samples, idx_ds, param_label, stan_model_label, use_gdgt23ratio_check, use_no3_check) in enumerate(all_samples):
            color = default_colors[idx_ds % len(default_colors)]

            if use_linestyle_by_param:
                ls_idx = unique_param_names.index(param_label)
                linestyle = linestyles[ls_idx % len(linestyles)]
            else:
                linestyle = '-'

            kde = stats.gaussian_kde(samples, bw_method=kde_bw)
            kde_y = kde(x)

            def _plot_line():
                (line,) = ax.plot(x, kde_y, color=color, lw=set_linewidth, linestyle=linestyle, label=param_label)
                if idx_ds not in _fig_legend_entries:
                    _fig_legend_entries[idx_ds] = (line, stan_model_label)
                if show_histogram:
                    ax.hist(samples, bins=100, density=True, alpha=0.2, color=color)
                if show_annotation:
                    med = np.median(samples)
                    if annotation_style == "ci95":
                        text = _format_ci(med, np.percentile(samples, 5),
                                               np.percentile(samples, 95))
                    else:
                        text = _format_stat(med, np.std(samples, ddof=1))
                    ypos = 0.98 - _n_annotated[0] * 0.065
                    ax.text(0.02, ypos, text, transform=ax.transAxes,
                            fontsize=8, va='top', ha='left', color=color)
                    _n_annotated[0] += 1

            if param_label.startswith("beta_G23"):
                if use_gdgt23ratio_check == 1:
                    _plot_line()
            elif param_label.startswith("beta_NO3"):
                if use_no3_check == 1:
                    _plot_line()
            else:
                _plot_line()


        if all_samples:
            combined = np.concatenate([s for s, _, _, _, _, _ in all_samples])
            
            # Handle dataset-specific zooming (priority over suffix-based zooming)
            if focus_on_posterior and zoomin_dataset_idx is not None:
                zoom_min, zoom_max = compute_dataset_specific_range(all_samples, zoomin_dataset_idx)
                if zoom_min is not None and zoom_max is not None:
                    ax.set_xlim([zoom_min, zoom_max])
                else:
                    # Fallback to standard range if dataset-specific fails
                    zoom_min, zoom_max = compute_sample_range(combined)
                    if zoom_min is not None:
                        ax.set_xlim([zoom_min, zoom_max])
            else:
                # Handle zoomin_suffix as either string or list (legacy behavior)
                should_zoom = False
                if focus_on_posterior and zoomin_suffix:
                    if isinstance(zoomin_suffix, str):
                        should_zoom = zoomin_suffix in base
                    else:
                        should_zoom = any(suffix in base for suffix in zoomin_suffix)
                
                if should_zoom:
                    # For zoomin_suffix matches, use suffix-specific P5-P95 range for aggressive zooming
                    if isinstance(zoomin_suffix, str):
                        zoom_min, zoom_max = compute_suffix_specific_range(all_samples, zoomin_suffix)
                    else:
                        # For list of suffixes, try each one
                        zoom_min, zoom_max = None, None
                        for suffix in zoomin_suffix:
                            if suffix in base:
                                zoom_min, zoom_max = compute_suffix_specific_range(all_samples, suffix)
                                break
                    
                    if zoom_min is not None and zoom_max is not None:
                        ax.set_xlim([zoom_min, zoom_max])
                    else:
                        # Fallback to standard range if suffix-specific fails
                        zoom_min, zoom_max = compute_sample_range(combined)
                        if zoom_min is not None:
                            ax.set_xlim([zoom_min, zoom_max])
                elif focus_on_posterior:
                    # For other cases, use the standard percentile-based range
                    zoom_min, zoom_max = compute_sample_range(combined)
                    if zoom_min is not None:
                        if x_min is not None and x_max is not None:
                            ax.set_xlim([max(x_min, zoom_min), min(x_max, zoom_max)])
                        else:
                            ax.set_xlim([zoom_min, zoom_max])
                elif x_min is not None and x_max is not None:
                    ax.set_xlim([x_min, x_max])
        else:
            if x_min is not None and x_max is not None:
                ax.set_xlim([x_min, x_max])

        
        ### Modified labels in ax
        ax_legends_labels_dict = {
            "t0_crtp": r"T$_0$",
            "k_crtp": "k",
            "b_crtp": "b",
            "v_crtp": r"$\nu$",
            "a_crtp": "a",
            "beta_G23_crtp": r"$\beta_{G_{2/3}}$",
            "beta_NO3_crtp": r"$\beta_{NO_3}$",
            
            "t0_culmeso": r"T$_{0, culmeso}$",
            "k_culmeso": r"k$_{culmeso}$",
            "b_culmeso": r"b$_{culmeso}$",
            "v_culmeso": r"$\nu_{culmeso}$",
            "a_culmeso": r"a$_{culmeso}$",
            "beta_G23_culmeso": r"$\beta_{G_{2/3},culmeso}$",
            "beta_NO3_culmeso": r"$\beta_{NO_3,culmeso}$",
        }

        if all_samples:
            handles, labels_in_ax = ax.get_legend_handles_labels()
            revised_labels_in_ax = []
            for lbl in labels_in_ax:
                revised_lbl = lbl
                for key, val in ax_legends_labels_dict.items():
                    if key in lbl:
                        ### strip with "_" before replacing both prefix and suffix
                        revised_lbl = val + revised_lbl.replace(key, "")
                        break
                revised_labels_in_ax.append(revised_lbl)
            if handles and show_subplot_legend:
                ax.legend(handles, revised_labels_in_ax, loc='upper right', fontsize=8, ncol=1, frameon=False)

        revised_base_dict = {
            "t0": r"T$_0$",
            "k": "k",
            "b": "b",
            "v": r"$\nu$",
            "a": "a",
            "beta_G23": r"$\beta_{G_{2/3}}$",
            "beta_NO3": r"$\beta_{NO_3}$",
        }
        revised_base = revised_base_dict.get(base, base)
                
        ax.set_xlabel(f"{revised_base}")
        ax.grid(True)

    if posterior_datasets:
        # Build figure legend: Prior first, then one entry per dataset in
        # posterior_datasets order (guaranteed by idx_ds key).
        fig_handles, fig_labels = [], []
        if _prior_handle is not None:
            fig_handles.append(_prior_handle)
            fig_labels.append("Prior")
        for i in range(len(posterior_datasets)):
            if i in _fig_legend_entries:
                h_ds, lbl_ds = _fig_legend_entries[i]
                fig_handles.append(h_ds)
                fig_labels.append(lbl_ds)

        legend_ncol = min(len(fig_labels), set_leg_max_ncol)
        legend_nrow = int(np.ceil(len(fig_labels) / legend_ncol))

        # Reserve space at the bottom for the figure legend (≈0.05 per legend row).
        # tight_layout fills the axes into rect=[left, bottom, right, top].
        top_margin = 0.95 if show_suptitle else 1.0
        bottom_margin = -0.05 + -0.04 * legend_nrow  # ~0.09 for 1 row, ~0.13 for 2 rows
        fig.tight_layout(rect=[0, bottom_margin if show_figure_legend else 0.02, 1, top_margin])

        if show_figure_legend:
            # Place the legend's upper-centre at the top of the reserved space.
            fig.legend(
                handles=fig_handles,
                labels=fig_labels,
                loc='lower center',
                bbox_to_anchor=(0.5, bottom_margin),
                ncol=legend_ncol,
                fontsize=10,
                frameon=True,
                borderaxespad=0.0,
                handletextpad=0.4,
                labelspacing=0.3,
            )

    if show_suptitle:
        fig.suptitle("Prior and Posterior Distributions", fontsize=14)

    # Hide any unused subplots in the grid (e.g. last cell when param count is odd).
    for ax in axes.flat:
        if not ax.has_data():
            ax.set_visible(False)

    return fig, axes
