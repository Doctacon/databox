"""eBird API source pipeline using dlt."""

import os
from collections.abc import Iterator
from typing import Any

import dlt
import pendulum
from databox_config.pipeline_config import PipelineConfig
from databox_config.settings import settings
from dlt.sources.helpers import requests as dlt_requests
from dotenv import load_dotenv

load_dotenv()

EBIRD_API_BASE = "https://api.ebird.org/v2"


def get_api_headers() -> dict[str, str]:
    api_token = os.getenv("EBIRD_API_TOKEN")
    if not api_token:
        raise ValueError("EBIRD_API_TOKEN not found in environment variables")
    return {"X-eBirdApiToken": api_token, "Accept": "application/json"}


def process_observation(
    obs: dict[str, Any], region: str, is_notable: bool = False
) -> dict[str, Any]:
    obs["_region_code"] = region
    obs["_loaded_at"] = pendulum.now().isoformat()
    obs["_observation_date"] = obs.get("obsDt")
    obs["_is_notable"] = is_notable

    if obs.get("howMany"):
        try:
            obs["howMany"] = int(obs["howMany"])
        except (ValueError, TypeError):
            obs["howMany"] = None

    return obs


@dlt.source
def ebird_source(
    region_code: str = "US-AZ",
    max_results: int = 10000,
    days_back: int = 30,
):
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
        url = f"{EBIRD_API_BASE}/data/obs/{region}/recent"
        params = {"back": back, "maxResults": max_results, "includeProvisional": True}

        try:
            response = dlt_requests.get(url, headers=get_api_headers(), params=params)
            response.raise_for_status()
            for obs in response.json():
                yield process_observation(obs, region)
        except Exception as e:
            print(f"Error fetching recent observations for {region}: {e}")

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
        url = f"{EBIRD_API_BASE}/data/obs/{region}/recent/notable"
        params = {"back": back, "maxResults": max_results}

        try:
            response = dlt_requests.get(url, headers=get_api_headers(), params=params)
            response.raise_for_status()
            for obs in response.json():
                yield process_observation(obs, region, is_notable=True)
        except Exception as e:
            print(f"Error fetching notable observations for {region}: {e}")

    @dlt.resource(primary_key="speciesCode", write_disposition="replace")
    def species_list(region: str = region_code) -> Iterator[dict[str, Any]]:
        url = f"{EBIRD_API_BASE}/product/spplist/{region}"

        try:
            response = dlt_requests.get(url, headers=get_api_headers())
            response.raise_for_status()
            species_codes = response.json()
            for idx, species_code in enumerate(species_codes):
                yield {
                    "speciesCode": species_code,
                    "region": region,
                    "order": idx,
                    "_loaded_at": loaded_at,
                }
        except Exception as e:
            print(f"Error fetching species list for {region}: {e}")

    @dlt.resource(
        primary_key="locId",
        write_disposition="merge",
        columns={
            "lat": {"data_type": "double"},
            "lng": {"data_type": "double"},
            "numSpeciesAllTime": {"data_type": "bigint"},
        },
    )
    def hotspots(region: str = region_code) -> Iterator[dict[str, Any]]:
        url = f"{EBIRD_API_BASE}/ref/hotspot/{region}"
        params = {"fmt": "json"}

        try:
            response = dlt_requests.get(url, headers=get_api_headers(), params=params)
            response.raise_for_status()
            for hotspot in response.json():
                hotspot["_loaded_at"] = loaded_at
                hotspot["_region_code"] = region
                yield hotspot
        except Exception as e:
            print(f"Error fetching hotspots for {region}: {e}")

    @dlt.resource(primary_key="sciName", write_disposition="replace")
    def taxonomy() -> Iterator[dict[str, Any]]:
        url = f"{EBIRD_API_BASE}/ref/taxonomy/ebird"
        params = {"fmt": "json", "locale": "en"}

        try:
            response = dlt_requests.get(url, headers=get_api_headers(), params=params)
            response.raise_for_status()
            for species in response.json():
                species["_loaded_at"] = loaded_at
                yield species
        except Exception as e:
            print(f"Error fetching taxonomy: {e}")

    @dlt.resource(primary_key=["regionCode", "year", "month", "day"], write_disposition="merge")
    def region_stats(region: str = region_code, back: int = days_back) -> Iterator[dict[str, Any]]:
        end_date = pendulum.now()

        for days_ago in range(back):
            date = end_date.subtract(days=days_ago)

            try:
                response = dlt_requests.get(
                    f"{EBIRD_API_BASE}/product/stats/{region}/{date.year}/{date.month}/{date.day}",
                    headers=get_api_headers(),
                )

                if response.status_code == 200:
                    data = response.json()
                    yield {
                        "regionCode": region,
                        "year": date.year,
                        "month": date.month,
                        "day": date.day,
                        "date": date.date().isoformat(),
                        "numChecklists": data.get("numChecklists"),
                        "numContributors": data.get("numContributors"),
                        "numSpecies": data.get("numSpecies"),
                        "_loaded_at": loaded_at,
                    }
            except Exception as e:
                print(f"Error fetching stats for {region} on {date.date()}: {e}")

    return [
        recent_observations,
        notable_observations,
        species_list,
        hotspots,
        taxonomy,
        region_stats,
    ]


class EbirdPipelineSource:
    """eBird pipeline source implementing the PipelineSource protocol."""

    def __init__(self, config: PipelineConfig) -> None:
        self.name = config.name
        self.config = config
        self._region = config.params.get("region_code", "US-AZ")
        self._max_results = config.params.get("max_results", 10000)
        self._days_back = config.params.get("days_back", 30)

    def resources(self) -> list:
        source = ebird_source(
            region_code=self._region,
            max_results=self._max_results,
            days_back=self._days_back,
        )
        return source.resources.values()

    def load(self, smoke: bool = False):
        schema_name = self.config.resolve_schema_name()
        pipeline = dlt.pipeline(
            pipeline_name=f"{self.name}_api",
            destination=dlt.destinations.duckdb(credentials=settings.database_path),
            dataset_name=schema_name,
            pipelines_dir=settings.dlt_data_dir,
            progress="log",
        )

        source = ebird_source(
            region_code=self._region,
            max_results=self._max_results,
            days_back=self._days_back,
        )
        if smoke:
            source.add_limit(max_items=5)
        print(f"Starting eBird pipeline [{schema_name}]{'  [SMOKE]' if smoke else ''}...")
        info = pipeline.run(source)

        print("\neBird data loaded successfully!")
        print(f"  Pipeline: {pipeline.pipeline_name}")
        print(f"  Schema: {schema_name}")
        print(f"  Region: {self._region}")
        print(f"  Days back: {self._days_back}")
        print(f"\n{info}")

        return pipeline

    def validate_config(self) -> bool:
        return bool(os.getenv("EBIRD_API_TOKEN"))


def create_pipeline(config: PipelineConfig) -> EbirdPipelineSource:
    return EbirdPipelineSource(config)
