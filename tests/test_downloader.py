"""Tests for CMS downloader module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.scrapers.cms_downloader import (
    load_config,
    get_cache_path,
    is_cached,
    USER_AGENT,
    DELAY_SECONDS,
    CONFIG_PATH,
    CACHE_DIR,
)


class TestLoadConfig:
    def test_config_loads(self):
        config = load_config()
        assert "sources" in config

    def test_config_has_all_sources(self):
        config = load_config()
        sources = config["sources"]
        expected = {"health_deficiencies", "penalties", "ownership",
                    "provider_info", "survey_summary", "quality_measures"}
        assert set(sources.keys()) == expected

    def test_sources_have_required_fields(self):
        config = load_config()
        for key, source in config["sources"].items():
            assert "name" in source, f"{key} missing 'name'"
            assert "url" in source, f"{key} missing 'url'"
            assert "download_url" in source, f"{key} missing 'download_url'"
            assert "dataset_id" in source, f"{key} missing 'dataset_id'"

    def test_download_urls_are_csv(self):
        config = load_config()
        for key, source in config["sources"].items():
            assert "format=csv" in source["download_url"], (
                f"{key} download_url should request CSV format"
            )


class TestCachePath:
    def test_returns_csv_path(self):
        path = get_cache_path("health_deficiencies")
        assert path.suffix == ".csv"
        assert "health_deficiencies" in path.name

    def test_in_cache_dir(self):
        path = get_cache_path("penalties")
        assert str(CACHE_DIR) in str(path.parent)


class TestIsCached:
    def test_not_cached_when_missing(self, tmp_path):
        with patch("src.scrapers.cms_downloader.CACHE_DIR", tmp_path):
            assert is_cached("nonexistent") is False

    def test_cached_when_recent(self, tmp_path):
        cache_file = tmp_path / "test_source.csv"
        cache_file.write_text("data")
        with patch("src.scrapers.cms_downloader.CACHE_DIR", tmp_path):
            assert is_cached("test_source") is True


class TestConstants:
    def test_user_agent_includes_contact(self):
        assert "nathanmauricegoldberg@gmail.com" in USER_AGENT

    def test_delay_is_polite(self):
        assert DELAY_SECONDS >= 1

    def test_config_path_exists(self):
        assert CONFIG_PATH.exists()
