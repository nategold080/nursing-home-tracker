"""Tests for SQLite database operations."""

import sqlite3
import pytest
from pathlib import Path

from src.storage.database import (
    SCHEMA_SQL,
    SOURCE_TABLES,
    upsert_providers,
    insert_records,
    clear_table,
)


class TestSchema:
    def test_schema_creates_all_tables(self, tmp_db):
        conn, _ = tmp_db
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        expected = {"providers", "health_deficiencies", "penalties", "ownership",
                    "survey_summary", "quality_measures", "pipeline_runs"}
        assert expected.issubset(table_names)

    def test_schema_creates_indexes(self, tmp_db):
        conn, _ = tmp_db
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchall()
        assert len(indexes) >= 10

    def test_providers_has_correct_columns(self, tmp_db):
        conn, _ = tmp_db
        cursor = conn.execute("PRAGMA table_info(providers)")
        columns = {row["name"] for row in cursor}
        assert "federal_provider_number" in columns
        assert "provider_name" in columns
        assert "overall_rating" in columns
        assert "quality_score" in columns
        assert "owner_classification" in columns


class TestUpsertProviders:
    def test_insert_new_provider(self, tmp_db, sample_provider):
        conn, _ = tmp_db
        upsert_providers([sample_provider], conn=conn)
        row = conn.execute("SELECT * FROM providers WHERE federal_provider_number = '015001'").fetchone()
        assert row is not None
        assert row["provider_name"] == "SUNSHINE NURSING HOME"

    def test_upsert_updates_existing(self, tmp_db, sample_provider):
        conn, _ = tmp_db
        upsert_providers([sample_provider], conn=conn)
        updated = sample_provider.copy()
        updated["overall_rating"] = 5
        upsert_providers([updated], conn=conn)
        row = conn.execute("SELECT * FROM providers WHERE federal_provider_number = '015001'").fetchone()
        assert row["overall_rating"] == 5

    def test_insert_multiple_providers(self, tmp_db):
        conn, _ = tmp_db
        providers = [
            {"federal_provider_number": "015001", "provider_name": "Facility A"},
            {"federal_provider_number": "015002", "provider_name": "Facility B"},
            {"federal_provider_number": "015003", "provider_name": "Facility C"},
        ]
        upsert_providers(providers, conn=conn)
        count = conn.execute("SELECT COUNT(*) FROM providers").fetchone()[0]
        assert count == 3


class TestInsertRecords:
    def test_insert_deficiencies(self, tmp_db, sample_provider, sample_deficiency):
        conn, _ = tmp_db
        upsert_providers([sample_provider], conn=conn)
        insert_records("health_deficiencies", [sample_deficiency], conn=conn)
        count = conn.execute("SELECT COUNT(*) FROM health_deficiencies").fetchone()[0]
        assert count == 1

    def test_insert_penalties(self, tmp_db, sample_provider, sample_penalty):
        conn, _ = tmp_db
        upsert_providers([sample_provider], conn=conn)
        insert_records("penalties", [sample_penalty], conn=conn)
        count = conn.execute("SELECT COUNT(*) FROM penalties").fetchone()[0]
        assert count == 1

    def test_insert_empty_list(self, tmp_db):
        conn, _ = tmp_db
        insert_records("penalties", [], conn=conn)
        count = conn.execute("SELECT COUNT(*) FROM penalties").fetchone()[0]
        assert count == 0


class TestClearTable:
    def test_clear_table(self, tmp_db, sample_provider):
        conn, _ = tmp_db
        upsert_providers([sample_provider], conn=conn)
        clear_table("providers", conn=conn)
        count = conn.execute("SELECT COUNT(*) FROM providers").fetchone()[0]
        assert count == 0


class TestSourceTables:
    def test_all_sources_mapped(self):
        expected = {"provider_info", "health_deficiencies", "penalties",
                    "ownership", "survey_summary", "quality_measures"}
        assert set(SOURCE_TABLES.keys()) == expected

    def test_table_names_valid(self):
        valid_tables = {"providers", "health_deficiencies", "penalties",
                        "ownership", "survey_summary", "quality_measures"}
        assert set(SOURCE_TABLES.values()) == valid_tables
