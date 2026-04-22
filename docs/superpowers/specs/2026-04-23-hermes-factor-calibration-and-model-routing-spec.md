# P20 Factor Calibration and Model Routing Spec

Date: 2026-04-23
Status: Draft for review
Scope: Upgrade Hermes from architecture-complete research orchestration into a more reliable factor-calibrated decision system

## 1. Purpose

Hermes has already established its core research pipeline:

- request routing
- orchestrator decomposition
- subagent execution
- evidence normalization
- final judgment
- boss-facing image-report delivery

The next major bottleneck is no longer workflow architecture.
It is factor quality, evidence depth, and model-output reliability.

P20 exists to improve:

1. the meaning and stability of thesis classification
2. the way fundamentals quality is scored
3. the distinction between insufficient coverage and genuine `No Trade`
4. the routing of different analyst roles to models strong enough for the task

This phase should make Hermes more decision-useful without discarding the existing research architecture.

## 2. Problem Statement

Recent live runs exposed a structural weakness:

- market data may be available
- analyst roles may execute
- but thesis quality can still collapse because too little structured fundamentals evidence is produced

This currently leads to an undesirable product behavior:

- thin or low-quality fundamentals evidence
- low `quality` score
- immediate thesis classification as `No Trade`

That is too coarse.
It conflates:

1. a genuinely unattractive setup
2. a research pass with inadequate evidence depth

Hermes therefore risks presenting:

- evidence scarcity as a negative conclusion
- weak analyst output as if it were a deliberate investment judgment

## 3. Non-Goals

P20 does not:

- replace the Phase 19 image-report pipeline
- change the approved boss-facing action vocabulary
- introduce bearish trading actions
- replace the orchestrator architecture
- convert Hermes into a pure quant strategy engine
- add auto-trading or execution

This phase is about decision calibration, not UI or order routing.

## 4. Core Product Decision

P20 treats Hermes as a structured discretionary research engine with factorized scoring.

Hermes is not becoming:

- a pure statistical factor model
- a generic LLM opinion wrapper
- a dashboard-only monitoring system

Hermes is becoming:

- a factor-aware research decision engine
- with explicit evidence coverage semantics
- and role-aware model routing

## 5. Key Observations From Current Runs

### 5.1 Current thesis gate is too hard

Current logic effectively does:

```text
if quality < threshold:
    No Trade
```

This is too aggressive when the root issue is analyst evidence sparsity rather than genuine negative fundamentals.

### 5.2 Fundamentals quality is too dependent on sparse evidence counts

Current quality behavior is too sensitive to:

- how many fundamentals evidence items were emitted
- how those items were normalized
- whether one analyst returned a shallow summary vs a multi-dimensional structured output

This makes thesis quality unstable and under-expressive.

### 5.3 Role coverage exists, but dimensional coverage does not

Hermes can currently know that:

- fundamentals ran
- technical ran
- news ran

But it cannot yet reliably express:

- whether profitability was covered
- whether cash flow was covered
- whether balance sheet quality was covered
- whether valuation support was covered
- whether management/capital allocation was covered

This means role coverage is mistaken for research completeness.

### 5.4 Model strength now matters at the analyst-role level

The system is entering a phase where:

- a weak or shallow fundamentals model can degrade the whole decision tree
- a stronger technical or news model may not compensate
- routing all analyst roles through the same model may no longer be optimal

## 6. P20 Design Goals

P20 should deliver:

1. a reliable distinction between `Inconclusive` and `No Trade`
2. a factorized fundamentals quality score
3. explicit evidence coverage accounting
4. role-specific analyst output schemas
5. configurable model routing by role
6. clearer auditability for why a ticker was blocked

## 7. Thesis State Redesign

## 7.1 Current issue

Hermes currently collapses too many situations into:

- `Investable`
- `Watchlist`
- `No Trade`

This is not enough.

## 7.2 Proposed thesis classification states

P20 should use:

- `Investable`
- `Watchlist`
- `Inconclusive`
- `No Trade`

## 7.3 Meanings

### `Investable`

Use when:

- factor quality is strong enough
- valuation and catalysts are supportive enough
- coverage is sufficient
- no major blocking issue exists

### `Watchlist`

Use when:

- thesis has meaningful support
- but timing, valuation, or catalyst strength is not yet sufficient
- research coverage is adequate enough to trust the judgment

### `Inconclusive`

Use when:

- research coverage is inadequate
- fundamentals evidence is too shallow
- model output did not provide enough dimensional support
- the system should not pretend this is a deliberate `No Trade`

This is the key new state.

### `No Trade`

Use only when:

- coverage is sufficient
- and the evaluated thesis is genuinely unattractive, broken, or not worth expressing long

## 7.4 Downstream behavior

### `Investable`

- continue into instrument selection
- continue into options structure / early exit when appropriate

### `Watchlist`

- do not produce an active instrument recommendation
- produce monitoring/watchlist output

### `Inconclusive`

- do not produce active instrument recommendation
- do not present as an investment conclusion
- explicitly request rerun / stronger coverage / later event-driven refresh

### `No Trade`

- do not produce active instrument recommendation
- explicitly communicate that the setup was evaluated and rejected

## 8. Fundamentals Factor Calibration

## 8.1 Current issue

A single scalar quality calculation based mainly on sparse bullish-count behavior is too fragile.

## 8.2 New factor structure

P20 should factorize fundamentals quality into sub-dimensions:

- profitability quality
- revenue and growth quality
- earnings quality
- cash flow quality
- balance sheet quality
- capital allocation quality
- valuation support
- management / execution confidence
- evidence coverage quality

## 8.3 Proposed scoring model

Use a weighted sub-score model instead of a single count-ratio formula.

Illustrative structure:

