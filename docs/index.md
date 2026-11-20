# TEXAS

**TetraEther indeX of Ammonia oxidizerS — Bayesian proxy system model for TEX86 paleothermometry**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/PaleoLipidRR/TEXAS/blob/main/LICENSE) [![PyPI](https://img.shields.io/pypi/v/texas-psm)](https://pypi.org/project/texas-psm/) [![Zenodo](https://img.shields.io/badge/data-10.5281%2Fzenodo.19666744-blue.svg)](https://doi.org/10.5281/zenodo.19666744)

TEXAS-PSM is a **Bayesian proxy system model (PSM)** for isoGDGT-based (TEX₈₆-family) ocean temperature reconstruction, built around the **TEXAS** sensor model. TEXAS links temperature to the **Scaled Ring Index** (Scaled RI) through a hierarchical generalized-logistic (S-shaped) curve, fitted in Stan to culture, mesocosm, and coretop data. Two optional nonthermal predictors account for archaeal community structure (the GDGT-2/GDGT-3 ratio, G₂/₃) and nutrient availability (nitrate, NO₃⁻). The package reconstructs either sea surface temperature (SST) or surface-to-thermocline temperature (Thermo-T), with full posterior uncertainty.

Of the three PSM submodels (sensor, archive, observation), this package implements the **sensor** and propagates **analytical** measurement uncertainty; sediment-archive effects (bioturbation, diagenesis) and age-model uncertainty are left to dedicated tools.

The result is a **posterior distribution of temperature** for each downcore sample, not just a point estimate with a fixed RMSE.

To see how one measurement becomes that distribution, without installing anything, try [From GDGTs to sea temperature](gdgts_to_temperature.md).

---

## The TEXAS-PSM framework

TEXAS-PSM links four components through three submodels, after Figure 2 of the manuscript. Click any card for its equations and references on the [Sensor models](sensor_models.md) page.

<div class="psm-schematic" role="group" aria-label="TEXAS-PSM framework schematic">
<p class="psm-panel"><span class="psm-panel-letter">a</span> TEXAS-PSM: a proxy system model for TetraEther indeX of Ammonia oxidizerS</p>
<div class="psm-a">
<a class="psm-box psm-c-env" style="grid-column:1/3" href="sensor_models.html#psm-environment"><span class="psm-head">Environment</span><span class="psm-body">Temperature<br>AOA ecology<br>Nutrient level</span></a>
<a class="psm-box psm-c-env" style="grid-column:3/5" href="sensor_models.html#psm-sensor"><span class="psm-head">Sensor</span><span class="psm-body">GDGT compositions</span></a>
<a class="psm-box psm-c-gray" style="grid-column:5/7" href="sensor_models.html#psm-archive"><span class="psm-head">Archive</span><span class="psm-body">Post-depositional processes<span class="psm-tag">not implemented</span></span></a>
<a class="psm-box psm-c-gray" style="grid-column:7/9" href="sensor_models.html#psm-observation"><span class="psm-head">Observation</span><span class="psm-body">Instrumental errors<br>Analytical errors<br>Age model<span class="psm-tag">analytical only</span></span></a>
<span class="psm-bracket psm-br-env" style="grid-column:2/4" aria-hidden="true"></span>
<span class="psm-bracket psm-br-gray" style="grid-column:4/6" aria-hidden="true"></span>
<span class="psm-bracket psm-br-gray" style="grid-column:6/8" aria-hidden="true"></span>
<a class="psm-sub psm-sub-on" style="grid-column:2/4" href="sensor_models.html#psm-sensor">sensor model</a>
<a class="psm-sub" style="grid-column:4/6" href="sensor_models.html#psm-archive">archive model</a>
<a class="psm-sub" style="grid-column:6/8" href="sensor_models.html#psm-observation">observation model</a>
</div>
<p class="psm-panel"><span class="psm-panel-letter">b</span> The sensor model</p>
<div class="psm-b-top">
<a class="psm-plain psm-temp" href="sensor_models.html#psm-environment"><svg class="psm-thermo" viewBox="0 0 40 100" aria-hidden="true" focusable="false"><rect x="12" y="4" width="16" height="66" rx="8" fill="none" stroke="currentColor" stroke-width="3"/><circle cx="20" cy="80" r="14" fill="var(--texas-red)" stroke="currentColor" stroke-width="3"/><rect x="16" y="26" width="8" height="50" rx="4" fill="var(--texas-red)"/></svg><span class="psm-big">Temperature</span></a>
<span class="psm-harrow" aria-hidden="true"></span>
<a class="psm-plain psm-gdgts" href="gdgts_to_temperature.html"><span class="psm-gdgt"><span class="psm-gdgt-name">GDGT-0</span><svg class="psm-gdgt-svg" viewBox="0 0 564.6 112.0" aria-hidden="true" focusable="false">  <g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"> <polyline points="72.18,32.80 86.03,24.80 99.89,32.80 113.75,24.80 127.60,32.80 141.46,24.80 155.32,32.80 169.17,24.80 183.03,32.80 196.89,24.80 210.74,32.80 224.60,24.80 238.45,32.80 252.31,24.80 266.17,32.80 280.02,24.80 293.88,32.80 307.74,24.80 321.59,32.80 335.45,24.80 349.31,32.80 363.16,24.80 377.02,32.80 390.88,24.80 404.73,32.80 418.59,24.80 432.44,32.80 446.30,24.80 460.16,32.80 474.01,24.80 487.87,32.80 501.73,24.80"/> <polyline points="99.89,32.80 99.89,44.80"/> <polyline points="155.32,32.80 155.32,44.80"/> <polyline points="210.74,32.80 210.74,44.80"/> <polyline points="266.17,32.80 266.17,44.80"/> <polyline points="307.74,24.80 307.74,12.80"/> <polyline points="363.16,24.80 363.16,12.80"/> <polyline points="418.59,24.80 418.59,12.80"/> <polyline points="474.01,24.80 474.01,12.80"/> <polyline points="72.18,79.20 86.03,87.20 99.89,79.20 113.75,87.20 127.60,79.20 141.46,87.20 155.32,79.20 169.17,87.20 183.03,79.20 196.89,87.20 210.74,79.20 224.60,87.20 238.45,79.20 252.31,87.20 266.17,79.20 280.02,87.20 293.88,79.20 307.74,87.20 321.59,79.20 335.45,87.20 349.31,79.20 363.16,87.20 377.02,79.20 390.88,87.20 404.73,79.20 418.59,87.20 432.44,79.20 446.30,87.20 460.16,79.20 474.01,87.20 487.87,79.20 501.73,87.20"/> <polyline points="99.89,79.20 99.89,67.20"/> <polyline points="155.32,79.20 155.32,67.20"/> <polyline points="210.74,79.20 210.74,67.20"/> <polyline points="266.17,79.20 266.17,67.20"/> <polyline points="307.74,87.20 307.74,99.20"/> <polyline points="363.16,87.20 363.16,99.20"/> <polyline points="418.59,87.20 418.59,99.20"/> <polyline points="474.01,87.20 474.01,99.20"/> <polyline points="72.18,32.80 62.89,38.16"/> <polyline points="53.61,43.18 44.03,48.00"/> <polyline points="72.18,79.20 62.89,73.84"/> <polyline points="53.61,68.82 44.03,64.00"/> <polyline points="44.03,48.00 44.03,64.00"/> <polyline points="44.03,64.00 30.18,72.00 22.56,67.60"/> <polyline points="501.73,24.80 511.01,30.16"/> <polyline points="517.23,37.82 520.58,48.00"/> <polyline points="501.73,87.20 511.01,81.84"/> <polyline points="517.23,74.18 520.58,64.00"/> <polyline points="520.58,48.00 520.58,64.00"/> <polyline points="520.58,64.00 534.44,72.00 542.06,67.60"/> </g> <g fill="currentColor" font-family="Helvetica, Arial, sans-serif" font-size="11.5" text-anchor="middle" dominant-baseline="central"> <text x="58.32" y="40.80">O</text> <text x="58.32" y="71.20">O</text> <text x="12.80" y="64.00">HO</text> <text x="515.58" y="32.80">O</text> <text x="515.58" y="79.20">O</text> <text x="551.81" y="64.00">OH</text> </g></svg></span><span class="psm-gdgt"><span class="psm-gdgt-name">GDGT-1</span><svg class="psm-gdgt-svg" viewBox="0 0 564.6 112.0" aria-hidden="true" focusable="false">  <g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"> <polygon class="ring" fill="#FAC775" points="158.95,32.80 168.35,45.74 183.57,40.80 183.57,24.80 168.35,19.86"/> <polyline points="72.18,32.80 86.64,24.80 101.10,32.80 115.56,24.80 130.02,32.80 144.49,24.80 158.95,32.80"/> <polyline points="183.57,24.80 198.03,32.80 212.49,24.80 226.95,32.80 241.42,24.80 255.88,32.80 270.34,24.80 284.80,32.80 299.26,24.80 313.72,32.80 328.19,24.80 342.65,32.80 357.11,24.80 371.57,32.80 386.03,24.80 400.49,32.80 414.96,24.80 429.42,32.80 443.88,24.80 458.34,32.80 472.80,24.80 487.26,32.80 501.73,24.80"/> <polyline points="101.10,32.80 101.10,44.80"/> <polyline points="198.03,32.80 198.03,44.80"/> <polyline points="255.88,32.80 255.88,44.80"/> <polyline points="299.26,24.80 299.26,12.80"/> <polyline points="357.11,24.80 357.11,12.80"/> <polyline points="414.96,24.80 414.96,12.80"/> <polyline points="472.80,24.80 472.80,12.80"/> <polyline points="72.18,79.20 86.03,87.20 99.89,79.20 113.75,87.20 127.60,79.20 141.46,87.20 155.32,79.20 169.17,87.20 183.03,79.20 196.89,87.20 210.74,79.20 224.60,87.20 238.45,79.20 252.31,87.20 266.17,79.20 280.02,87.20 293.88,79.20 307.74,87.20 321.59,79.20 335.45,87.20 349.31,79.20 363.16,87.20 377.02,79.20 390.88,87.20 404.73,79.20 418.59,87.20 432.44,79.20 446.30,87.20 460.16,79.20 474.01,87.20 487.87,79.20 501.73,87.20"/> <polyline points="99.89,79.20 99.89,67.20"/> <polyline points="155.32,79.20 155.32,67.20"/> <polyline points="210.74,79.20 210.74,67.20"/> <polyline points="266.17,79.20 266.17,67.20"/> <polyline points="307.74,87.20 307.74,99.20"/> <polyline points="363.16,87.20 363.16,99.20"/> <polyline points="418.59,87.20 418.59,99.20"/> <polyline points="474.01,87.20 474.01,99.20"/> <polyline points="72.18,32.80 62.89,38.16"/> <polyline points="53.61,43.18 44.03,48.00"/> <polyline points="72.18,79.20 62.89,73.84"/> <polyline points="53.61,68.82 44.03,64.00"/> <polyline points="44.03,48.00 44.03,64.00"/> <polyline points="44.03,64.00 30.18,72.00 22.56,67.60"/> <polyline points="501.73,24.80 511.01,30.16"/> <polyline points="517.23,37.82 520.58,48.00"/> <polyline points="501.73,87.20 511.01,81.84"/> <polyline points="517.23,74.18 520.58,64.00"/> <polyline points="520.58,48.00 520.58,64.00"/> <polyline points="520.58,64.00 534.44,72.00 542.06,67.60"/> </g> <g fill="currentColor" font-family="Helvetica, Arial, sans-serif" font-size="11.5" text-anchor="middle" dominant-baseline="central"> <text x="58.32" y="40.80">O</text> <text x="58.32" y="71.20">O</text> <text x="12.80" y="64.00">HO</text> <text x="515.58" y="32.80">O</text> <text x="515.58" y="79.20">O</text> <text x="551.81" y="64.00">OH</text> </g></svg></span><span class="psm-gdgt"><span class="psm-gdgt-name">GDGT-2</span><svg class="psm-gdgt-svg" viewBox="0 0 564.6 112.0" aria-hidden="true" focusable="false">  <g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"> <polygon class="ring" fill="#FAC775" points="158.95,32.80 168.35,45.74 183.57,40.80 183.57,24.80 168.35,19.86"/> <polygon class="ring" fill="#FAC775" points="390.33,79.20 399.74,66.26 414.96,71.20 414.96,87.20 399.74,92.14"/> <polyline points="72.18,32.80 86.64,24.80 101.10,32.80 115.56,24.80 130.02,32.80 144.49,24.80 158.95,32.80"/> <polyline points="183.57,24.80 198.03,32.80 212.49,24.80 226.95,32.80 241.42,24.80 255.88,32.80 270.34,24.80 284.80,32.80 299.26,24.80 313.72,32.80 328.19,24.80 342.65,32.80 357.11,24.80 371.57,32.80 386.03,24.80 400.49,32.80 414.96,24.80 429.42,32.80 443.88,24.80 458.34,32.80 472.80,24.80 487.26,32.80 501.73,24.80"/> <polyline points="101.10,32.80 101.10,44.80"/> <polyline points="198.03,32.80 198.03,44.80"/> <polyline points="255.88,32.80 255.88,44.80"/> <polyline points="299.26,24.80 299.26,12.80"/> <polyline points="357.11,24.80 357.11,12.80"/> <polyline points="414.96,24.80 414.96,12.80"/> <polyline points="472.80,24.80 472.80,12.80"/> <polyline points="72.18,79.20 86.64,87.20 101.10,79.20 115.56,87.20 130.02,79.20 144.49,87.20 158.95,79.20 173.41,87.20 187.87,79.20 202.33,87.20 216.79,79.20 231.26,87.20 245.72,79.20 260.18,87.20 274.64,79.20 289.10,87.20 303.56,79.20 318.03,87.20 332.49,79.20 346.95,87.20 361.41,79.20 375.87,87.20 390.33,79.20"/> <polyline points="414.96,87.20 429.42,79.20 443.88,87.20 458.34,79.20 472.80,87.20 487.26,79.20 501.73,87.20"/> <polyline points="101.10,79.20 101.10,67.20"/> <polyline points="158.95,79.20 158.95,67.20"/> <polyline points="216.79,79.20 216.79,67.20"/> <polyline points="274.64,79.20 274.64,67.20"/> <polyline points="318.03,87.20 318.03,99.20"/> <polyline points="375.87,87.20 375.87,99.20"/> <polyline points="472.80,87.20 472.80,99.20"/> <polyline points="72.18,32.80 62.89,38.16"/> <polyline points="53.61,43.18 44.03,48.00"/> <polyline points="72.18,79.20 62.89,73.84"/> <polyline points="53.61,68.82 44.03,64.00"/> <polyline points="44.03,48.00 44.03,64.00"/> <polyline points="44.03,64.00 30.18,72.00 22.56,67.60"/> <polyline points="501.73,24.80 511.01,30.16"/> <polyline points="517.23,37.82 520.58,48.00"/> <polyline points="501.73,87.20 511.01,81.84"/> <polyline points="517.23,74.18 520.58,64.00"/> <polyline points="520.58,48.00 520.58,64.00"/> <polyline points="520.58,64.00 534.44,72.00 542.06,67.60"/> </g> <g fill="currentColor" font-family="Helvetica, Arial, sans-serif" font-size="11.5" text-anchor="middle" dominant-baseline="central"> <text x="58.32" y="40.80">O</text> <text x="58.32" y="71.20">O</text> <text x="12.80" y="64.00">HO</text> <text x="515.58" y="32.80">O</text> <text x="515.58" y="79.20">O</text> <text x="551.81" y="64.00">OH</text> </g></svg></span><span class="psm-gdgt"><span class="psm-gdgt-name">GDGT-3</span><svg class="psm-gdgt-svg" viewBox="0 0 564.6 112.0" aria-hidden="true" focusable="false">  <g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"> <polygon class="ring" fill="#FAC775" points="163.45,32.80 172.86,45.74 188.07,40.80 188.07,24.80 172.86,19.86"/> <polygon class="ring" fill="#FAC775" points="385.83,32.80 395.24,45.74 410.45,40.80 410.45,24.80 395.24,19.86"/> <polygon class="ring" fill="#FAC775" points="158.95,79.20 168.35,66.26 183.57,71.20 183.57,87.20 168.35,92.14"/> <polyline points="72.18,32.80 87.39,24.80 102.60,32.80 117.81,24.80 133.03,32.80 148.24,24.80 163.45,32.80"/> <polyline points="188.07,24.80 203.28,32.80 218.50,24.80 233.71,32.80 248.92,24.80 264.13,32.80 279.35,24.80 294.56,32.80 309.77,24.80 324.98,32.80 340.19,24.80 355.41,32.80 370.62,24.80 385.83,32.80"/> <polyline points="410.45,24.80 425.67,32.80 440.88,24.80 456.09,32.80 471.30,24.80 486.51,32.80 501.73,24.80"/> <polyline points="102.60,32.80 102.60,44.80"/> <polyline points="203.28,32.80 203.28,44.80"/> <polyline points="264.13,32.80 264.13,44.80"/> <polyline points="309.77,24.80 309.77,12.80"/> <polyline points="370.62,24.80 370.62,12.80"/> <polyline points="471.30,24.80 471.30,12.80"/> <polyline points="72.18,79.20 86.64,87.20 101.10,79.20 115.56,87.20 130.02,79.20 144.49,87.20 158.95,79.20"/> <polyline points="183.57,87.20 198.03,79.20 212.49,87.20 226.95,79.20 241.42,87.20 255.88,79.20 270.34,87.20 284.80,79.20 299.26,87.20 313.72,79.20 328.19,87.20 342.65,79.20 357.11,87.20 371.57,79.20 386.03,87.20 400.49,79.20 414.96,87.20 429.42,79.20 443.88,87.20 458.34,79.20 472.80,87.20 487.26,79.20 501.73,87.20"/> <polyline points="101.10,79.20 101.10,67.20"/> <polyline points="198.03,79.20 198.03,67.20"/> <polyline points="255.88,79.20 255.88,67.20"/> <polyline points="299.26,87.20 299.26,99.20"/> <polyline points="357.11,87.20 357.11,99.20"/> <polyline points="414.96,87.20 414.96,99.20"/> <polyline points="472.80,87.20 472.80,99.20"/> <polyline points="72.18,32.80 62.89,38.16"/> <polyline points="53.61,43.18 44.03,48.00"/> <polyline points="72.18,79.20 62.89,73.84"/> <polyline points="53.61,68.82 44.03,64.00"/> <polyline points="44.03,48.00 44.03,64.00"/> <polyline points="44.03,64.00 30.18,72.00 22.56,67.60"/> <polyline points="501.73,24.80 511.01,30.16"/> <polyline points="517.23,37.82 520.58,48.00"/> <polyline points="501.73,87.20 511.01,81.84"/> <polyline points="517.23,74.18 520.58,64.00"/> <polyline points="520.58,48.00 520.58,64.00"/> <polyline points="520.58,64.00 534.44,72.00 542.06,67.60"/> </g> <g fill="currentColor" font-family="Helvetica, Arial, sans-serif" font-size="11.5" text-anchor="middle" dominant-baseline="central"> <text x="58.32" y="40.80">O</text> <text x="58.32" y="71.20">O</text> <text x="12.80" y="64.00">HO</text> <text x="515.58" y="32.80">O</text> <text x="515.58" y="79.20">O</text> <text x="551.81" y="64.00">OH</text> </g></svg></span><span class="psm-gdgt"><span class="psm-gdgt-name">Cren</span><svg class="psm-gdgt-svg" viewBox="0 0 564.6 112.0" aria-hidden="true" focusable="false">  <g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"> <polygon class="ring" fill="#FAC775" points="172.92,32.80 182.32,45.74 197.54,40.80 197.54,24.80 182.32,19.86"/> <polygon class="ring ring6" fill="#FAC775" points="214.33,32.80 214.33,48.80 228.19,56.80 242.04,48.80 242.04,32.80 228.19,24.80"/> <polygon class="ring" fill="#FAC775" points="376.36,32.80 385.77,45.74 400.99,40.80 400.99,24.80 385.77,19.86"/> <polygon class="ring" fill="#FAC775" points="163.45,79.20 172.86,66.26 188.07,71.20 188.07,87.20 172.86,92.14"/> <polygon class="ring" fill="#FAC775" points="385.83,79.20 395.24,66.26 410.45,71.20 410.45,87.20 395.24,92.14"/> <polyline points="72.18,32.80 88.97,24.80 105.76,32.80 122.55,24.80 139.34,32.80 156.13,24.80 172.92,32.80"/> <polyline points="197.54,24.80 214.33,32.80"/> <polyline points="242.04,32.80 258.83,24.80 275.62,32.80 292.41,24.80 309.20,32.80 325.99,24.80 342.78,32.80 359.57,24.80 376.36,32.80"/> <polyline points="400.99,24.80 417.78,32.80 434.57,24.80 451.36,32.80 468.15,24.80 484.94,32.80 501.73,24.80"/> <polyline points="105.76,32.80 105.76,44.80"/> <polyline points="214.33,32.80 203.94,38.80"/> <polyline points="292.41,24.80 292.41,12.80"/> <polyline points="359.57,24.80 359.57,12.80"/> <polyline points="468.15,24.80 468.15,12.80"/> <polyline points="72.18,79.20 87.39,87.20 102.60,79.20 117.81,87.20 133.03,79.20 148.24,87.20 163.45,79.20"/> <polyline points="188.07,87.20 203.28,79.20 218.50,87.20 233.71,79.20 248.92,87.20 264.13,79.20 279.35,87.20 294.56,79.20 309.77,87.20 324.98,79.20 340.19,87.20 355.41,79.20 370.62,87.20 385.83,79.20"/> <polyline points="410.45,87.20 425.67,79.20 440.88,87.20 456.09,79.20 471.30,87.20 486.51,79.20 501.73,87.20"/> <polyline points="102.60,79.20 102.60,67.20"/> <polyline points="203.28,79.20 203.28,67.20"/> <polyline points="264.13,79.20 264.13,67.20"/> <polyline points="309.77,87.20 309.77,99.20"/> <polyline points="370.62,87.20 370.62,99.20"/> <polyline points="471.30,87.20 471.30,99.20"/> <polyline points="72.18,32.80 62.89,38.16"/> <polyline points="53.61,43.18 44.03,48.00"/> <polyline points="72.18,79.20 62.89,73.84"/> <polyline points="53.61,68.82 44.03,64.00"/> <polyline points="44.03,48.00 44.03,64.00"/> <polyline points="44.03,64.00 30.18,72.00 22.56,67.60"/> <polyline points="501.73,24.80 511.01,30.16"/> <polyline points="517.23,37.82 520.58,48.00"/> <polyline points="501.73,87.20 511.01,81.84"/> <polyline points="517.23,74.18 520.58,64.00"/> <polyline points="520.58,48.00 520.58,64.00"/> <polyline points="520.58,64.00 534.44,72.00 542.06,67.60"/> </g> <g fill="currentColor" font-family="Helvetica, Arial, sans-serif" font-size="11.5" text-anchor="middle" dominant-baseline="central"> <text x="58.32" y="40.80">O</text> <text x="58.32" y="71.20">O</text> <text x="12.80" y="64.00">HO</text> <text x="515.58" y="32.80">O</text> <text x="515.58" y="79.20">O</text> <text x="551.81" y="64.00">OH</text> </g></svg></span><span class="psm-gdgt"><span class="psm-gdgt-name">Cren&prime;<small>stereoisomer</small></span><svg class="psm-gdgt-svg" viewBox="0 0 564.6 112.0" aria-hidden="true" focusable="false">  <g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"> <polygon class="ring" fill="#FAC775" points="172.92,32.80 182.32,45.74 197.54,40.80 197.54,24.80 182.32,19.86"/> <polygon class="ring ring6" fill="#7FB8E0" points="214.33,32.80 214.33,48.80 228.19,56.80 242.04,48.80 242.04,32.80 228.19,24.80"/> <polygon class="ring" fill="#FAC775" points="376.36,32.80 385.77,45.74 400.99,40.80 400.99,24.80 385.77,19.86"/> <polygon class="ring" fill="#FAC775" points="163.45,79.20 172.86,66.26 188.07,71.20 188.07,87.20 172.86,92.14"/> <polygon class="ring" fill="#FAC775" points="385.83,79.20 395.24,66.26 410.45,71.20 410.45,87.20 395.24,92.14"/> <polyline points="72.18,32.80 88.97,24.80 105.76,32.80 122.55,24.80 139.34,32.80 156.13,24.80 172.92,32.80"/> <polyline points="197.54,24.80 214.33,32.80"/> <polyline points="242.04,32.80 258.83,24.80 275.62,32.80 292.41,24.80 309.20,32.80 325.99,24.80 342.78,32.80 359.57,24.80 376.36,32.80"/> <polyline points="400.99,24.80 417.78,32.80 434.57,24.80 451.36,32.80 468.15,24.80 484.94,32.80 501.73,24.80"/> <polyline points="105.76,32.80 105.76,44.80"/> <polyline points="214.33,32.80 203.94,38.80"/> <polyline points="292.41,24.80 292.41,12.80"/> <polyline points="359.57,24.80 359.57,12.80"/> <polyline points="468.15,24.80 468.15,12.80"/> <polyline points="72.18,79.20 87.39,87.20 102.60,79.20 117.81,87.20 133.03,79.20 148.24,87.20 163.45,79.20"/> <polyline points="188.07,87.20 203.28,79.20 218.50,87.20 233.71,79.20 248.92,87.20 264.13,79.20 279.35,87.20 294.56,79.20 309.77,87.20 324.98,79.20 340.19,87.20 355.41,79.20 370.62,87.20 385.83,79.20"/> <polyline points="410.45,87.20 425.67,79.20 440.88,87.20 456.09,79.20 471.30,87.20 486.51,79.20 501.73,87.20"/> <polyline points="102.60,79.20 102.60,67.20"/> <polyline points="203.28,79.20 203.28,67.20"/> <polyline points="264.13,79.20 264.13,67.20"/> <polyline points="309.77,87.20 309.77,99.20"/> <polyline points="370.62,87.20 370.62,99.20"/> <polyline points="471.30,87.20 471.30,99.20"/> <polyline points="72.18,32.80 62.89,38.16"/> <polyline points="53.61,43.18 44.03,48.00"/> <polyline points="72.18,79.20 62.89,73.84"/> <polyline points="53.61,68.82 44.03,64.00"/> <polyline points="44.03,48.00 44.03,64.00"/> <polyline points="44.03,64.00 30.18,72.00 22.56,67.60"/> <polyline points="501.73,24.80 511.01,30.16"/> <polyline points="517.23,37.82 520.58,48.00"/> <polyline points="501.73,87.20 511.01,81.84"/> <polyline points="517.23,74.18 520.58,64.00"/> <polyline points="520.58,48.00 520.58,64.00"/> <polyline points="520.58,64.00 534.44,72.00 542.06,67.60"/> </g> <g fill="currentColor" font-family="Helvetica, Arial, sans-serif" font-size="11.5" text-anchor="middle" dominant-baseline="central"> <text x="58.32" y="40.80">O</text> <text x="58.32" y="71.20">O</text> <text x="12.80" y="64.00">HO</text> <text x="515.58" y="32.80">O</text> <text x="515.58" y="79.20">O</text> <text x="551.81" y="64.00">OH</text> </g></svg></span><span class="psm-big">GDGT compositions</span></a>
<span class="psm-legend">
<a class="psm-leg psm-c-red" href="sensor_models.html#sensor-linear"><b>Linear</b><small>Schouten et al. (2002)</small></a>
<a class="psm-leg psm-c-ochre" href="sensor_models.html#sensor-tex86h"><b>Exponential</b><small>TEX<sub>86</sub><sup>H</sup>, Kim et al. (2010)</small></a>
<a class="psm-leg psm-c-purple" href="sensor_models.html#sensor-bayspar"><b>BAYSPAR</b><small>Tierney &amp; Tingley (2014)</small></a>
</span>
</div>
<div class="psm-flow">
<span class="psm-trunk psm-t-arrow" aria-hidden="true"></span><p class="psm-cap">Existing models link SST to coretop GDGTs via <a href="sensor_models.html#psm-sensor"><b class="psm-tex">TEX<sub>86</sub></b></a></p>
<span class="psm-trunk psm-t-line" aria-hidden="true"></span><a class="psm-box psm-c-blue psm-texas" href="sensor_models.html#sensor-texas"><span class="psm-head">TEXAS (this study)</span><span class="psm-body">Scaled Ring Index on a generalized logistic curve; nonthermal predictors shift its location T<sub>0</sub></span></a>
<span class="psm-trunk psm-t-arrow" aria-hidden="true"></span><p class="psm-cap psm-cap-strong">Unexplained variance in GDGT distributions (i.e., proxy residuals)</p>
<span class="psm-trunk psm-t-tee" aria-hidden="true"></span><a class="psm-branch psm-c-teal" href="sensor_models.html#sensor-aoa"><span class="psm-pill">AOA ecology</span><span class="psm-via">link via <b>GDGT-2/GDGT-3</b></span></a>
<span class="psm-trunk psm-t-end" aria-hidden="true"></span><a class="psm-branch psm-c-green" href="sensor_models.html#sensor-nutrient"><span class="psm-pill">Nutrient level</span><span class="psm-via">link via <b>surface ocean nitrate levels</b></span></a>
</div>
</div>

---

## How it works

TEXAS uses a two-stage workflow:

**Stage 1 — Forward calibration** fits a hierarchical Bayesian generalized logistic curve (temperature → Scaled RI) to modern culture, mesocosm, and coretop data. The output is a posterior distribution of calibration parameters saved as a `.nc` file. Pre-computed posteriors ship with the package (the defaults) or download from Zenodo — most users can skip this stage entirely.

**Stage 2 — Inverse reconstruction** passes your downcore Scaled RI measurements through the forward posterior, marginalizing over all calibration parameter uncertainty, and returns a full temperature posterior per sample.

---

## Quickstart

### Install

```bash
pip install texas-psm            # inside a virtual environment
# or, with uv:  uv pip install texas-psm   (or `uv add texas-psm` in a uv project)
```

Or open the interactive notebook in Google Colab — no installation needed:

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/PaleoLipidRR/TEXAS/blob/main/notebooks/quickstart_demo.ipynb)

That is all you need to use TEXAS on your own data. To fork the repository or run the manuscript notebooks (`uv sync` from a clone, Docker, or conda), see [Installation](installation.md).

---

### Step 1 — Compute Scaled Ring Index

Before prediction you need **Scaled Ring Index** (RI₀₋₃) values. Pass raw LC/MS peak areas or fractional abundances — the formula normalizes by the six-GDGT total, so either works:

```python
import pandas as pd
from TEXAS import compute_scaledRI

df = pd.read_csv("my_gdgt_data.csv")

df["scaledRI_cren3"] = compute_scaledRI(
    df["GDGT-0"], df["GDGT-1"], df["GDGT-2"], df["GDGT-3"],
    df["cren"],   df["cren_prime"],   # cren_weight=3 by default → RI₀₋₃
)
```

`````{admonition} Which Ring Index convention?
:class: note

The canonical TEXAS posteriors are calibrated against **RI₀₋₃** (`cren_weight=3`, crenarchaeol and its regioisomer weighted 3). Pass `cren_weight=4` to reproduce the RI₀₋₄ convention of Zhang et al. (2016), but the canonical posteriors were **not** calibrated against that convention — the weight also sets the scale the index is expressed on, so the two are not interchangeable inputs.

`cren_weight` was called `cren_rings` before 2026-08-21. The old keyword still works and warns.
`````

---

### Step 1b — Screen your proxy data (recommended)

Use the Mahalanobis-distance criterion the calibration itself was built with (manuscript Section 5.1) to flag samples that fall outside the modern coretop calibration domain. `from_calibration()` loads the **published** 90 % χ² ellipse in TEX₈₆ × Scaled RI space — fitted on the low-G₂/₃ coretops (`gdgt23ratio ≤ 5`) — so nothing is downloaded and nothing is refit. A flagged sample is an extrapolation, not necessarily a bad sample: past assemblages may genuinely occupy a region with no modern analogue, so the recommendation is to flag and interpret with caution, not to exclude.

```python
import matplotlib.pyplot as plt
from TEXAS.data import MahalanobisOutlierDetector

cols = {"TEX86": "<your_tex86_column>", "scaledRI_cren3": "<your_scaled_RI_column>"}

detector = MahalanobisOutlierDetector.from_calibration(confidence=0.90)
df["mahal_dist"] = detector.transform(df, columns=cols)
df["flagged"] = detector.detect_outliers_manual(df, columns=cols)   # keeps warm end-members (TEX86 > 0.75 and Scaled RI > 0.75)
print(f"Flagged: {int(df['flagged'].sum())} / {len(df)} samples")

# Visualize — 90% confidence ellipse with inliers/outliers color-coded
fig, ax = plt.subplots(figsize=(5, 4))
detector.plot_decision_boundary(df, ax=ax, columns=cols)
ax.set_xlabel("TEX$_{86}$")
ax.set_ylabel(r"Scaled RI$_{0-3}$")
plt.tight_layout()
plt.show()
```

Raising `confidence` (e.g. to 0.99) widens the ellipse so that only strong departures are flagged. The `outside_domain` column of `result["flags"]` applies the same criterion automatically when `tex86=` is passed to `predict_T_from_proxyObs`; the other quality flags (unattainable proxy values, extrapolated predictors, prior-dominated posteriors) are described on the [PSM page](PSM.md#8-reconstructing-temperature-from-proxy-observations) and demonstrated in the quickstart notebook.

---

### Step 2 — Choose a calibration posterior

**You can skip this step.** Four calibrations ship inside the package — the full multivariate T₀-shift fit and its thermal-only counterpart, each for both temperature targets — so a reconstruction needs no download and no network access. TEXAS picks between them from what you pass:

```python
from TEXAS import predict_T_from_proxyObs

result = predict_T_from_proxyObs(          # fwd_posterior omitted →
    proxyObs=df["scaledRI_cren3"].values,  # tx.GHEB.sst.sri03.G23-N1p0
    prior_mu_t=15.0, prior_sigma_t=10.0,
    gdgt23ratio=df["gdgt23ratio"].values,
    no3=df["no3"].values,
)
```

If you supply **no** predictors, TEXAS uses the thermal-only calibration instead and warns that it has done so:

```python
result = predict_T_from_proxyObs(          # no predictors →
    proxyObs=df["scaledRI_cren3"].values,  # tx.GHPU.sst.sri03.p0
    prior_mu_t=15.0, prior_sigma_t=10.0,
)
```

Read that warning rather than dismissing it. The thermal-only fit is a *different* calibration, not the multivariate one with its corrections switched off: the non-thermal effects are in the core-top data either way, and a univariate fit absorbs them into its thermal parameters. Its reconstructions will not match the ones the manuscript reports. Supplying one predictor but not the other raises instead, since that is more likely a mistake than a choice.

Pass `temptype="thermoT"` to get the thermocline-integrated calibration instead; both the multivariate and thermal-only versions of it ship too. Any other posterior is fetched once from [Zenodo](https://doi.org/10.5281/zenodo.19666744) and cached:

```python
import TEXAS

# Culture + mesocosm calibration (<1 MB)
TEXAS.download_posteriors(["tx.GCDU.cul.sri03.p0"])

# Everything in the current Zenodo record (~510 MB: ~475 MB of posteriors,
# of which the six T₀-shift posteriors with predictors are ~78-81 MB each,
# plus ~37 MB of training data)
TEXAS.download_all()

# What you already have — bundled and downloaded alike
TEXAS.list_posteriors()
```

Available forward posteriors:

| Name (no `.nc`) | Model | Predictors | Temperature | In package? | Zenodo size |
|---|---|---|---|---|---|
| `tx.GHEB.sst.sri03.G23-N1p0` | **T₀-shift coretop — the published calibration (default)** | G₂/₃ + NO₃⁻ | SST | **bundled** | ~78 MB |
| `tx.GHEB.thm.sri03.G23-N1p0` | **T₀-shift coretop — the published calibration (default)** | G₂/₃ + NO₃⁻ | Thermo-T | **bundled** | ~78 MB |
| `tx.GHPU.sst.sri03.p0` | Temperature-only coretop | none | SST | **bundled** | 0.3 MB |
| `tx.GHPU.thm.sri03.p0` | Temperature-only coretop | none | Thermo-T | **bundled** | 0.3 MB |
| `tx.GHEB.sst.sri03.G23` | T₀-shift coretop, single predictor | G₂/₃ | SST | download | ~78 MB |
| `tx.GHEB.thm.sri03.G23` | T₀-shift coretop, single predictor | G₂/₃ | Thermo-T | download | ~78 MB |
| `tx.GHEB.sst.sri03.N1p0` | T₀-shift coretop, single predictor | NO₃⁻ | SST | download | ~81 MB |
| `tx.GHEB.thm.sri03.N1p0` | T₀-shift coretop, single predictor | NO₃⁻ | Thermo-T | download | ~81 MB |
| `tx.GCDU.cul.sri03.p0` | Culture + mesocosm (the curve's top layer) | none | Culture T | download | 0.2 MB |
| `tx.GHEA.sst.sri03.G23-N1p0` | Additive (response-offset) coretop — initial submission, superseded | G₂/₃ + NO₃⁻ | SST | download (v0.2.0 record) | ~78 MB |
| `tx.GHEA.thm.sri03.G23-N1p0` | Additive (response-offset) coretop — initial submission, superseded | G₂/₃ + NO₃⁻ | Thermo-T | download (v0.2.0 record) | ~78 MB |

“Bundled” posteriors are installed with `pip install texas-psm` and need no network access. The default needs **both** predictors and refuses to run if one is missing (a missing value is never treated as zero). To switch the nitrate term off, pass a value above the cutoff, e.g. `no3=10`. Use a single-predictor calibration when only one nonthermal predictor applies to your record.

The bundled pair is the same posterior as the archived one with the error-in-variables model's per-site latent variables removed — everything the forward and inverse models read is present and unmodified, which is what takes the file from ~80 MB to 0.37 MB. The complete versions, latents included, are archived on Zenodo with the release record that the paper cites.

From **v0.3.0** the Zenodo record's flat files are named by case id (`tx.GHPU.sst.sri03.p0.fwd.nc`). Version 0.2.0 of the record — the initial submission's additive fits — carries the older names instead (e.g. `gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc`), and `download_posteriors()` still resolves those, pinned to that version, so preprint-era notebooks keep working. `load_posterior()` accepts **either** spelling, and downloads are saved flat in the cache as `<case id>.fwd.nc`.

#### How posterior files are named

Posteriors use CESM-style **case ids**: fixed dot-delimited positions instead of ever-growing concatenated descriptions.

```
tx . GHEB . sst . sri03 . G23-N1p0 . fwd.nc
│    │      │     │       │         └ role: fwd = forward calibration;
│    │      │     │       │           inv.<site>.<tags> = a reconstruction
│    │      │     │       └ predictors: G23, N1p0 (NO₃, cutoff 1.0 — `p`
│    │      │     │         is the decimal point), p0 = none
│    │      │     └ proxy: sri03 = scaledRI_cren3, sri = scaledRI, tex = TEX86
│    │      └ target temperature: sst, thm (Thermo-T), cul (culture T)
│    └ compset — the model recipe, one letter per axis (see table)
└ project prefix
```

The four **compset** letters encode, in order:

| Axis | Letters |
|---|---|
| Curve | `G` generalized logistic · `L` logistic · `N` linear |
| Training set | `H` hierarchical coretop · `C` culture+mesocosm · `J` culture+mesocosm+coretop · `T` coretop-only |
| Estimator | `P` priorApprox · `E` priorApprox + errors-in-variables · `D` full hierarchical |
| Predictor structure | `U` univariate · `A` additive (β on the response, unbounded) · `B` bounded-by-construction (the **T₀-shift** structure: γ on T₀) |

So `tx.GHEB.sst.sri03.G23-N1p0` is the published T₀-shift multivariate SST calibration, and `tx.GHPU.sst.sri03.p0` the univariate SST one. A date/run token may be appended to distinguish refits of the same configuration. Every function that takes a posterior name resolves case ids and legacy long names alike.

```{note}
**Two formulations of the non-thermal terms exist, and they are not interchangeable.** The current calibration — the bundled `GHEB` pair — applies G₂/₃ and NO₃ *inside* the logistic, as a shift of the curve location T₀ in °C (`gamma_G23_crtp` / `gamma_NO3_crtp`), so the predicted Scaled RI stays inside its bounds for any predictor value. The `GHEA` posteriors on Zenodo are the preprint's response-offset formulation (`beta_G23_crtp` / `beta_NO3_crtp`, in Scaled-RI units per predictor unit); they are kept for reproducing the preprint and are documented on the [preprint archive page](preprint_additive_archive.md).

You do not have to choose between them by hand: TEXAS reads which formulation a posterior uses from the coefficients it carries and selects the matching inverse model. The univariate and culture/mesocosm posteriors are unaffected either way — they have no non-thermal predictors.
```

---

### Step 3 — Forward prediction (temperature → proxy)

Useful for plotting the calibration curve and its uncertainty envelope:

```python
import numpy as np
from TEXAS import predict_proxy_from_T

result = predict_proxy_from_T(
    temperatures=np.linspace(5, 35, 100),
    posterior="tx.GHPU.sst.sri03.p0",
)
result["p50"]   # median Scaled RI (numpy array, length 100)
result["p5"]    # 5th percentile
result["p95"]   # 95th percentile
```

---

### Step 4 — Inverse reconstruction (proxy → temperature)

```{note}
`temptype=` is optional here. It does not change the reconstruction, which follows whichever calibration you supply — the target is read from that posterior's own attributes, and a `temptype` that contradicts it warns. It matters in exactly one case: when `fwd_posterior` is omitted, it picks which bundled calibration is used, `"SST"` (the default) or `"thermoT"`. On the forward side, `get_posterior(..., temptype=...)` is a real argument — that is where the target is decided.
```

````````{tab-set}
```````{tab-item} Univariate


```python
from TEXAS import predict_T_from_proxyObs

result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0,        # prior mean temperature (°C) — geological estimate
    prior_sigma_t=10.0,     # prior uncertainty (°C) — use wide prior if unsure
    fwd_posterior="tx.GHPU.sst.sri03.p0",   # temperature-only calibration
)
result["p50"]   # median SST (°C), one value per sample
result["p5"]    # 5th percentile
result["p95"]   # 95th percentile
```
```````
```````{tab-item} Multivariate (GDGT-2/3 + NO₃)


```python
result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0,
    prior_sigma_t=10.0,
    # fwd_posterior omitted → the bundled tx.GHEB.sst.sri03.G23-N1p0
    gdgt23ratio=df["gdgt23ratio"].values,
    no3=df["no3"].values,   # µmol/L; scalar or per-sample array
)
```
```````
```````{tab-item} NO₃ from the CMEMS climatology


```python
import xarray as xr

ocean_ds = xr.load_dataset("ocean_prop_ds.nc")  # CMEMS nitrate on the WOA23 grid, from SI_code00

result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0, prior_sigma_t=10.0,
    gdgt23ratio=df["gdgt23ratio"].values,
    site_lat=15.3, site_lon=-23.7,   # modern drill-site coordinates
    no3_dataset=ocean_ds,
)
# Prints: CMEMS NO₃ lookup: lat=15.3, lon=-23.7 → 0.42 µmol/L
```
```````
```````{tab-item} Load from disk / Google Drive


If you have a posterior `.nc` file locally or on Google Drive, pass it directly — no cache lookup, no download:

```python
import xarray as xr
from TEXAS import predict_T_from_proxyObs

# Colab: mount Google Drive first, then load
ds = xr.load_dataset("/content/drive/MyDrive/posteriors/tx.GHPU.sst.sri03.p0.fwd.nc")

result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior=ds,    # xr.Dataset — skips all file I/O
)
```
```````
````````

