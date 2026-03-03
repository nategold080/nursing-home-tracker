"""SQLite database operations for Nursing Home Tracker.

Uses WAL mode for concurrent read access. Stores all extracted, normalized,
and validated records. Supports cross-table joins on federal_provider_number.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "nursing_homes.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection with WAL mode enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    console.print(f"[green]Database initialized at {DB_PATH}[/green]")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS providers (
    federal_provider_number TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    provider_address TEXT,
    provider_city TEXT,
    provider_state TEXT,
    provider_zip_code TEXT,
    provider_county_name TEXT,
    provider_phone_number TEXT,
    ownership_type TEXT,
    number_of_certified_beds INTEGER,
    number_of_residents_in_certified_beds REAL,
    provider_type TEXT,
    legal_business_name TEXT,
    overall_rating INTEGER,
    health_inspection_rating INTEGER,
    staffing_rating INTEGER,
    quality_measure_rating INTEGER,
    total_weighted_health_survey_score REAL,
    number_of_facility_reported_incidents INTEGER,
    number_of_substantiated_complaints INTEGER,
    number_of_fines INTEGER,
    total_amount_of_fines_in_dollars REAL,
    number_of_payment_denials INTEGER,
    total_number_of_penalties INTEGER,
    quality_score REAL,
    owner_classification TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS health_deficiencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    federal_provider_number TEXT NOT NULL,
    provider_name TEXT,
    provider_state TEXT,
    survey_date TEXT,
    survey_type TEXT,
    deficiency_tag_number TEXT,
    deficiency_description TEXT,
    scope_severity_code TEXT,
    deficiency_corrected TEXT,
    correction_date TEXT,
    inspection_cycle INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS penalties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    federal_provider_number TEXT NOT NULL,
    provider_name TEXT,
    provider_state TEXT,
    penalty_type TEXT,
    fine_amount REAL,
    penalty_date TEXT,
    penalty_status TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ownership (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    federal_provider_number TEXT NOT NULL,
    provider_name TEXT,
    provider_state TEXT,
    owner_name TEXT,
    owner_type TEXT,
    owner_percentage REAL,
    role_description TEXT,
    association_date TEXT,
    normalized_owner_name TEXT,
    owner_classification TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS survey_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    federal_provider_number TEXT NOT NULL,
    provider_name TEXT,
    provider_state TEXT,
    survey_date TEXT,
    survey_type TEXT,
    total_number_of_health_deficiencies INTEGER,
    total_number_of_fire_safety_deficiencies INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quality_measures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    federal_provider_number TEXT NOT NULL,
    provider_name TEXT,
    provider_state TEXT,
    measure_code TEXT,
    measure_description TEXT,
    measure_period TEXT,
    score REAL,
    footnote TEXT,
    used_in_quality_measure_five_star_rating BOOLEAN,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    sources_processed TEXT,
    total_records INTEGER DEFAULT 0,
    errors TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_deficiencies_provider ON health_deficiencies(federal_provider_number);
CREATE INDEX IF NOT EXISTS idx_deficiencies_date ON health_deficiencies(survey_date);
CREATE INDEX IF NOT EXISTS idx_deficiencies_severity ON health_deficiencies(scope_severity_code);
CREATE INDEX IF NOT EXISTS idx_penalties_provider ON penalties(federal_provider_number);
CREATE INDEX IF NOT EXISTS idx_penalties_date ON penalties(penalty_date);
CREATE INDEX IF NOT EXISTS idx_ownership_provider ON ownership(federal_provider_number);
CREATE INDEX IF NOT EXISTS idx_ownership_owner ON ownership(normalized_owner_name);
CREATE INDEX IF NOT EXISTS idx_ownership_classification ON ownership(owner_classification);
CREATE INDEX IF NOT EXISTS idx_survey_provider ON survey_summary(federal_provider_number);
CREATE INDEX IF NOT EXISTS idx_quality_provider ON quality_measures(federal_provider_number);
CREATE INDEX IF NOT EXISTS idx_providers_state ON providers(provider_state);
CREATE INDEX IF NOT EXISTS idx_providers_rating ON providers(overall_rating);
CREATE INDEX IF NOT EXISTS idx_providers_classification ON providers(owner_classification);
"""


# Table name mapping for each source
SOURCE_TABLES = {
    "provider_info": "providers",
    "health_deficiencies": "health_deficiencies",
    "penalties": "penalties",
    "ownership": "ownership",
    "survey_summary": "survey_summary",
    "quality_measures": "quality_measures",
}


