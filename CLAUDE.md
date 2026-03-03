# Nursing Home Inspection & Deficiency Tracker

## Project Overview
Cross-linked database of nursing home quality, ownership, and enforcement data from CMS. The first comprehensive free tool that connects deficiency citations + penalties + ownership chains (including PE/REIT) + staffing levels + quality measures across 14,000+ US nursing homes.

## Core Value Proposition
- **ProPublica Nursing Home Inspect** covers deficiencies but excludes fire safety, financial data, and ownership analysis
- **StarPRO** does financial analytics but is expensive and investor-focused
- **Definitive Healthcare** is enterprise-only (six figures)
- **Nobody** has built the unified cross-linked product connecting ownership changes to quality outcomes

## Data Sources (all freely downloadable CSVs from data.cms.gov)

| Dataset | CMS ID | Key Fields | URL Pattern |
|---------|--------|------------|-------------|
| Health Deficiencies | r5ix-sfxw | Provider ID, survey date, deficiency tag, scope, severity | data.cms.gov/provider-data/dataset/r5ix-sfxw |
| Penalties | g6vv-u9sr | Provider ID, penalty type, amount, date | data.cms.gov/provider-data/dataset/g6vv-u9sr |
| Ownership | y2hd-n93e | Provider ID, owner name, owner type, role | data.cms.gov/provider-data/dataset/y2hd-n93e |
| Provider Info | 4pq5-n9py | Provider ID, name, address, star ratings, staffing | data.cms.gov/provider-data/dataset/4pq5-n9py |
| Survey Summary | tbry-pc2d | Provider ID, survey date, type | data.cms.gov/provider-data/dataset/tbry-pc2d |
| Quality Measures | ijh5-nb2v | Provider ID, measure code, score | data.cms.gov/provider-data/dataset/ijh5-nb2v |

## Technical Standards
- Python 3.12+, SQLite WAL mode, Click CLI, Streamlit + Plotly
- Zero LLM dependency for core pipeline
- Quality scoring on every record (weighted 0.0-1.0)
- All data from public CMS sources
- Dark theme dashboard: primaryColor="#0984E3", backgroundColor="#0E1117"
- Footer: "Built by Nathan Goldberg" + nathanmauricegoldberg@gmail.com + LinkedIn

## Entity Resolution
- Primary join key: CMS Provider ID (6-digit, consistent across all datasets)
- Owner entity resolution: fuzzy match owner names across facilities (thefuzz)
- PE/REIT classification: rule-based identification from owner type + name patterns
- Geographic normalization: state/county standardization

## Quality Scoring Formula
Each facility record scored 0.0-1.0:
- has_deficiency_data: 0.20
- has_penalty_data: 0.15
- has_ownership_data: 0.20
- has_staffing_data: 0.15
- has_quality_measures: 0.15
- has_star_rating: 0.10
- has_survey_data: 0.05

## Build Order
1. Config files (sources.yaml, owner_types.yaml, deficiency_tags.yaml)
2. Downloaders — Fetch CSVs from CMS (not scraping — direct download)
3. Extractors — Parse and validate CSV data, standardize fields
4. Normalization — Owner entity resolution, PE/REIT classification
5. Validation — Pydantic schemas, quality scoring, dedup
6. Storage — SQLite schema, CRUD, cross-table joins
7. Pipeline — Wire download → extract → normalize → validate → store
8. Run pipeline against all 6 CMS datasets
9. Exports — CSV, JSON, Excel, Markdown stats
10. Dashboard — 6+ interactive sections
11. Methodology doc — 1-page PDF
12. Tests — 50+ covering all stages

## Dashboard Sections (planned)
1. **National Overview** — KPI cards (total facilities, avg star rating, total penalties, PE-owned %)
2. **Deficiency Explorer** — Search/filter by state, severity, tag, date
3. **Ownership Analysis** — PE vs nonprofit vs government comparison
4. **Penalty Tracker** — Top penalized facilities, penalty trends
5. **Quality Comparison** — Star ratings, staffing, quality measures by ownership type
6. **Geographic Map** — Interactive map of facility quality by state/county
7. **Facility Deep Dive** — Individual facility profile with full history

## Target Audiences
- PE firms evaluating senior care acquisitions
- Senior care REITs monitoring portfolio quality
- Elder law attorneys and consumer advocates
- Health policy researchers (Wharton, NYU, NBER)
- Investigative journalists (KFF Health News, ProPublica)
- State health departments
