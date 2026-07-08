-- Semantic metrics over environmental_observations.fact_bird_observation.
-- The legacy analytics flagship mart was retired in favor of the CDM fact layer.

METRIC (
  name species_richness,
  description 'Distinct eBird species count. Grouping by observation_date gives daily richness.',
  expression COUNT(DISTINCT environmental_observations.fact_bird_observation.species_code)
);

METRIC (
  name total_observations,
  description 'Count of eBird observation fact rows.',
  expression COUNT(DISTINCT environmental_observations.fact_bird_observation.bird_observation_sk)
);

METRIC (
  name total_observed_birds,
  description 'Sum of reported bird counts. Null/X counts are ignored by SQL SUM semantics.',
  expression SUM(environmental_observations.fact_bird_observation.observation_count)
);
