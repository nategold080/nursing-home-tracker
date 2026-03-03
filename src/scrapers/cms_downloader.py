"""CMS Data Downloader — fetches CSV datasets from data.cms.gov.

Downloads nursing home datasets from CMS's Provider Data Catalog using the
metastore API to find direct bulk CSV download URLs. This is much faster than
paginated API calls. Falls back to pagination if bulk download fails.
All datasets are freely available. We cache raw files locally to avoid
re-downloading on subsequent runs.
"""

import csv
import io
import time
from pathlib import Path

import httpx
import yaml
from rich.console import Console

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yaml"
CACHE_DIR = PROJECT_ROOT / "data" / "raw"

USER_AGENT = "DataFactory/1.0 (research; contact: nathanmauricegoldberg@gmail.com)"
DELAY_SECONDS = 2
PAGE_SIZE = 1500  # CMS API maximum


def load_config() -> dict:
    """Load source configuration from YAML."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_cache_path(source_key: str) -> Path:
    """Get the cache file path for a given source."""
    return CACHE_DIR / f"{source_key}.csv"


def is_cached(source_key: str) -> bool:
    """Check if a source's data is already cached."""
    cache_path = get_cache_path(source_key)
    if not cache_path.exists():
        return False
    # Consider cache valid for 24 hours
    age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
    return age_hours < 24


def _get_bulk_download_url(dataset_id: str, client: httpx.Client) -> str | None:
    """Get the direct bulk CSV download URL from CMS metastore."""
    url = f"https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{dataset_id}"
    try:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
        for dist in data.get("distribution", []):
            dl_url = dist.get("downloadURL", dist.get("accessURL", ""))
            if dl_url and ".csv" in dl_url.lower():
                return dl_url
    except Exception:
        pass
    return None


def download_bulk(dataset_id: str, dest: Path, source_name: str) -> bool:
    """Download a complete CMS dataset via direct bulk CSV URL (single request)."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/csv,application/csv,*/*",
    }

    try:
        with httpx.Client(timeout=300.0, follow_redirects=True, headers=headers) as client:
            # Get direct download URL from metastore
            bulk_url = _get_bulk_download_url(dataset_id, client)
            if not bulk_url:
                console.print(f"  [yellow]⚠[/yellow] {source_name}: No bulk URL found, falling back to pagination")
                return download_paginated(dataset_id, dest, source_name)

            console.print(f"  Downloading [cyan]{source_name}[/cyan] (bulk)...")
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Stream the download to avoid loading entire file into memory
            with client.stream("GET", bulk_url) as response:
                response.raise_for_status()
                total_bytes = int(response.headers.get("content-length", 0))
                downloaded = 0
                with open(dest, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_bytes:
                            pct = 100 * downloaded / total_bytes
                            console.print(f"    {downloaded / 1024 / 1024:.1f} MB ({pct:.0f}%)", end="\r")

            # Count rows
            row_count = sum(1 for _ in open(dest)) - 1  # subtract header
            size_mb = dest.stat().st_size / (1024 * 1024)
            console.print(f"  [green]✓[/green] {source_name}: {row_count:,} records, {size_mb:.1f} MB")
            return True

    except httpx.HTTPStatusError as e:
        console.print(f"  [red]✗[/red] {source_name}: HTTP {e.response.status_code}")
        return False
    except httpx.RequestError as e:
        console.print(f"  [red]✗[/red] {source_name}: {e}")
        return False


def _get_total_count(dataset_id: str, client: httpx.Client) -> int:
    """Get the total number of records for a dataset."""
    url = f"https://data.cms.gov/provider-data/api/1/datastore/query/{dataset_id}/0"
    params = {"limit": 1, "offset": 0, "count": "true", "results": "false"}
    response = client.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return data.get("count", 0)


def _download_page(dataset_id: str, offset: int, client: httpx.Client) -> str:
    """Download one page of CSV data from CMS API."""
    url = f"https://data.cms.gov/provider-data/api/1/datastore/query/{dataset_id}/0"
    params = {
        "limit": PAGE_SIZE,
        "offset": offset,
        "format": "csv",
    }
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.text


def download_paginated(dataset_id: str, dest: Path, source_name: str) -> bool:
    """Download a complete CMS dataset via paginated CSV requests (fallback)."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/csv,application/csv,*/*",
    }

    try:
        with httpx.Client(timeout=120.0, follow_redirects=True, headers=headers) as client:
            total = _get_total_count(dataset_id, client)
            console.print(f"  Downloading [cyan]{source_name}[/cyan] ({total:,} records, paginated)...")

            if total == 0:
                console.print(f"  [yellow]⚠[/yellow] {source_name}: 0 records found")
                return False

            dest.parent.mkdir(parents=True, exist_ok=True)
            header_written = False
            rows_downloaded = 0

            with open(dest, "w", newline="") as outfile:
                offset = 0
                while offset < total:
                    page_csv = _download_page(dataset_id, offset, client)
                    reader = csv.reader(io.StringIO(page_csv))

                    for i, row in enumerate(reader):
                        if i == 0:
                            if not header_written:
                                outfile.write(",".join(f'"{c}"' for c in row) + "\n")
                                header_written = True
                            continue
                        outfile.write(",".join(f'"{c}"' for c in row) + "\n")
                        rows_downloaded += 1

                    offset += PAGE_SIZE
                    pct = min(100, 100 * rows_downloaded / total)
                    console.print(f"    {rows_downloaded:,}/{total:,} ({pct:.0f}%)", end="\r")
                    time.sleep(DELAY_SECONDS)

            size_mb = dest.stat().st_size / (1024 * 1024)
            console.print(f"  [green]✓[/green] {source_name}: {rows_downloaded:,} records, {size_mb:.1f} MB")
            return True

    except httpx.HTTPStatusError as e:
        console.print(f"  [red]✗[/red] {source_name}: HTTP {e.response.status_code}")
        return False
    except httpx.RequestError as e:
        console.print(f"  [red]✗[/red] {source_name}: {e}")
        return False


def download_source(source_key: str, force: bool = False) -> bool:
    """Download a single CMS dataset (prefers bulk download)."""
    config = load_config()
    sources = config.get("sources", {})

    if source_key not in sources:
        console.print(f"[red]Unknown source: {source_key}[/red]")
        console.print(f"Available sources: {', '.join(sources.keys())}")
        return False

    source = sources[source_key]
    cache_path = get_cache_path(source_key)

    if not force and is_cached(source_key):
        console.print(f"  [yellow]⟳[/yellow] {source['name']}: cached (use --force to re-download)")
        return True

    dataset_id = source["dataset_id"]
    return download_bulk(dataset_id, cache_path, source["name"])


def download_all(force: bool = False) -> dict:
    """Download all CMS datasets. Returns dict of source_key -> success."""
    config = load_config()
    sources = config.get("sources", {})
    results = {}

    console.print(f"\n[bold blue]Downloading {len(sources)} CMS datasets...[/bold blue]")
    console.print(f"Cache directory: {CACHE_DIR}\n")

    for source_key in sources:
        results[source_key] = download_source(source_key, force=force)

    succeeded = sum(1 for v in results.values() if v)
    console.print(f"\n[bold]Download complete: {succeeded}/{len(sources)} succeeded[/bold]")

    return results
