"""Data quality validation and quality scoring.

Computes a quality score (0.0–1.0) for each facility based on data
completeness across the 6 CMS datasets. Also validates referential
integrity and flags data anomalies.
"""

from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.storage.database import get_connection

console = Console()

# Quality scoring weights — how much each data component contributes
QUALITY_WEIGHTS = {
    "has_deficiency_data": 0.20,
    "has_penalty_data": 0.15,
    "has_ownership_data": 0.20,
    "has_staffing_data": 0.15,
    "has_quality_measures": 0.15,
    "has_star_rating": 0.10,
    "has_survey_data": 0.05,
}


def compute_quality_scores():
    """Compute quality score for each provider based on data completeness."""
    conn = get_connection()

    providers = conn.execute(
        "SELECT federal_provider_number FROM providers"
    ).fetchall()

    if not providers:
        console.print("  [yellow]No providers to score.[/yellow]")
        conn.close()
        return

    scores = []
    for prov in providers:
        fpn = prov["federal_provider_number"]
        score = _compute_facility_score(conn, fpn)
        scores.append((score, fpn))
        conn.execute(
            "UPDATE providers SET quality_score = ? WHERE federal_provider_number = ?",
            (score, fpn),
        )

    conn.commit()

    # Stats
    if scores:
        avg_score = sum(s[0] for s in scores) / len(scores)
        above_threshold = sum(1 for s in scores if s[0] >= 0.5)
        console.print(f"  [green]✓[/green] Scored {len(scores):,} facilities")
        console.print(f"    Average quality score: {avg_score:.3f}")
        console.print(f"    Above 0.5 threshold: {above_threshold:,} ({100*above_threshold/len(scores):.1f}%)")

    conn.close()


def _compute_facility_score(conn, fpn: str) -> float:
    """Compute quality score for a single facility."""
    components = {}

    # Check deficiency data
    count = conn.execute(
        "SELECT COUNT(*) FROM health_deficiencies WHERE federal_provider_number = ?", (fpn,)
    ).fetchone()[0]
    components["has_deficiency_data"] = 1.0 if count > 0 else 0.0

    # Check penalty data
    count = conn.execute(
        "SELECT COUNT(*) FROM penalties WHERE federal_provider_number = ?", (fpn,)
    ).fetchone()[0]
    components["has_penalty_data"] = 1.0 if count > 0 else 0.0

    # Check ownership data
    count = conn.execute(
        "SELECT COUNT(*) FROM ownership WHERE federal_provider_number = ?", (fpn,)
    ).fetchone()[0]
    components["has_ownership_data"] = 1.0 if count > 0 else 0.0

    # Check staffing data (from provider_info — staffing_rating not null)
    row = conn.execute(
        "SELECT staffing_rating FROM providers WHERE federal_provider_number = ?", (fpn,)
    ).fetchone()
    components["has_staffing_data"] = 1.0 if (row and row["staffing_rating"]) else 0.0

    # Check quality measures
    count = conn.execute(
        "SELECT COUNT(*) FROM quality_measures WHERE federal_provider_number = ?", (fpn,)
    ).fetchone()[0]
    components["has_quality_measures"] = 1.0 if count > 0 else 0.0

    # Check star rating
    row = conn.execute(
        "SELECT overall_rating FROM providers WHERE federal_provider_number = ?", (fpn,)
    ).fetchone()
    components["has_star_rating"] = 1.0 if (row and row["overall_rating"]) else 0.0

    # Check survey data
    count = conn.execute(
        "SELECT COUNT(*) FROM survey_summary WHERE federal_provider_number = ?", (fpn,)
    ).fetchone()[0]
    components["has_survey_data"] = 1.0 if count > 0 else 0.0

    # Weighted sum
    score = sum(
        components.get(k, 0.0) * w for k, w in QUALITY_WEIGHTS.items()
    )
    return round(score, 4)


def validate_referential_integrity():
    """Check that all records reference valid provider IDs."""
    conn = get_connection()
    issues = []

    tables = ["health_deficiencies", "penalties", "ownership", "survey_summary", "quality_measures"]
    for table in tables:
        try:
            orphan_count = conn.execute(f"""
                SELECT COUNT(*) FROM {table} t
                LEFT JOIN providers p ON t.federal_provider_number = p.federal_provider_number
                WHERE p.federal_provider_number IS NULL
            """).fetchone()[0]

            if orphan_count > 0:
                issues.append(f"{table}: {orphan_count:,} orphan records (no matching provider)")
        except Exception:
            pass

    conn.close()

    if issues:
        console.print("  [yellow]Referential integrity issues:[/yellow]")
        for issue in issues:
            console.print(f"    ⚠ {issue}")
    else:
        console.print("  [green]✓[/green] Referential integrity OK")

    return issues


def validate_data_ranges():
    """Check for obviously invalid data values."""
    conn = get_connection()
    issues = []

    # Star ratings should be 1-5
    bad_ratings = conn.execute(
        "SELECT COUNT(*) FROM providers WHERE overall_rating IS NOT NULL AND (overall_rating < 1 OR overall_rating > 5)"
    ).fetchone()[0]
    if bad_ratings:
        issues.append(f"providers: {bad_ratings} records with invalid overall_rating (not 1-5)")

    # Fine amounts should be positive
    bad_fines = conn.execute(
        "SELECT COUNT(*) FROM penalties WHERE fine_amount IS NOT NULL AND fine_amount < 0"
    ).fetchone()[0]
    if bad_fines:
        issues.append(f"penalties: {bad_fines} records with negative fine_amount")

    # Bed counts should be positive
    bad_beds = conn.execute(
        "SELECT COUNT(*) FROM providers WHERE number_of_certified_beds IS NOT NULL AND number_of_certified_beds < 0"
    ).fetchone()[0]
    if bad_beds:
        issues.append(f"providers: {bad_beds} records with negative bed count")

    conn.close()

    if issues:
        console.print("  [yellow]Data range issues:[/yellow]")
        for issue in issues:
            console.print(f"    ⚠ {issue}")
    else:
        console.print("  [green]✓[/green] Data ranges OK")

    return issues


def validate_all():
    """Run all validation checks and compute quality scores."""
    console.print("\n[bold blue]Validating data quality...[/bold blue]\n")

    console.print("[bold]Referential integrity:[/bold]")
    ref_issues = validate_referential_integrity()

    console.print("\n[bold]Data ranges:[/bold]")
    range_issues = validate_data_ranges()

    console.print("\n[bold]Quality scoring:[/bold]")
    compute_quality_scores()

    total_issues = len(ref_issues) + len(range_issues)
    if total_issues:
        console.print(f"\n[yellow]Validation found {total_issues} issue(s)[/yellow]")
    else:
        console.print("\n[bold green]All validations passed.[/bold green]")
