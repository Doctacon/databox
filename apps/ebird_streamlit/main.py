"""
eBird Observation Dashboard

Interactive Streamlit dashboard for exploring bird observation data from the eBird API.
This app connects to the transformed data in DuckDB and provides various filters and visualizations.
"""

from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Streamlit page
st.set_page_config(
    page_title="eBird Dashboard", page_icon="🐦", layout="wide", initial_sidebar_state="expanded"
)


# Database connection
@st.cache_resource
def get_database_path():
    """Get path to DuckDB database."""
    # Since we're running from apps/ebird_streamlit directory, go up two levels to project root
    current_dir = Path.cwd()

    # If we're in ebird_streamlit, go up to project root
    if current_dir.name == "ebird_streamlit":
        project_root = current_dir.parent.parent
    elif current_dir.name == "apps":
        project_root = current_dir.parent
    else:
        # Assume we're at project root
        project_root = current_dir

    # Try multiple possible database locations
    possible_paths = [
        project_root / "pipelines" / "sources" / "data" / "databox.db",
        current_dir.parent.parent
        / "pipelines"
        / "sources"
        / "data"
        / "databox.db",  # In case we're in ebird_streamlit
        project_root / "data" / "databox.db",
    ]

    db_path = None
    for path in possible_paths:
        if path.exists():
            db_path = path
            break

    if db_path is None:
        st.error("Database not found. Please run the eBird pipeline first: `task pipeline:ebird`")
        st.info(f"Searched locations: {', '.join(str(p) for p in possible_paths)}")
        st.info(f"Current directory: {current_dir}")
        st.stop()

    return str(db_path)


def get_database_connection():
    """Get fresh connection to DuckDB database."""
    db_path = get_database_path()
    try:
        return duckdb.connect(db_path)
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        st.stop()


@st.cache_data
def load_observation_data():
    """Load bird observation data from the transformed tables."""
    conn = get_database_connection()

    query = """
    SELECT
        submission_id,
        species_code,
        common_name,
        scientific_name,
        location_id,
        location_name,
        observation_datetime,
        observation_date,
        observation_year,
        observation_month,
        observation_day,
        observation_hour,
        count,
        latitude,
        longitude,
        is_valid,
        is_reviewed,
        region_code,
        is_notable,
        loaded_at
    FROM sqlmesh_example.stg_ebird_observations
    WHERE observation_datetime IS NOT NULL
    ORDER BY observation_datetime DESC
    LIMIT 10000
    """

    try:
        df = conn.execute(query).df()
        conn.close()
        return df
    except Exception as e:
        conn.close()
        st.error(f"Failed to load observation data: {e}")
        st.info("Make sure SQLMesh transformations have been run: `task transform:run`")
        return pd.DataFrame()  # Return empty DataFrame


@st.cache_data
def load_daily_facts():
    """Load daily aggregated facts."""
    try:
        conn = get_database_connection()
        query = """
        SELECT *
        FROM sqlmesh_example.fct_daily_bird_observations
        ORDER BY observation_date DESC
        LIMIT 1000
        """
        df = conn.execute(query).df()
        conn.close()
        return df
    except Exception as e:
        st.warning(f"Could not load daily facts: {e}")
        return pd.DataFrame()


@st.cache_data
def load_hotspots():
    """Load hotspot data."""
    try:
        conn = get_database_connection()
        query = """
        SELECT *
        FROM sqlmesh_example.stg_ebird_hotspots
        LIMIT 1000
        """
        df = conn.execute(query).df()
        conn.close()
        return df
    except Exception as e:
        st.warning(f"Could not load hotspots: {e}")
        return pd.DataFrame()


