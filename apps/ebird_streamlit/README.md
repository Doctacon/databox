# eBird Observation Dashboard

Interactive Streamlit dashboard for exploring bird observation data from the eBird API.

## Usage

```bash
# From project root
task streamlit

# Or directly
cd apps/ebird_streamlit
streamlit run main.py
```

Access at http://localhost:8501

## Prerequisites

1. Run the eBird pipeline: `databox run ebird`
2. Apply SQLMesh transforms: `databox transform run`
3. Database at `data/databox.db`

## Data Sources

The dashboard reads from these transformed tables:

- `ebird.stg_ebird_observations` — Individual bird observations
- `ebird.fct_daily_bird_observations` — Daily aggregated facts
- `ebird.stg_ebird_hotspots` — Birding hotspot locations

## Features

- Interactive filters (date range, species, region, time of day)
- Observation map with hotspot overlay
- Species diversity and activity trends
- Raw data exploration with CSV download
