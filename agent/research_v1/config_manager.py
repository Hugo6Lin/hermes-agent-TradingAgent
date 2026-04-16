"""Configuration management for research system."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


DEFAULT_CONFIG = {
    # Model configuration
    "model.minimax": "MiniMax-2.7",
    "model.gpt": "gpt-5.4",
    "model.claude": "claude-opus-4-6",

    # API endpoints (use environment variable or default)
    "api.minimax_base_url": "",
    "api.openai_base_url": "",
    "api.anthropic_base_url": "",

    # Monitor thresholds
    "monitor.atr_multiplier": "2.5",
    "monitor.volume_multiplier": "3.0",

    # Pipeline settings
    "pipeline.max_rounds": "3",
    "pipeline.timeout_phase1": "30",
    "pipeline.timeout_phase2": "60",
    "pipeline.timeout_phase3": "90",
    "pipeline.timeout_phase4": "120",

    # Token budget
    "budget.max_tokens_per_task": "500000",

    # Report settings
    "report.include_analyst_details": "true",
    "report.include_debate_details": "true",
}


@dataclass
class ConfigManager:
    """Manage research system configuration.

    Configuration is stored in JSON format and can be persisted to file.
    Values are stored as strings and converted on retrieval.
    """

    config_path: str = "~/.hermes/research_config.json"
    _config: dict[str, str] = field(default_factory=dict)
    _loaded: bool = field(default=False, repr=False)

    def __post_init__(self):
        """Expand path and load config."""
        self.config_path = os.path.expanduser(self.config_path)
        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        if self._loaded:
            return

        config_file = Path(self.config_path)
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._config = dict(DEFAULT_CONFIG)
        else:
            self._config = dict(DEFAULT_CONFIG)
        self._loaded = True

    def _save(self) -> None:
        """Save configuration to file."""
        config_file = Path(self.config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get configuration value.

        Args:
            key: Configuration key (e.g., "model.minimax").
            default: Default value if key not found.

        Returns:
            Configuration value as string, or default if not found.
        """
        self._load()
        return self._config.get(key, default)

    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Get configuration value as integer.

        Args:
            key: Configuration key.
            default: Default value if key not found or not convertible.

        Returns:
            Configuration value as int, or default.
        """
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def get_float(self, key: str, default: Optional[float] = None) -> Optional[float]:
        """Get configuration value as float.

        Args:
            key: Configuration key.
            default: Default value if key not found or not convertible.

        Returns:
            Configuration value as float, or default.
        """
        value = self.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def get_bool(self, key: str, default: Optional[bool] = None) -> Optional[bool]:
        """Get configuration value as boolean.

        Args:
            key: Configuration key.
            default: Default value if key not found or not convertible.

        Returns:
            Configuration value as bool, or default.
        """
        value = self.get(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    def set(self, key: str, value: str) -> None:
        """Set configuration value.

        Args:
            key: Configuration key.
            value: Value to set (will be stored as string).
        """
        self._load()
        self._config[key] = value
        self._save()

    def set_default(self, key: str) -> None:
        """Reset a key to its default value.

        Args:
            key: Configuration key.
        """
        if key in DEFAULT_CONFIG:
            self.set(key, DEFAULT_CONFIG[key])

    def reset_all(self) -> None:
        """Reset all configuration to defaults."""
        self._config = dict(DEFAULT_CONFIG)
        self._save()

    def get_all(self) -> dict[str, str]:
        """Get all configuration as a dictionary.

        Returns:
            Copy of current configuration.
        """
        self._load()
        return dict(self._config)

    def to_markdown(self) -> str:
        """Format configuration as markdown for display.

        Returns:
            Markdown string showing current configuration.
        """
        self._load()

        lines = [
            "# Research System Configuration",
            "",
            "## Model Settings",
            f"- MiniMax: `{self.get('model.minimax')}`",
            f"- GPT: `{self.get('model.gpt')}`",
            f"- Claude: `{self.get('model.claude')}`",
            "",
            "## Monitor Thresholds",
            f"- ATR Multiplier: `{self.get('monitor.atr_multiplier')}`",
            f"- Volume Multiplier: `{self.get('monitor.volume_multiplier')}`",
            "",
            "## Pipeline Timeouts (seconds)",
            f"- Phase 1 (Analysts): `{self.get('pipeline.timeout_phase1')}`",
            f"- Phase 2 (Debate): `{self.get('pipeline.timeout_phase2')}`",
            f"- Phase 3 (Manager): `{self.get('pipeline.timeout_phase3')}`",
            f"- Phase 4 (Report): `{self.get('pipeline.timeout_phase4')}`",
            "",
            "## Token Budget",
            f"- Max tokens per task: `{self.get('budget.max_tokens_per_task')}`",
            "",
            "## Report Settings",
            f"- Include analyst details: `{self.get('report.include_analyst_details')}`",
            f"- Include debate details: `{self.get('report.include_debate_details')}`",
        ]

        return "\n".join(lines)


# Global config instance
_config_instance: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global config instance.

    Returns:
        ConfigManager singleton.
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance
