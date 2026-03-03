"""Shared test fixtures for Nursing Home Tracker tests."""

import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database with the full schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row

    from src.storage.database import SCHEMA_SQL
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    yield conn, db_path
    conn.close()


@pytest.fixture
def sample_provider():
    """Sample provider record dict."""
    return {
        "federal_provider_number": "015001",
        "provider_name": "SUNSHINE NURSING HOME",
        "provider_address": "123 Main St",
        "provider_city": "Springfield",
        "provider_state": "AL",
        "provider_zip_code": "36101",
        "provider_county_name": "Montgomery",
        "provider_phone_number": "3345551234",
        "ownership_type": "For profit - Corporation",
        "number_of_certified_beds": 120,
        "number_of_residents_in_certified_beds": 98,
        "overall_rating": 3,
        "health_inspection_rating": 2,
        "staffing_rating": 4,
        "quality_measure_rating": 3,
    }


@pytest.fixture
def sample_deficiency():
    """Sample health deficiency record dict."""
    return {
        "federal_provider_number": "015001",
        "provider_name": "SUNSHINE NURSING HOME",
        "provider_state": "AL",
        "survey_date": "2025-01-15",
        "survey_type": "Health",
        "deficiency_tag_number": "F880",
        "deficiency_description": "Infection Prevention and Control",
        "scope_severity_code": "D",
        "deficiency_corrected": "Y",
        "correction_date": "2025-02-01",
        "inspection_cycle": 1,
    }


@pytest.fixture
def sample_penalty():
    """Sample penalty record dict."""
    return {
        "federal_provider_number": "015001",
        "provider_name": "SUNSHINE NURSING HOME",
        "provider_state": "AL",
        "penalty_type": "Civil money penalty",
        "fine_amount": 25000.0,
        "penalty_date": "2025-03-01",
        "penalty_status": "Final",
    }


@pytest.fixture
def sample_ownership():
    """Sample ownership record dict."""
    return {
        "federal_provider_number": "015001",
        "provider_name": "SUNSHINE NURSING HOME",
        "provider_state": "AL",
        "owner_name": "Carlyle Group Healthcare Partners LLC",
        "owner_type": "For profit - Corporation",
        "owner_percentage": 100.0,
        "role_description": "5% or Greater Direct Ownership Interest",
        "association_date": "2020-01-01",
    }


@pytest.fixture
def sample_csv_file(tmp_path):
    """Create a sample CSV file for testing extraction using actual CMS column names."""
    csv_content = '''"CMS Certification Number (CCN)","Provider Name","State","Overall Rating","Staffing Rating"
"015001","SUNSHINE NURSING HOME","AL","3","4"
"015002","HAPPY VALLEY CARE CENTER","AL","5","5"
"015003","GOLDEN YEARS FACILITY","AL","1","2"
'''
    csv_path = tmp_path / "provider_info.csv"
    csv_path.write_text(csv_content)
    return csv_path
