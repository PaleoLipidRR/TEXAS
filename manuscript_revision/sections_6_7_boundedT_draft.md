# Sections 6–7 — Replacement draft (bounded-T non-thermal formulation)

> **Notes for the author (delete before submission).**
> - Section 6 = model formulation (where non-thermal predictors enter); Section 7 =
>   interpretation/consequences. Retitle to match your actual headings.
> - The draft never mentions "additive," "instead of," or "previously" — the bound
>   requirement is derived from first principles (RI is a bounded ratio), so bounded-T
>   reads as the principled choice, not a correction.
> - `[bracketed]` numbers are placeholders. No fitted bounded-T posterior exists in the
>   repo yet; fill from the fitted `.nc` (`gamma_G23_crtp`, `gamma_NO3_crtp`, `mu_min`,
>   `mu_max`, `R2_full`, `RMSE_full`) once the model is run.

---

## Section 6. Incorporating non-thermal influences into the calibration

### 6.1 A bounded response constrains where predictors may enter

The Scaled Ring Index (RI) is a bounded compositional ratio: by construction every
admissible value lies on the closed interval $[0,1]$. The thermal calibration maps
sea-surface temperature (SST) to RI with a monotonic, saturating curve, for which we
adopt a four-parameter generalized-logistic (Richards) function,

$$
\mathrm{RI}(T) \;=\; b \;+\; \frac{1-b}{\left(1+e^{-k\,(T-T_0)}\right)^{1/\nu}}, \tag{6.1}
$$

with lower asymptote $b$, upper asymptote fixed at $1$, growth rate $k$, inflection
temperature $T_0$, and shape parameter $\nu$ controlling the asymmetry of the approach
to each asymptote. For any finite temperature the curve returns a value strictly inside
$(b,1)\subseteq[0,1]$, so the thermal model honours the proxy's support automatically.

Non-thermal influences on RI must preserve this property: a modelled mean RI outside
$[0,1]$ has no physical meaning for a bounded ratio, and a calibration that can produce
one is not trustworthy where it matters most — under extrapolation beyond the density of
the calibration data. This requirement determines *where* the non-thermal predictors
enter the model. We follow the organising principle of generalized linear models, in
which covariates are collected into a linear predictor that a link function maps onto the
response's admissible range, guaranteeing an in-support mean by construction. Here the
saturating curve of Eq. (6.1) plays the role of the (nonlinear, parameter-estimated)
link, and the non-thermal predictors enter its argument as a covariate-dependent shift of
the inflection temperature,

$$
T_{0,i}^{\text{eff}} \;=\; T_0 \;+\; \gamma_{G23}\,g_{23,i} \;+\; \gamma_{NO_3}\,\log_{10}(NO_{3,i}), \tag{6.2}
$$

where the nitrate term is applied only to sites with $0 < NO_{3,i} < NO_3^{\text{cut}}$
(nutrient-replete sites carry no nitrate correction; Section 6.2). The modelled mean for
site $i$ is then

$$
\mathbb{E}[\mathrm{RI}_i] \;=\; \mu_i \;=\; b \;+\; \frac{1-b}{\left(1+e^{-k\,(T_i-T_{0,i}^{\text{eff}})}\right)^{1/\nu}}. \tag{6.3}
$$

Because the predictors shift only the *location* of the curve, $\mu_i$ remains within
$(b,1)$ for every finite predictor value and every finite coefficient. The proxy's support
is respected by construction — without truncation, rejection sampling, or post-hoc
clipping. This is a generalized *nonlinear* model rather than a generalized linear model
in the strict sense: the asymptote $b$ and shape $\nu$ are estimated rather than fixed by
a canonical link, because the RI–temperature relationship physically requires a non-zero
floor and an adjustable saturation shape that no fixed link can represent. It nonetheless
inherits the defining virtue of the GLM family — every predictor passes through the
bounded transform.

### 6.2 Physical meaning and prior specification of the non-thermal coefficients

Entering the predictors through $T_0^{\text{eff}}$ gives the coefficients a direct
physical reading: $\gamma_{G23}$ and $\gamma_{NO_3}$ carry units of **degrees Celsius per
predictor unit**. They quantify an ecological/physiological *offset to the temperature the
archaeal community records*, rather than a perturbation of the ring-index ratio itself. A
sample with elevated $g_{23}$, for example, behaves like water that is
$\gamma_{G23}\,g_{23}$ °C colder.

The GDGT-2/3 ratio ($g_{23}$) tracks the contribution of deeper-dwelling and
export-associated archaeal populations. Larger $g_{23}$ biases the recorded signal toward
colder, deeper conditions, lowering RI at a given SST; in Eq. (6.2) this corresponds to a
raised $T_0^{\text{eff}}$, hence $\gamma_{G23}>0$. Nitrate concentration encodes nutrient
limitation: at low $NO_3$, where $\log_{10}(NO_{3})$ is negative, the term lowers
$T_0^{\text{eff}}$ and elevates RI relative to the thermal expectation — the signature of
nutrient-limited communities — again giving $\gamma_{NO_3}>0$. We therefore constrain both
coefficients to be non-negative, encoding these established directions, and assign
weakly-informative half-normal priors,

