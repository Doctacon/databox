# Databox: Modern Bird Observation Analytics Platform

A production-ready data platform for analyzing bird observation data from eBird API, featuring real-time data ingestion, transformation pipelines, and interactive dashboards.

## 🚀 Features

### **Complete Data Pipeline**
- **eBird API Integration**: Real-time bird observation data from multiple US states
- **Multi-State Support**: Arizona, California, and expandable to all US states
- **Automated Ingestion**: Scheduled data collection with 30-day lookback
- **Data Transformation**: Clean, standardized models using SQLMesh
- **Interactive Dashboard**: Rich Streamlit app with maps, charts, and filters

### **Modern Data Stack**
- **Database**: DuckDB (fast, embedded analytical database)
- **Ingestion**: dlt (data load tool) with robust error handling
- **Transformations**: SQLMesh with version control and testing
- **Orchestration**: Dagster for workflow management
- **Visualization**: Streamlit with Plotly for interactive charts and maps
- **Task Management**: Task (go-task) for streamlined development

## 🎯 Quick Start

### 1. Environment Setup

```bash
# Install Task (macOS)
brew install go-task/tap/go-task

# Clone and setup
git clone <your-repo>
cd databox
task setup

# Configure your eBird API token
cp .env.example .env
# Edit .env and add your EBIRD_API_TOKEN
```

### 2. Run the Data Pipeline

```bash
# Ingest Arizona bird data (default)
task pipeline:ebird

# Or specify a different state
task pipeline:ebird -- --region US-CA  # California
task pipeline:ebird -- --region US-NY  # New York

# Transform raw data into analytics-ready tables
task transform:run
```

### 3. Launch the Dashboard

```bash
# Start interactive bird observation dashboard
task streamlit

# Access at http://localhost:8501
```

## 🏗️ Project Architecture

```
databox/
├── apps/                    # Applications and dashboards
│   └── ebird_streamlit/    # Streamlit bird observation dashboard
│       ├── main.py         # Main dashboard application
│       ├── README.md       # Dashboard documentation
│       └── .streamlit/     # Streamlit configuration
├── pipelines/              # Data ingestion pipelines
│   └── sources/
│       └── ebird_api.py    # eBird API integration with multi-state support
├── transformations/        # SQLMesh data transformation project
│   └── home_team/         # Main transformation project
│       ├── models/        # SQL transformation models
│       │   ├── staging/   # Clean, standardized data (stg_*)
│       │   ├── intermediate/ # Business logic (int_*)
│       │   └── marts/     # Final analytics tables (fct_*, dim_*)
│       ├── tests/         # Model tests and data quality checks
│       └── config.yaml    # SQLMesh configuration
├── orchestration/          # Dagster workflow orchestration
│   └── dagster_project.py # Asset definitions and jobs
├── data/                  # Data storage (gitignored)
│   └── databox.db        # DuckDB database file
├── scripts/               # Utility scripts
└── .dagster/             # Dagster state and configuration
```

## 📊 Dashboard Features

### **Interactive Filters**
- **State/Region**: Select Arizona, California, or multiple states
- **Date Range**: Filter observations by date with smart defaults
- **Species**: Multi-select from 700+ observed bird species
- **Time of Day**: Hour-based filtering (0-23)
- **Notable Observations**: Show only rare/unusual sightings

### **Visualization Tabs**

#### 🗺️ **Map Tab** (Default)
- Interactive map of all observation locations
- Color-coded by bird species
- Semi-transparent red star markers for birding hotspots
- Hover details with location and observation info

#### 📊 **Overview Tab**
- Top 15 most frequently observed species (horizontal bar chart)
- Hourly bird activity patterns (line chart)
- Daily observation timeline showing trends over time
- Key metrics: total observations, unique species, locations, notable sightings

#### 📈 **Trends Tab**
- Species diversity over time
- Daily observation count trends
- Aggregated analytics from daily fact tables

#### 📋 **Data Tab**
- Raw data exploration with search functionality
- Searchable by species name, scientific name, or location
- CSV export functionality
- Data overview metrics


## 🐦 Data Model

