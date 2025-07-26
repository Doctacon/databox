"""CSV file source pipeline using dlt."""

import dlt
from typing import Iterator, Dict, Any
import pandas as pd
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config import settings


@dlt.source
def csv_file_source(file_path: str, encoding: str = "utf-8"):
    """Source that reads CSV files and loads them to the database."""
    
    @dlt.resource(
        write_disposition="replace"  # Replace data on each load
    )
    def read_csv() -> Iterator[Dict[str, Any]]:
        """Read a CSV file and yield rows."""
        # Check if file exists
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        # Read CSV in chunks for memory efficiency
        chunk_size = 10000
        
        # Infer the table name from file name
        table_name = path.stem.lower().replace(" ", "_").replace("-", "_")
        
        for chunk in pd.read_csv(
            file_path,
            encoding=encoding,
            chunksize=chunk_size,
            parse_dates=True,
            infer_datetime_format=True
        ):
            # Convert DataFrame to records
            for record in chunk.to_dict("records"):
                # Clean up the record
                cleaned_record = {}
                for key, value in record.items():
                    # Clean column names
                    clean_key = key.lower().replace(" ", "_").replace("-", "_")
                    
                    # Handle NaN values
                    if pd.isna(value):
                        cleaned_record[clean_key] = None
                    else:
                        cleaned_record[clean_key] = value
                
                yield cleaned_record
    
    # Set the resource name based on file
    read_csv.__name__ = Path(file_path).stem.lower().replace(" ", "_").replace("-", "_")
    
    return read_csv


@dlt.source
def csv_directory_source(directory_path: str, pattern: str = "*.csv", encoding: str = "utf-8"):
    """Source that reads all CSV files from a directory."""
    
    dir_path = Path(directory_path)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    
    # Find all CSV files
    csv_files = list(dir_path.glob(pattern))
    
    if not csv_files:
        raise ValueError(f"No CSV files found in {directory_path} with pattern {pattern}")
    
    # Create a resource for each CSV file
    resources = []
    
    for csv_file in csv_files:
        @dlt.resource(
            name=csv_file.stem.lower().replace(" ", "_").replace("-", "_"),
            write_disposition="replace"
        )
        def read_csv_file(file_path: str = str(csv_file)) -> Iterator[Dict[str, Any]]:
            """Read a specific CSV file."""
            chunk_size = 10000
            
            for chunk in pd.read_csv(
                file_path,
                encoding=encoding,
                chunksize=chunk_size,
                parse_dates=True,
                infer_datetime_format=True
            ):
                for record in chunk.to_dict("records"):
                    cleaned_record = {}
                    for key, value in record.items():
                        clean_key = key.lower().replace(" ", "_").replace("-", "_")
                        cleaned_record[clean_key] = None if pd.isna(value) else value
                    
                    yield cleaned_record
        
        resources.append(read_csv_file)
    
    return resources


def load_csv_file(file_path: str, dataset_name: str = "raw_csv_data"):
    """Load a single CSV file to the database."""
    pipeline = dlt.pipeline(
        pipeline_name="csv_loader",
        destination=dlt.destinations.duckdb(
            credentials=settings.database_url
        ),
        dataset_name=dataset_name,
        dir=str(settings.dlt_data_dir)
    )
    
    source = csv_file_source(file_path)
    info = pipeline.run(source)
    
    print(f"Loaded CSV file: {file_path}")
    print(info)
    
    return info


def load_csv_directory(directory_path: str, dataset_name: str = "raw_csv_data"):
    """Load all CSV files from a directory."""
    pipeline = dlt.pipeline(
        pipeline_name="csv_directory_loader",
        destination=dlt.destinations.duckdb(
            credentials=settings.database_url
        ),
        dataset_name=dataset_name,
        dir=str(settings.dlt_data_dir)
    )
    
    source = csv_directory_source(directory_path)
    info = pipeline.run(source)
    
    print(f"Loaded CSV files from: {directory_path}")
    print(info)
    
    return info


if __name__ == "__main__":
    # Example: Load a single CSV file
    # load_csv_file("data/raw/sales_data.csv")
    
    # Example: Load all CSV files from a directory
    # load_csv_directory("data/raw/")
    
    print("CSV loader ready. Use load_csv_file() or load_csv_directory() to load data.")