def main():
    """Main dashboard function."""

    # Header
    st.title("🐦 eBird Observation Dashboard")
    st.markdown("Interactive dashboard for exploring bird observation data from multiple US states")

    # Sidebar filters
    st.sidebar.header("Filters")

    # Load data
    with st.spinner("Loading bird observation data..."):
        obs_df = load_observation_data()
        daily_df = load_daily_facts()
        hotspots_df = load_hotspots()

    if obs_df.empty:
        st.error(
            """
            No observation data found.
            Please ensure the eBird pipeline has been run and SQLMesh transformations are complete.
            """
        )
        return

    # State/Region filter
    region_list = sorted(obs_df["region_code"].dropna().unique())
    # Create readable state names from region codes
    region_mapping = {
        "US-AZ": "Arizona",
        "US-CA": "California",
        "US-NY": "New York",
        "US-TX": "Texas",
        "US-FL": "Florida",
    }

    # Create display options with readable names
    region_options = []
    region_display_map = {}
    for region in region_list:
        display_name = region_mapping.get(region, region)
        region_options.append(display_name)
        region_display_map[display_name] = region

    selected_states = st.sidebar.multiselect(
        "State/Region",
        options=region_options,
        default=region_options,  # Default to all available states
        help="Select which states/regions to include",
    )

    # Date range filter - convert datetime columns to date for picker compatibility
    obs_df["observation_date"] = pd.to_datetime(obs_df["observation_date"]).dt.date
    min_date = obs_df["observation_date"].min()
    max_date = obs_df["observation_date"].max()

    # Calculate default date range (last 7 days or all data if less than 7 days)
    date_diff = (max_date - min_date).days
    if date_diff >= 7:
        default_start = max_date - timedelta(days=7)
    else:
        default_start = min_date

    date_range = st.sidebar.date_input(
        "Date Range", value=(default_start, max_date), min_value=min_date, max_value=max_date
    )

    # Species filter
    species_list = sorted(obs_df["common_name"].dropna().unique())
    selected_species = st.sidebar.multiselect(
        "Species",
        options=species_list,
        default=[],  # Default to no species filter (show all)
    )

    # Time of day filter
    hour_range = st.sidebar.slider(
        "Hour of Day",
        min_value=0,
        max_value=23,
        value=(0, 23),  # Default to all hours
        help="Filter observations by hour (0-23)",
    )

    # Notable observations filter
    show_notable = st.sidebar.checkbox("Show Notable Observations Only", value=False)

    # Apply filters
    filtered_df = obs_df.copy()

    # State/Region filter
    if selected_states:
        # Convert display names back to region codes
        selected_region_codes = [region_display_map[state] for state in selected_states]
        filtered_df = filtered_df[filtered_df["region_code"].isin(selected_region_codes)]

    # Date filter
    if len(date_range) == 2:
        start_date, end_date = date_range
        # Filter using the date column directly
        filtered_df = filtered_df[
            (filtered_df["observation_date"] >= start_date)
            & (filtered_df["observation_date"] <= end_date)
        ]

    # Species filter (only apply if species are selected)
    if selected_species:
        filtered_df = filtered_df[filtered_df["common_name"].isin(selected_species)]

    # Hour filter
    filtered_df = filtered_df[
        (filtered_df["observation_hour"] >= hour_range[0])
        & (filtered_df["observation_hour"] <= hour_range[1])
    ]

    # Notable filter
    if show_notable:
        filtered_df = filtered_df[filtered_df["is_notable"]]

    # Main dashboard
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Observations", len(filtered_df))

    with col2:
        st.metric("Unique Species", filtered_df["species_code"].nunique())

    with col3:
        st.metric("Locations", filtered_df["location_id"].nunique())

    with col4:
        notable_count = filtered_df["is_notable"].sum()
        st.metric("Notable Sightings", notable_count)

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Map", "📊 Overview", "📈 Trends", "📋 Data"])

    with tab1:
        map_tab(filtered_df, hotspots_df)

    with tab2:
        overview_tab(filtered_df)

    with tab3:
        trends_tab(daily_df)

    with tab4:
        data_tab(filtered_df)


