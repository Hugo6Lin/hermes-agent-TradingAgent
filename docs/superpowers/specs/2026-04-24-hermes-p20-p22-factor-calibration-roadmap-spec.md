# P20-P22 Factor Calibration Roadmap Spec

Date: 2026-04-24
Status: Draft for engineering handoff
Scope: Redesign Hermes factor calibration as a dual-track, hard-data-first, audit-first roadmap across P20, P21, and P22

## 1. Purpose

Hermes has a strong research orchestration architecture, but its next bottleneck is not report delivery or workflow shape. The bottleneck is decision calibration.

This spec replaces the earlier P20 direction with a staged roadmap that separates:

1. systems-engineering correctness: honest thesis states, explicit coverage gates, and auditable factor logs
2. financial-validity work: factor persistence, autocorrelation, orthogonality diagnostics, IC, ICIR, IC decay, and later shrinkage-based calibration

The key design change is that P20 must not merely introduce a better scoring formula. P20 must create the logging contract that makes future factor evaluation possible.

## 2. Core Decision

Hermes will use a hard-data-first factor architecture.

Hard data provides the base scores. LLM output may add bounded, signed, auditable adjustments. Coverage and regime state are gates, not linear components of company quality.

P20, P21, and P22 accumulate as follows:

- P20: factor logging contract and honest thesis gates
- P21: hard-data base scoring and early diagnostics
- P22: financial validity loop and calibration handoff

No calendar estimates are assigned. Data-dependent stages are explicitly data-gated rather than time-gated.

## 3. Non-Goals

This roadmap does not:

- add autonomous trading
- add bearish trading actions
- replace the Phase 19 image-report pipeline
- turn Hermes into a full quant portfolio platform
- require CRSP, Compustat, or institutional historical datasets in P20
- require portfolio optimization in P20 or P21
- allow image/report delivery to change research decisions
- allow a single final scalar score to become the thesis classification authority

## 4. Design Principles

### 4.1 Logging contract before scoring confidence

P20 must freeze the fields that future diagnostics will need. The system cannot add those fields months later without losing calibration history.

Every research run should persist the factor state needed for later regression, ranking, backtest, IC, ICIR, IC decay, autocorrelation, and orthogonality analysis.

### 4.2 Gates before weighted sums

Thesis classification should be gate-based, not a single weighted sum.

Coverage, regime, quality, valuation, and timing each answer different questions. A low-quality company should not become `Investable` because timing is strong. A coverage-thin run should not become `No Trade` merely because the evidence is sparse.

### 4.3 Coverage is meta-level, not object-level

Coverage describes the research process. It must not be linearly added to company quality.

Coverage should decide whether Hermes is allowed to classify the thesis with confidence. It should not pretend to be a company-quality dimension.

### 4.4 Valuation is separate from quality

Valuation attractiveness describes the relationship between current price and expected value. It is not company quality.

A good company at an expensive price and a weak company at a cheap price must remain distinguishable in logs, reports, and later diagnostics.

### 4.5 LLM output is an overlay, not the base score

LLM analysis may identify qualitative red flags, management execution issues, catalyst nuance, or accounting anomalies. It must not become an unbounded replacement for hard-data scoring.

All LLM adjustments must be signed, bounded, reasoned, and logged.

### 4.6 Evaluation and scoring are planned in parallel, but data flows one way

The tracks are parallel in planning, but Track 2 depends on Track 1's logging contract.

```text
Track 1:  P20 schema freeze -> P21 hard-data scoring -> P21 LLM overlay -> P20/P21 structured gates
                         |
                         v
Track 2:              P20 persistence -> P21 autocorr/orthogonality -> P22 backtest -> P22 IC/ICIR/shrinkage
```

Track 2 consumes persisted scores and gate outcomes. It must not invent a separate shadow schema.

## 5. Factor Categories

Hermes should use four primary factor categories plus explicit regime/risk gating.

### 5.1 Company Quality

Purpose: measure the quality of the business itself.

Examples of future hard-data dimensions:

- profitability
- growth quality
- earnings quality
- cash-flow quality
- balance-sheet quality
- capital efficiency
- capital allocation quality

This score should not include valuation attractiveness or coverage.

### 5.2 Valuation Attractiveness

Purpose: measure whether current price is attractive relative to business quality and expected value.

Examples of future dimensions:

- relative valuation
- earnings yield
- free-cash-flow yield
- sales multiple versus growth
- valuation residual after controlling for company quality

P20 does not need to implement residualized valuation, but the schema must not prevent P21/P22 from adding it.

### 5.3 Timing / Market Fit

