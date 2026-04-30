# P25-A XGBoost Meta-Model Shadow Dry Adapter Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: First real P25 shadow candidate adapter for XGBoost-style meta-model experiments

## 1. Purpose

P24 built the safety scaffold:

```text
Entry Gate -> Registry -> Runner -> Persistence/Observation -> Health Report
```

P25-A introduces the first real shadow candidate into that scaffold.

The candidate is an XGBoost-style meta-model adapter, but P25-A is still a dry/stub phase. It does not import XGBoost, does not train a model, and does not persist model objects. It proves Hermes can pass a real candidate through P24 safely.

## 2. Core Principle

P25-A is not "use XGBoost in production."

P25-A is "register and run an XGBoost-style candidate as a shadow-only dry adapter with auditable feature contracts and namespace-safe outputs."

The adapter may produce deterministic stub scores for testing the pipeline. Those scores are not calibrated alpha and must never feed production classification.

## 3. Non-Goals

P25-A must not:

- import `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines`, or model-training libraries
- train any model
- load or save model objects
- compute real fitted predictions
- write canonical `FactorSnapshot`
- write production configs
- modify thesis classification
- modify trade plans, exits, sizing, or portfolio logic
- promote any score
- execute live trades

## 4. Inputs

### 4.1 Feature rows

The adapter accepts feature rows as dictionaries.

Required fields:

- `snapshot_id`
- `ticker`
- `trading_day`
- `company_quality_score`
- `valuation_attractiveness_score`
- `timing_market_fit_score`
- `llm_adjustment_total`
- `coverage_confidence_score`
- `data_as_of_date`
- `universe_membership_snapshot_id`

Optional fields:

- `sector`
- `market_cap_bucket`
- `regime_label`
- `negative_signal_strength_decile`

### 4.2 `XGBoostMetaFeatureContract`

Required fields:

- `schema_version`: `p25_xgb_feature_contract.0`
- `required_features`
- `optional_features`
- `target_return_basis`: must be `net`
- `point_in_time_required`: must be `true`
- `forbidden_features`
- `namespace`

Forbidden features:

- `future_return`
- `forward_return`
- `net_return_pct`
- `gross_return_pct`
- `return_value`
- `classification`
- `take_profit`
- `stop_loss`
- `live_trade_signal`

### 4.3 `XGBoostShadowAdapterConfig`

Required fields:

- `schema_version`: `p25_xgb_adapter.0`
- `candidate_namespace`
- `adapter_name`
- `adapter_version`
- `feature_contract`
- `score_output_name`
- `feature_audit_output_name`
- `metadata_output_name`
- `min_rows`
- `allow_missing_optional_features`
- `calibration_status`: must be `shadow_dry_run`

Accepted namespace:

```text
candidate_namespace starts with "shadow_meta_model."
all output names start with candidate_namespace + "."
```

### 4.4 `XGBoostDryRunAdapter`

Required behavior:

- accepts `XGBoostShadowAdapterConfig`
- accepts feature rows as `list[dict]`
- exposes `adapter_name`
- exposes `adapter_version`
- implements `run(manifest, request) -> ShadowAdapterResult`
- performs validation and deterministic stub scoring only

## 5. Outputs

### 5.1 Adapter result

The adapter must return `ShadowAdapterResult` from P24-C.

Produced artifacts:

- `<namespace>.shadow_predictions`
- `<namespace>.feature_audit`
- `<namespace>.dry_run_metadata`

Attempted outputs must match produced artifacts.

Metrics:

- `input_rows`
- `valid_rows`
- `missing_required_feature_rows`
- `forbidden_feature_rows`
- `stub_score_min`
- `stub_score_max`
- `stub_score_mean`

Warnings:

- `missing_optional_features:<feature>` for optional feature gaps
- `row_excluded_missing_required_features` if any row is excluded
- `row_excluded_forbidden_features` if any row is excluded

## 6. Stub Score

P25-A may compute a deterministic stub score only to exercise the shadow pipeline.

Required formula:

```text
base = 0.45 * company_quality_score
     + 0.30 * valuation_attractiveness_score
     + 0.20 * timing_market_fit_score
     + 0.05 * bounded_llm_adjustment

bounded_llm_adjustment = clamp(llm_adjustment_total, -15, 15) / 100
coverage_multiplier = clamp(coverage_confidence_score, 0, 1)
stub_score = clamp(base * coverage_multiplier, 0, 1)
```

If input scores are in `0..100`, the adapter must normalize them to `0..1` before scoring.

The score is explicitly not a production ranking score.

## 7. Validation

The adapter must:

- reject config namespace outside `shadow_meta_model.*`
- reject output names outside namespace
- reject `target_return_basis != "net"`
- reject `point_in_time_required != true`
- reject rows with forbidden features
- exclude rows missing required features
- exclude rows with missing point-in-time fields
- produce no predictions for invalid rows
- return metrics that reveal excluded rows

If all rows are invalid, the adapter may still return a completed `ShadowAdapterResult` with zero valid rows and warnings. P24-C runner remains responsible for namespace and forbidden-output enforcement.

## 8. P24 Integration

P25-A must work through existing P24 components:

1. P24-A gate admits `xgboost_meta_model`.
2. P24-B registry creates a manifest.
3. P24-C runner executes adapter in `shadow_stub` mode.
4. P24-D store persists the run record.
5. P24-E health report surfaces the experiment.

The P25-A adapter must not bypass runner or persistence.

## 9. Tests

Acceptance tests must cover:

1. default config uses `shadow_meta_model.*` namespace
2. config rejects non-shadow namespace
3. config rejects output outside namespace
4. feature contract rejects non-net target basis
5. feature contract contains required PIT fields
6. adapter returns `ShadowAdapterResult`
7. adapter excludes rows with missing required features
8. adapter excludes rows with forbidden future-return features
9. adapter emits optional-feature warnings
10. stub scores are deterministic and clamped to `0..1`
11. runner executes adapter in `shadow_stub`
12. run record persists through P24-D
13. health report sees experiment through P24-E
14. no model libraries are imported

## 10. Acceptance Checklist

- Feature contract exists.
- Adapter config exists.
- Namespace validation works.
- Point-in-time fields are required.
- Forbidden features are blocked.
- Missing required feature rows are excluded.
- Optional feature gaps are warned.
- Stub scores are deterministic.
- Outputs stay under `shadow_meta_model.*`.
- P24-C runner executes adapter.
- P24-D persists run record.
- P24-E health report sees experiment.
- No model libraries are imported.
- No production outputs are written.

## 11. Boundary to P25-B

P25-A ends at deterministic dry/stub scoring.

P25-B may introduce offline training-data extraction for a future fitted meta-model, but only if it remains point-in-time, shadow-only, and passes a separate design review.
