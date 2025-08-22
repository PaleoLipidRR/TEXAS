import re
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats
from typing import Union, Optional, Dict, List, Tuple, Sequence


def compute_sample_range(samples):
    if len(samples) == 0:
        return None, None
    p1, p99 = np.percentile(samples, [1, 99])
    span = p99 - p1
    return p1 - 0.2 * span, p99 + 0.2 * span


def compute_density_based_range(samples, kde_bw=0.3, density_threshold=0.01):
    """
    Compute a range based on meaningful density regions rather than just percentiles.
    This is particularly useful for distributions with flat tails.
    """
    if len(samples) == 0:
        return None, None
    
    # Get initial range using percentiles
    p1, p99 = np.percentile(samples, [1, 99])
    
    # Create a fine grid for density estimation
    x_range = np.linspace(p1, p99, 1000)
    
    # Compute KDE
    kde = stats.gaussian_kde(samples, bw_method=kde_bw)
    density = kde(x_range)
    
    # Find the maximum density
    max_density = np.max(density)
    
    # Find regions where density is above the threshold (relative to max)
    meaningful_density_mask = density > (density_threshold * max_density)
    
    if not np.any(meaningful_density_mask):
        # Fallback to percentile-based range if no meaningful density found
        return compute_sample_range(samples)
    
    # Find the range of meaningful density
    meaningful_indices = np.where(meaningful_density_mask)[0]
    density_min = x_range[meaningful_indices[0]]
    density_max = x_range[meaningful_indices[-1]]
    
    # Add some padding
    span = density_max - density_min
    padding = 0.1 * span
    
    return density_min - padding, density_max + padding


def compute_suffix_specific_range(all_samples, target_suffix):
    """
    Compute range based specifically on samples that contain the target suffix.
    Uses P5-P95 percentiles for aggressive zooming on the relevant distributions.
    """
    # Filter samples to only include those with the target suffix
    suffix_samples = []
    for samples, idx_ds, param_label, stan_model_label, use_gdgt23ratio_check, use_no3_check in all_samples:
        if target_suffix in param_label:
            suffix_samples.append(samples)
    
    if not suffix_samples:
        return None, None
    
    # Combine all suffix-specific samples
    combined_suffix = np.concatenate(suffix_samples)
    
    if len(combined_suffix) == 0:
        return None, None
    
    # Use P5-P95 for aggressive zooming
    p5, p95 = np.percentile(combined_suffix, [5, 95])
    span = p95 - p5
    padding = 0.05 * span  # Small padding
    
    return p5 - padding, p95 + padding


def compute_dataset_specific_range(all_samples, target_dataset_idx):
    """
    Compute range based specifically on samples from a specific posterior dataset.
    Uses P5-P95 percentiles for aggressive zooming on the relevant distributions.
    """
    # Filter samples to only include those from the target dataset
    dataset_samples = []
    for samples, idx_ds, param_label, stan_model_label, use_gdgt23ratio_check, use_no3_check in all_samples:
        if idx_ds == target_dataset_idx:
            dataset_samples.append(samples)
    
    if not dataset_samples:
        return None, None
    
    # Combine all dataset-specific samples
    combined_dataset = np.concatenate(dataset_samples)
    
    if len(combined_dataset) == 0:
        return None, None

    # Use P1-P99 for aggressive zooming
    p1, p99 = np.percentile(combined_dataset, [1, 99])
    span = p99 - p1
    padding = 0.05 * span  # Small padding

    return p1 - padding, p99 + padding


