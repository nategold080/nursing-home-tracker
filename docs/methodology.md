# Methodology — Nursing Home Inspection & Deficiency Tracker

## Overview

This dataset cross-links 6 CMS (Centers for Medicare & Medicaid Services) datasets to create a unified view of nursing home quality, ownership, and enforcement across 14,710+ US nursing homes. All data is publicly available from data.cms.gov.

## Data Sources

| Dataset | Records | Source | Update Frequency |
|---------|---------|--------|-----------------|
| Provider Information | 14,710 | data.cms.gov/provider-data/dataset/4pq5-n9py | Monthly |
| Health Deficiencies | 435,898 | data.cms.gov/provider-data/dataset/r5ix-sfxw | Monthly |
| Penalties | 17,463 | data.cms.gov/provider-data/dataset/g6vv-u9sr | Monthly |
| Ownership | 159,220 | data.cms.gov/provider-data/dataset/y2hd-n93e | Monthly |
| Survey Summary | 43,983 | data.cms.gov/provider-data/dataset/tbry-pc2d | Monthly |
| Quality Measures | 58,840 | data.cms.gov/provider-data/dataset/ijh5-nb2v | Quarterly |

## Entity Resolution

**Primary Join Key:** CMS Certification Number (CCN), a 6-character alphanumeric identifier assigned to each facility. This ID is consistent across all 6 datasets, enabling reliable cross-linking.

**Owner Entity Resolution:** Owner names are normalized by stripping corporate suffixes (LLC, Inc., Corp., DBA, et al.) and collapsing whitespace. Fuzzy matching (token sort ratio >= 85%) is used to group variant spellings of the same entity.

## Ownership Classification

Each facility is classified using a three-stage process:

1. **Known Firm Match:** Owner names are compared against a curated list of known PE firms and REITs using exact substring matching and fuzzy matching. This is the highest-confidence classification.

2. **Regex Pattern Match:** Names are checked against regex patterns associated with ownership categories (e.g., "capital", "partners", "investments" for PE; "trust", "REIT" for REITs; "church", "charity", "foundation" for nonprofits).

3. **CMS Type Field:** The CMS-provided `owner_type` field is used to classify remaining records (e.g., "Non-profit" -> nonprofit, "Government" -> government).

4. **Default:** Records not matched by any of the above are classified as `for_profit_chain`.

**Provider-Level Classification:** Each provider's classification is determined by the highest-priority owner type across all its ownership records (priority: PE > REIT > for_profit > nonprofit > government > individual > unknown).

## Quality Scoring

Each facility receives a quality score from 0.0 to 1.0 based on data completeness:

| Component | Weight | Criteria |
|-----------|--------|----------|
| Deficiency data | 0.20 | At least one deficiency record exists |
| Penalty data | 0.15 | At least one penalty record exists |
| Ownership data | 0.20 | At least one ownership record exists |
| Staffing data | 0.15 | Staffing rating is non-null |
| Quality measures | 0.15 | At least one quality measure exists |
| Star rating | 0.10 | Overall star rating is non-null |
| Survey data | 0.05 | At least one survey summary exists |

Average quality score: 0.918 (99.8% of facilities above 0.5 threshold).

## Data Validation

- **Referential integrity:** All child records (deficiencies, penalties, etc.) are checked for matching provider IDs
- **Data ranges:** Star ratings validated 1-5, fine amounts validated positive, bed counts validated positive
- **Deduplication:** Records are matched on composite keys (provider ID + date + tag number for deficiencies, provider ID + date + type for penalties)

## Coverage

- **Facilities:** 14,710 across 53 states and territories (50 states + DC, GU, PR)
- **Time span:** Deficiency data covers the most recent 3 inspection cycles per facility
- **Ownership:** 159,220 ownership records covering current active owners
- **Financial:** $480M in tracked civil money penalties

## Limitations

1. **Ownership classification is probabilistic.** While known PE firms and REITs are matched with high confidence, the regex-based classification may produce false positives or negatives for smaller entities.

2. **CMS data has a publication lag.** New inspection results take 2-4 weeks to appear in the public data.

3. **Not all deficiencies are equal.** Scope/severity codes (A-L) distinguish between isolated minor issues and widespread immediate jeopardy. Analysis should account for severity, not just count.

4. **Historical ownership changes are limited.** The CMS ownership dataset reflects current ownership, not historical transfers. PE ownership prior to the Nov 2023 CMS disclosure rule may be underreported.

## Technical Implementation

- **Zero LLM dependency:** All extraction is deterministic/rule-based
- **Pipeline:** Download → Extract → Normalize → Validate → Store
- **Storage:** SQLite with WAL mode for concurrent read access
- **Exports:** CSV, JSON, Excel, Markdown
- **Dashboard:** Interactive Streamlit app with 7 analytical sections

---

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com | [LinkedIn](https://linkedin.com/in/nathanmauricegoldberg)
