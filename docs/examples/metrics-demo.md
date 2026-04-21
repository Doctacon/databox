# Metrics demo notebook

The notebook below queries the flagship mart
(`analytics.fct_species_environment_daily`) through the Databox semantic
metrics layer and produces three charts: a daily time-series, a
cross-domain slice, and a top-N comparative breakdown.

Source notebook:
[`notebooks/metrics_demo.ipynb`](https://github.com/Doctacon/databox/blob/main/notebooks/metrics_demo.ipynb).
Regenerate the rendered output with `task docs:build`.

If the warehouse is empty the notebook falls back to seeded synthetic
data so the rendered page always has charts — the real pipeline
replaces the synthetic path once `task full-refresh` has run.

<iframe
  src="metrics-demo/index.html"
  width="100%"
  height="1400"
  style="border: none;"
  loading="lazy">
</iframe>
