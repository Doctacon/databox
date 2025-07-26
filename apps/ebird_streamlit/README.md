# eBird Observation Dashboard

Interactive Streamlit dashboard for exploring bird observation data from the eBird API.

Located at `apps/ebird_streamlit/` - part of the broader apps ecosystem for the Databox project.

## Features

### 🔍 Interactive Filters
- **Date Range**: Filter observations by date
- **Species Selection**: Choose specific bird species to analyze
- **Time of Day**: Filter by hour of observation (0-23)
- **Notable Observations**: Show only rare/notable sightings

### 📊 Dashboard Tabs

#### Overview Tab
- Key metrics (total observations, unique species, locations, notable sightings)
- Top 15 species by observation count
- Hourly activity patterns
- Daily observation timeline

#### Map Tab
- Interactive map showing observation locations
- Color-coded by species
- Hotspot locations marked with red stars
- Hover details for each observation

#### Trends Tab
- Species diversity over time
- Daily observation trends
- Aggregated analytics from SQLMesh fact tables

#### Data Tab
- Raw data exploration
- Search functionality across species and locations
- Download filtered data as CSV
- Data overview metrics

## Usage

### Start the Dashboard
```bash
# From project root
task streamlit

# Or directly
cd apps/ebird_streamlit
streamlit run main.py
```

### Access the Dashboard
- **Local URL**: http://localhost:8501
- **Network URL**: http://192.168.4.38:8501

### Prerequisites
1. eBird pipeline must be run: `task pipeline:ebird`
2. SQLMesh transformations must be applied: `task transform:run`
3. Data should be available in DuckDB at `pipelines/sources/data/databox.db`

## Data Sources

The dashboard connects to the following SQLMesh-transformed tables:
- `sqlmesh_example.stg_ebird_observations` - Individual bird observations
- `sqlmesh_example.fct_daily_bird_observations` - Daily aggregated facts
- `sqlmesh_example.stg_ebird_hotspots` - Birding hotspot locations

## Dependencies

- `streamlit>=1.41.1` - Web app framework
- `plotly>=5.24.1` - Interactive visualizations
- `altair>=5.4.1` - Additional charting
- `pandas>=2.2.3` - Data manipulation
- `duckdb>=1.1.3` - Database connection

## Configuration

The app includes Streamlit configuration in `.streamlit/config.toml`:
- Custom theme colors
- Port configuration (8501)
- Performance optimizations

## Performance Notes

- Data is cached using `@st.cache_data` for better performance
- Observation data limited to 10,000 rows for initial load
- Map visualizations filtered to prevent browser overload
- Raw data display limited to 1,000 rows in Data tab

## Troubleshooting

### No Data Found
1. Ensure eBird pipeline has been run: `task pipeline:ebird`
2. Check that SQLMesh transformations are complete: `task transform:run`
3. Verify database exists at `pipelines/sources/data/databox.db`

### Performance Issues
1. Reduce date range in filters
2. Select fewer species in multiselect
3. Clear browser cache and refresh

### Map Not Loading
1. Check that observations have valid latitude/longitude data
2. Ensure internet connection for map tiles
3. Try refreshing the page
