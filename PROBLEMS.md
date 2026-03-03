# Problems Tracker — Nursing Home Inspection & Deficiency Tracker

## P1: Database connection closing in tests — DONE
Database functions called `conn.close()` which closed the test fixture connection.
**Fix:** Added optional `conn=` parameter to all database functions; only close if internally created.

## P2: DBA regex ordering — DONE
"LLC DBA Fake Name" wasn't fully stripped because LLC regex ran before DBA regex.
**Fix:** Reordered suffixes: DBA first, then ET AL, then LLC/Inc/Corp.

## P3: CMS API HTTP 400 on limit=0 — DONE
Original download URLs used `limit=0` which CMS API rejects (max 1500).
**Fix:** Rewrote downloader with pagination, then upgraded to bulk download via metastore API.

## P4: Column name mismatch — DONE
Column maps used assumed field names ("federal_provider_number") instead of actual CMS headers ("CMS Certification Number (CCN)").
**Fix:** Updated all COLUMN_MAPS to use exact CMS column header strings.

## P5: Provider extraction — 90% records failing — DONE
CMS stores "Average Number of Residents per Day" as a float (48.4) but schema had `Optional[int]`.
Also, CMS integer fields sometimes stored as float strings ("3.0").
**Fix:** Changed `number_of_residents_in_certified_beds` to `Optional[float]`. Added `parse_int_from_float_string` validator for all integer fields.

## P6: FK constraint on bulk load — DONE
SQLite FK constraints are per-connection; `store_source_data` creates its own connections.
Also, CMS data naturally has orphan records (deficiencies for facilities not in provider_info).
**Fix:** Removed FK constraints from schema. Referential integrity validated in quality layer instead.

## P7: Malformed CSV rows in health_deficiencies — DONE
CMS bulk CSV had rows with unexpected field counts (expected 23, saw 32 in line 253439).
**Fix:** Added `on_bad_lines='skip'` to pandas `read_csv()`.
