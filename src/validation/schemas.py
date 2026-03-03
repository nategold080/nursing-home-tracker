"""Pydantic v2 schemas for CMS nursing home data entities.

These models validate and normalize records extracted from CMS CSV downloads.
Each model corresponds to one of the 6 CMS datasets. The Provider ID
(federal_provider_number) is the primary join key across all datasets.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProviderRecord(BaseModel):
    """Provider Information — general facility details, star ratings, staffing."""

    federal_provider_number: str = Field(..., min_length=6, max_length=10)
    provider_name: str
    provider_address: Optional[str] = None
    provider_city: Optional[str] = None
    provider_state: Optional[str] = Field(None, max_length=2)
    provider_zip_code: Optional[str] = None
    provider_county_name: Optional[str] = None
    provider_phone_number: Optional[str] = None
    ownership_type: Optional[str] = None
    number_of_certified_beds: Optional[int] = None
    number_of_residents_in_certified_beds: Optional[float] = None
    provider_type: Optional[str] = None
    legal_business_name: Optional[str] = None

    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    health_inspection_rating: Optional[int] = Field(None, ge=1, le=5)
    staffing_rating: Optional[int] = Field(None, ge=1, le=5)
    quality_measure_rating: Optional[int] = Field(None, ge=1, le=5)

    total_weighted_health_survey_score: Optional[float] = None
    number_of_facility_reported_incidents: Optional[int] = None
    number_of_substantiated_complaints: Optional[int] = None
    number_of_fines: Optional[int] = None
    total_amount_of_fines_in_dollars: Optional[float] = None
    number_of_payment_denials: Optional[int] = None
    total_number_of_penalties: Optional[int] = None

    @field_validator("provider_state", mode="before")
    @classmethod
    def normalize_state(cls, v):
        if v:
            return str(v).strip().upper()[:2]
        return v

    @field_validator(
        "number_of_certified_beds",
        "number_of_facility_reported_incidents",
        "number_of_substantiated_complaints",
        "number_of_fines",
        "number_of_payment_denials",
        "total_number_of_penalties",
        "overall_rating",
        "health_inspection_rating",
        "staffing_rating",
        "quality_measure_rating",
        mode="before",
    )
    @classmethod
    def parse_int_from_float_string(cls, v):
        """Parse integer fields that CMS may store as float strings (e.g., '3.0')."""
        if v is None or v == "" or str(v).strip() == "":
            return None
        try:
            return int(float(str(v).strip()))
        except (ValueError, TypeError):
            return None


class HealthDeficiency(BaseModel):
    """Health Deficiency citation from a standard survey or complaint investigation."""

    federal_provider_number: str = Field(..., min_length=6, max_length=10)
    provider_name: Optional[str] = None
    provider_state: Optional[str] = Field(None, max_length=2)
    survey_date: Optional[date] = None
    survey_type: Optional[str] = None
    deficiency_tag_number: Optional[str] = None
    deficiency_description: Optional[str] = None
    scope_severity_code: Optional[str] = Field(None, max_length=2)
    deficiency_corrected: Optional[str] = None
    correction_date: Optional[date] = None
    inspection_cycle: Optional[int] = None

    @field_validator("survey_date", "correction_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if not v or v == "" or str(v).strip() == "":
            return None
        if isinstance(v, date):
            return v
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(v).strip(), fmt).date()
            except ValueError:
                continue
        return None

    @field_validator("scope_severity_code", mode="before")
    @classmethod
    def normalize_severity(cls, v):
        if v:
            return str(v).strip().upper()[:2]
        return v


class Penalty(BaseModel):
    """Civil money penalty or payment denial imposed on a nursing home."""

    federal_provider_number: str = Field(..., min_length=6, max_length=10)
    provider_name: Optional[str] = None
    provider_state: Optional[str] = Field(None, max_length=2)
    penalty_type: Optional[str] = None
    fine_amount: Optional[float] = None
    penalty_date: Optional[date] = None
    penalty_status: Optional[str] = None

    @field_validator("penalty_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if not v or v == "" or str(v).strip() == "":
            return None
        if isinstance(v, date):
            return v
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(v).strip(), fmt).date()
            except ValueError:
                continue
        return None

    @field_validator("fine_amount", mode="before")
    @classmethod
    def parse_amount(cls, v):
        if not v or v == "":
            return None
        try:
            cleaned = str(v).replace("$", "").replace(",", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None


class Ownership(BaseModel):
    """Ownership record for a nursing home facility."""

    federal_provider_number: str = Field(..., min_length=6, max_length=10)
    provider_name: Optional[str] = None
    provider_state: Optional[str] = Field(None, max_length=2)
    owner_name: Optional[str] = None
    owner_type: Optional[str] = None
    owner_percentage: Optional[float] = None
    role_description: Optional[str] = None
    association_date: Optional[date] = None

    @field_validator("association_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if not v or v == "" or str(v).strip() == "":
            return None
        if isinstance(v, date):
            return v
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(v).strip(), fmt).date()
            except ValueError:
                continue
        return None

    @field_validator("owner_percentage", mode="before")
    @classmethod
    def parse_pct(cls, v):
        if not v or v == "":
            return None
        try:
            val = float(str(v).replace("%", "").strip())
            return val
        except (ValueError, TypeError):
            return None


class SurveySummary(BaseModel):
    """Survey summary record — metadata about inspections conducted."""

    federal_provider_number: str = Field(..., min_length=6, max_length=10)
    provider_name: Optional[str] = None
    provider_state: Optional[str] = Field(None, max_length=2)
    survey_date: Optional[date] = None
    survey_type: Optional[str] = None
    total_number_of_health_deficiencies: Optional[int] = None
    total_number_of_fire_safety_deficiencies: Optional[int] = None

    @field_validator("survey_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if not v or v == "" or str(v).strip() == "":
            return None
        if isinstance(v, date):
            return v
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(v).strip(), fmt).date()
            except ValueError:
                continue
        return None


class QualityMeasure(BaseModel):
    """Quality measure score for a nursing home."""

    federal_provider_number: str = Field(..., min_length=6, max_length=10)
    provider_name: Optional[str] = None
    provider_state: Optional[str] = Field(None, max_length=2)
    measure_code: Optional[str] = None
    measure_description: Optional[str] = None
    measure_period: Optional[str] = None
    score: Optional[float] = None
    footnote: Optional[str] = None
    used_in_quality_measure_five_star_rating: Optional[bool] = None

    @field_validator("score", mode="before")
    @classmethod
    def parse_score(cls, v):
        if not v or v == "" or str(v).strip() == "":
            return None
        try:
            return float(str(v).strip())
        except (ValueError, TypeError):
            return None


# Mapping from source_key to schema class
SOURCE_SCHEMAS = {
    "provider_info": ProviderRecord,
    "health_deficiencies": HealthDeficiency,
    "penalties": Penalty,
    "ownership": Ownership,
    "survey_summary": SurveySummary,
    "quality_measures": QualityMeasure,
}