Purpose: measure whether current market conditions support entering or expressing the thesis now.

Examples:

- trend state
- volatility state
- liquidity state
- options environment
- technical momentum

Timing may influence entry, instrument selection, and watchlist state. Timing must not rescue an otherwise low-quality company into `Investable`.

### 5.4 Coverage Confidence

Purpose: measure whether Hermes has enough evidence to make a reliable classification.

Coverage must be tracked per category, not only as one global number.

Required coverage fields:

- `quality_coverage`
- `valuation_coverage`
- `timing_coverage`
- `regime_coverage`
- `llm_overlay_coverage`

Coverage failures should preferentially produce `Inconclusive`, not `No Trade`.

### 5.5 Regime / Risk Gate

Purpose: detect whether the current market regime is outside the distribution where Hermes is calibrated.

If the regime is out-of-sample, degraded, or not sufficiently covered, Hermes should return an explicit inconclusive state rather than overstate confidence.

Example classification:

- `Inconclusive-Regime`

P20 operational status:

- P20 must log regime fields and allow a regime gate result.
- P20 may treat the regime gate as conservative/stubbed if the required inputs are unavailable.
- P21 must define and implement the operational regime feature set.

Recommended P21 v1 regime feature set:

- VIX percentile or volatility proxy percentile
- rolling realized volatility percentile
- sector breadth or market breadth proxy
- cross-sectional dispersion proxy
- major index trend state

P21 must specify explicit thresholds for each feature before the gate is allowed to become fully authoritative. Until those thresholds exist, regime outputs must be disclosed as `regime_gate_status = "stubbed"` or `regime_gate_status = "insufficient_definition"`.

## 6. Thesis States

P20 should make `Inconclusive` a first-class thesis state.

Allowed high-level states:

- `Investable`
- `Watchlist`
- `Inconclusive`
- `No Trade`

### 6.1 Investable

Use when:

- required coverage gates pass
- regime gate passes
- company quality is strong enough
- valuation and/or timing are sufficiently supportive
- no blocking risk gate fires

### 6.2 Watchlist

Use when coverage is adequate enough to judge the setup, but the setup is not currently actionable.

Watchlist should have actionable sub-states:

- `Watchlist-PricedOut`: quality is strong but valuation is stretched
- `Watchlist-CoverageGap`: some non-critical dimension needs targeted refresh before action
- `Watchlist-TimingWait`: quality and valuation may be acceptable, but timing or market fit is not ready

### 6.3 Inconclusive

Use when Hermes cannot honestly classify the setup.

Examples:

- required coverage is missing
- fundamental data is too sparse
- valuation data is stale or incomplete
- regime is out-of-sample or not covered
- LLM output failed to provide structured support and no hard-data fallback exists

Inconclusive is not a softer label for `No Trade`. It is an explicit statement that Hermes lacks enough reliable evidence.

Suggested sub-states:

- `Inconclusive-Coverage`
- `Inconclusive-Regime`
- `Inconclusive-DataQuality`
- `Inconclusive-ModelFailure`

### 6.4 No Trade

Use only when:

- required coverage gates pass
- regime gate passes
- the setup was evaluated with sufficient evidence
- the result is genuinely unattractive, broken, too risky, or not worth expressing long

## 7. Classification Gate Logic

Classification must not be driven by a single final scalar score.

Recommended gate order:

```text
1. Data quality gate
   if critical data is missing or stale -> Inconclusive-DataQuality

2. Coverage gate
   if required category coverage is below threshold -> Inconclusive-Coverage

3. Regime gate
   if current regime is out-of-sample or uncalibrated -> Inconclusive-Regime

4. Company quality gate
   if company quality is poor and coverage passed -> No Trade

5. Valuation gate
   if quality is strong but valuation is stretched -> Watchlist-PricedOut

6. Timing gate
   if quality/valuation are acceptable but timing is weak -> Watchlist-TimingWait

7. Investable gate
   if quality, valuation, timing, coverage, and regime pass -> Investable

8. Fallback
   otherwise -> Watchlist-CoverageGap or Watchlist-TimingWait with structured reason
```

A `ranking_score` or `display_score` may exist later for sorting candidates, but it must be explicitly marked as non-authoritative for classification.

## 8. Required P20 Contracts

### 8.1 FactorSnapshot

`FactorSnapshot` is the core logging object for P20.

Required fields:

