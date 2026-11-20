# Calibration data

The explorer below starts with the dataset the bundled TEXAS calibration was fitted to: coretop, culture and mesocosm samples, screened with the Mahalanobis distance and gridded to 0.25° cells (manuscript Section 5), in the manuscript's data-type colors. Buttons switch to the data and fitted curves of the calibrations before it: the original linear TEX₈₆ calibration (Schouten et al., 2002), TEX₈₆ᴴ (Kim et al., 2010) and BAYSPAR (Tierney & Tingley, 2014), with BAYSPAR's three regions from the manuscript's Fig. 1a. The table names the original study behind every TEXAS sample, linked to the paper, and which earlier calibrations also used it.

```{raw} html
<p style="margin:1rem 0 0;">
  <a href="_static/calibration-data.html" target="_blank" rel="noopener"><strong>Open the explorer full-page →</strong></a>
</p>
<iframe src="_static/calibration-data.html"
        title="TEXAS calibration data: scatter plot and map"
        style="width:100%;height:92vh;border:1px solid var(--pst-color-border,#ccc);border-radius:4px;margin-top:1rem;"
        loading="lazy"></iframe>
```

To work with the data yourself, download it with `TEXAS.download_training_data()`; the file shown here is `ds_gridded_screened_global_compilation_finalized.csv`. How each data type enters the calibration is described on the [Sensor models](sensor_models.md) page.
