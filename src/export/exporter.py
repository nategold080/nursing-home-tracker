"""Data export module — CSV, JSON, Excel, and Markdown outputs.

Exports the full dataset or filtered subsets in multiple formats
for consumption by researchers, journalists, and data platforms.
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from rich.console import Console

from src.storage.database import get_connection, SOURCE_TABLES

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _get_dataframe(table: str) -> pd.DataFrame:
    """Load a full table into a pandas DataFrame."""
    conn = get_connection()
    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    conn.close()
    return df


def _get_enriched_providers() -> pd.DataFrame:
    """Get provider data enriched with deficiency/penalty summaries."""
    conn = get_connection()

    sql = """
    SELECT
        p.*,
        COALESCE(d.deficiency_count, 0) as total_deficiencies,
        COALESCE(d.severe_count, 0) as severe_deficiencies,
        COALESCE(pen.penalty_count, 0) as total_penalties_count,
        COALESCE(pen.total_fines, 0) as total_penalty_amount,
        COALESCE(o.owner_count, 0) as owner_count,
        COALESCE(qm.measure_count, 0) as quality_measure_count
    FROM providers p
    LEFT JOIN (
        SELECT federal_provider_number,
               COUNT(*) as deficiency_count,
               SUM(CASE WHEN scope_severity_code IN ('G','H','I','J','K','L') THEN 1 ELSE 0 END) as severe_count
        FROM health_deficiencies
        GROUP BY federal_provider_number
    ) d ON p.federal_provider_number = d.federal_provider_number
    LEFT JOIN (
        SELECT federal_provider_number,
               COUNT(*) as penalty_count,
               SUM(fine_amount) as total_fines
        FROM penalties
        GROUP BY federal_provider_number
    ) pen ON p.federal_provider_number = pen.federal_provider_number
    LEFT JOIN (
        SELECT federal_provider_number,
               COUNT(*) as owner_count
        FROM ownership
        GROUP BY federal_provider_number
    ) o ON p.federal_provider_number = o.federal_provider_number
    LEFT JOIN (
        SELECT federal_provider_number,
               COUNT(*) as measure_count
        FROM quality_measures
        GROUP BY federal_provider_number
    ) qm ON p.federal_provider_number = qm.federal_provider_number
    ORDER BY p.provider_state, p.provider_name
    """
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df


def export_csv(output_dir: Path):
    """Export all tables as CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Enriched provider summary
    df = _get_enriched_providers()
    path = output_dir / "providers_enriched.csv"
    df.to_csv(path, index=False)
    console.print(f"  [green]✓[/green] {path.name}: {len(df):,} rows")

    # Individual tables
    for source_key, table_name in SOURCE_TABLES.items():
        if table_name == "providers":
            continue  # Already exported enriched version
        df = _get_dataframe(table_name)
        path = output_dir / f"{table_name}.csv"
        df.to_csv(path, index=False)
        console.print(f"  [green]✓[/green] {path.name}: {len(df):,} rows")


def export_json(output_dir: Path):
    """Export all tables as JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    df = _get_enriched_providers()
    path = output_dir / "providers_enriched.json"
    df.to_json(path, orient="records", indent=2, default_handler=str)
    console.print(f"  [green]✓[/green] {path.name}: {len(df):,} records")

    for source_key, table_name in SOURCE_TABLES.items():
        if table_name == "providers":
            continue
        df = _get_dataframe(table_name)
        path = output_dir / f"{table_name}.json"
        df.to_json(path, orient="records", indent=2, default_handler=str)
        console.print(f"  [green]✓[/green] {path.name}: {len(df):,} records")


def export_excel(output_dir: Path):
    """Export a multi-sheet Excel workbook."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "nursing_home_tracker.xlsx"

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df = _get_enriched_providers()
        df.to_excel(writer, sheet_name="Providers", index=False)

        for source_key, table_name in SOURCE_TABLES.items():
            if table_name == "providers":
                continue
            df = _get_dataframe(table_name)
            # Excel sheet names max 31 chars
            sheet_name = table_name[:31].replace("_", " ").title()
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    console.print(f"  [green]✓[/green] {path.name}")


