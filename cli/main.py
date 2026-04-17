"""Databox CLI — dataset-agnostic data pipeline tool."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="databox",
    help="Dataset-agnostic data pipeline tool for ingestion, transformation, and quality checks.",
    no_args_is_help=True,
)


@app.command(name="list")
def list_pipelines():
    """List all registered pipelines."""
    from rich.console import Console
    from rich.table import Table

    from sources.registry import get_registry

    console = Console()
    registry = get_registry()

    if not registry:
        console.print("[yellow]No pipelines registered.[/yellow]")
        console.print("Add a config.yaml to sources/<name>/ to register a pipeline.")
        return

    tbl = Table(title="Registered Pipelines")
    tbl.add_column("Name", style="cyan")
    tbl.add_column("Source Module")
    tbl.add_column("Schema")
    tbl.add_column("Schedule")
    tbl.add_column("Valid")

    for name, source in sorted(registry.items()):
        cfg = source.config
        valid = source.validate_config()
        tbl.add_row(
            name,
            cfg.source_module,
            cfg.resolve_schema_name(),
            cfg.schedule.cron,
            "[green]Yes[/green]" if valid else "[red]No[/red]",
        )

    console.print(tbl)


@app.command()
def run(
    name: str = typer.Argument(..., help="Pipeline name (e.g. ebird)"),
):
    """Run a registered pipeline by name."""
    from sources.registry import get_source

    source = get_source(name)

    if not source.validate_config():
        msg = f"Pipeline '{name}' config invalid. Check .env and config."
        typer.echo(msg, err=True)
        raise typer.Exit(code=1)

    source.load()


@app.command()
def validate(
    name: str = typer.Argument(..., help="Pipeline name to validate"),
):
    """Validate a pipeline's configuration and credentials."""
    from sources.registry import get_source

    source = get_source(name)
    valid = source.validate_config()
    if valid:
        typer.echo(f"Pipeline '{name}' configuration is valid.")
    else:
        typer.echo(f"Pipeline '{name}' configuration is INVALID.", err=True)
        raise typer.Exit(code=1)


_transform_app = typer.Typer(help="SQLMesh transformation commands.")
app.add_typer(_transform_app, name="transform")


@_transform_app.command("plan")
def transform_plan(
    project: str = typer.Argument(
        None, help="Transform project name (e.g. ebird). Defaults to all."
    ),
):
    """Preview SQLMesh transformation changes."""
    import subprocess
    import sys

    from config.settings import PROJECT_ROOT

    projects = _resolve_transform_projects(project)
    for proj in projects:
        proj_dir = PROJECT_ROOT / "transforms" / proj
        if not proj_dir.exists():
            typer.echo(f"Transform project '{proj}' not found at {proj_dir}", err=True)
            continue
        typer.echo(f"Planning transforms for: {proj}")
        from pathlib import Path

        sqlmesh_bin = str(Path(sys.executable).parent / "sqlmesh")
        result = subprocess.run(
            [sqlmesh_bin, "plan", "--auto-apply"],
            cwd=str(proj_dir),
        )
        if result.returncode != 0:
            raise typer.Exit(code=result.returncode)


@_transform_app.command("run")
def transform_run(
    project: str = typer.Argument(None, help="Transform project name. Defaults to all."),
):
    """Apply SQLMesh transformations."""
    import subprocess
    import sys

    from config.settings import PROJECT_ROOT

    projects = _resolve_transform_projects(project)
    for proj in projects:
        proj_dir = PROJECT_ROOT / "transforms" / proj
        if not proj_dir.exists():
            typer.echo(f"Transform project '{proj}' not found at {proj_dir}", err=True)
            continue
        typer.echo(f"Running transforms for: {proj}")
        from pathlib import Path

        sqlmesh_bin = str(Path(sys.executable).parent / "sqlmesh")
        result = subprocess.run(
            [sqlmesh_bin, "run"],
            cwd=str(proj_dir),
        )
        if result.returncode != 0:
            raise typer.Exit(code=result.returncode)


@_transform_app.command("test")
def transform_test(
    project: str = typer.Argument(None, help="Transform project name. Defaults to all."),
):
    """Run SQLMesh tests."""
    import subprocess
    import sys

    from config.settings import PROJECT_ROOT

    projects = _resolve_transform_projects(project)
    for proj in projects:
        proj_dir = PROJECT_ROOT / "transforms" / proj
        if not proj_dir.exists():
            typer.echo(f"Transform project '{proj}' not found at {proj_dir}", err=True)
            continue
        typer.echo(f"Testing transforms for: {proj}")
        from pathlib import Path

        sqlmesh_bin = str(Path(sys.executable).parent / "sqlmesh")
        result = subprocess.run(
            [sqlmesh_bin, "test"],
            cwd=str(proj_dir),
        )
        if result.returncode != 0:
            raise typer.Exit(code=result.returncode)


_quality_app = typer.Typer(help="Data quality commands.")
app.add_typer(_quality_app, name="quality")


