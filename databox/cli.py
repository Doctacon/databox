"""Command-line interface for Databox."""

import click
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from pipelines.sources.example_api import load_example_api_data
from pipelines.sources.csv_files import load_csv_file, load_csv_directory
from config import settings

console = Console()


@click.group()
def cli():
    """Databox - World-class data project using dlt and sqlmesh."""
    pass


@cli.group()
def pipeline():
    """Manage data pipelines."""
    pass


@pipeline.command()
def list():
    """List available pipelines."""
    table = Table(title="Available Pipelines")
    table.add_column("Pipeline", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Type", style="yellow")
    
    table.add_row("example_api", "Fetch data from JSONPlaceholder API", "API")
    table.add_row("csv_files", "Load CSV files to database", "File")
    
    console.print(table)


@pipeline.command()
@click.argument("name")
@click.option("--file", "-f", help="File path for file-based pipelines")
@click.option("--directory", "-d", help="Directory path for directory-based pipelines")
def run(name: str, file: str = None, directory: str = None):
    """Run a specific pipeline."""
    console.print(f"[bold cyan]Running pipeline: {name}[/bold cyan]")
    
    try:
        if name == "example_api":
            load_example_api_data()
        elif name == "csv_files":
            if file:
                load_csv_file(file)
            elif directory:
                load_csv_directory(directory)
            else:
                console.print("[bold red]Error:[/bold red] CSV pipeline requires --file or --directory")
                sys.exit(1)
        else:
            console.print(f"[bold red]Error:[/bold red] Unknown pipeline: {name}")
            sys.exit(1)
            
        console.print("[bold green]Pipeline completed successfully![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Pipeline failed:[/bold red] {str(e)}")
        sys.exit(1)


@cli.group()
def transform():
    """Manage SQLMesh transformations."""
    pass


@transform.command()
def plan():
    """Plan SQLMesh changes."""
    import subprocess
    
    console.print("[bold cyan]Planning SQLMesh changes...[/bold cyan]")
    result = subprocess.run(
        ["sqlmesh", "plan"],
        cwd=str(settings.transformations_dir),
        capture_output=False
    )
    
    if result.returncode != 0:
        console.print("[bold red]SQLMesh plan failed[/bold red]")
        sys.exit(1)


@transform.command()
def run():
    """Apply SQLMesh transformations."""
    import subprocess
    
    console.print("[bold cyan]Running SQLMesh transformations...[/bold cyan]")
    result = subprocess.run(
        ["sqlmesh", "run"],
        cwd=str(settings.transformations_dir),
        capture_output=False
    )
    
    if result.returncode != 0:
        console.print("[bold red]SQLMesh run failed[/bold red]")
        sys.exit(1)


@transform.command()
def test():
    """Run SQLMesh tests."""
    import subprocess
    
    console.print("[bold cyan]Running SQLMesh tests...[/bold cyan]")
    result = subprocess.run(
        ["sqlmesh", "test"],
        cwd=str(settings.transformations_dir),
        capture_output=False
    )
    
    if result.returncode != 0:
        console.print("[bold red]SQLMesh tests failed[/bold red]")
        sys.exit(1)


@transform.command()
def ui():
    """Start SQLMesh UI."""
    import subprocess
    
    console.print("[bold cyan]Starting SQLMesh UI...[/bold cyan]")
    subprocess.run(
        ["sqlmesh", "ui"],
        cwd=str(settings.transformations_dir)
    )


@cli.command()
def init():
    """Initialize the project (create directories, install dependencies)."""
    console.print("[bold cyan]Initializing Databox project...[/bold cyan]")
    
    # Create directories
    directories = [
        "data/raw", "data/staging", "data/processed", "data/dlt",
        "logs", "notebooks"
    ]
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        console.print(f"✓ Created directory: {dir_path}")
    
    # Create .env from template
    if not Path(".env").exists() and Path(".env.example").exists():
        import shutil
        shutil.copy(".env.example", ".env")
        console.print("✓ Created .env from template")
    
    console.print("[bold green]Project initialized successfully![/bold green]")


@cli.command()
def info():
    """Show project information."""
    table = Table(title="Databox Project Information")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Project Root", str(settings.project_root))
    table.add_row("Data Directory", str(settings.data_dir))
    table.add_row("Database URL", settings.database_url)
    table.add_row("DLT Data Directory", str(settings.dlt_data_dir))
    table.add_row("SQLMesh Project", str(settings.sqlmesh_project_root))
    table.add_row("Log Level", settings.log_level)
    
    console.print(table)


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()