---

### Saving results

By default `predict_T_from_proxyObs` returns a dict in memory and writes nothing to disk. Pass `save_results=True` to persist:

```python
result = predict_T_from_proxyObs(
    ...,
    save_results=True,            # writes quantile .nc + .npz
    save_draws=True,              # also saves raw MCMC draws as _draws.nc
    cache_dir="/your/output/",    # default: ~/.texas/cache/TEXAS_invT_posterior_cache/
)
```

---

## Running forward calibration from scratch

Only needed if you want to re-fit the model to your own data or reproduce the published calibration. Requires CmdStan and the GDGT training database (`TEXAS.download_training_data()`).

```python
from TEXAS import build_fwd_data, get_posterior, save_posterior

data = build_fwd_data(
    t_cul=cul_df["SST"].values,       proxy_cul=cul_df["scaledRI"].values,
    t_meso=meso_df["SST"].values,     proxy_meso=meso_df["scaledRI"].values,
    t_crtp=crtp_df["SST"].values,     proxy_crtp=crtp_df["scaledRI"].values,
    gdgt23ratio_crtp=crtp_df["gdgt23ratio"].values,
    no3_crtp=crtp_df["no3"].values,   # no3_cutoff auto-calculated via Spearman if omitted
)

posterior, diagnostics = get_posterior(
    data,
    stan_file="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift",
    temptype="SST",
    proxy_name="scaledRI_cren3",
)
save_posterior(posterior)
```