@_quality_app.command("check")
def quality_check(
    table: str = typer.Argument(..., help="Table name (schema.table) to check"),
):
    """Run data quality checks on a table."""
    from config.settings import settings
    from quality.engine import check_table

    db_path = settings.database_path
    if not db_path.exists():
        typer.echo(f"Database not found at {db_path}", err=True)
        raise typer.Exit(code=1)

    try:
        result = check_table(table, db_path)
    except Exception as e:
        typer.echo(f"Error checking table: {e}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"Table: {result['table']}")
    typer.echo(f"  Total rows: {result['row_count']}")
    typer.echo("  Null counts:")
    for col, null_count in result["null_counts"]:
        marker = " (!)" if null_count > 0 else ""
        typer.echo(f"    {col}: {null_count}{marker}")
    if result["latest_load"]:
        typer.echo(f"  Latest load: {result['latest_load']}")


@_quality_app.command("report")
def quality_report():
    """Run all configured quality rules against loaded data and show a report."""
    from rich.console import Console
    from rich.table import Table

    from config.pipeline_config import load_all_pipeline_configs
    from config.settings import settings
    from quality.engine import run_report

    console = Console()
    db_path = settings.database_path

    if not db_path.exists():
        console.print("[yellow]Database not found. Run a pipeline first.[/yellow]")
        raise typer.Exit(code=1)

    configs = load_all_pipeline_configs()
    results = run_report(db_path, configs)

    tbl = Table(title="Quality Report")
    tbl.add_column("Pipeline", style="cyan")
    tbl.add_column("Table", style="green")
    tbl.add_column("Rows", justify="right")
    tbl.add_column("Freshness")
    tbl.add_column("Rule")
    tbl.add_column("Status")

    for r in results:
        status_str = r["status"]
        if status_str.startswith("OK"):
            styled = f"[green]{status_str}[/green]"
        elif status_str.startswith("FAIL"):
            styled = f"[red]{status_str}[/red]"
        elif status_str.startswith("ERROR"):
            styled = f"[bold red]{status_str}[/bold red]"
        else:
            styled = f"[yellow]{status_str}[/yellow]"
        tbl.add_row(
            r["pipeline"],
            r["table"],
            str(r["rows"]),
            r["freshness"],
            r["rule"],
            styled,
        )

    console.print(tbl)

    failures = sum(
        1 for r in results if r["status"].startswith("FAIL") or r["status"].startswith("ERROR")
    )
    if failures:
        console.print(f"\n[red]{failures} check(s) failed.[/red]")
        raise typer.Exit(code=1)
    else:
        console.print("\n[green]All checks passed.[/green]")


@app.command()
def status():
    """Show pipeline status and data freshness."""
    import duckdb
    from rich.console import Console
    from rich.table import Table

    from config.settings import settings
    from sources.registry import get_registry

    console = Console()
    db_path = settings.database_path

    if not db_path.exists():
        console.print("[yellow]Database not found. Run a pipeline first.[/yellow]")
        return

    con = duckdb.connect(str(db_path), read_only=True)

    try:
        schemas = con.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('information_schema', 'pg_catalog')"
        ).fetchall()

        table = Table(title="Database Status")
        table.add_column("Schema", style="cyan")
        table.add_column("Table", style="green")
        table.add_column("Rows", justify="right")
        table.add_column("Latest Load")

        for (schema,) in schemas:
            try:
                tables = con.execute(
                    f"SELECT table_name FROM information_schema.tables "
                    f"WHERE table_schema = '{schema}'"
                ).fetchall()
                for (tbl,) in tables:
                    fqn = f"{schema}.{tbl}"
                    count = con.execute(f"SELECT COUNT(*) FROM {fqn}").fetchone()[0]
                    try:
                        latest = con.execute(f"SELECT MAX(_loaded_at) FROM {fqn}").fetchone()[0]
                    except Exception:
                        latest = "N/A"
                    table.add_row(schema, tbl, str(count), str(latest) if latest else "N/A")
            except Exception:
                continue

        console.print(table)

        registry = get_registry()
        if registry:
            console.print("\n[bold]Registered Pipelines:[/bold]")
            for name, source in sorted(registry.items()):
                valid = source.validate_config()
                status_icon = "[green]valid[/green]" if valid else "[red]invalid[/red]"
                console.print(f"  {name}: {status_icon}")
    finally:
        con.close()


def _resolve_transform_projects(project: str | None) -> list[str]:
    from config.settings import PROJECT_ROOT

    transforms_dir = PROJECT_ROOT / "transforms"
    if project:
        return [project]

    candidates: list[str] = []
    for child in sorted(transforms_dir.iterdir()):
        if (
            child.is_dir()
            and not child.name.startswith("_")
            and not child.name.startswith(".")
            and (child / "config.yaml").exists()
        ):
            candidates.append(child.name)

    if not candidates:
        raise typer.BadParameter(f"No transform projects found in {transforms_dir}")

    return candidates
