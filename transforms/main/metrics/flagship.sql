-- Semantic metrics over analytics.fct_species_environment_daily.
-- All metrics are defined against the flagship mart's grain
-- (species_code, h3_cell, obs_date).

METRIC (
  name species_richness,
  description 'Distinct species count. Grouping by (h3_cell, obs_date) gives per-cell-day diversity; grouping by obs_date gives platform-wide daily diversity.',
  expression COUNT(DISTINCT analytics.fct_species_environment_daily.species_code)
);

METRIC (
  name total_observations,
  description 'Sum of eBird observations recorded (one per species-hotspot-date entry).',
  expression SUM(analytics.fct_species_environment_daily.n_observations)
);

METRIC (
  name total_checklists,
  description 'Sum of eBird checklists covering the grouped slice.',
  expression SUM(analytics.fct_species_environment_daily.n_checklists)
);

METRIC (
  name observation_intensity,
  description 'Average observations per checklist. Derived from total_observations / total_checklists.',
  expression total_observations / NULLIF(total_checklists, 0)
);

METRIC (
  name heat_stress_index,
  description 'Fraction of grouped rows where tmax >= 30C (uses the precomputed is_hot_day flag on the flagship mart). Grouped by species reveals heat-tolerant species.',
  expression AVG(analytics.fct_species_environment_daily.is_hot_day)
);

METRIC (
  name rainfall_anomaly_7d,
  description 'Mean 7-day precipitation z-score across grouped rows. Positive = wetter than local recent average; negative = drier. Null when the 7-day window has zero stddev (uniform precipitation).',
  expression AVG(analytics.fct_species_environment_daily.prcp_mm_z_7d)
);

METRIC (
  name discharge_anomaly_7d,
  description 'Mean 7-day streamflow z-score across grouped rows. Positive = higher than local recent average (e.g. post-rainfall surge); negative = lower.',
  expression AVG(analytics.fct_species_environment_daily.discharge_cfs_z_7d)
);