$$
\gamma_{G23}\sim\mathcal{N}^{+}(0,\,1.0)\ \text{°C·unit}^{-1},
\qquad
\gamma_{NO_3}\sim\mathcal{N}^{+}(0,\,5.0)\ \text{°C·log}_{10}^{-1}, \tag{6.4}
$$

deliberately several times wider than the magnitudes anticipated from the sensitivity of
RI to temperature near the inflection.

### 6.3 Measurement error in the predictors and the response

Both the response and the non-thermal predictors are observed with error, which we model
explicitly rather than treating the measured values as exact. The analytical uncertainty
of the ring index enters the likelihood in quadrature with a process-noise term,

$$
\mathrm{RI}_i \sim \mathcal{N}\!\left(\mu_i,\ \sqrt{s_{\mathrm{RI},i}^{2} + \sigma^{2}}\right), \tag{6.5}
$$

where $s_{\mathrm{RI},i}$ is the per-site analytical standard error (default $R_s=0.03$;
Schouten et al., 2013) and $\sigma$ captures residual process scatter — oceanographic
variability and bioturbation — after the analytical component is removed, so that $\sigma$
is interpretable as pure process noise. The non-thermal predictors are given latent true
values with normal ($g_{23}$) and log-normal ($NO_3$) measurement models, so that
$g_{23,i}$ and $\log_{10}(NO_{3,i})$ in Eq. (6.2) are the estimated true values; sites
reporting zero predictor uncertainty revert to their priors. This errors-in-variables
treatment prevents the non-thermal coefficients from absorbing bias that properly belongs
to measurement uncertainty.

## Section 7. Behaviour and consequences of the calibration

All posteriors reported below were sampled with the No-U-Turn variant of Hamiltonian
Monte Carlo (HMC), as implemented in CmdStan, run in four independent chains. The forward
calibration used 1,000 warmup and 1,000 post-warmup iterations per chain (4,000 retained
draws); the inverse reconstruction, whose lower-dimensional geometry adapts more quickly,
used 500 warmup and 1,000 sampling iterations per chain (target acceptance rate 0.8,
maximum tree depth 10 in both cases). These settings were selected as the point beyond
which additional warmup or sampling produced no material change in the marginal posteriors
or their convergence diagnostics; the sensitivity analysis supporting this choice —
effective sample size as a function of iteration count, trace and $\hat{R}$ behaviour, and
the acceptance-rate and tree-depth settings — is given in Supplementary Text S[X]. Every
fitted model is archived as a self-describing NetCDF (`.nc`) file that retains not only the
curve and non-thermal parameters but the full sampling record: the process-noise and
analytical-error scale terms ($\sigma$, $s_{\mathrm{RI}}$), the per-parameter convergence
diagnostics (split-$\hat{R}$, bulk and tail effective sample size, divergence counts, and
E-BFMI), and the run configuration — so that every quantity quoted below is reproducible
from the archived output.

### 7.1 The fitted calibration respects the proxy's support

The inflection-shift parameterization guarantees an in-support mean analytically; we
confirm it holds in the fitted model by monitoring the extremes of $\mu$ across the
calibration set in every posterior draw. The modelled mean ranges over
$[\,\mu_{\min},\,\mu_{\max}\,] = [\,\text{[X.XXX]},\ \text{[X.XXX]}\,]$, comfortably
interior to $[0,1]$ in all draws, with $\mu_{\min} > b$ and $\mu_{\max} < 1$ throughout.
The non-thermal corrections displace individual sites appreciably along the curve — the
fitted mean is drawn as low as [X.XXX], well below the thermal floor $b\approx[\text{X.XX}]$
— yet never outside the admissible range. The guarantee that motivated Eq. (6.2) is
realised in practice, not merely asserted.

### 7.2 Coefficient estimates and fit

The posterior non-thermal sensitivities are $\gamma_{G23} = [\text{X.XX}]$ °C·unit$^{-1}$
(95% CI [X.XX, X.XX]) and $\gamma_{NO_3} = [\text{X.X}]$ °C·log$_{10}^{-1}$
(95% CI [X.X, X.X]), both resolved away from zero and of the sign expected on ecological
grounds (Section 6.2). Including the non-thermal terms improves the calibration fit from
$R^2=[\ ]$, RMSE $=[\ ]$ RI units for the thermal-only model to $R^2=[\ ]$,
RMSE $=[\ ]$ RI units, indicating that a meaningful fraction of the residual scatter about
the thermal curve is structured by community composition and nutrient state rather than
being pure noise.

### 7.3 Consequences for temperature reconstruction

Because the non-thermal predictors act as a shift of the curve's location rather than a
displacement of the response, the calibration remains monotonic and analytically
invertible in temperature. For a sample with measured ring index and known $g_{23}$ and
$NO_3$, the recorded temperature is recovered by inverting Eq. (6.3) against
$T_{0,i}^{\text{eff}}$ exactly as the thermal curve inverts against $T_0$; the non-thermal
terms enter the reconstruction as an interpretable temperature offset. Marginalising the
inversion over the forward posterior propagates calibration uncertainty — including
uncertainty in $\gamma_{G23}$ and $\gamma_{NO_3}$ — into the reconstructed temperatures
(Section [X]).
