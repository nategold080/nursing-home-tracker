"""Tests for Pydantic validation schemas."""

import pytest
from datetime import date

from src.validation.schemas import (
    ProviderRecord,
    HealthDeficiency,
    Penalty,
    Ownership,
    SurveySummary,
    QualityMeasure,
    SOURCE_SCHEMAS,
)


class TestProviderRecord:
    def test_valid_provider(self, sample_provider):
        record = ProviderRecord.model_validate(sample_provider)
        assert record.federal_provider_number == "015001"
        assert record.provider_name == "SUNSHINE NURSING HOME"
        assert record.overall_rating == 3

    def test_state_normalization(self):
        record = ProviderRecord(
            federal_provider_number="015001",
            provider_name="Test",
            provider_state="  al  ",
        )
        assert record.provider_state == "AL"

    def test_rating_bounds(self):
        with pytest.raises(Exception):
            ProviderRecord(
                federal_provider_number="015001",
                provider_name="Test",
                overall_rating=6,
            )

    def test_rating_min_bound(self):
        with pytest.raises(Exception):
            ProviderRecord(
                federal_provider_number="015001",
                provider_name="Test",
                overall_rating=0,
            )

    def test_optional_fields_default_none(self):
        record = ProviderRecord(
            federal_provider_number="015001",
            provider_name="Test",
        )
        assert record.provider_state is None
        assert record.overall_rating is None
        assert record.number_of_certified_beds is None

    def test_provider_number_too_short(self):
        with pytest.raises(Exception):
            ProviderRecord(
                federal_provider_number="123",
                provider_name="Test",
            )


class TestHealthDeficiency:
    def test_valid_deficiency(self, sample_deficiency):
        record = HealthDeficiency.model_validate(sample_deficiency)
        assert record.federal_provider_number == "015001"
        assert record.survey_date == date(2025, 1, 15)
        assert record.scope_severity_code == "D"

    def test_date_parsing_slash_format(self):
        record = HealthDeficiency(
            federal_provider_number="015001",
            survey_date="01/15/2025",
        )
        assert record.survey_date == date(2025, 1, 15)

    def test_date_parsing_iso_format(self):
        record = HealthDeficiency(
            federal_provider_number="015001",
            survey_date="2025-01-15",
        )
        assert record.survey_date == date(2025, 1, 15)

    def test_empty_date_becomes_none(self):
        record = HealthDeficiency(
            federal_provider_number="015001",
            survey_date="",
        )
        assert record.survey_date is None

    def test_severity_code_normalization(self):
        record = HealthDeficiency(
            federal_provider_number="015001",
            scope_severity_code="  g  ",
        )
        assert record.scope_severity_code == "G"

    def test_invalid_date_becomes_none(self):
        record = HealthDeficiency(
            federal_provider_number="015001",
            survey_date="not-a-date",
        )
        assert record.survey_date is None


class TestPenalty:
    def test_valid_penalty(self, sample_penalty):
        record = Penalty.model_validate(sample_penalty)
        assert record.fine_amount == 25000.0

    def test_amount_with_dollar_sign(self):
        record = Penalty(
            federal_provider_number="015001",
            fine_amount="$25,000.00",
        )
        assert record.fine_amount == 25000.0

    def test_amount_with_commas(self):
        record = Penalty(
            federal_provider_number="015001",
            fine_amount="1,234,567.89",
        )
        assert record.fine_amount == 1234567.89

    def test_empty_amount_becomes_none(self):
        record = Penalty(
            federal_provider_number="015001",
            fine_amount="",
        )
        assert record.fine_amount is None

    def test_invalid_amount_becomes_none(self):
        record = Penalty(
            federal_provider_number="015001",
            fine_amount="N/A",
        )
        assert record.fine_amount is None

    def test_date_parsing(self):
        record = Penalty(
            federal_provider_number="015001",
            penalty_date="03/01/2025",
        )
        assert record.penalty_date == date(2025, 3, 1)


class TestOwnership:
    def test_valid_ownership(self, sample_ownership):
        record = Ownership.model_validate(sample_ownership)
        assert record.owner_name == "Carlyle Group Healthcare Partners LLC"
        assert record.owner_percentage == 100.0

    def test_percentage_with_percent_sign(self):
        record = Ownership(
            federal_provider_number="015001",
            owner_percentage="75%",
        )
        assert record.owner_percentage == 75.0

    def test_empty_percentage_becomes_none(self):
        record = Ownership(
            federal_provider_number="015001",
            owner_percentage="",
        )
        assert record.owner_percentage is None


class TestSurveySummary:
    def test_valid_survey(self):
        record = SurveySummary(
            federal_provider_number="015001",
            survey_date="2025-01-15",
            survey_type="Health",
            total_number_of_health_deficiencies=5,
        )
        assert record.survey_date == date(2025, 1, 15)
        assert record.total_number_of_health_deficiencies == 5


class TestQualityMeasure:
    def test_valid_measure(self):
        record = QualityMeasure(
            federal_provider_number="015001",
            measure_code="401",
            measure_description="Falls with Major Injury",
            score="2.5",
        )
        assert record.score == 2.5

    def test_empty_score_becomes_none(self):
        record = QualityMeasure(
            federal_provider_number="015001",
            score="",
        )
        assert record.score is None

    def test_invalid_score_becomes_none(self):
        record = QualityMeasure(
            federal_provider_number="015001",
            score="Not Available",
        )
        assert record.score is None


class TestSourceSchemas:
    def test_all_sources_have_schemas(self):
        expected = {"provider_info", "health_deficiencies", "penalties", "ownership", "survey_summary", "quality_measures"}
        assert set(SOURCE_SCHEMAS.keys()) == expected

    def test_schema_values_are_pydantic_models(self):
        for key, cls in SOURCE_SCHEMAS.items():
            assert hasattr(cls, "model_validate"), f"{key} schema missing model_validate"
