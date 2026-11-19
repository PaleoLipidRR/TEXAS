# The TEXAS-PSM framework and its sensor models

TEXAS-PSM follows the proxy system model (PSM) framework of [Evans et al. (2013)](https://doi.org/10.1016/j.quascirev.2013.05.024): three submodels (sensor, archive and observation) connect four components, from the ocean conditions an archaeon lives in to the number a mass spectrometer reports (Figure 2 of the manuscript). This page gives the equations behind each box of the schematic on the [home page](index.md). The classical TEX₈₆ calibrations are included for comparison, because TEXAS is built to explain what they leave unexplained. How TEXAS turns these models into calibration and temperature posteriors is covered in the [Bayesian inference workflow](PSM.md).

(psm-environment)=
## Environment

The ambient conditions that set the GDGT distribution an archaeal community makes. TEXAS uses three of them:

- **Temperature**: either sea surface temperature (SST) or surface-to-thermocline temperature (Thermo-T), chosen by the calibration posterior.
- **AOA ecology**: the mix of shallow (Water Column A) and deep (Water Column B) ammonia-oxidizing archaea, read from the GDGT-2/GDGT-3 ratio (G₂/₃). See [AOA ecology](sensor-aoa).
- **Nutrient level**: surface ocean nitrate, [NO₃⁻]. See [Nutrient level](sensor-nutrient).

(psm-sensor)=
## Sensor: from environment to GDGT compositions

The sensor model describes how archaea adjust their membrane lipids, the isoprenoid GDGTs, to their environment. Every calibration below is a sensor model. They differ in which GDGT index they use, which environmental variables they include, and how they treat uncertainty.

:::{container} sensor-summary
|  | [Linear](sensor-linear) | [Exponential (TEX₈₆ᴴ)](sensor-tex86h) | [BAYSPAR](sensor-bayspar) | [TEXAS](sensor-texas) |
| --- | --- | --- | --- | --- |
| **Reference** | Schouten et al. (2002) | Kim et al. (2010) | Tierney & Tingley (2014) | Rattanasriampaipong et al. (2026) |
| **Paper** | <a class="paper-btn" href="https://doi.org/10.1016/S0012-821X(02)00979-2" target="_blank" rel="noopener">Paper &#8599;</a> | <a class="paper-btn" href="https://doi.org/10.1016/j.gca.2010.05.027" target="_blank" rel="noopener">Paper &#8599;</a> | <a class="paper-btn" href="https://doi.org/10.1016/j.gca.2013.11.026" target="_blank" rel="noopener">Paper &#8599;</a> | <a class="paper-btn" href="https://doi.org/10.22541/essoar.15002926/v3" target="_blank" rel="noopener">Preprint &#8599;</a> |
| **GDGT index** | <span class="chip chip-index">TEX₈₆</span> | <span class="chip chip-index">TEX₈₆ᴴ = log₁₀(TEX₈₆)</span> | <span class="chip chip-index">TEX₈₆</span> | <span class="chip chip-index">Scaled RI = RI₀₋₃ / 3</span><br><small>all six isoGDGTs</small> |
| **Shape of the response** | Straight line | Straight line in TEX₈₆ᴴ, so exponential in TEX₈₆ | Straight line whose slope, intercept and error vary by 20° × 20° grid box | Generalized logistic (S-shaped), bounded between b and 1 |
| **Temperature target** | <span class="chip chip-temp">SST</span> | <span class="chip chip-temp">SST</span> | <span class="chip chip-temp">SST</span> <span class="chip chip-temp">SubT</span> | <span class="chip chip-temp">SST</span> <span class="chip chip-temp">Thermo-T</span> |
| **Nonthermal predictors** | — | — | — | <a href="#sensor-aoa"><span class="chip chip-pred">G₂/₃</span></a> <a href="#sensor-nutrient"><span class="chip chip-pred">NO₃⁻</span></a><br><small>shift the curve location T₀</small> |
| **Calibration data** | <span class="chip chip-coretop">Coretop</span> | <span class="chip chip-coretop">Coretop</span> | <span class="chip chip-coretop">Coretop</span> | <span class="chip chip-culture">Culture</span> <span class="chip chip-mesocosm">Mesocosm</span> <span class="chip chip-coretop">Coretop</span><br><small>cultures and mesocosms set the curve-shape priors</small> |
| **Uncertainty** | <span class="chip chip-unc">Fixed calibration error</span> | <span class="chip chip-unc">Fixed calibration error</span> | <span class="chip chip-unc">Bayesian</span> <span class="chip chip-unc">Spatially varying</span> | <span class="chip chip-unc">Bayesian</span> <span class="chip chip-unc">Hierarchical</span> <span class="chip chip-unc">Errors-in-variables</span> |
| **In TEXAS** | `CalibrationRegistry.get("schouten02")` | `CalibrationRegistry.get("kim2010_tex86H")` | `BAYSPARCalibration` (needs `baysparpy`) | `predict_T_from_proxyObs` |
:::

The classical calibrations use TEX₈₆ (Eq. 1 of the manuscript), which leaves out GDGT-0 and crenarchaeol:

$$
\mathrm{TEX}_{86} = \frac{[\text{GDGT-2}] + [\text{GDGT-3}] + [\text{Cren}']}{[\text{GDGT-1}] + [\text{GDGT-2}] + [\text{GDGT-3}] + [\text{Cren}']}
$$

(sensor-linear)=
### Linear TEX₈₆ (Schouten et al., 2002)

The original calibration: a straight line through coretop TEX₈₆ against annual mean SST ([Schouten et al., 2002](https://doi.org/10.1016/S0012-821X(02)00979-2)).

$$
\mathrm{TEX}_{86} = 0.015\,\mathrm{SST} + 0.28 \quad\Longleftrightarrow\quad \mathrm{SST} = 66.67\,\mathrm{TEX}_{86} - 18.67
$$

In TEXAS: `CalibrationRegistry.get("schouten02")` or `predict_sst_from_tex86(tex86, "schouten02")` in `TEXAS.models.calibration`.

(sensor-tex86h)=
### Exponential: TEX₈₆ᴴ (Kim et al., 2010)

A logarithmic transform of TEX₈₆, fitted to coretops from warmer waters ([Kim et al., 2010](https://doi.org/10.1016/j.gca.2010.05.027)). It is linear in TEX₈₆ᴴ, so it is exponential in TEX₈₆.

$$
\mathrm{TEX}_{86}^{\mathrm{H}} = \log_{10}\left(\mathrm{TEX}_{86}\right), \qquad \mathrm{SST} = 68.4\,\mathrm{TEX}_{86}^{\mathrm{H}} + 38.6
$$

In TEXAS: `CalibrationRegistry.get("kim2010_tex86H")`.

(sensor-bayspar)=
### BAYSPAR (Tierney & Tingley, 2014)

A Bayesian, spatially varying linear calibration ([Tierney & Tingley, 2014](https://doi.org/10.1016/j.gca.2013.11.026); database and subsurface calibration extended in [Tierney & Tingley, 2015](https://doi.org/10.1038/sdata.2015.29)). The slope, intercept and error vary between 20° × 20° grid boxes of the modern ocean:

$$
\mathrm{TEX}_{86} = \alpha(\mathbf{x}) + \beta(\mathbf{x})\,\mathrm{SST} + \varepsilon, \qquad \varepsilon \sim \mathcal{N}\!\left(0,\ \sigma^2(\mathbf{x})\right)
$$

where $\mathbf{x}$ is the grid box. To reconstruct, BAYSPAR combines this relationship with a prior on SST. In *standard* mode it uses the coefficients of the site's own grid box. In *analog* mode, meant for deep time, it uses grid boxes whose modern TEX₈₆ resembles the samples'. Code: [BAYSPAR for MATLAB](https://github.com/jesstierney/BAYSPAR) and [baysparpy](https://github.com/brews/baysparpy). In TEXAS: `BAYSPARCalibration(mode="standard")` or `"analog"`, which needs the optional `baysparpy` package.

(sensor-texas)=
### TEXAS (this study)

TEXAS replaces TEX₈₆ with the **Scaled Ring Index**, which keeps all six isoGDGTs and counts crenarchaeol as three rings (Eqs. 6 and 8 of the manuscript):

$$
\mathrm{RI}_{0\text{–}3} = \frac{[\text{GDGT-1}] + 2[\text{GDGT-2}] + 3[\text{GDGT-3}] + 3[\text{Cren}] + 3[\text{Cren}']}{[\text{GDGT-0}] + [\text{GDGT-1}] + [\text{GDGT-2}] + [\text{GDGT-3}] + [\text{Cren}] + [\text{Cren}']}
$$

$$
\text{Scaled RI} = \frac{\mathrm{RI}_{0\text{–}3}}{3}
$$

Scaled RI follows a generalized logistic (S-shaped) curve in temperature, bounded below by $b$ and above by 1. The two nonthermal predictors shift the curve's location $T_0$ along the temperature axis without changing its shape, the *T₀-shift parameterization* (Eq. 13 of the manuscript):

$$
\begin{aligned}
T_{0,\text{eff}} &= T_0 + \gamma_{\text{G23}}\, G_{2/3} + \gamma_{\text{NO}_3}\, \log_{10}[\text{NO}_3^-]\ \mathbb{I}_{([\text{NO}_3^-] < 1.0)} \\
\text{Scaled RI} &= b + \frac{1 - b}{\left(1 + \exp\left[-k\,(T - T_{0,\text{eff}})\right]\right)^{1/\nu}} + \varepsilon, \qquad \varepsilon \sim \mathcal{N}(0, \sigma_{\text{total}})
\end{aligned}
$$

$T_0$ is the curve's location, not its inflection point: the response is steepest at $T_0 - \ln(\nu)/k$, several °C below $T_0$. Setting both $\gamma$ to zero recovers the thermal-only curve. The fit is hierarchical: culture and mesocosm experiments set the priors on the curve's shape, and the coretop fit treats G₂/₃ and NO₃⁻ as uncertain measurements (errors-in-variables). To reconstruct, TEXAS averages (marginalizes) over draws of this calibration posterior; see [Stan models](stan_models.md) and [How marginalization works](marginalization_explainer.md). To try the curve yourself, see the [calibration curve explorer](calibration_curve_explorer.ipynb) or the in-browser walkthrough [From GDGTs to sea temperature](gdgts_to_temperature.md).

TEXAS adds the two nonthermal predictors to explain the variance that temperature leaves in GDGT distributions, the proxy residuals:

(sensor-aoa)=
#### AOA ecology: the GDGT-2/GDGT-3 ratio

Deep-water (Water Column B) ammonia-oxidizing archaea make more GDGT-2 relative to GDGT-3 than shallow-water (Water Column A) archaea. A high G₂/₃ therefore marks a sedimentary GDGT pool with more deep-water input, whose GDGTs record colder water than the surface ([Taylor et al., 2013](https://doi.org/10.1016/j.gloplacha.2013.06.011); [Rattanasriampaipong et al., 2022](https://doi.org/10.1073/pnas.2123193119)). Its coefficient $\gamma_{\text{G23}}$ is in °C per unit of G₂/₃. G₂/₃ comes from the same GDGT measurement as Scaled RI, so every sample has it.

(sensor-nutrient)=
#### Nutrient level: surface ocean nitrate

Low nitrate shifts GDGT distributions toward more rings at a given temperature ("nutrient stress"; [Rattanasriampaipong et al., 2025](https://doi.org/10.1029/2025GL115237)). The term acts only below 1.0 µmol/L, where $\log_{10}[\text{NO}_3^-]$ is negative; above the cutoff it is switched off. Its coefficient $\gamma_{\text{NO}_3}$ is in °C per log₁₀ unit. For modern sites, `lookup_modern_no3` reads nitrate from a gridded climatology; for the past, pass `no3=10` (above the cutoff) to switch the term off.

(psm-archive)=
## Archive: post-depositional processes

The archive model describes what happens to GDGTs after they reach the seafloor: diagenesis, lateral transport and bioturbation. **TEXAS does not implement it.** TEXAS-PSM is designed to be paired with existing sediment archive models, such as TURBO2 ([Trauth, 2013](https://doi.org/10.1016/j.cageo.2013.05.003)), where archive smoothing matters.

(psm-observation)=
## Observation: measurement and age

The observation model describes the measurement itself. TEXAS propagates **analytical** uncertainty: the calibration includes each site's measurement error (`sd_proxyObs`, 0.03 Scaled RI by default) alongside the curve's own scatter, and the reconstruction accepts a per-sample uncertainty. Age-model uncertainty is left to age–depth tools such as [Bchron](https://cran.r-project.org/package=Bchron) or [Bacon](https://cran.r-project.org/package=rbacon), whose age ensembles can be carried through a TEXAS reconstruction.
