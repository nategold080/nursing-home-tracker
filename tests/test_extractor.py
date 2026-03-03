"""Tests for CSV extraction module."""

import pytest
from pathlib import Path
from unittest.mock import patch

from src.extractors.csv_parser import (
    _normalize_column_name,
    _find_column_match,
    extract_source,
    COLUMN_MAPS,
)


class TestNormalizeColumnName:
    def test_lowercase(self):
        assert _normalize_column_name("PROVIDER_NAME") == "provider_name"

    def test_spaces_to_underscores(self):
        assert _normalize_column_name("Provider Name") == "provider_name"

    def test_hyphens_to_underscores(self):
        assert _normalize_column_name("provider-name") == "provider_name"

    def test_strips_whitespace(self):
        assert _normalize_column_name("  provider_name  ") == "provider_name"

    def test_removes_dots(self):
        assert _normalize_column_name("provider.name") == "providername"

    def test_removes_parens(self):
        assert _normalize_column_name("score (adjusted)") == "score_adjusted"

    def test_removes_slashes(self):
        assert _normalize_column_name("score/value") == "score_value"


class TestFindColumnMatch:
    def test_exact_match(self):
        cols = {"provider_name": "Provider Name", "state": "State"}
        result = _find_column_match(cols, "provider_name")
        assert result == "Provider Name"

    def test_no_match_returns_none(self):
        cols = {"provider_name": "Provider Name"}
        result = _find_column_match(cols, "nonexistent_field")
        assert result is None


class TestColumnMaps:
    def test_all_sources_have_maps(self):
        expected = {"provider_info", "health_deficiencies", "penalties",
                    "ownership", "survey_summary", "quality_measures"}
        assert set(COLUMN_MAPS.keys()) == expected

    def test_all_maps_include_provider_number(self):
        for source_key, col_map in COLUMN_MAPS.items():
            assert "federal_provider_number" in col_map.values(), (
                f"{source_key} missing federal_provider_number in mapped values"
            )

    def test_provider_info_has_rating_fields(self):
        pi_values = set(COLUMN_MAPS["provider_info"].values())
        assert "overall_rating" in pi_values
        assert "staffing_rating" in pi_values


class TestExtractSource:
    def test_extract_from_csv(self, sample_csv_file, tmp_path):
        """Test extracting from a valid CSV file."""
        with patch("src.extractors.csv_parser.RAW_DIR", tmp_path):
            records = extract_source("provider_info")

        assert len(records) == 3
        assert records[0]["federal_provider_number"] == "015001"
        assert records[0]["provider_name"] == "SUNSHINE NURSING HOME"

    def test_missing_csv_returns_empty(self, tmp_path):
        with patch("src.extractors.csv_parser.RAW_DIR", tmp_path):
            records = extract_source("nonexistent_source")
        assert records == []

    def test_extract_preserves_state(self, sample_csv_file, tmp_path):
        with patch("src.extractors.csv_parser.RAW_DIR", tmp_path):
            records = extract_source("provider_info")
        assert records[0]["provider_state"] == "AL"

    def test_extract_parses_ratings(self, sample_csv_file, tmp_path):
        with patch("src.extractors.csv_parser.RAW_DIR", tmp_path):
            records = extract_source("provider_info")
        assert records[0]["overall_rating"] == 3
        assert records[1]["overall_rating"] == 5
