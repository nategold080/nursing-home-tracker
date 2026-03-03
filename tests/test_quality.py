"""Tests for quality scoring and validation."""

import pytest

from src.validation.quality import (
    QUALITY_WEIGHTS,
    _compute_facility_score,
)
from src.storage.database import upsert_providers, insert_records


class TestQualityWeights:
    def test_weights_sum_to_one(self):
        total = sum(QUALITY_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_weights_positive(self):
        for key, weight in QUALITY_WEIGHTS.items():
            assert weight > 0, f"Weight for {key} should be positive"

    def test_expected_components_present(self):
        expected = {
            "has_deficiency_data",
            "has_penalty_data",
            "has_ownership_data",
            "has_staffing_data",
            "has_quality_measures",
            "has_star_rating",
            "has_survey_data",
        }
        assert set(QUALITY_WEIGHTS.keys()) == expected


class TestComputeFacilityScore:
    def test_full_data_scores_one(self, tmp_db, sample_provider, sample_deficiency,
                                   sample_penalty, sample_ownership):
        conn, _ = tmp_db
        upsert_providers([sample_provider], conn=conn)
        insert_records("health_deficiencies", [sample_deficiency], conn=conn)
        insert_records("penalties", [sample_penalty], conn=conn)
        insert_records("ownership", [sample_ownership], conn=conn)
        insert_records("survey_summary", [{
            "federal_provider_number": "015001",
            "survey_date": "2025-01-15",
            "survey_type": "Health",
        }], conn=conn)
        insert_records("quality_measures", [{
            "federal_provider_number": "015001",
            "measure_code": "401",
            "score": 2.5,
        }], conn=conn)

        score = _compute_facility_score(conn, "015001")
        assert score == 1.0

    def test_empty_data_scores_zero(self, tmp_db):
        conn, _ = tmp_db
        provider = {
            "federal_provider_number": "015099",
            "provider_name": "EMPTY FACILITY",
        }
        upsert_providers([provider], conn=conn)
        score = _compute_facility_score(conn, "015099")
        assert score == 0.0

    def test_partial_data_scores_between(self, tmp_db, sample_provider, sample_deficiency):
        conn, _ = tmp_db
        upsert_providers([sample_provider], conn=conn)
        insert_records("health_deficiencies", [sample_deficiency], conn=conn)
        score = _compute_facility_score(conn, "015001")
        assert 0.0 < score < 1.0

    def test_score_is_rounded(self, tmp_db, sample_provider):
        conn, _ = tmp_db
        upsert_providers([sample_provider], conn=conn)
        score = _compute_facility_score(conn, "015001")
        assert score == round(score, 4)
