# Appendix C — copy-paste LaTeX (complete section)

Your current text with C2.4 tightened. Each paragraph is a single line; tables and `verbatim` blocks keep their line structure. What was cut, and why, is listed at the bottom.

---

```latex
\section{Running TEXAS on your own data}
\label{sec:AppendixC-using-TEXAS}

This appendix guides a user on how to use the TEXAS Python package to reconstruct ocean temperatures with one's own GDGT record. The full documentation for the \texttt{texas-psm} package can be found at \url{https://paleolipidrr.github.io/TEXAS/}.

\subsection{Installation}

TEXAS is a Python package. It is installed with \mbox{\texttt{pip install texas-psm}}, and the calibration models are compiled Stan programs, so a working CmdStan toolchain (version 2.23 or later; developed against 2.36) and a C++ compiler are also required. Two commands cover the setup: \mbox{\texttt{texas-install-cmdstan}} performs a one-call install if CmdStan is not already present, and \mbox{\texttt{texas-doctor}} reports on the whole toolchain---including, Python package, CmdStan path and version, compiler, and cache directories---and is the first thing to run if anything fails. Users who prefer not to manage a compiler can use the Docker image or the Colab-ready quickstart notebook in the repository, both of which ship a working toolchain. Pre-generated \mbox{\texttt{conda-lock}} and \mbox{\texttt{uv}} lock files are provided for reproducible python environments.

The calibration posterior used by default is distributed with the package, so a reconstruction can be run immediately after installation, with no download and no network access. The remaining calibrations---the single-predictor and temperature-only specifications, and the complete archival copies of the default pair---are retrieved on demand from the Zenodo archive via \mbox{\texttt{TEXAS.download\_posteriors()}}. All of them correspond to the forward-model calibrations described in \textbf{Section \ref{sec:TEXAS-models}} and illustrated in \mbox{\textbf{\ref{sec:AppendixA}}}, and they are required as inputs for the inverse-model temperature reconstructions (\textbf{C2.4}).

\subsection{Prerequisites}

\textbf{Table \ref{tab:texas-ingredients}} lists the mandatory and optional input parameters for the temperature prediction function \texttt{predict\_T\_from\_proxyObs()}.

\vspace{0.5em}
\begin{table}[!h]
\caption{Inputs required for a TEXAS reconstruction. Only the first two groups must be assembled by the user; the calibration posterior is required by the inversion but defaults to the one distributed with the package.}
\label{tab:texas-ingredients}
\centering
\small
\begin{tabular}{p{0.3\textwidth}p{0.10\textwidth}p{0.5\textwidth}}
\toprule
\textbf{Input} & \textbf{Status} & \textbf{Notes} \\
\midrule
Six isoGDGT abundances & Required & Either peak areas or fractional abundances \\
Temperature prior ($\mu_T$, $\sigma_T$) & Required & In $\degree$C unit. $\mu_T$ can be a single, time-invariant value or a per-sample, time-variant array; $\sigma_T$ is a single value shared across samples \\
GDGT-2/GDGT-3 (G23) & Optional & Calculated from the same set of six compounds \\
$[$NO$_{\text{3}}^-]$ & Optional & May be supplied as a single, time-invariant value or a per-sample, time-varying array \\
Forward calibration posterior & Required & The full multivariate calibration is set to default and is distributed with the package \\
\bottomrule
\end{tabular}
\end{table}
\vspace{0.5em}

\textbf{C2.1 | Calculate Scaled RI (Required)}

Because TEXAS uses the Scaled RI as its predictand (\textbf{Section \ref{sec:RI-as-predictand}}), you must provide either absolute or relative abundances for the six isoprenoid GDGTs: GDGT-0, GDGT-1, GDGT-2, GDGT-3, Cren, and Cren'. Similar to TEX$_{86}$, the Scaled RI is a dimensionless ratio that varies between 0 and 1. To compute this index, the user can call the \texttt{compute\_scaledRI} function. The \texttt{cren\_weight} argument in the function signature specifies the weighting factor applied to the cren and cren' fractions; it defaults to 3.

\begin{verbatim}
    import pandas as pd
    from TEXAS import compute_scaledRI
    
    df = pd.read_csv("my_gdgt_data.csv")
    
    df["scaledRI_cren3"] = compute_scaledRI(
        df["GDGT-0"], df["GDGT-1"], df["GDGT-2"], df["GDGT-3"],
        df["cren"],   df["cren_prime"],
        # cren_weight = 3 by default
    )
\end{verbatim}

\textbf{C2.2 | Set the temperature prior (Required)}

The user needs to supply a prior for temperature: a mean ($\mu_T$; \texttt{prior\_mu\_t}) and a standard deviation ($\sigma_T$; \texttt{prior\_sigma\_t}), in \mbox{$\degree$C}. This is the expectation the reconstruction starts from, not a constraint on the answer, and a deliberately wide prior is the appropriate choice when little is known about the site. The $\mu_T$ parameter can be passed as a single value (\textit{time-invariant}) or a per-sample array (\textit{time-variant}); $\sigma_T$ is a single value shared across all samples.

\textbf{C2.3 | Secondary nonthermal predictors (Optional)}

Because the TEXAS sensor incorporates both G23 and $[$NO$_{\text{3}}^-]$ into its calibration scheme, users may supply these variables to account for nonthermal influences that could otherwise bias the reconstructed temperatures (\textbf{Section~\ref{sec:TEXAS-models-bottomlayer}}). Similar to $\mu_T$, each of these predictors can be provided either as a single constant value or as an array specified for each sample.

The G23 ratio can be directly derived from the individual GDGT fractional abundances. For [NO$_{3}^{-}$], users may either (i) input a modern concentration obtained from the associated CMEMS ocean nitrate product we provide, or (ii) supply the modern latitude/longitude to \texttt{predict\_T\_from\_proxyObs} to have the built-in helper routine interpolates the modern [NO$_{3}^{-}$] to those coordinates. The $[$NO$_{\text{3}}^-]$ correction is applied only to values inside \mbox{(0, 1.0]}~\mbox{$\mu$mol$\cdot$L$^{\text{-1}}$}, the threshold recorded in the calibration posterior itself. To effectively turn off the [NO$_{3}^{-}$] correction, users can therefore set [NO$_{3}^{-}$] = 10, i.e., a value that exceeds the [NO$_{3}^{-}$] $<$ 1 threshold.

\textbf{C2.4 | Forward-model posterior distributions of calibration parameters (Required; supplied by default)}

Every reconstruction is conditioned on a forward calibration posterior: the MCMC draws of the calibration parameters $\boldsymbol{\theta}$ = ($T_{\text{0}}$, $k$, $b$, $\nu$, $\gamma_{\text{G}_{\text{2/3}}}$, $\gamma_{\text{NO}_3^-}$, $\sigma_{proxyObs}$) reported in \textbf{Section~\ref{sec:TEXAS-models}}. \texttt{predict\_T\_from\_proxyObs} does not refit the calibration; it draws $M$ parameter sets from the posterior and marginalizes over them (\textbf{Equation~\ref{eq:post-pred}}), reading the model structure from the posterior itself to select the matching \texttt{invT} Stan program. The full multivariate calibration \mbox{\texttt{tx.GHEB.sst.sri03.G23-N1p0}}---the specification used for the case studies in \textbf{Section~\ref{sec:paleo-applications}}---is distributed with the package and is used whenever no other posterior is named; \mbox{\texttt{temptype="thermoT"}} selects its thermocline counterpart, \mbox{\texttt{tx.GHEB.thm.sri03.G23-N1p0}}.

Posteriors are identified by a case name of the form \mbox{\texttt{tx.\textit{compset}.\textit{temperature}.\textit{proxy}.\textit{predictors}}}. The compset is a four-letter code carrying one modeling decision per position (\textbf{Table~\ref{tab:texas-compset}}); the remaining fields record the calibration target (\texttt{sst}, or \texttt{thm} for thermo-T), the predictand (\texttt{sri03} = Scaled RI at \mbox{\texttt{cren\_weight = 3}}), and the nonthermal predictors (\texttt{G23}; \texttt{N1p0} = \mbox{[NO$_{\text{3}}^-$]} with its threshold of 1.0~\mbox{$\mu$mol$\cdot$L$^{\text{-1}}$}, the \texttt{p} standing for the decimal point; \texttt{p0} = none).

\vspace{0.5em}
\begin{table}[!h]
\caption{The four positions of the compset code. Letters in bold are those used by the calibrations published with this study; the remainder denote model variants retained in the package for comparison.}
\label{tab:texas-compset}
\centering
\small
\begin{tabular}{p{0.06\textwidth}p{0.18\textwidth}p{0.68\textwidth}}
\toprule
\textbf{Pos.} & \textbf{Decision} & \textbf{Letters} \\
\midrule
1 & Curve & \textbf{\texttt{G}} generalized logistic; \texttt{L} logistic; \texttt{N} linear \\
2 & Training data & \textbf{\texttt{H}} hierarchical coretop, conditioned on culture and mesocosm hyperpriors; \textbf{\texttt{C}} culture and mesocosm (top layer); \texttt{J} culture, mesocosm and coretop pooled; \texttt{T} coretop only \\
3 & Estimator & \textbf{\texttt{E}} two-stage prior approximation with error-in-variables regression; \textbf{\texttt{P}} two-stage prior approximation; \textbf{\texttt{D}} full hierarchical \\
4 & Nonthermal terms & \textbf{\texttt{B}} $T_{\text{0}}$-shift parameterization ($\gamma$ on $T_{\text{0}}$); \textbf{\texttt{U}} univariate, temperature only; \texttt{A} additive ($\beta$ on $\mu$; used by the preprint manuscript) \\
\bottomrule
\end{tabular}
\end{table}
\vspace{0.5em}

\textbf{Table~\ref{tab:texas-posteriors}} lists the published calibrations. Those not distributed with the package are fetched once and cached:

\begin{verbatim}
    from TEXAS import list_posteriors, download_posteriors

    # what is available without a download
    list_posteriors("forward")

    # any other calibration, fetched once and cached
    download_posteriors(["tx.GHPU.sst.sri03.p0"])
\end{verbatim}

\vspace{0.5em}
\begin{table}[!h]
\caption{Forward calibration posteriors published with this study, each available for both calibration targets (\texttt{sst}, sea-surface temperature; \texttt{thm}, surface-to-thermocline integrated temperature). The full multivariate pair ships with the package, with the error-in-variables latent variables removed; the complete archival copies, and the remaining calibrations, are on Zenodo.}
\label{tab:texas-posteriors}
\centering
\small
\begin{tabular}{p{0.31\textwidth}p{0.20\textwidth}p{0.39\textwidth}}
\toprule
\textbf{Case name} & \textbf{Nonthermal Predictors} & \textbf{Inputs the user supplies} \\
\midrule
\texttt{tx.GHEB.sst.sri03.G23-N1p0} \newline \texttt{tx.GHEB.thm.sri03.G23-N1p0} & G23 and $[$NO$_{\text{3}}^-]$ & Scaled RI, G23, $[$NO$_{\text{3}}^-]$ \textbf{(default; bundled)} \\
\texttt{tx.GHEB.sst.sri03.G23} \newline \texttt{tx.GHEB.thm.sri03.G23} & G23 & Scaled RI, G23 \\
\texttt{tx.GHEB.sst.sri03.N1p0} \newline \texttt{tx.GHEB.thm.sri03.N1p0} & $[$NO$_{\text{3}}^-]$ & Scaled RI, $[$NO$_{\text{3}}^-]$ \\
\texttt{tx.GHPU.sst.sri03.p0} \newline \texttt{tx.GHPU.thm.sri03.p0} & None (temperature only) & Scaled RI \\
\bottomrule
\end{tabular}
\end{table}
\vspace{0.5em}

Two constraints apply to any choice. The proxy convention must match: every posterior reported here is calibrated on Scaled RI computed with \mbox{\texttt{cren\_weight = 3}} (\textbf{C2.1}), and an index built on another convention is expressed on a different scale. And with a multivariate calibration, a predictor the user does not supply is taken to be zero: for \mbox{[NO$_{\text{3}}^-$]} that is equivalent to switching the correction off (\textbf{C2.3}), but for G23 it asserts a ratio of zero and biases the reconstruction cold by $\gamma_{\text{G}_{\text{2/3}}}$ per unit of the true ratio ($\approx$0.6~$\degree$C per unit for the SST calibration). The package warns when this happens; G23 should always be supplied alongside a multivariate calibration.

Users who wish to calibrate on their own training data, rather than apply ours, can do so with \mbox{\texttt{build\_fwd\_data()}} and \mbox{\texttt{get\_posterior()}}.

\textbf{C2.5 | Run the reconstruction}

With the four ingredients in hand, a reconstruction is a single call. Omitting \texttt{fwd\_posterior} selects the default calibration of \textbf{C2.4}, so nothing is downloaded; nothing is written to disk unless \mbox{\texttt{save\_results=True}} is passed.

\begin{verbatim}
    from TEXAS import predict_T_from_proxyObs

    result = predict_T_from_proxyObs(
        proxyObs      = df["scaledRI_cren3"].values,
        prior_mu_t    = 20.0,   # degrees C; scalar, or one value per sample
        prior_sigma_t = 10.0,   # deliberately wide
        gdgt23ratio   = df["gdgt23ratio"].values,
        no3           = 10.0,   # above the 1.0 umol/L threshold: correction off
    )

    result["p50"]                 # median reconstructed temperature, per sample
    result["p16"], result["p84"]  # 68% credible interval
\end{verbatim}

The returned object holds the input observations, temperature percentiles from p1 to p99 for every sample, and the run metadata, which records the calibration the reconstruction was conditioned on so that a result remains traceable to its parent afterwards. Where the local posterior cache is unavailable, as in a hosted notebook, an already-opened dataset may be passed to \mbox{\texttt{fwd\_posterior}} in place of a name, and no file access is attempted.

\subsection{Documentation}

Full API (Application Programming Interface) documentation, guides, and an interactive tutorial are published at \mbox{\url{https://paleolipidrr.github.io/TEXAS/}}, and the repository README at \mbox{\url{https://github.com/PaleoLipidRR/TEXAS}} carries the quickstart. The notebooks that generate every figure in this manuscript are archived with the software release, so any analysis reported here can be reproduced end to end.
```