def export_markdown(output_dir: Path):
    """Export a markdown summary report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = get_connection()

    lines = [
        "# Nursing Home Inspection & Deficiency Tracker",
        f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n",
        "## Dataset Summary\n",
    ]

    # Table counts
    total_records = 0
    lines.append("| Table | Records |")
    lines.append("|-------|---------|")
    for source_key, table_name in SOURCE_TABLES.items():
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            lines.append(f"| {table_name} | {count:,} |")
            total_records += count
        except Exception:
            lines.append(f"| {table_name} | — |")
    lines.append(f"| **Total** | **{total_records:,}** |")

    # Key metrics
    try:
        providers = conn.execute("SELECT COUNT(*) FROM providers").fetchone()[0]
        states = conn.execute(
            "SELECT COUNT(DISTINCT provider_state) FROM providers WHERE provider_state IS NOT NULL"
        ).fetchone()[0]
        avg_rating = conn.execute(
            "SELECT AVG(overall_rating) FROM providers WHERE overall_rating IS NOT NULL"
        ).fetchone()[0]
        total_fines = conn.execute(
            "SELECT SUM(fine_amount) FROM penalties WHERE fine_amount IS NOT NULL"
        ).fetchone()[0]
        pe_count = conn.execute(
            "SELECT COUNT(*) FROM providers WHERE owner_classification = 'private_equity'"
        ).fetchone()[0]

        lines.append("\n## Key Metrics\n")
        lines.append(f"- **Facilities:** {providers:,}")
        lines.append(f"- **States:** {states}")
        if avg_rating:
            lines.append(f"- **Average Star Rating:** {avg_rating:.2f}/5.0")
        if total_fines:
            lines.append(f"- **Total Fines:** ${total_fines:,.0f}")
        lines.append(f"- **PE-Owned Facilities:** {pe_count:,}")
    except Exception:
        pass

    # Top 10 most penalized
    try:
        top_penalized = conn.execute("""
            SELECT p.provider_name, p.provider_state, p.overall_rating,
                   COUNT(pen.id) as penalty_count, SUM(pen.fine_amount) as total_fines
            FROM providers p
            JOIN penalties pen ON p.federal_provider_number = pen.federal_provider_number
            GROUP BY p.federal_provider_number
            ORDER BY total_fines DESC
            LIMIT 10
        """).fetchall()

        if top_penalized:
            lines.append("\n## Top 10 Most Penalized Facilities\n")
            lines.append("| Facility | State | Stars | Penalties | Total Fines |")
            lines.append("|----------|-------|-------|-----------|-------------|")
            for row in top_penalized:
                name = row["provider_name"] or "Unknown"
                state = row["provider_state"] or "—"
                stars = f"{row['overall_rating']}/5" if row["overall_rating"] else "—"
                fines = f"${row['total_fines']:,.0f}" if row["total_fines"] else "—"
                lines.append(f"| {name} | {state} | {stars} | {row['penalty_count']} | {fines} |")
    except Exception:
        pass

    # Ownership breakdown
    try:
        ownership_breakdown = conn.execute("""
            SELECT owner_classification, COUNT(*) as count
            FROM providers
            WHERE owner_classification IS NOT NULL
            GROUP BY owner_classification
            ORDER BY count DESC
        """).fetchall()

        if ownership_breakdown:
            lines.append("\n## Ownership Breakdown\n")
            lines.append("| Classification | Facilities |")
            lines.append("|---------------|------------|")
            for row in ownership_breakdown:
                lines.append(f"| {row['owner_classification']} | {row['count']:,} |")
    except Exception:
        pass

    lines.append("\n---")
    lines.append("\n*Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com*")

    conn.close()

    path = output_dir / "summary_report.md"
    path.write_text("\n".join(lines))
    console.print(f"  [green]✓[/green] {path.name}")


def export_data(fmt: str, output_dir: str):
    """Export data in the specified format(s)."""
    out = Path(output_dir)
    if not out.is_absolute():
        out = PROJECT_ROOT / out

    console.print(f"\n[bold blue]Exporting data to {out}...[/bold blue]\n")

    if fmt in ("csv", "all"):
        console.print("[bold]CSV exports:[/bold]")
        export_csv(out / "csv")

    if fmt in ("json", "all"):
        console.print("\n[bold]JSON exports:[/bold]")
        export_json(out / "json")

    if fmt in ("excel", "all"):
        console.print("\n[bold]Excel export:[/bold]")
        export_excel(out)

    if fmt in ("markdown", "all"):
        console.print("\n[bold]Markdown report:[/bold]")
        export_markdown(out)

    console.print("\n[bold green]Export complete.[/bold green]")