`..._eiv_t0shift` is the published calibration. The non-thermal predictors enter inside the logistic, shifting the curve's location parameter T₀ rather than adding an offset to the response:

```
T₀_eff = T₀ + γ_{G₂/₃}·G₂/₃ + γ_{NO₃}·log₁₀(NO₃)
Scaled RI = b + (1 − b) / (1 + exp(−k·(T − T₀_eff)))^(1/ν)
```

so the fitted coefficients are `gamma_G23_crtp` and `gamma_NO3_crtp`, in °C per predictor unit, and the predicted Scaled RI is confined to (b, 1) by construction. `R2_thermal` must be supplied to this model — compute it from a thermal-only coretop fit with `gen_logi_fixed_hier_crtp_univ_priorApprox`.

---

## Citation

If you use TEXAS in published work, please cite:

> Rattanasriampaipong, R., Tierney, J. E., Elling, F. J., & Inglis, G. N. (2026). *TEXAS: A proxy system model for TEX86 paleothermometry.* ESS Open Archive (preprint). https://doi.org/10.22541/essoar.15002926/v3 — under review at *Paleoceanography and Paleoclimatology*.

See [`CITATION.cff`](https://github.com/PaleoLipidRR/TEXAS/blob/main/CITATION.cff) for machine-readable metadata.
