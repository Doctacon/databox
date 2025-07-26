"""eBird API source pipeline using dlt."""

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import dlt
import pendulum
from dlt.sources.helpers import requests as dlt_requests

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config import settings

# eBird API base URL
EBIRD_API_BASE = "https://api.ebird.org/v2"


def get_api_headers() -> dict[str, str]:
    """Get API headers with token from environment."""
    api_token = os.getenv("EBIRD_API_TOKEN")
    if not api_token:
        raise ValueError("EBIRD_API_TOKEN not found in environment variables")

    return {"X-eBirdApiToken": api_token, "Accept": "application/json"}


@dlt.source
def ebird_source(
    region_code: str = "US-CA",  # Default to California, USA
    max_results: int = 100,
    days_back: int = 7,
):
    """
    eBird API source that fetches bird observation data.

    Args:
        region_code: Region code (country, state, or county)
        max_results: Maximum number of results per endpoint
        days_back: Number of days to look back for observations
    """

    @dlt.resource(
        primary_key="subId",
        write_disposition="merge",
        columns={
            "howMany": {"data_type": "bigint"},
            "lat": {"data_type": "double"},
            "lng": {"data_type": "double"},
        },
    )
    def recent_observations(
        region: str = region_code, back: int = days_back
    ) -> Iterator[dict[str, Any]]:
        """Fetch recent bird observations in a region."""
        url = f"{EBIRD_API_BASE}/data/obs/{region}/recent"
        params = {"back": back, "maxResults": max_results, "includeProvisional": True}

        response = dlt_requests.get(url, headers=get_api_headers(), params=params)
        response.raise_for_status()

        for obs in response.json():
            # Add metadata
            obs["_region_code"] = region
            obs["_loaded_at"] = pendulum.now().isoformat()
            obs["_observation_date"] = obs.get("obsDt")

            # Convert howMany to int if present
            if obs.get("howMany"):
                try:
                    obs["howMany"] = int(obs["howMany"])
                except (ValueError, TypeError):
                    obs["howMany"] = None

            yield obs

    @dlt.resource(
        primary_key="subId",
        write_disposition="merge",
        columns={
            "howMany": {"data_type": "bigint"},
            "lat": {"data_type": "double"},
            "lng": {"data_type": "double"},
        },
    )
    def notable_observations(
        region: str = region_code, back: int = days_back
    ) -> Iterator[dict[str, Any]]:
        """Fetch notable (rare) bird observations in a region."""
        url = f"{EBIRD_API_BASE}/data/obs/{region}/recent/notable"
        params = {"back": back, "maxResults": max_results}

        response = dlt_requests.get(url, headers=get_api_headers(), params=params)
        response.raise_for_status()

        for obs in response.json():
            obs["_region_code"] = region
            obs["_loaded_at"] = pendulum.now().isoformat()
            obs["_is_notable"] = True
            obs["_observation_date"] = obs.get("obsDt")

            if obs.get("howMany"):
                try:
                    obs["howMany"] = int(obs["howMany"])
                except (ValueError, TypeError):
                    obs["howMany"] = None

            yield obs

    @dlt.resource(primary_key="speciesCode", write_disposition="replace")
    def species_list(region: str = region_code) -> Iterator[dict[str, Any]]:
        """Fetch list of species observed in a region."""
        url = f"{EBIRD_API_BASE}/product/spplist/{region}"

        response = dlt_requests.get(url, headers=get_api_headers())
        response.raise_for_status()

        species_codes = response.json()

        # For each species code, we'll yield a record
        for idx, species_code in enumerate(species_codes):
            yield {
                "speciesCode": species_code,
                "region": region,
                "order": idx,
                "_loaded_at": pendulum.now().isoformat(),
            }

    @dlt.resource(
        primary_key="locId",
        write_disposition="merge",
        columns={
            "lat": {"data_type": "double"},
            "lng": {"data_type": "double"},
            "numSpeciesAllTime": {"data_type": "bigint"},
        },
    )
    def hotspots(region: str = region_code, back: int = days_back) -> Iterator[dict[str, Any]]:
        """Fetch birding hotspots in a region."""
        url = f"{EBIRD_API_BASE}/ref/hotspot/{region}"
        params = {"back": back, "fmt": "json"}

        response = dlt_requests.get(url, headers=get_api_headers(), params=params)
        response.raise_for_status()

        for hotspot in response.json():
            hotspot["_loaded_at"] = pendulum.now().isoformat()
            hotspot["_region_code"] = region
            yield hotspot

    @dlt.resource(primary_key="sciName", write_disposition="replace")
    def taxonomy() -> Iterator[dict[str, Any]]:
        """Fetch eBird taxonomy (bird species reference data)."""
        url = f"{EBIRD_API_BASE}/ref/taxonomy/ebird"
        params = {"fmt": "json", "locale": "en"}

        response = dlt_requests.get(url, headers=get_api_headers(), params=params)
        response.raise_for_status()

        for species in response.json():
            species["_loaded_at"] = pendulum.now().isoformat()
            yield species

    @dlt.resource(primary_key=["regionCode", "year", "month", "day"], write_disposition="merge")
    def region_stats(region: str = region_code, back: int = days_back) -> Iterator[dict[str, Any]]:
        """Generate daily statistics for a region."""
        # This is a derived resource that aggregates observation counts by day
        # Get observations for the past N days
        end_date = pendulum.now()

        for days_ago in range(back):
            date = end_date.subtract(days=days_ago)
            date_str = date.format("YYYY/MM/DD")

            params = {
                "back": 1,  # Just for this specific day
                "maxResults": 500,  # Get more results for stats
            }

            response = dlt_requests.get(
                f"{EBIRD_API_BASE}/data/obs/{region}/recent/{date_str}",
                headers=get_api_headers(),
                params=params,
            )

            if response.status_code == 200:
                observations = response.json()

                # Calculate statistics
                species_count = len(set(obs.get("speciesCode", "") for obs in observations))
                observation_count = len(observations)
                location_count = len(set(obs.get("locId", "") for obs in observations))

                yield {
                    "regionCode": region,
                    "year": date.year,
                    "month": date.month,
                    "day": date.day,
                    "date": date.date().isoformat(),
                    "speciesCount": species_count,
                    "observationCount": observation_count,
                    "locationCount": location_count,
                    "_loaded_at": pendulum.now().isoformat(),
                }

    # Return all resources
    return [
        recent_observations,
        notable_observations,
        species_list,
        hotspots,
        taxonomy,
        region_stats,
    ]


