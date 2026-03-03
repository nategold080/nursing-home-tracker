"""CLI interface for Nursing Home Inspection & Deficiency Tracker.

Commands: download, extract, normalize, validate, export, dashboard, stats
"""

import click
from pathlib import Path
from rich.console import Console

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Nursing Home Inspection & Deficiency Tracker

    Cross-linked database of nursing home quality, ownership, and enforcement
    data from CMS. Connects deficiency citations, penalties, ownership chains
    (including PE/REIT), staffing levels, and quality measures across 14,000+
    US nursing homes.
    """
    pass


@cli.command()
@click.option("--source", "-s", help="Specific source to download (default: all)")
@click.option("--force", "-f", is_flag=True, help="Re-download even if cached")
def download(source, force):
    """Download CSV datasets from CMS data.cms.gov."""
    from src.scrapers.cms_downloader import download_all, download_source
    if source:
        download_source(source, force=force)
    else:
        download_all(force=force)


@cli.command()
@click.option("--source", "-s", help="Extract from specific source only")
def extract(source):
    """Extract and parse structured records from raw CSV downloads."""
    from src.extractors.csv_parser import extract_all, extract_source
    if source:
        extract_source(source)
    else:
        extract_all()


@cli.command()
def normalize():
    """Normalize entities and classify ownership types (PE, REIT, nonprofit, etc.)."""
    from src.normalization.owners import normalize_owners
    normalize_owners()


@cli.command()
def validate():
    """Run data quality validation and compute quality scores."""
    from src.validation.quality import validate_all
    validate_all()


@cli.command()
@click.option("--format", "-f", "fmt",
              type=click.Choice(["csv", "json", "excel", "markdown", "all"]),
              default="all")
@click.option("--output-dir", "-o", default="data/exports", help="Output directory")
def export(fmt, output_dir):
    """Export data in various formats."""
    from src.export.exporter import export_data
    export_data(fmt, output_dir)


@cli.command()
@click.option("--port", "-p", type=int, default=8501, help="Dashboard port")
def dashboard(port):
    """Launch the Streamlit dashboard."""
    import subprocess
    subprocess.run([
        "streamlit", "run", "src/dashboard/app.py",
        "--server.port", str(port)
    ])


@cli.command()
def stats():
    """Show database statistics."""
    from src.storage.database import get_stats
    get_stats()


@cli.command()
@click.option("--skip-download", is_flag=True, help="Skip download step (use cached data)")
@click.option("--force-download", is_flag=True, help="Force re-download even if cached")
def pipeline(skip_download, force_download):
    """Run the full pipeline: download → extract → normalize → validate → store."""
    console.print("[bold blue]Starting full pipeline...[/bold blue]")
    from src.scrapers.cms_downloader import download_all
    from src.extractors.csv_parser import extract_all
    from src.normalization.owners import normalize_owners
    from src.validation.quality import validate_all
    from src.storage.database import init_db, store_source_data

    # Initialize database
    console.print("\n[bold]Initializing database...[/bold]")
    init_db()

    if not skip_download:
        console.print("\n[bold]Step 1/5: Downloading CMS datasets...[/bold]")
        download_all(force=force_download)
    else:
        console.print("\n[bold]Step 1/5: Skipping download (using cached data)...[/bold]")

    console.print("\n[bold]Step 2/5: Extracting records...[/bold]")
    all_records = extract_all()

    console.print("\n[bold]Step 3/5: Storing records...[/bold]")
    # Load providers first, then other tables
    if "provider_info" in all_records and all_records["provider_info"]:
        store_source_data("provider_info", all_records["provider_info"])
    for source_key, records in all_records.items():
        if source_key != "provider_info" and records:
            store_source_data(source_key, records)

    console.print("\n[bold]Step 4/5: Normalizing entities...[/bold]")
    normalize_owners()

    console.print("\n[bold]Step 5/5: Validating data quality...[/bold]")
    validate_all()

    console.print("\n[bold green]Pipeline complete![/bold green]")


if __name__ == "__main__":
    cli()
