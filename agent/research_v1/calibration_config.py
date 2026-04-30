"""Prior-only calibration configuration for P20-P22.

All P21 configuration values are priors labeled with calibration_status.
Allowed values: prior_only, shadow_observed, calibrated (P22 only), disabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


CALIBRATION_STATUSES = {"prior_only", "shadow_observed", "calibrated", "disabled"}


def _validate_status(status: str) -> None:
    if status not in CALIBRATION_STATUSES:
        raise ValueError(f"invalid calibration_status: {status}")


# ---------------------------------------------------------------------------
# Shared metadata contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalibrationMetadata:
    """Lightweight metadata for config-driven outputs."""
    config_name: str
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"
    source: str = "engineering_prior"

    def __post_init__(self):
        _validate_status(self.calibration_status)


# ---------------------------------------------------------------------------
# Thesis threshold config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThesisThresholdConfig:
    """Threshold configuration for thesis classification gates."""
    no_trade_quality_threshold: float = 0.35
    investable_quality_threshold: float = 0.65
    investable_valuation_threshold: float = 0.15
    investable_catalyst_threshold: float = 0.50
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"

    def __post_init__(self):
        _validate_status(self.calibration_status)


# ---------------------------------------------------------------------------
# Role weight config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoleWeight:
    """Role weight with optional disable reason for zero-weight roles."""
    weight: float
    disabled_with_reason: Optional[str] = None


@dataclass(frozen=True)
class RoleWeightConfig:
    """Configuration for role-based score aggregation weights."""
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"
    weights: dict = field(default_factory=lambda: {
        "fundamentals": RoleWeight(0.40),
        "technical": RoleWeight(0.25),
        "news": RoleWeight(0.15),
        "sentiment": RoleWeight(0.10),
        "industry": RoleWeight(0.05),
        "options": RoleWeight(0.05),
        "risk": RoleWeight(0.00, "risk informs warnings until P22 IC calibration"),
        "valuation": RoleWeight(0.00, "valuation handled by thesis layer until P22 IC calibration"),
    })

    def __post_init__(self):
        _validate_status(self.calibration_status)

    def as_plain_weights(self) -> dict:
        """Return plain weight dict after validating zero-weight guards."""
        plain: dict = {}
        for role, config in self.weights.items():
            if config.weight < 0:
                raise ValueError(f"role {role} has negative weight")
            if config.weight == 0.0 and not config.disabled_with_reason:
                raise ValueError(f"role {role} has zero weight without disabled_with_reason")
            plain[role] = config.weight
        return plain


# ---------------------------------------------------------------------------
# Grading weight config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GradingWeightConfig:
    """Configuration for GradingAgent composite score weights."""
    fundamental: float = 0.40
    technical: float = 0.30
    macro: float = 0.30
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"

    def __post_init__(self):
        _validate_status(self.calibration_status)
        self._validate_sum()

    def _validate_sum(self) -> None:
        total = self.fundamental + self.technical + self.macro
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Grading weights must sum to 1.0, got {total}")
        if self.fundamental < 0 or self.technical < 0 or self.macro < 0:
            raise ValueError("Grading weights must be non-negative")

    def with_overrides(self, overrides: dict) -> "GradingWeightConfig":
        """Return a new config with merged overrides.

        Partial overrides are re-proportionalized to maintain sum-to-1.
        Rejection occurs only when a non-overridden weight would go negative
        (i.e. the override alone leaves insufficient room for others).
        """
        values = {
            "fundamental": self.fundamental,
            "technical": self.technical,
            "macro": self.macro,
        }
        for key, value in overrides.items():
            if key not in values:
                raise ValueError(f"unknown grading weight override: {key}")
            values[key] = float(value)

        overridden_keys = set(overrides.keys())
        remaining_budget = 1.0 - sum(values[ok] for ok in overridden_keys)
        if remaining_budget < 0:
            raise ValueError(f"Grading weights must sum to 1.0, got >1.0")

        # Check each non-overridden weight fits in remaining budget
        for k in values:
            if k not in overridden_keys and values[k] > remaining_budget:
                raise ValueError(
                    f"Grading weights must sum to 1.0, got >1.0 "
                    f"(override {overrides} leaves insufficient room for {k})"
                )

        # Re-proportionalize the non-overridden weights to fill remaining budget
        non_overridden_total = sum(values[k] for k in values if k not in overridden_keys)
        for k in values:
            if k not in overridden_keys:
                if non_overridden_total > 0:
                    values[k] = values[k] / non_overridden_total * remaining_budget
                else:
                    values[k] = 0.0

        return GradingWeightConfig(
            fundamental=values["fundamental"],
            technical=values["technical"],
            macro=values["macro"],
            config_version=self.config_version,
            calibration_status=self.calibration_status,
        )


# ---------------------------------------------------------------------------
# Exit plan config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExitPlanConfig:
    """Prior-only exit plan configuration."""
    stop_multiple: float = 2.0
    target_multiple: float = 3.0
    horizon_bucket: str = "default"
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"

    def __post_init__(self):
        _validate_status(self.calibration_status)
        if self.stop_multiple <= 0 or self.target_multiple <= 0:
            raise ValueError("exit multiples must be positive")


# ---------------------------------------------------------------------------
# Sector benchmark config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SectorBenchmarkConfig:
    """Sector benchmark multiples with fallback and metadata."""
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"
    sector_multiples: dict = field(default_factory=lambda: {
        "technology": {"pe": 26.0, "pb": 8.0, "ps": 7.0},
        "financials": {"pe": 12.0, "pb": 1.4, "ps": 3.0},
        "healthcare": {"pe": 22.0, "pb": 4.5, "ps": 5.0},
        "consumer_discretionary": {"pe": 20.0, "pb": 4.0, "ps": 2.5},
        "industrials": {"pe": 18.0, "pb": 3.0, "ps": 2.0},
        "default": {"pe": 18.0, "pb": 3.0, "ps": 4.0},
    })

    def __post_init__(self):
        _validate_status(self.calibration_status)

    def _normalize_key(self, sector: str | None) -> str:
        return (sector or "default").strip().lower().replace(" ", "_")

    def get(self, sector: str | None) -> dict:
        """Return sector multiples with fallback metadata."""
        key = self._normalize_key(sector)
        used_fallback = key not in self.sector_multiples
        resolved_key = key if not used_fallback else "default"
        return {
            "sector": key,
            "resolved_sector": resolved_key,
            "used_fallback": used_fallback,
            "multiples": dict(self.sector_multiples[resolved_key]),
            "config_version": self.config_version,
            "calibration_status": self.calibration_status,
        }


# ---------------------------------------------------------------------------
# Position sizing config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PositionSizingConfig:
    """Volatility-aware position sizing configuration."""
    target_position_volatility: float = 0.02
    max_single_name_weight: float = 0.05
    max_position_as_pct_adv: float = 0.05
    min_position_units: int = 1
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"

    def __post_init__(self):
        _validate_status(self.calibration_status)
        if not 0 < self.max_single_name_weight <= 1:
            raise ValueError("max_single_name_weight must be in (0, 1]")
        if not 0 <= self.max_position_as_pct_adv <= 1:
            raise ValueError("max_position_as_pct_adv must be in [0, 1]")
        if self.target_position_volatility <= 0:
            raise ValueError("target_position_volatility must be positive")
        if self.min_position_units < 0:
            raise ValueError("min_position_units must be non-negative")


# ---------------------------------------------------------------------------
# Regime gate config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegimeGateConfig:
    """P21 conservative regime gate configuration."""
    vix_fail_percentile: float = 0.95
    realized_vol_fail_percentile: float = 0.95
    breadth_warn_percentile: float = 0.20
    dispersion_fail_percentile: float = 0.95
    missing_data_status: str = "insufficient_definition"
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"

    def __post_init__(self):
        _validate_status(self.calibration_status)
        if self.missing_data_status not in {"stubbed", "insufficient_definition"}:
            raise ValueError("missing_data_status must be stubbed or insufficient_definition")