def plot_prior_distributions(
    priors_list: Union[List[str], Dict[str, str]],
    posterior_datasets=None,
    posterior_labels_list: Optional[List[str]] = None,
    show_suptitle=True,
    kde_bw=0.3,
    focus_on_posterior=True,
    include_groups=["t0", "k", "b", "v", "Q", "a", "beta0_gdgt23ratio", "beta0_no3"],
    suffix_include: Optional[List[str]] = None,
    zoomin_suffix: Optional[List[str]] = None,
    zoomin_dataset_idx: Optional[int] = None,
    use_linestyle_by_param=False,
    show_histogram=True,
    set_linewidth=1.5,
    set_bottom_space=0.2,
    set_fig_width_factor=3,
    set_fig_height_factor=3.5,
    set_leg_max_ncol=3,
    color_list: Optional[Sequence[str]] = None,
):
    fig, axes = None, None
    parsed_priors = {}

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
    
    if posterior_datasets:
        for ds in posterior_datasets:
            all_param_names.update(ds.data_vars)


    grouped = {key: [] for key in include_groups}
    for name in all_param_names:
        for prefix in include_groups:
            if name.startswith(prefix + "_"):
                grouped[prefix].append(name)
    # Add this to debug
    print("Grouped param names:", grouped)

    param_groups = [g for g in include_groups if grouped[g]]
    print(param_groups)
    ncols = 3 if len(param_groups) > 3 else len(param_groups)
    nrows = int(np.ceil(len(param_groups) / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, 
                             figsize=(set_fig_width_factor * ncols, set_fig_height_factor * nrows), 
                             squeeze=False, clear=True,
                             sharex=False, sharey=False,
                             constrained_layout=True)

    model_labels = []
    for idx, base in enumerate(param_groups):
        row_idx, col_idx = divmod(idx, ncols)
        ax = axes[row_idx][col_idx]
        ax.clear()
            

        param_names = grouped[base]
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

            ax.plot(x, y, color='black', lw=set_linewidth, label="Prior")

        # Collect all samples first to determine x range if no prior available
        for name in param_names:
            if posterior_datasets:
                for idx_ds, ds in enumerate(posterior_datasets):
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

        for samples, idx_ds, param_label, stan_model_label, use_gdgt23ratio_check, use_no3_check in all_samples:
            color = default_colors[idx_ds % len(default_colors)]

            if param_label.split("_")[0] == "t0":
                model_labels.append(stan_model_label)

            if use_linestyle_by_param:
                ls_idx = unique_param_names.index(param_label)
                linestyle = linestyles[ls_idx % len(linestyles)]
            else:
                linestyle = '-'

            kde = stats.gaussian_kde(samples, bw_method=kde_bw)
            kde_y = kde(x)
            
            if param_label.startswith("beta0_gdgt23ratio"):
                if use_gdgt23ratio_check == 1:
                    ax.plot(x, kde_y, color=color, lw=set_linewidth, linestyle=linestyle, label=param_label)
                    if show_histogram:
                        ax.hist(samples, bins=100, density=True, alpha=0.2, color=color)
            elif param_label.startswith("beta0_no3"):
                if use_no3_check == 1:
                    ax.plot(x, kde_y, color=color, lw=set_linewidth, linestyle=linestyle, label=param_label)
                    if show_histogram:
                        ax.hist(samples, bins=100, density=True, alpha=0.2, color=color)
            else:
                ax.plot(x, kde_y, color=color, lw=set_linewidth, linestyle=linestyle, label=param_label)
                if show_histogram:
                    ax.hist(samples, bins=100, density=True, alpha=0.2, color=color)


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

        
        ax.set_xlabel(f"{base}")
        ax.grid(True)

        if all_samples:
            handles, labels_in_ax = ax.get_legend_handles_labels()
            if handles:
                ax.legend(handles, labels_in_ax, loc='upper right', fontsize=8, ncol=1, frameon=False)

    model_labels.insert(0, "Prior")

    if posterior_datasets:
        h, l = axes[0][0].get_legend_handles_labels()
        legend_labels = model_labels
        legend_rows = int(np.ceil(len(legend_labels) / set_leg_max_ncol))
        # Dynamically adjust space based on number of rows — shrink when only 1 row
        if legend_rows == 1:
            bottom_padding = 0.06
        elif legend_rows == 2:
            bottom_padding = 0.10
        else:
            bottom_padding = 0.12 + 0.02 * (legend_rows - 2)

        fig.tight_layout(rect=[0, bottom_padding, 1, 0.92])

        fig.legend(
            handles=h,
            labels=legend_labels,
            loc='lower center',
            ncol=min(len(legend_labels), set_leg_max_ncol),
            fontsize=10,
            bbox_to_anchor=(0.5, bottom_padding - 0.05),
            frameon=True,
            borderaxespad=0.0,
            handletextpad=0.6,
            labelspacing=0.4
        )
    else:
        fig.tight_layout(rect=[0, set_bottom_space, 1, 0.92])

    
    if show_suptitle:
        fig.suptitle("Prior and Posterior Distributions", fontsize=14)

    # axes[0][2].legend(loc='upper left', fontsize=8, ncol=1, frameon=False)
    # Align legends for bottom row
    for row in axes:
        for ax in row:
            if not ax.has_data():
                ax.set_visible(False)
                
    # detect if there are axes[1] then make all axs[1][:] to have legend loc='upper left'
    if axes.shape[0] > 1:
        for ax in axes[1]:
            handles, labels_in_ax = ax.get_legend_handles_labels()
            if handles:
                ax.legend(loc='upper right', fontsize=8, ncol=1, frameon=False)
    
    # Top right and bottom left legends override if present
    if axes.shape[0] > 1:
        for ax in axes[1]:
            handles, labels_in_ax = ax.get_legend_handles_labels()
            if handles:
                ax.legend(loc='upper right', fontsize=8, ncol=1, frameon=False)
                

    return fig, axes