def upsert_providers(records: list[dict], conn=None):
    """Insert or update provider records."""
    _conn = conn or get_connection()
    for rec in records:
        fields = {k: v for k, v in rec.items() if v is not None}
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(["?"] * len(fields))
        updates = ", ".join(f"{k}=excluded.{k}" for k in fields.keys() if k != "federal_provider_number")
        sql = f"""
            INSERT INTO providers ({cols}) VALUES ({placeholders})
            ON CONFLICT(federal_provider_number) DO UPDATE SET {updates}, updated_at=datetime('now')
        """
        _conn.execute(sql, list(fields.values()))
    _conn.commit()
    if conn is None:
        _conn.close()


def _validate_table_name(table: str):
    """Validate table name against known tables to prevent SQL injection."""
    valid_tables = set(SOURCE_TABLES.values())
    if table not in valid_tables:
        raise ValueError(f"Invalid table name: {table}")


def insert_records(table: str, records: list[dict], conn=None):
    """Insert records into a table (non-provider tables with auto-increment IDs)."""
    if not records:
        return
    _validate_table_name(table)
    _conn = conn or get_connection()
    # Use first record to determine columns (exclude 'id' and 'created_at')
    sample = records[0]
    cols = [k for k in sample.keys() if k not in ("id", "created_at")]
    col_str = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})"

    for rec in records:
        values = [rec.get(c) for c in cols]
        # Convert date objects to strings
        values = [str(v) if hasattr(v, "isoformat") else v for v in values]
        _conn.execute(sql, values)
    _conn.commit()
    if conn is None:
        _conn.close()


def clear_table(table: str, conn=None):
    """Clear all records from a table."""
    _validate_table_name(table)
    _conn = conn or get_connection()
    _conn.execute(f"DELETE FROM {table}")
    _conn.commit()
    if conn is None:
        _conn.close()


def store_source_data(source_key: str, records: list[dict]):
    """Store extracted records for a given source, clearing old data first."""
    table = SOURCE_TABLES.get(source_key)
    if not table:
        console.print(f"[red]Unknown source: {source_key}[/red]")
        return

    clear_table(table)

    if source_key == "provider_info":
        upsert_providers(records)
    else:
        insert_records(table, records)

    console.print(f"  [green]✓[/green] Stored {len(records)} records in {table}")


def get_table_count(table: str) -> int:
    """Get the number of records in a table."""
    conn = get_connection()
    result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    conn.close()
    return result[0]


def get_stats():
    """Print database statistics to console."""
    try:
        conn = get_connection()
    except Exception:
        console.print("[yellow]Database not initialized. Run 'pipeline' first.[/yellow]")
        return

    table = Table(title="Nursing Home Tracker — Database Statistics")
    table.add_column("Table", style="cyan")
    table.add_column("Records", justify="right", style="green")

    total = 0
    for source_key, table_name in SOURCE_TABLES.items():
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            table.add_row(table_name, f"{count:,}")
            total += count
        except sqlite3.OperationalError:
            table.add_row(table_name, "[red]not created[/red]")

    table.add_row("─" * 20, "─" * 10)
    table.add_row("[bold]Total[/bold]", f"[bold]{total:,}[/bold]")

    console.print(table)

    # Show additional stats
    try:
        providers = conn.execute("SELECT COUNT(*) FROM providers").fetchone()[0]
        avg_rating = conn.execute("SELECT AVG(overall_rating) FROM providers WHERE overall_rating IS NOT NULL").fetchone()[0]
        states = conn.execute("SELECT COUNT(DISTINCT provider_state) FROM providers WHERE provider_state IS NOT NULL").fetchone()[0]
        pe_count = conn.execute("SELECT COUNT(*) FROM providers WHERE owner_classification = 'private_equity'").fetchone()[0]
        total_fines = conn.execute("SELECT SUM(fine_amount) FROM penalties WHERE fine_amount IS NOT NULL").fetchone()[0]

        console.print(f"\n[bold]Key Metrics:[/bold]")
        console.print(f"  Facilities: {providers:,}")
        if avg_rating:
            console.print(f"  Avg Star Rating: {avg_rating:.2f}/5.0")
        console.print(f"  States: {states}")
        console.print(f"  PE-Owned Facilities: {pe_count:,}")
        if total_fines:
            console.print(f"  Total Fines: ${total_fines:,.0f}")
    except sqlite3.OperationalError:
        pass

    conn.close()
