"""eBird API source pipeline using dlt."""

import os
from collections.abc import Iterator
from typing import Any

import dlt
import pendulum
from dlt.sources.helpers import requests as dlt_requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# eBird API base URL
EBIRD_API_BASE = "https://api.ebird.org/v2"


def get_api_headers() -> dict[str, str]:
    """Get API headers with token from environment."""
    api_token = os.getenv("EBIRD_API_TOKEN")
    if not api_token:
        raise ValueError("EBIRD_API_TOKEN not found in environment variables")

    return {"X-eBirdApiToken": api_token, "Accept": "application/json"}


def process_observation(
    obs: dict[str, Any], region: str, is_notable: bool = False
) -> dict[str, Any]:
    """Process and enrich observation data."""
    # Add metadata
    obs["_region_code"] = region
    obs["_loaded_at"] = pendulum.now().isoformat()
    obs["_observation_date"] = obs.get("obsDt")

    if is_notable:
        obs["_is_notable"] = True

    # Convert howMany to int if present
    if obs.get("howMany"):
        try:
            obs["howMany"] = int(obs["howMany"])
        except (ValueError, TypeError):
            obs["howMany"] = None

    return obs


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
    # Cache timestamp for this run
    loaded_at = pendulum.now().isoformat()

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

        try:
            response = dlt_requests.get(url, headers=get_api_headers(), params=params)
            response.raise_for_status()

            for obs in response.json():
                yield process_observation(obs, region)

        except Exception as e:
            print(f"⚠️  Error fetching recent observations for {region}: {e}")
            # Allow pipeline to continue with other resources

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

        try:
            response = dlt_requests.get(url, headers=get_api_headers(), params=params)
            response.raise_for_status()

            for obs in response.json():
                yield process_observation(obs, region, is_notable=True)

        except Exception as e:
            print(f"⚠️  Error fetching notable observations for {region}: {e}")

    @dlt.resource(primary_key="speciesCode", write_disposition="replace")
    def species_list(region: str = region_code) -> Iterator[dict[str, Any]]:
        """Fetch list of species observed in a region."""
        url = f"{EBIRD_API_BASE}/product/spplist/{region}"

        try:
            response = dlt_requests.get(url, headers=get_api_headers())
            response.raise_for_status()

            species_codes = response.json()

            # Batch yield for better performance
            for idx, species_code in enumerate(species_codes):
                yield {
                    "speciesCode": species_code,
                    "region": region,
                    "order": idx,
                    "_loaded_at": loaded_at,
                }
        except Exception as e:
            print(f"⚠️  Error fetching species list for {region}: {e}")

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

        try:
            response = dlt_requests.get(url, headers=get_api_headers(), params=params)
            response.raise_for_status()

            for hotspot in response.json():
                hotspot["_loaded_at"] = loaded_at
                hotspot["_region_code"] = region
                yield hotspot
        except Exception as e:
            print(f"⚠️  Error fetching hotspots for {region}: {e}")

    @dlt.resource(primary_key="sciName", write_disposition="replace")
    def taxonomy() -> Iterator[dict[str, Any]]:
        """Fetch eBird taxonomy (bird species reference data)."""
        url = f"{EBIRD_API_BASE}/ref/taxonomy/ebird"
        params = {"fmt": "json", "locale": "en"}

        try:
            response = dlt_requests.get(url, headers=get_api_headers(), params=params)
            response.raise_for_status()

            for species in response.json():
                species["_loaded_at"] = loaded_at
                yield species
        except Exception as e:
            print(f"⚠️  Error fetching taxonomy: {e}")

    @dlt.resource(primary_key=["regionCode", "year", "month", "day"], write_disposition="merge")
    def region_stats(region: str = region_code, back: int = days_back) -> Iterator[dict[str, Any]]:
        """Generate daily statistics for a region."""
        end_date = pendulum.now()

        for days_ago in range(back):
            date = end_date.subtract(days=days_ago)
            date_str = date.format("YYYY/MM/DD")

            params = {
                "back": 1,  # Just for this specific day
                "maxResults": 500,  # Get more results for stats
            }

            try:
                response = dlt_requests.get(
                    f"{EBIRD_API_BASE}/data/obs/{region}/recent/{date_str}",
                    headers=get_api_headers(),
                    params=params,
                )

                if response.status_code == 200:
                    observations = response.json()

                    # Calculate statistics
                    species_set = {
                        obs.get("speciesCode", "") for obs in observations if obs.get("speciesCode")
                    }
                    location_set = {
                        obs.get("locId", "") for obs in observations if obs.get("locId")
                    }

                    yield {
                        "regionCode": region,
                        "year": date.year,
                        "month": date.month,
                        "day": date.day,
                        "date": date.date().isoformat(),
                        "speciesCount": len(species_set),
                        "observationCount": len(observations),
                        "locationCount": len(location_set),
                        "_loaded_at": loaded_at,
                    }
            except Exception as e:
                print(f"⚠️  Error fetching stats for {region} on {date_str}: {e}")

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
    database_url: str = None,
    dlt_data_dir: str = None,
):
    """
    Load eBird data to the database.

    Args:
        region_code: Region code to fetch data for
        max_results: Maximum results per API call
        days_back: Number of days to look back
        dataset_name: Name of the dataset in the database
        database_url: Database connection URL (defaults to DuckDB)
        dlt_data_dir: Directory for DLT state files
    """
    # Default configuration if not provided
    if database_url is None:
        database_url = os.getenv("DATABASE_URL", "duckdb:///data/databox.db")
    if dlt_data_dir is None:
        dlt_data_dir = os.getenv("DLT_DATA_DIR", "./data/dlt")

    # Configure the pipeline
    pipeline = dlt.pipeline(
        pipeline_name="ebird_api",
        destination=dlt.destinations.duckdb(credentials=database_url),
        dataset_name=dataset_name,
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
    try:
        with pipeline.sql_client() as client:
            tables = client.execute_sql(
                f"""
                SELECT
                    table_name
                FROM
                    information_schema.tables
                WHERE
                    table_schema = '{dataset_name}'
                """
            )
            print("\nLoaded tables:")
            for table in tables:
                count = client.execute_sql(f"SELECT COUNT(*) FROM {dataset_name}.{table[0]}")
                print(f"  - {table[0]}: {count[0][0]} rows")
    except Exception as e:
        print(f"⚠️  Could not fetch table counts: {e}")

    return info


def load_multiple_regions(
    regions: list[str],
    max_results: int = 100,
    days_back: int = 7,
    database_url: str = None,
    dlt_data_dir: str = None,
):
    """Load eBird data for multiple regions."""
    results = {}

    for region in regions:
        print(f"\n📍 Loading data for region: {region}")
        try:
            info = load_ebird_data(
                region_code=region,
                max_results=max_results,
                days_back=days_back,
                database_url=database_url,
                dlt_data_dir=dlt_data_dir,
            )
            results[region] = {"status": "success", "info": info}
        except Exception as e:
            print(f"❌ Error loading region {region}: {e}")
            results[region] = {"status": "error", "error": str(e)}
            continue

    # Summary
    success_count = sum(1 for r in results.values() if r["status"] == "success")
    print(f"\n📊 Summary: {success_count}/{len(regions)} regions loaded successfully")

    return results


if __name__ == "__main__":
    print("eBird API pipeline ready!")
    print("Set EBIRD_API_TOKEN in your .env file")
    print("\nExamples:")
    print("  python pipelines/sources/ebird_api.py")
    print("\nOr import and use:")
    print("  from pipelines.sources.ebird_api import load_ebird_data")
    print("  load_ebird_data('US-CA', days_back=7)")

    # Uncomment to run examples:
    # load_ebird_data("US-CA", days_back=7)
    # regions = ["US-CA", "US-NY", "US-TX", "US-FL"]
    # load_multiple_regions(regions, days_back=3)
