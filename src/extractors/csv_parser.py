"""CSV Extractor — parses downloaded CMS CSV files into validated records.

Reads raw CSV files from data/raw/, maps column names to our schema fields,
validates each row through Pydantic models, and returns lists of clean dicts.
"""

import csv
from pathlib import Path
from typing import Optional

import pandas as pd
from rich.console import Console

from src.validation.schemas import SOURCE_SCHEMAS

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"


# Actual CMS CSV column name → our schema field name
# Maps the exact CMS column headers (as they appear in downloaded CSVs)
# to our normalized Pydantic schema field names.
COLUMN_MAPS = {
    "provider_info": {
        "CMS Certification Number (CCN)": "federal_provider_number",
        "Provider Name": "provider_name",
        "Provider Address": "provider_address",
        "City/Town": "provider_city",
        "State": "provider_state",
        "ZIP Code": "provider_zip_code",
        "County/Parish": "provider_county_name",
        "Telephone Number": "provider_phone_number",
        "Ownership Type": "ownership_type",
        "Number of Certified Beds": "number_of_certified_beds",
        "Average Number of Residents per Day": "number_of_residents_in_certified_beds",
        "Provider Type": "provider_type",
        "Legal Business Name": "legal_business_name",
        "Overall Rating": "overall_rating",
        "Health Inspection Rating": "health_inspection_rating",
        "Staffing Rating": "staffing_rating",
        "QM Rating": "quality_measure_rating",
        "Total Weighted Health Survey Score": "total_weighted_health_survey_score",
        "Number of Fines": "number_of_fines",
        "Total Amount of Fines in Dollars": "total_amount_of_fines_in_dollars",
        "Number of Payment Denials": "number_of_payment_denials",
        "Total Number of Penalties": "total_number_of_penalties",
    },
    "health_deficiencies": {
        "CMS Certification Number (CCN)": "federal_provider_number",
        "Provider Name": "provider_name",
        "State": "provider_state",
        "Survey Date": "survey_date",
        "Survey Type": "survey_type",
        "Deficiency Tag Number": "deficiency_tag_number",
        "Deficiency Description": "deficiency_description",
        "Scope Severity Code": "scope_severity_code",
        "Deficiency Corrected": "deficiency_corrected",
        "Correction Date": "correction_date",
        "Inspection Cycle": "inspection_cycle",
    },
    "penalties": {
        "CMS Certification Number (CCN)": "federal_provider_number",
        "Provider Name": "provider_name",
        "State": "provider_state",
        "Penalty Type": "penalty_type",
        "Fine Amount": "fine_amount",
        "Penalty Date": "penalty_date",
    },
    "ownership": {
        "CMS Certification Number (CCN)": "federal_provider_number",
        "Provider Name": "provider_name",
        "State": "provider_state",
        "Owner Name": "owner_name",
        "Owner Type": "owner_type",
        "Ownership Percentage": "owner_percentage",
        "Role played by Owner or Manager in Facility": "role_description",
        "Association Date": "association_date",
    },
    "survey_summary": {
        "CMS Certification Number (CCN)": "federal_provider_number",
        "Provider Name": "provider_name",
        "State": "provider_state",
        "Health Survey Date": "survey_date",
        "Inspection Cycle": "survey_type",
        "Total Number of Health Deficiencies": "total_number_of_health_deficiencies",
        "Total Number of Fire Safety Deficiencies": "total_number_of_fire_safety_deficiencies",
    },
    "quality_measures": {
        "CMS Certification Number (CCN)": "federal_provider_number",
        "Provider Name": "provider_name",
        "State": "provider_state",
        "Measure Code": "measure_code",
        "Measure Description": "measure_description",
        "Measure Period": "measure_period",
        "Adjusted Score": "score",
        "Footnote for Score": "footnote",
        "Used in Quality Measure Five Star Rating": "used_in_quality_measure_five_star_rating",
    },
}


def _normalize_column_name(name: str) -> str:
    """Normalize a CMS column name to lowercase snake_case."""
    return (
        name.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
        .replace("'", "")
    )


def _find_column_match(normalized_cols: dict, target_field: str) -> Optional[str]:
    """Find the best matching column for a target field name.

    CMS datasets sometimes use slightly different naming conventions.
    This fuzzy-matches against normalized column names.
    """
    # Exact match on normalized name
    if target_field in normalized_cols:
        return normalized_cols[target_field]

    # Try common CMS variations
    variations = [
        target_field.replace("_", ""),
        target_field.replace("number_of_", ""),
        target_field.replace("total_", ""),
        target_field.replace("provider_", ""),
    ]
    for var in variations:
        if var in normalized_cols:
            return normalized_cols[var]

    return None


def extract_source(source_key: str) -> list[dict]:
    """Extract records from a single CMS CSV file.

    Returns a list of validated dicts ready for storage.
    """
    csv_path = RAW_DIR / f"{source_key}.csv"
    if not csv_path.exists():
        console.print(f"  [red]✗[/red] {source_key}: CSV not found at {csv_path}")
        return []

    schema_class = SOURCE_SCHEMAS.get(source_key)
    column_map = COLUMN_MAPS.get(source_key, {})

    if not schema_class:
        console.print(f"  [red]✗[/red] {source_key}: No schema defined")
        return []

    console.print(f"  Parsing [cyan]{source_key}[/cyan]...")

    try:
        # Read with pandas for robust CSV handling; skip malformed rows
        df = pd.read_csv(csv_path, dtype=str, low_memory=False, on_bad_lines="skip")
    except Exception as e:
        console.print(f"  [red]✗[/red] {source_key}: Failed to read CSV: {e}")
        return []

    # Build column name mapping from CSV columns to our field names
    # First try exact match, then try normalized match
    col_mapping = {}
    normalized_cols = {_normalize_column_name(col): col for col in df.columns}
    for csv_field, our_field in column_map.items():
        if csv_field in df.columns:
            # Exact match on the CMS column name
            col_mapping[csv_field] = our_field
        else:
            # Fallback: try normalized name matching
            norm_key = _normalize_column_name(csv_field)
            original_col = _find_column_match(normalized_cols, norm_key)
            if original_col:
                col_mapping[original_col] = our_field

    records = []
    errors = 0

    for _, row in df.iterrows():
        raw_dict = {}
        for csv_col, our_field in col_mapping.items():
            val = row.get(csv_col)
            if pd.isna(val):
                val = None
            raw_dict[our_field] = val

        # Skip rows without a provider number
        if not raw_dict.get("federal_provider_number"):
            errors += 1
            continue

        try:
            validated = schema_class.model_validate(raw_dict)
            records.append(validated.model_dump())
        except Exception:
            errors += 1

    console.print(
        f"  [green]✓[/green] {source_key}: {len(records):,} records extracted"
        + (f" ({errors:,} skipped)" if errors else "")
    )
    return records


def extract_all() -> dict[str, list[dict]]:
    """Extract records from all downloaded CMS CSV files.

    Returns dict of source_key -> list of validated record dicts.
    """
    results = {}
    console.print("\n[bold blue]Extracting CMS datasets...[/bold blue]\n")

    for source_key in SOURCE_SCHEMAS:
        records = extract_source(source_key)
        results[source_key] = records

    total = sum(len(v) for v in results.values())
    console.print(f"\n[bold]Extraction complete: {total:,} total records[/bold]")
    return results
