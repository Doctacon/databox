"""Example API source pipeline using dlt."""

import dlt
from dlt.sources.helpers import requests
from typing import Iterator, Dict, Any
import pendulum
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config import settings


@dlt.source
def example_api_source(api_base_url: str = "https://jsonplaceholder.typicode.com"):
    """Example API source that fetches data from JSONPlaceholder."""
    
    @dlt.resource(
        primary_key="id",
        write_disposition="merge",
        columns={"id": {"data_type": "bigint"}}
    )
    def users() -> Iterator[Dict[str, Any]]:
        """Fetch users from the API."""
        response = requests.get(f"{api_base_url}/users")
        response.raise_for_status()
        
        for user in response.json():
            # Add metadata
            user["_loaded_at"] = pendulum.now().isoformat()
            yield user
    
    @dlt.resource(
        primary_key="id",
        write_disposition="merge",
        columns={
            "id": {"data_type": "bigint"},
            "userId": {"data_type": "bigint"}
        }
    )
    def posts(updated_after: pendulum.DateTime = None) -> Iterator[Dict[str, Any]]:
        """Fetch posts from the API with optional incremental loading."""
        response = requests.get(f"{api_base_url}/posts")
        response.raise_for_status()
        
        for post in response.json():
            # Add metadata
            post["_loaded_at"] = pendulum.now().isoformat()
            
            # Simple example of incremental loading logic
            if updated_after:
                # In a real API, you'd filter by actual timestamps
                # This is just for demonstration
                post_date = pendulum.now().subtract(days=post["id"])
                if post_date <= updated_after:
                    continue
            
            yield post
    
    @dlt.resource(
        primary_key="id",
        write_disposition="merge",
        columns={
            "id": {"data_type": "bigint"},
            "postId": {"data_type": "bigint"}
        }
    )
    def comments() -> Iterator[Dict[str, Any]]:
        """Fetch comments from the API."""
        response = requests.get(f"{api_base_url}/comments")
        response.raise_for_status()
        
        for comment in response.json():
            comment["_loaded_at"] = pendulum.now().isoformat()
            yield comment
    
    # Return all resources
    return users, posts, comments


def load_example_api_data():
    """Load data from the example API to DuckDB."""
    # Configure the pipeline
    pipeline = dlt.pipeline(
        pipeline_name="example_api",
        destination=dlt.destinations.duckdb(
            credentials=settings.database_url
        ),
        dataset_name="raw_api_data",
        dir=str(settings.dlt_data_dir)
    )
    
    # Create the source
    source = example_api_source()
    
    # Run the pipeline
    info = pipeline.run(source)
    
    # Print the outcome
    print(info)
    
    # Print some statistics
    print(f"Pipeline name: {pipeline.pipeline_name}")
    print(f"Destination: {pipeline.destination}")
    print(f"Dataset name: {pipeline.dataset_name}")
    
    # Show the loaded tables
    with pipeline.sql_client() as client:
        tables = client.execute_sql(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw_api_data'"
        )
        print("\nLoaded tables:")
        for table in tables:
            print(f"  - {table[0]}")
            
            # Show row count
            count = client.execute_sql(
                f"SELECT COUNT(*) FROM raw_api_data.{table[0]}"
            )
            print(f"    Rows: {count[0][0]}")


if __name__ == "__main__":
    load_example_api_data()