### **Raw Data Sources**
- **Recent Observations**: Current bird sightings (33+ records from Arizona)
- **Notable Observations**: Rare/unusual birds (81+ records)
- **Hotspots**: Popular birding locations (477+ locations)
- **Species List**: State-specific bird species (700+ species)
- **Taxonomy**: Global eBird taxonomy (17,415+ species)

### **Transformed Models**
- **`stg_ebird_observations`**: Cleaned observation data with standardized columns
- **`stg_ebird_hotspots`**: Processed hotspot locations with coordinates
- **`stg_ebird_taxonomy`**: Normalized species taxonomy data
- **`int_ebird_enriched_observations`**: Business logic applied observations
- **`fct_daily_bird_observations`**: Daily aggregated metrics by species and location

## 🛠️ Development Workflows

### **Data Pipeline Operations**
```bash
# List available pipelines
task pipeline:list

# Run full data refresh
task full-refresh

# Plan transformation changes
task transform:plan

# Apply transformations
task transform:run

# Run transformation tests
task transform:test

# Open SQLMesh UI for model development
task transform:ui
```

### **Dashboard Development**
```bash
# Start development server with hot reload
task streamlit

# Or run directly
cd apps/ebird_streamlit
streamlit run main.py
```

### **Orchestration**
```bash
# Start Dagster development server
task dagster:dev

# Execute specific job
task dagster:job daily_ebird_pipeline

# Materialize specific assets
task dagster:materialize ebird_raw_data
```

### **Code Quality**
```bash
# Format and lint code
task format
task lint

# Type checking
task typecheck

# Run all CI checks
task ci

# Security scanning
task check-secrets
```

## 🌍 Multi-State Support

The platform is designed for easy expansion to additional US states:

```bash
# Add new states by running pipeline with different regions
task pipeline:ebird -- --region US-TX  # Texas
task pipeline:ebird -- --region US-FL  # Florida
task pipeline:ebird -- --region US-NY  # New York

# The dashboard automatically detects and includes new states
# No code changes required!
```

**Supported Region Codes:**
- `US-AZ` - Arizona
- `US-CA` - California
- `US-NY` - New York
- `US-TX` - Texas
- `US-FL` - Florida
- `US` - All United States (if API supports)

## 📈 Performance & Scalability

### **Current Scale**
- **10,000+ observations** per state per pipeline run
- **30-day lookback** for historical data
- **Sub-second dashboard response** with caching
- **Real-time filtering** across multiple dimensions

### **Optimizations**
- Streamlit `@st.cache_data` for query performance
- DuckDB columnar storage for analytical queries
- SQLMesh incremental models for efficient transformations
- Connection pooling and proper resource management

## 🔒 Security & Best Practices

### **API Key Management**
- Environment variables for sensitive configuration
- Pre-commit hooks prevent accidental secret commits
- Placeholder values in example files

### **Data Quality**
- SQLMesh built-in testing framework
- Data type validation and constraints
- Error handling and graceful degradation
- Monitoring and alerting through Dagster

## 🚀 Deployment

### **Development**
```bash
task prod  # Shows available production commands
```

### **Production Considerations**
- Replace DuckDB with PostgreSQL/Snowflake for multi-user access
- Add Airflow/Prefect for production orchestration
- Implement proper logging and monitoring
- Add CI/CD pipeline for automated deployments
- Set up data backup and disaster recovery

## 📚 Documentation

- **Main README**: You're reading it!
- **Dashboard Docs**: `apps/ebird_streamlit/README.md`
- **Pipeline Docs**: Inline documentation in `pipelines/sources/ebird_api.py`
- **SQLMesh Models**: SQL comments and model descriptions
- **Development Guide**: `CLAUDE.md` for development workflows

## 🤝 Contributing

1. **Code Quality**: All PRs must pass linting, type checking, and tests
2. **Documentation**: Update relevant README files for new features
3. **Testing**: Add tests for new models and pipeline components
4. **Security**: Run `task check-secrets` before committing

## 📄 License

MIT License - see LICENSE file for details.

---

**Built with ❤️ for bird enthusiasts and data engineers**

*Transform raw eBird data into actionable insights with modern data engineering practices.*
