"""P25-A XGBoost-style shadow dry adapter.

This module intentionally does not import xgboost or train models. It provides
a deterministic dry-run adapter that exercises the P24 shadow experiment path.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from agent.research_v1.p24_shadow_runner import ShadowAdapterResult


REQUIRED_FEATURES = (
    "snapshot_id",
    "ticker",
    "trading_day",
    "company_quality_score",
    "valuation_attractiveness_score",
    "timing_market_fit_score",
    "llm_adjustment_total",
    "coverage_confidence_score",
    "data_as_of_date",
    "universe_membership_snapshot_id",
)

OPTIONAL_FEATURES = (
    "sector",
    "market_cap_bucket",
    "regime_label",
    "negative_signal_strength_decile",
)

FORBIDDEN_FEATURES = (
    "future_return",
    "forward_return",
    "net_return_pct",
    "gross_return_pct",
    "return_value",
    "classification",
    "take_profit",
    "stop_loss",
    "live_trade_signal",
)


class XGBoostShadowAdapterConfigError(ValueError):
    """Raised when P25-A shadow adapter config or feature contract is unsafe."""


@dataclass(frozen=True)
class XGBoostMetaFeatureContract:
    schema_version: str
    required_features: list[str]
    optional_features: list[str]
    target_return_basis: str
    point_in_time_required: bool
    forbidden_features: list[str]
    namespace: str

    def __post_init__(self) -> None:
        if self.schema_version != "p25_xgb_feature_contract.0":
            raise XGBoostShadowAdapterConfigError("schema_version must be p25_xgb_feature_contract.0")
        if self.target_return_basis != "net":
            raise XGBoostShadowAdapterConfigError("target_return_basis must be net")
        if self.point_in_time_required is not True:
            raise XGBoostShadowAdapterConfigError("point_in_time_required must be true")
        if not self.namespace.startswith("shadow_meta_model."):
            raise XGBoostShadowAdapterConfigError("namespace must start with shadow_meta_model.")
        for feature in ("data_as_of_date", "universe_membership_snapshot_id"):
            if feature not in self.required_features:
                raise XGBoostShadowAdapterConfigError(f"required point-in-time feature missing: {feature}")

    @classmethod
    def default(cls, namespace: str) -> "XGBoostMetaFeatureContract":
        return cls(
            schema_version="p25_xgb_feature_contract.0",
            required_features=list(REQUIRED_FEATURES),
            optional_features=list(OPTIONAL_FEATURES),
            target_return_basis="net",
            point_in_time_required=True,
            forbidden_features=list(FORBIDDEN_FEATURES),
            namespace=namespace,
        )


def _within_namespace(name: str, namespace: str) -> bool:
    return str(name) == namespace or str(name).startswith(namespace + ".")


@dataclass(frozen=True)
class XGBoostShadowAdapterConfig:
    schema_version: str
    candidate_namespace: str
    adapter_name: str
    adapter_version: str
    feature_contract: XGBoostMetaFeatureContract
    score_output_name: str
    feature_audit_output_name: str
    metadata_output_name: str
    min_rows: int
    allow_missing_optional_features: bool
    calibration_status: str

    def __post_init__(self) -> None:
        if self.schema_version != "p25_xgb_adapter.0":
            raise XGBoostShadowAdapterConfigError("schema_version must be p25_xgb_adapter.0")
        if not self.candidate_namespace.startswith("shadow_meta_model."):
            raise XGBoostShadowAdapterConfigError("candidate_namespace must start with shadow_meta_model.")
        for output_name in (self.score_output_name, self.feature_audit_output_name, self.metadata_output_name):
            if not _within_namespace(output_name, self.candidate_namespace):
                raise XGBoostShadowAdapterConfigError("output names must stay within candidate namespace")
        if self.feature_contract.namespace != self.candidate_namespace:
            raise XGBoostShadowAdapterConfigError("feature contract namespace must match candidate namespace")
        if self.min_rows < 1:
            raise XGBoostShadowAdapterConfigError("min_rows must be >= 1")
        if self.calibration_status != "shadow_dry_run":
            raise XGBoostShadowAdapterConfigError("calibration_status must be shadow_dry_run")

    @classmethod
    def default(cls, candidate_namespace: str) -> "XGBoostShadowAdapterConfig":
        contract = XGBoostMetaFeatureContract.default(candidate_namespace)
        return cls(
            schema_version="p25_xgb_adapter.0",
            candidate_namespace=candidate_namespace,
            adapter_name="xgboost_dry_run",
            adapter_version="0.1",
            feature_contract=contract,
            score_output_name=f"{candidate_namespace}.shadow_predictions",
            feature_audit_output_name=f"{candidate_namespace}.feature_audit",
            metadata_output_name=f"{candidate_namespace}.dry_run_metadata",
            min_rows=1,
            allow_missing_optional_features=True,
            calibration_status="shadow_dry_run",
        )


@dataclass(frozen=True)
class _ValidatedRows:
    valid_rows: list[dict]
    missing_required_feature_rows: int
    forbidden_feature_rows: int
    warnings: list[str]


class XGBoostDryRunAdapter:
    def __init__(self, config: XGBoostShadowAdapterConfig, feature_rows: list[dict]) -> None:
        self.config = config
        self.feature_rows = list(feature_rows)
        self.adapter_name = config.adapter_name
        self.adapter_version = config.adapter_version

    def run(self, manifest, request) -> ShadowAdapterResult:
        validated = _validate_rows(
            self.config.feature_contract,
            self.feature_rows,
            self.config.allow_missing_optional_features,
        )
        scores = [_stub_score(row) for row in validated.valid_rows]
        metrics = _build_metrics(
            input_rows=len(self.feature_rows),
            validated=validated,
            scores=scores,
        )
        produced = [
            self.config.score_output_name,
            self.config.feature_audit_output_name,
            self.config.metadata_output_name,
        ]
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=produced,
            attempted_outputs=produced,
            metrics=metrics,
            logs=["p25_xgboost_shadow_dry_adapter_completed"],
            warnings=validated.warnings,
        )


def _validate_rows(
    contract: XGBoostMetaFeatureContract,
    rows: list[dict],
    allow_missing_optional_features: bool,
) -> _ValidatedRows:
    valid_rows: list[dict] = []
    missing_required_count = 0
    forbidden_count = 0
    warnings: list[str] = []
    missing_optional_seen: set[str] = set()

    for row in rows:
        missing_required = [feature for feature in contract.required_features if feature not in row or row.get(feature) in (None, "")]
        forbidden_present = [feature for feature in contract.forbidden_features if feature in row]
        if missing_required:
            missing_required_count += 1
            continue
        if forbidden_present:
            forbidden_count += 1
            continue
        for feature in contract.optional_features:
            if feature not in row and feature not in missing_optional_seen:
                missing_optional_seen.add(feature)
                if allow_missing_optional_features:
                    warnings.append(f"missing_optional_features:{feature}")
        valid_rows.append(dict(row))

    if missing_required_count:
        warnings.append("row_excluded_missing_required_features")
    if forbidden_count:
        warnings.append("row_excluded_forbidden_features")
    return _ValidatedRows(
        valid_rows=valid_rows,
        missing_required_feature_rows=missing_required_count,
        forbidden_feature_rows=forbidden_count,
        warnings=warnings,
    )


def _normalize_score(value) -> float:
    numeric = float(value)
    if numeric > 1:
        numeric = numeric / 100.0
    return _clamp(numeric, 0.0, 1.0)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _stub_score(row: dict) -> float:
    quality = _normalize_score(row["company_quality_score"])
    valuation = _normalize_score(row["valuation_attractiveness_score"])
    timing = _normalize_score(row["timing_market_fit_score"])
    llm_adjustment = _clamp(float(row["llm_adjustment_total"]), -15.0, 15.0) / 100.0
    coverage = _clamp(float(row["coverage_confidence_score"]), 0.0, 1.0)
    base = (0.45 * quality) + (0.30 * valuation) + (0.20 * timing) + (0.05 * llm_adjustment)
    return round(_clamp(base * coverage, 0.0, 1.0), 6)


def _build_metrics(input_rows: int, validated: _ValidatedRows, scores: list[float]) -> dict:
    if scores:
        score_min = min(scores)
        score_max = max(scores)
        score_mean = round(mean(scores), 6)
    else:
        score_min = 0.0
        score_max = 0.0
        score_mean = 0.0
    return {
        "input_rows": input_rows,
        "valid_rows": len(validated.valid_rows),
        "missing_required_feature_rows": validated.missing_required_feature_rows,
        "forbidden_feature_rows": validated.forbidden_feature_rows,
        "stub_score_min": score_min,
        "stub_score_max": score_max,
        "stub_score_mean": score_mean,
    }