def overview_tab(df):
    """Overview tab with key visualizations."""

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 15 Species by Observations")

        species_counts = df["common_name"].value_counts().head(15)

        fig = px.bar(
            x=species_counts.values,
            y=species_counts.index,
            orientation="h",
            labels={"x": "Number of Observations", "y": "Species"},
            title="Most Frequently Observed Species",
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Observations by Hour")

        hourly_counts = df.groupby("observation_hour").size().reset_index(name="count")

        fig = px.line(
            hourly_counts,
            x="observation_hour",
            y="count",
            title="Bird Activity Throughout the Day",
            labels={"observation_hour": "Hour of Day", "count": "Number of Observations"},
        )
        fig.update_layout(xaxis=dict(range=[0, 23]))
        st.plotly_chart(fig, use_container_width=True)

    # Daily observations timeline
    st.subheader("Daily Observations Timeline")

    if not df.empty:
        # Create a copy to avoid modifying the original data
        timeline_df = df.copy()
        # Ensure observation_date is treated as string for groupby, then convert to datetime
        daily_counts = (
            timeline_df.groupby(timeline_df["observation_date"].astype(str))
            .size()
            .reset_index(name="count")
        )
        daily_counts["observation_date"] = pd.to_datetime(daily_counts["observation_date"])

        fig = px.line(
            daily_counts,
            x="observation_date",
            y="count",
            title="Observations Over Time",
            labels={"observation_date": "Date", "count": "Number of Observations"},
        )
        fig.update_layout(xaxis_title="Date", yaxis_title="Number of Observations")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for timeline.")


def map_tab(df, hotspots_df):
    """Map tab with geographic visualizations."""

    st.subheader("🗺️ Observation Locations")

    # Map of observations
    if not df.empty and "latitude" in df.columns and "longitude" in df.columns:
        # Remove rows with missing coordinates
        map_df = df.dropna(subset=["latitude", "longitude"])

        if not map_df.empty:
            fig = px.scatter_map(
                map_df,
                lat="latitude",
                lon="longitude",
                color="common_name",
                hover_data=["location_name", "observation_datetime"],
                title="Bird Observation Locations",
                height=600,
                zoom=6,
            )

            # Add hotspots if available
            if not hotspots_df.empty and "latitude" in hotspots_df.columns:
                hotspot_map_df = hotspots_df.dropna(subset=["latitude", "longitude"])
                if not hotspot_map_df.empty:
                    fig.add_trace(
                        go.Scattermap(
                            lat=hotspot_map_df["latitude"],
                            lon=hotspot_map_df["longitude"],
                            mode="markers",
                            marker=dict(
                                size=6,
                                color="red",
                                symbol="star",
                                opacity=0.4,  # 40% opacity
                            ),
                            text=hotspot_map_df["location_name"],
                            name="Hotspots",
                            hovertemplate="<b>%{text}</b><br>Hotspot<extra></extra>",
                        )
                    )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No observations with valid coordinates found.")
    else:
        st.warning("No coordinate data available for mapping.")


def trends_tab(daily_df):
    """Trends tab with aggregated analytics."""

    st.subheader("📈 Daily Trends")

    if daily_df.empty:
        st.warning("No daily aggregated data available.")
        return

    # Species diversity over time
    if "observation_date" in daily_df.columns and "species_code" in daily_df.columns:
        # Ensure observation_date is datetime
        daily_df["observation_date"] = pd.to_datetime(daily_df["observation_date"])

        col1, col2 = st.columns(2)

        with col1:
            # Daily species count
            daily_species = (
                daily_df.groupby("observation_date")["species_code"].nunique().reset_index()
            )
            daily_species.columns = ["date", "unique_species"]

            fig = px.line(
                daily_species,
                x="date",
                y="unique_species",
                title="Species Diversity Over Time",
                labels={"date": "Date", "unique_species": "Number of Unique Species"},
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Observation count trends
            if "observation_count" in daily_df.columns:
                daily_obs = (
                    daily_df.groupby("observation_date")["observation_count"].sum().reset_index()
                )

                fig = px.line(
                    daily_obs,
                    x="observation_date",
                    y="observation_count",
                    title="Total Daily Observations",
                    labels={
                        "observation_date": "Date",
                        "observation_count": "Number of Observations",
                    },
                )
                st.plotly_chart(fig, use_container_width=True)


def data_tab(df):
    """Data tab with raw data exploration."""

    st.subheader("📋 Raw Data")

    # Data overview
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Rows", len(df))

    with col2:
        st.metric("Total Columns", len(df.columns))

    with col3:
        st.metric(
            "Data Period", f"{df['observation_date'].min()} to {df['observation_date'].max()}"
        )

    # Search functionality
    search_term = st.text_input("Search species or location:")

    if search_term:
        mask = (
            df["common_name"].str.contains(search_term, case=False, na=False)
            | df["scientific_name"].str.contains(search_term, case=False, na=False)
            | df["location_name"].str.contains(search_term, case=False, na=False)
        )
        display_df = df[mask]
    else:
        display_df = df

    # Display data
    st.dataframe(
        display_df.head(1000),  # Limit to 1000 rows for performance
        use_container_width=True,
        height=400,
    )

    # Download option
    csv = display_df.to_csv(index=False)
    st.download_button(
        label="Download filtered data as CSV",
        data=csv,
        file_name=f"ebird_observations_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
