# Nursing Home Inspection & Deficiency Tracker

Cross-linked database of nursing home quality, ownership, and enforcement data from CMS. The first comprehensive free tool that connects deficiency citations, penalties, ownership chains (including PE/REIT), staffing levels, and quality measures across 14,000+ US nursing homes.

## What This Does

- **Downloads** 6 CMS datasets monthly (deficiencies, penalties, ownership, provider info, survey summaries, quality measures)
- **Extracts** and validates records through Pydantic v2 schemas
- **Classifies** owners as PE-backed, REIT, nonprofit, government, or for-profit chain using regex + fuzzy matching
- **Scores** every facility 0.0–1.0 based on data completeness
- **Exports** as CSV, JSON, Excel, or Markdown
- **Visualizes** via interactive Streamlit dashboard with 7 sections

## Quick Start

```bash
pip install -r requirements.txt

# Run the full pipeline
python -m src.cli pipeline

# Or step by step
python -m src.cli download
python -m src.cli extract
python -m src.cli normalize
python -m src.cli validate

# Export data
python -m src.cli export --format all

# Launch dashboard
python -m src.cli dashboard
```

## Data Sources

All data is freely available from [CMS Provider Data Catalog](https://data.cms.gov/provider-data/):

| Dataset | Records | Update Frequency |
|---------|---------|-----------------|
| Health Deficiencies | ~420K | Monthly |
| Penalties | ~52K | Monthly |
| Ownership | ~210K | Monthly |
| Provider Info | ~15K | Monthly |
| Survey Summary | ~48K | Monthly |
| Quality Measures | ~285K | Quarterly |

## Dashboard

7 interactive sections:
1. **National Overview** — KPIs, rating distribution, ownership breakdown
2. **Deficiency Explorer** — Filter by state, severity, date
3. **Ownership Analysis** — PE vs nonprofit quality comparison
4. **Penalty Tracker** — Top penalized facilities, fine trends
5. **Quality Comparison** — Star ratings by ownership type
6. **Geographic Map** — Choropleth maps by metric
7. **Facility Deep Dive** — Individual facility profiles

## Methodology

- Primary join key: CMS Federal Provider Number (consistent across all 6 datasets)
- Owner classification: rule-based regex patterns + fuzzy matching against known PE/REIT firms
- Quality scoring: weighted sum across 7 data completeness components
- Zero LLM dependency — all extraction is deterministic/rule-based

## Tests

```bash
python -m pytest tests/ -v
```

106 tests covering schemas, database operations, extraction, normalization, and quality scoring.

## License

Data is from public US government sources (CMS). No restrictions on government data.

---

Built by [Nathan Goldberg](https://www.linkedin.com/in/nathanmauricegoldberg/) | nathanmauricegoldberg@gmail.com
