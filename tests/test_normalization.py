"""Tests for owner normalization and classification."""

import pytest
import yaml
from pathlib import Path

from src.normalization.owners import (
    normalize_owner_name,
    classify_owner,
    load_owner_config,
)


@pytest.fixture
def owner_config():
    """Load the actual owner type configuration."""
    config_path = Path(__file__).parent.parent / "config" / "owner_types.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


class TestNormalizeOwnerName:
    def test_strips_llc(self):
        assert normalize_owner_name("ACME Healthcare LLC") == "ACME HEALTHCARE"

    def test_strips_inc(self):
        assert normalize_owner_name("Senior Care Inc.") == "SENIOR CARE"

    def test_strips_corporation(self):
        assert normalize_owner_name("Big Health Corporation") == "BIG HEALTH"

    def test_strips_lp(self):
        assert normalize_owner_name("Capital Partners LP") == "CAPITAL PARTNERS"

    def test_strips_dba(self):
        assert normalize_owner_name("Real Name LLC DBA Fake Name") == "REAL NAME"

    def test_uppercases(self):
        result = normalize_owner_name("lowercase name")
        assert result == "LOWERCASE NAME"

    def test_collapses_whitespace(self):
        result = normalize_owner_name("  Too   Many   Spaces  ")
        assert result == "TOO MANY SPACES"

    def test_empty_string(self):
        assert normalize_owner_name("") == ""

    def test_none_returns_empty(self):
        assert normalize_owner_name(None) == ""

    def test_strips_et_al(self):
        assert normalize_owner_name("John Smith Et Al.") == "JOHN SMITH"


class TestClassifyOwner:
    def test_known_pe_firm_carlyle(self, owner_config):
        result = classify_owner("Carlyle Group Healthcare Partners", "For profit", owner_config)
        assert result == "private_equity"

    def test_known_pe_firm_formation_capital(self, owner_config):
        result = classify_owner("Formation Capital LLC", "For profit", owner_config)
        assert result == "private_equity"

    def test_known_pe_firm_genesis(self, owner_config):
        result = classify_owner("Genesis Healthcare Inc", "For profit", owner_config)
        assert result == "private_equity"

    def test_known_reit_sabra(self, owner_config):
        result = classify_owner("Sabra Health Care REIT Inc", "For profit", owner_config)
        assert result == "reit"

    def test_known_reit_omega(self, owner_config):
        result = classify_owner("Omega Healthcare Investors", "For profit", owner_config)
        assert result == "reit"

    def test_pe_pattern_capital_partners(self, owner_config):
        result = classify_owner("Apex Capital Partners LLC", "For profit", owner_config)
        assert result == "private_equity"

    def test_pe_pattern_holdings_group(self, owner_config):
        result = classify_owner("Meridian Holdings Group", "For profit", owner_config)
        assert result == "private_equity"

    def test_reit_pattern(self, owner_config):
        result = classify_owner("Healthcare Trust Properties REIT", "For profit", owner_config)
        assert result == "reit"

    def test_nonprofit_pattern_church(self, owner_config):
        result = classify_owner("First Baptist Church Senior Living", "Nonprofit", owner_config)
        assert result == "nonprofit"

    def test_nonprofit_pattern_foundation(self, owner_config):
        result = classify_owner("Smith Family Foundation", "Nonprofit", owner_config)
        assert result == "nonprofit"

    def test_government_pattern_county(self, owner_config):
        result = classify_owner("County of Montgomery", "Government", owner_config)
        assert result == "government"

    def test_government_pattern_veterans(self, owner_config):
        result = classify_owner("Veterans Administration Medical Center", "Government", owner_config)
        assert result == "government"

    def test_nonprofit_from_cms_type(self, owner_config):
        result = classify_owner("Generic Senior Care", "Non-profit - Church related", owner_config)
        assert result == "nonprofit"

    def test_government_from_cms_type(self, owner_config):
        result = classify_owner("County Hospital", "Government - County", owner_config)
        assert result == "government"

    def test_default_for_profit_chain(self, owner_config):
        result = classify_owner("Generic Care Center Inc", "For profit - Corporation", owner_config)
        assert result == "for_profit_chain"

    def test_empty_name_returns_unknown(self, owner_config):
        result = classify_owner("", "For profit", owner_config)
        assert result == "unknown"

    def test_none_name_returns_unknown(self, owner_config):
        result = classify_owner(None, "For profit", owner_config)
        assert result == "unknown"


class TestOwnerConfig:
    def test_config_loads(self, owner_config):
        assert "owner_classifications" in owner_config

    def test_has_all_categories(self, owner_config):
        cats = owner_config["owner_classifications"]
        expected = {"private_equity", "reit", "nonprofit", "government", "for_profit_chain"}
        assert set(cats.keys()) == expected

    def test_pe_has_known_firms(self, owner_config):
        pe = owner_config["owner_classifications"]["private_equity"]
        assert len(pe["known_firms"]) >= 5

    def test_reit_has_known_firms(self, owner_config):
        reit = owner_config["owner_classifications"]["reit"]
        assert len(reit["known_firms"]) >= 5

    def test_severity_levels_exist(self, owner_config):
        assert "severity_levels" in owner_config
        assert "isolated" in owner_config["severity_levels"]

    def test_severity_grades_complete(self, owner_config):
        grades = owner_config["severity_grades"]
        codes = [g["code"] for g in grades]
        assert codes == list("ABCDEFGHIJKL")
