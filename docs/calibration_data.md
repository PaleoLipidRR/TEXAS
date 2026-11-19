# Calibration data

The bundled TEXAS calibration was fitted to a global compilation of coretop, culture and mesocosm samples, screened with the Mahalanobis distance and gridded to 0.25° cells (manuscript Section 5). The explorer below plots every one of those samples: temperature against Scaled RI or TEX₈₆ beside a map of the coretop sites, in the manuscript's data-type colors. Hover a sample to find it in both panels, switch the axes between SST and Thermo-T, or color the points by GDGT-2/GDGT-3 or nitrate to see the nonthermal predictors TEXAS uses.

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