---

## What was cut from C2.4

Nine paragraphs down to five; the two tables and the two code blocks are unchanged apart from the caption noted below.

| Cut | Where it already lives |
|---|---|
| The paragraph arguing why the multivariate model is the default (nonthermal effects are in the data whether or not they are modelled; a temperature-only fit absorbs them into the thermal parameters) | \textbf{Section~\ref{sec:TEXAS-models-bottomlayer}} and the results — the appendix now just states which calibration is the default |
| The three "legitimate departures" from the default (thermocline target, no defensible nitrate, no GDGT-2/3) | readable straight off \textbf{Table~\ref{tab:texas-posteriors}} |
| "the SST and thermo-T calibrations differ systematically ($T_0$ = 34.8 vs 33.0 °C)" | \textbf{\ref{sec:AppendixA}} and the parameter tables |
| The standalone paragraph on the package reading the model structure from the file to pick the \texttt{invT} program | folded into one clause of the opening paragraph |
| "documented in the package guides rather than here" | the Documentation subsection says this once already |
| The per-site latent-variable explanation of the bundled vs archival copies | moved into the \textbf{Table~\ref{tab:texas-posteriors}} caption |

Kept, because a user cannot get them elsewhere: the case-name grammar and compset table, the list of published calibrations, the `cren_weight` matching constraint, and the G23-defaults-to-zero trap.
