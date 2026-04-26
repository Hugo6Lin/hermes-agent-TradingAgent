"""P21 conservative regime gate."""

from __future__ import annotations

from agent.research_v1.calibration_config import RegimeGateConfig


REQUIRED_REGIME_FEATURES = [
    "vix_percentile",
    "realized_vol_percentile",
    "market_breadth_percentile",
    "cross_sectional_dispersion_percentile",
    "major_index_trend_state",
]


def evaluate_regime_gate(features: dict, config: RegimeGateConfig | None = None) -> dict:
    """Evaluate regime features against conservative thresholds.

    Returns:
        dict with regime_gate_status, failing_features, missing_features,
        calibration_status, and config_version.
    """
    active_config = config or RegimeGateConfig()

    missing_features = [name for name in REQUIRED_REGIME_FEATURES if name not in features]
    if missing_features:
        return {
            "regime_gate_status": active_config.missing_data_status,
            "failing_features": [],
            "missing_features": missing_features,
            "calibration_status": active_config.calibration_status,
            "config_version": active_config.config_version,
        }

    failing_features = []
    warn_features = []

    if float(features["vix_percentile"]) >= active_config.vix_fail_percentile:
        failing_features.append("vix_percentile")
    if float(features["realized_vol_percentile"]) >= active_config.realized_vol_fail_percentile:
        failing_features.append("realized_vol_percentile")
    if float(features["cross_sectional_dispersion_percentile"]) >= active_config.dispersion_fail_percentile:
        failing_features.append("cross_sectional_dispersion_percentile")
    if float(features["market_breadth_percentile"]) <= active_config.breadth_warn_percentile:
        warn_features.append("market_breadth_percentile")
    if str(features["major_index_trend_state"]).lower() in {"downtrend", "crash"}:
        warn_features.append("major_index_trend_state")

    if failing_features:
        status = "fail"
    elif warn_features:
        status = "warn"
    else:
        status = "pass"

    return {
        "regime_gate_status": status,
        "failing_features": failing_features + warn_features,
        "missing_features": [],
        "calibration_status": active_config.calibration_status,
        "config_version": active_config.config_version,
    }