- `snapshot_id`
- `schema_version`
- `task_id`
- `ticker`
- `as_of_timestamp`
- `trading_day`
- `data_as_of_date`
- `universe_id` or `universe_label`
- `universe_membership_snapshot_id`
- `company_quality_score`
- `valuation_attractiveness_score`
- `timing_market_fit_score`
- `quality_coverage`
- `valuation_coverage`
- `timing_coverage`
- `regime_coverage`
- `llm_overlay_coverage`
- `llm_adjustment_total`
- `llm_adjustments`
- `gate_results`
- `classification`
- `classification_reason`
- `negative_signal_strength_decile`
- `thresholds_used`
- `model_routes_used`
- `source_refs`
- `created_at`

Optional but recommended fields:

- `raw_factor_values`
- `normalized_factor_values`
- `missing_dimensions`
- `stale_dimensions`
- `fallback_reasons`
- `provider_versions`
- `prompt_versions`
- `sector_id`
- `size_decile`

### 8.2 ForwardReturnObservation

`ForwardReturnObservation` is required so P22 can compute IC and ICIR from persisted P20 logs without re-reading prices directly.

Required fields:

- `observation_id`
- `snapshot_id`
- `ticker`
- `trading_day`
- `horizon_days`
- `return_value`
- `return_source`
- `price_start`
- `price_end`
- `start_price_date`
- `end_price_date`
- `gap_handled`
- `computed_at`

Rules:

- supported first horizons should include `1`, `5`, `21`, and `63` trading days
- observations must be linked to a `FactorSnapshot` by `snapshot_id`
- P22 IC, ICIR, and decay jobs must consume this table rather than reading price history directly
- P20 should add the contract and a stub or scheduled-job placeholder even if the first implementation only computes observations when horizons become available
- if a horizon cannot be computed, the missing observation must be logged with a reason rather than silently omitted from diagnostics

### 8.3 UniverseMembershipSnapshot

Point-in-time universe membership is required to avoid look-ahead bias.

Required fields:

- `universe_membership_snapshot_id`
- `universe_id`
- `universe_label`
- `as_of_timestamp`
- `members`
- `source`
- `created_at`

Rules:

- `members` must represent the usable universe as of `as_of_timestamp`
- factor diagnostics must use the point-in-time membership snapshot linked from `FactorSnapshot`
- diagnostics must not use today's index membership to evaluate old snapshots
- if point-in-time membership is unavailable, the diagnostic output must disclose the bias risk explicitly

### 8.4 LLMAdjustment

LLM adjustments must be bounded and auditable.

Required fields:

- `affected_category`
- `delta`
- `max_abs_delta`
- `reason`
- `source_refs`
- `model_provider`
- `model_name`
- `prompt_version`

Rules:

- `delta` must be signed
- `abs(delta)` must not exceed `max_abs_delta`
- first implementation should cap category-level adjustment around 0.10 to 0.15
- no adjustment may change a failed hard gate into a passed hard gate without explicit override support, which is out of scope for P20

### 8.5 ThesisGateResult

Required fields:

- `gate`
- `status`
- `score`
- `threshold`
- `failing_dimension`
- `reason_code`
- `recommended_action`

Example:

```json
{
  "gate": "coverage",
  "status": "failed",
  "score": 0.31,
  "threshold": 0.50,
  "failing_dimension": "valuation_coverage",
  "reason_code": "valuation_data_stale",
  "recommended_action": "rerun_valuation_with_fresh_data"
}
```

### 8.6 ClassificationReason

`classification_reason` must be structured, not free text only.

Required fields:

- `classification`
- `primary_gate`
- `primary_reason_code`
- `supporting_gates`
- `blocking_gates`
- `recommended_next_action`
- `human_summary`

### 8.7 SourceValueRef

Flat source lists are insufficient for later audit. Factor values should reference structured source records.

Required fields:

- `field_name`
- `value`
- `source`
- `fetched_at`
- `as_of_date`
- `provider`
- `quality_flags`

Rules:

- each material hard-data score should be traceable to source values when available
- missing values should be represented explicitly in `missing_dimensions`
- stale values should be represented explicitly in `stale_dimensions`

### 8.8 Schema Evolution

The factor logging contract must evolve without destroying calibration history.

Rules:

- every persisted factor object must include `schema_version`
- minor versions should be additive-only
- removals, renames, or semantic changes require a major version
- diagnostics must declare which schema versions they consume
- new fields that are needed for diagnostics should include a backfill strategy or an explicit statement that historical data before the field is not usable for that diagnostic

### 8.9 Snapshot Deduplication

P22 diagnostics need one canonical row per ticker per trading day unless an analysis explicitly opts into intraday rows.

Rules:

- the canonical key for daily diagnostics is `(ticker, trading_day, universe_membership_snapshot_id)`
- if Hermes runs the same ticker multiple times in one trading day, the latest successful snapshot for that key is the canonical daily snapshot
- superseded same-day snapshots should remain stored for audit but must be excluded from default IC and autocorrelation consumers
- diagnostics must disclose whether they use canonical daily snapshots or all intraday snapshots

## 9. P20 Deliverables

P20 is complete when Hermes can produce and persist the correct decision logs even before its factors are proven predictive.

Required artifacts:

1. `FactorSnapshot` contract
2. `ForwardReturnObservation` contract
3. `UniverseMembershipSnapshot` contract
4. `LLMAdjustment` contract
5. `ThesisGateResult` contract
6. structured `classification_reason`
7. first-class `Inconclusive` state
8. actionable Watchlist sub-states
9. per-category coverage fields
10. explicit non-authoritative `ranking_score` or no ranking score at all
11. persistence path for factor snapshots and forward-return observations
12. test fixtures showing future diagnostics can consume P20 logs

## 10. P20 Decision Gates

P20 does not pass unless these checks pass:

1. Every classification has a structured gate reason.
2. Coverage is not linearly added to company quality.
3. Valuation is not linearly added to company quality.
4. `Inconclusive` is distinct from `No Trade` in contracts, reporting, and image-report content truth.
5. `No Trade` requires sufficient coverage.
6. `final_thesis_score` is absent or renamed to `ranking_score` / `display_score` and marked non-authoritative.
7. The persisted snapshot contains all fields needed for P21/P22 diagnostics.
8. LLM adjustments are bounded, signed, and logged with reasons.
9. Regime failure can produce `Inconclusive-Regime`.
10. Tests assert that timing strength cannot rescue a poor company-quality gate into `Investable`.
11. P22 diagnostics can obtain forward returns from `ForwardReturnObservation` without reading prices directly.
12. Factor diagnostics use point-in-time universe membership or explicitly disclose bias risk.
13. Daily diagnostics have a deterministic deduplication rule for repeated same-day ticker runs.
14. `schema_version` exists and the schema evolution policy is documented.

## 11. P21 Roadmap: Hard-Data Base Scoring and Early Diagnostics

P21 builds on P20 logs. It should not change the P20 logging contract casually, because doing so fragments calibration history.

### 11.1 P21 scoring deliverables

- hard-data `company_quality_score`
- hard-data `valuation_attractiveness_score`
- rule-based `timing_market_fit_score`
- category-specific coverage scoring
- bounded LLM overlay implementation
- model-route logging per analyst role

### 11.2 P21 diagnostics deliverables

- factor snapshot persistence queries
- factor autocorrelation report
- cross-factor correlation report
- orthogonality diagnostic
- basic distribution diagnostics for each score
- LLM adjustment saturation report

### 11.3 P21 decision gates

P21 should pause for redesign if:

- major factor categories are highly collinear across tickers and time
- LLM adjustments frequently hit bounds
- coverage is usually missing in the same dimensions
- score distributions collapse into a narrow middle band
- Watchlist sub-states become a dumping ground rather than action-specific outputs

Suggested orthogonality gate:

- If `company_quality_score` and `valuation_attractiveness_score` are persistently correlated above an agreed threshold, investigate residualized valuation before proceeding.

The exact threshold may be finalized in implementation, but the diagnostic must exist.

## 12. P22 Roadmap: Financial Validity Loop

P22 is data-gated. It should begin once enough factor snapshots and forward returns exist to produce meaningful diagnostics.

### 12.1 P22 deliverables

- signal backtest by factor buckets
- IC and rank IC by factor category
- ICIR and rank ICIR
- IC decay across multiple horizons
- Newey-West / HAC significance annotations
- factor bucket monotonicity report
- calibration handoff report
- shrinkage-based threshold and ranking calibration

### 12.2 P22 entry gate

P22 is data-gated by sample quality, not by calendar time.

Minimum entry requirements:

- enough `FactorSnapshot` rows exist for the target universe and factor category
- enough `ForwardReturnObservation` rows exist for the target horizon
- default minimum floor should be approximately 24 monthly observations or 60 weekly observations per factor before data-derived weights influence calibration
- Newey-West / HAC-adjusted t-statistics must be computed before any `w_data` contribution is accepted
- before the sample floor and significance checks pass, `delta = 1.0` and weights remain entirely on the engineering prior

These floors may be refined during implementation, but P22 must not update shrinkage weights from tiny, noisy samples.

### 12.3 Shrinkage calibration

The calibration handoff should use a prior-plus-data structure:

```text
w_final = delta * w_prior + (1 - delta) * w_data
```

Rules:

- `w_prior` is the engineering prior
- `w_data` is derived from factor diagnostics such as IC, ICIR, and stability
- `delta` should decline as usable evidence grows
- shrinkage may tune ranking and thresholds
- shrinkage must not bypass explicit gates

### 12.4 P22 decision gates

P22 should not promote a factor unless:

- it has non-trivial IC or rank IC
- ICIR suggests usable stability
- decay behavior matches intended holding horizon
- results are not dominated by one market regime
- factor buckets show at least partial monotonicity
- transaction-cost sensitivity does not obviously destroy the signal, if portfolio simulation is added later

P22 diagnostics must also disclose:

- sample size per factor and horizon
- universe membership source and point-in-time status
- deduplication policy used
- forward-return observation coverage
- whether the result is eligible for shrinkage or still prior-only

## 13. Reporting Requirements

Boss-facing reporting must remain honest about classification state.

### 13.1 Inconclusive reporting

Reports should say:

- what coverage failed
- which gate blocked classification
- what rerun or data refresh is recommended
- that no investment conclusion was reached

Reports must not say or imply that `Inconclusive` means `No Trade`.

### 13.2 Watchlist reporting

Watchlist reports should show the actionable sub-state:

- priced out: show target price or valuation condition
- coverage gap: show missing dimension and rerun instruction
- timing wait: show trigger condition

### 13.3 Image report content truth

The image report layer must consume structured gate outcomes. It must not invent a cleaner classification than Hermes produced.

### 13.4 Baseline expectation disclosure

Early P20/P21 runs should be expected to produce a high `Inconclusive` rate while coverage, regime definitions, and data availability mature.

Rules:

- high early `Inconclusive` rates are valid behavior, not automatic evidence that the system is broken
- thresholds must not be loosened merely to reduce the visible `Inconclusive` rate
- reporting should distinguish "system failed" from "system correctly refused to overstate confidence"
- operator-facing summaries should disclose the current coverage maturity of the factor system

## 14. Testing Requirements

P20 tests should focus on contracts, gates, and logging completeness.

Required test categories:

1. `Inconclusive` contract tests
2. per-category coverage gate tests
3. `No Trade` requires sufficient coverage tests
4. `Watchlist-PricedOut`, `Watchlist-CoverageGap`, and `Watchlist-TimingWait` tests
5. LLM adjustment bound tests
6. structured `classification_reason` tests
7. factor snapshot serialization tests
8. factor snapshot persistence tests
9. image-report mapping tests for `Inconclusive`
10. regression tests proving `ranking_score` cannot drive classification
11. forward-return observation contract and serialization tests
12. point-in-time universe membership tests
13. same-day snapshot deduplication tests
14. schema-version compatibility tests
15. negative-signal-strength logging tests

P21 tests should add diagnostics over small fixtures.

P22 tests should add deterministic fixture-based IC, ICIR, decay, and shrinkage calculations.

## 15. Implementation Boundaries

P20 should modify the canonical research pipeline without disturbing Phase 19 report authority boundaries.

Likely affected files:

- `agent/research_v1/contracts.py`
- `agent/research_v1/thesis_engine.py`
- `agent/research_v1/app.py`
- `agent/research_v1/orchestrator_reporting.py`
- `agent/research_v1/image_prompt_builder.py`
- `agent/research_v1/data/database.py`

Likely new files:

- `agent/research_v1/thesis_factors.py`
- `agent/research_v1/factor_snapshot.py`
- `agent/research_v1/factor_persistence.py`
- `agent/research_v1/forward_returns.py`
- `agent/research_v1/universe_membership.py`

P21 may add:

- `agent/research_v1/factor_diagnostics.py`
- `agent/research_v1/factor_hard_data.py`
- `agent/research_v1/model_routing.py`

P22 may add:

- `agent/research_v1/factor_backtest.py`
- `agent/research_v1/factor_ic.py`
- `agent/research_v1/factor_calibration.py`

## 16. Success Criteria

The roadmap succeeds if Hermes becomes more honest before it becomes more confident.

P20 success means:

- Hermes records the right factor history
- Hermes records the forward-return observation targets needed for P22
- Hermes links factor snapshots to point-in-time universe membership
- Hermes separates missing evidence from negative conclusions
- Hermes keeps quality, valuation, timing, coverage, and regime distinct
- future diagnostics can consume today's logs

P21 success means:

- Hermes has reproducible hard-data base scores
- LLM output is bounded and auditable
- early diagnostics reveal whether factor categories are meaningfully distinct

P22 success means:

- Hermes can evaluate whether factors predict future returns
- calibration is data-informed rather than hand-tuned
- factor weights and thresholds evolve through an auditable feedback loop