```text
fundamentals_quality =
    0.18 * profitability_quality +
    0.16 * growth_quality +
    0.14 * earnings_quality +
    0.12 * cashflow_quality +
    0.12 * balance_sheet_quality +
    0.10 * capital_allocation_quality +
    0.08 * management_execution_quality +
    0.10 * valuation_support +
    0.10 * evidence_coverage_quality
```

Exact weights can be tuned during implementation.
The important design decision is that Hermes should score dimensions, not just evidence counts.

## 8.4 Evidence coverage quality

Coverage itself should affect quality.

Example coverage scoring:

- 0.00 to 0.20: almost no meaningful fundamentals coverage
- 0.21 to 0.50: partial coverage
- 0.51 to 0.80: solid coverage
- 0.81 to 1.00: strong multi-dimensional coverage

Low coverage should pull the score down, but should preferentially drive `Inconclusive` rather than force `No Trade`.

## 9. Coverage Semantics

## 9.1 New required audit fields

Hermes should expose:

- `role_coverage`
- `fundamentals_evidence_count`
- `fundamentals_dimensions_covered`
- `fundamentals_dimensions_missing`
- `coverage_limited`
- `coverage_reason`
- `thesis_classification_reason`

## 9.2 Coverage-limited output semantics

Hermes must stop presenting evidence-thin runs as normal conclusions.

When coverage is insufficient:

- classify as `Inconclusive`
- mark the report as coverage-limited
- state what dimensions are missing
- recommend rerun conditions

## 9.3 Required distinction

Hermes must distinguish:

- `No Trade because the setup is unattractive`
from
- `Inconclusive because the system does not yet know enough`

This distinction must be visible in:

- `TickerResearchResult.audit`
- boss-facing summary fields
- image report prompt pack

## 10. Analyst Output Schema Upgrade

## 10.1 Fundamentals analyst must stop returning shallow verdict-only output

The fundamentals role should produce a structured payload with dimension-level fields.

Minimum desired schema:

- `profitability_assessment`
- `revenue_growth_assessment`
- `earnings_quality_assessment`
- `cashflow_assessment`
- `balance_sheet_assessment`
- `capital_allocation_assessment`
- `valuation_support_assessment`
- `management_execution_assessment`
- `key_fundamental_risks`
- `dimension_confidences`
- `overall_verdict`

## 10.2 EvidenceStore must extract atomic evidence by dimension

Evidence extraction should create separate evidence items for each covered dimension.

This allows:

- better factor scoring
- better auditability
- clearer coverage tracking
- less dependence on one verdict string

## 10.3 Other roles remain supporting, not dominant

Technical, news, sentiment, industry, and options should remain additive.
They may improve timing and conviction, but should not fully replace fundamentals quality.

## 11. Model Routing

## 11.1 Purpose

Different analyst roles may benefit from different model strengths.

P20 should introduce explicit role-to-model routing.

## 11.2 Routing design

Hermes should support:

- default provider/model
- per-role provider overrides
- per-role model overrides

Example routing intent:

- fundamentals: strongest reasoning / structured extraction model available
- valuation: strong reasoning model
- technical: fast structured model acceptable if quality remains sufficient
- news/sentiment: medium-cost model may be acceptable
- options/risk: structure-sensitive model preferred

## 11.3 Routing contract

Routing should be configurable without rewriting the orchestrator.

Suggested abstraction:

- provider registry
- role routing map
- safe fallback ordering

## 11.4 Failure semantics

If one role's provider is unavailable:

- Hermes should surface the missing role
- Hermes should degrade coverage explicitly
- Hermes should avoid pretending the run is fully trustworthy

## 12. Calibration Rules

## 12.1 Do not over-promote technical support

Technical strength may help timing, but should not rescue a fundamentally unsupported setup into `Investable`.

## 12.2 Do not over-punish evidence sparsity by calling it rejection

Insufficient coverage should usually become `Inconclusive`, not `No Trade`.

## 12.3 No forced symmetry

Hermes should not require every ticker to have the same evidence count to be comparable.
It should require enough dimensional coverage to justify classification.

## 13. Reporting Implications

P20 affects P19 outputs indirectly.

Image reports should reflect:

- `Investable`
- `Watchlist`
- `Inconclusive`
- `No Trade`

Specifically:

- `Inconclusive` must not be presented in the same language as a real rejection
- image prompts should include coverage reason and rerun guidance
- one-line call should remain honest about evidence depth

## 14. Implementation Boundaries

P20 should be implemented incrementally.

### Stage 1

- introduce `Inconclusive`
- separate coverage-limited semantics from `No Trade`
- add audit fields for coverage

### Stage 2

- redesign fundamentals factor scoring into dimensions
- extend EvidenceStore extraction
- add classification reason output

### Stage 3

- add model routing by analyst role
- add provider availability reporting
- add calibration tests and quality thresholds

## 15. Validation Requirements

P20 should be considered successful only if it can demonstrate:

1. thin-evidence runs no longer default to `No Trade`
2. fundamentals-rich runs can cross thresholds without relying on evidence-count hacks
3. `Inconclusive` is visible in audit and report pack
4. role-specific model routing is configurable and testable
5. image-report outputs remain honest about coverage state

## 16. Testing Strategy

Required tests should include:

- thesis classification under sparse coverage
- distinction between `Inconclusive` and `No Trade`
- dimension-based fundamentals scoring
- EvidenceStore extraction from structured fundamentals schema
- role routing selection
- provider unavailability behavior
- report-pack propagation of coverage semantics

## 17. Success Criteria

P20 is successful when Hermes can say, with high clarity:

- this ticker is investable
- this ticker is worth watching
- this ticker is inconclusive because the research pass is too thin
- this ticker is genuinely a no-trade setup

That is the point of this phase.

