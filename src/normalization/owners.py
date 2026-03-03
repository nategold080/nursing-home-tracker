"""Owner entity normalization and PE/REIT classification.

Cross-links ownership records with known PE firms, REITs, and other
owner types using regex patterns and fuzzy string matching. This is
where the unique analytical value of the dataset lives.
"""

import re
from pathlib import Path

import yaml
from rich.console import Console
from thefuzz import fuzz

from src.storage.database import get_connection

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "owner_types.yaml"


def load_owner_config() -> dict:
    """Load owner type classification rules from YAML."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def normalize_owner_name(name: str) -> str:
    """Normalize an owner name for fuzzy matching.

    Strips common suffixes, normalizes whitespace and case.
    """
    if not name:
        return ""

    normalized = name.strip().upper()

    # Remove common corporate suffixes (DBA first since it can precede LLC)
    suffixes = [
        r"\s*,?\s*(DBA|D/B/A|D\.B\.A\.)\s+.*$",
        r"\s*,?\s*(ET\s+AL\.?)\s*$",
        r"\s*,?\s*(LLC|L\.L\.C\.|INC\.?|INCORPORATED|CORP\.?|CORPORATION|LP|L\.P\.|LLP|LTD\.?|CO\.?)\s*$",
    ]
    for suffix in suffixes:
        normalized = re.sub(suffix, "", normalized, flags=re.IGNORECASE)

    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def classify_owner(owner_name: str, owner_type: str, config: dict) -> str:
    """Classify an owner as PE, REIT, nonprofit, government, or for-profit chain.

    Classification order (first match wins):
    1. Known firm exact/fuzzy match (PE firms, REITs)
    2. Regex pattern match on name
    3. CMS owner_type field mapping
    4. Default to 'for_profit_chain'
    """
    if not owner_name:
        return "unknown"

    name_upper = owner_name.strip().upper()
    classifications = config.get("owner_classifications", {})

    # Step 1: Check known firms (PE and REIT first — highest value classification)
    for category in ["private_equity", "reit"]:
        cat_config = classifications.get(category, {})
        known_firms = cat_config.get("known_firms", [])
        for firm in known_firms:
            firm_upper = firm.upper()
            # Exact substring match
            if firm_upper in name_upper or name_upper in firm_upper:
                return category
            # Fuzzy match (high threshold to avoid false positives)
            if fuzz.token_sort_ratio(name_upper, firm_upper) >= 85:
                return category

    # Step 2: Check regex patterns (all categories)
    for category, cat_config in classifications.items():
        patterns = cat_config.get("name_patterns", [])
        for pattern in patterns:
            try:
                if re.search(pattern, owner_name, re.IGNORECASE):
                    return category
            except re.error:
                continue

    # Step 3: CMS owner_type field mapping
    if owner_type:
        ot = owner_type.strip().lower()
        if "non-profit" in ot or "nonprofit" in ot:
            return "nonprofit"
        if "government" in ot or "state" in ot or "county" in ot:
            return "government"
        if "individual" in ot:
            return "individual"

    # Step 4: Default
    return "for_profit_chain"


def normalize_owners():
    """Run owner normalization on all ownership records in the database.

    Updates normalized_owner_name and owner_classification fields.
    Also updates provider-level owner_classification based on majority owner.
    """
    config = load_owner_config()
    conn = get_connection()

    console.print("\n[bold blue]Normalizing ownership records...[/bold blue]\n")

    # Get all ownership records
    rows = conn.execute(
        "SELECT id, federal_provider_number, owner_name, owner_type, owner_percentage FROM ownership"
    ).fetchall()

    if not rows:
        console.print("  [yellow]No ownership records to normalize.[/yellow]")
        conn.close()
        return

    classifications_count = {}
    updated = 0

    for row in rows:
        owner_name = row["owner_name"] or ""
        owner_type = row["owner_type"] or ""

        normalized_name = normalize_owner_name(owner_name)
        classification = classify_owner(owner_name, owner_type, config)

        conn.execute(
            "UPDATE ownership SET normalized_owner_name = ?, owner_classification = ? WHERE id = ?",
            (normalized_name, classification, row["id"]),
        )

        classifications_count[classification] = classifications_count.get(classification, 0) + 1
        updated += 1

    conn.commit()

    # Print classification summary
    console.print(f"  [green]✓[/green] Classified {updated:,} ownership records:")
    for cat, count in sorted(classifications_count.items(), key=lambda x: -x[1]):
        console.print(f"    {cat}: {count:,}")

    # Update provider-level classification based on majority owner
    _update_provider_classifications(conn)

    conn.commit()
    conn.close()

    console.print("\n[bold]Owner normalization complete.[/bold]")


def _update_provider_classifications(conn):
    """Set each provider's owner_classification based on the dominant ownership record.

    Priority: private_equity > reit > for_profit_chain > nonprofit > government > individual > unknown
    """
    priority = {
        "private_equity": 7,
        "reit": 6,
        "for_profit_chain": 5,
        "nonprofit": 4,
        "government": 3,
        "individual": 2,
        "unknown": 1,
    }

    providers = conn.execute(
        "SELECT DISTINCT federal_provider_number FROM ownership"
    ).fetchall()

    updated = 0
    for prov in providers:
        fpn = prov["federal_provider_number"]
        owner_records = conn.execute(
            "SELECT owner_classification, owner_percentage FROM ownership WHERE federal_provider_number = ?",
            (fpn,),
        ).fetchall()

        if not owner_records:
            continue

        # Pick classification with highest priority (PE > REIT > etc.)
        best_class = "unknown"
        best_priority = 0
        for rec in owner_records:
            cls = rec["owner_classification"] or "unknown"
            p = priority.get(cls, 0)
            if p > best_priority:
                best_priority = p
                best_class = cls

        conn.execute(
            "UPDATE providers SET owner_classification = ? WHERE federal_provider_number = ?",
            (best_class, fpn),
        )
        updated += 1

    console.print(f"  [green]✓[/green] Updated classification for {updated:,} providers")