def load_ebird_data(
    region_code: str = "US-CA",
    max_results: int = 100,
    days_back: int = 7,
    dataset_name: str = "raw_ebird_data",
):
    """
    Load eBird data to the database.

    Args:
        region_code: Region code to fetch data for
        max_results: Maximum results per API call
        days_back: Number of days to look back
        dataset_name: Name of the dataset in the database
    """
    # Configure the pipeline
    pipeline = dlt.pipeline(
        pipeline_name="ebird_api",
        destination=dlt.destinations.duckdb(credentials=settings.database_url),
        dataset_name=dataset_name,
        dir=str(settings.dlt_data_dir),
    )

    # Create the source
    source = ebird_source(region_code=region_code, max_results=max_results, days_back=days_back)

    # Run the pipeline
    info = pipeline.run(source)

    # Print the outcome
    print("\n✅ eBird data loaded successfully!")
    print(f"Pipeline: {pipeline.pipeline_name}")
    print(f"Dataset: {dataset_name}")
    print(f"Region: {region_code}")
    print(f"Days back: {days_back}")
    print(f"\n{info}")

    # Show loaded tables and counts
    with pipeline.sql_client() as client:
        tables = client.execute_sql(
            f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{dataset_name}'"
        )
        print("\nLoaded tables:")
        for table in tables:
            count = client.execute_sql(f"SELECT COUNT(*) FROM {dataset_name}.{table[0]}")
            print(f"  - {table[0]}: {count[0][0]} rows")

    return info


def load_multiple_regions(regions: list[str], max_results: int = 100, days_back: int = 7):
    """Load eBird data for multiple regions."""
    for region in regions:
        print(f"\n📍 Loading data for region: {region}")
        try:
            load_ebird_data(region_code=region, max_results=max_results, days_back=days_back)
        except Exception as e:
            print(f"❌ Error loading region {region}: {e}")
            continue


if __name__ == "__main__":
    # Example: Load data for California
    # load_ebird_data("US-CA", days_back=7)

    # Example: Load data for multiple regions
    # regions = ["US-CA", "US-NY", "US-TX", "US-FL"]
    # load_multiple_regions(regions, days_back=3)

    print("eBird API pipeline ready!")
    print("Set EBIRD_API_TOKEN in your .env file")
    print("\nExamples:")
    print("  load_ebird_data('US-CA')  # California")
    print("  load_ebird_data('US-NY')  # New York")
    print("  load_ebird_data('CA-ON')  # Ontario, Canada")
    print("  load_ebird_data('GB')     # Great Britain")
