"""Tests for config manager."""

import pytest
import tempfile
import os
from agent.research_v1.config_manager import ConfigManager, get_config


def test_config_manager_initialization():
    """Test ConfigManager initializes with defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        config = ConfigManager(config_path=config_path)
        assert config.get("model.minimax") == "MiniMax-2.7"
        assert config.get("model.gpt") == "gpt-5.4"


def test_config_set_and_get():
    """Test setting and getting values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        config = ConfigManager(config_path=config_path)

        config.set("test.key", "test_value")
        assert config.get("test.key") == "test_value"


def test_config_get_int():
    """Test getting integer values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        config = ConfigManager(config_path=config_path)

        config.set("test.int", "42")
        assert config.get_int("test.int") == 42
        assert config.get_int("nonexistent", 99) == 99


def test_config_get_float():
    """Test getting float values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        config = ConfigManager(config_path=config_path)

        config.set("test.float", "3.14")
        assert config.get_float("test.float") == 3.14


def test_config_get_bool():
    """Test getting boolean values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        config = ConfigManager(config_path=config_path)

        config.set("test.bool", "true")
        assert config.get_bool("test.bool") is True

        config.set("test.bool", "false")
        assert config.get_bool("test.bool") is False


def test_config_reset_key():
    """Test resetting a key to default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        config = ConfigManager(config_path=config_path)

        config.set("monitor.atr_multiplier", "99")
        assert config.get("monitor.atr_multiplier") == "99"

        config.set_default("monitor.atr_multiplier")
        assert config.get("monitor.atr_multiplier") == "2.5"


def test_config_reset_all():
    """Test resetting all config to defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        config = ConfigManager(config_path=config_path)

        config.set("test.key", "value")
        config.set("model.minimax", "custom")

        config.reset_all()

        assert config.get("test.key") is None
        assert config.get("model.minimax") == "MiniMax-2.7"


def test_config_to_markdown():
    """Test markdown output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        config = ConfigManager(config_path=config_path)

        markdown = config.to_markdown()
        assert "# Research System Configuration" in markdown
        assert "MiniMax" in markdown
        assert "ATR Multiplier" in markdown


def test_get_config_singleton():
    """Test get_config returns singleton."""
    # This test uses the global instance which persists across tests
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2
