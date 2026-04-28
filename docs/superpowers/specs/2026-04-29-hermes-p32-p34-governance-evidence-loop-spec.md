# Hermes P32-P34 Governance Evidence Loop Spec

Date: 2026-04-29
Status: Approved design for implementation planning
Scope: P32 evidence artifact registry, P33 signal-family edge review, and P34 boss governance daily brief

## 1. Purpose

P31 created the readiness layer:

```text
VersionReadinessDossier
  -> SignalFamilyReadinessDossier[]
  -> DailyGovernanceRun
```

P32-P34 extend that readiness layer into a governance evidence loop:

```text
P31 DailyGovernanceRun
  -> P32-A EvidenceArtifactRegistry
  -> P32-B ControlledEvidenceGenerationDryRun
  -> P33 SignalFamilyEdgeReview
  -> P34 BossGovernanceDailyBrief
```

The goal is to help Hermes answer:

- What evidence exists?
- What evidence is missing or stale?
- Which missing evidence can be safely requested later?
- Which signal or factor families have enough evidence for shadow observation or human review?
- What should the boss see each day without turning the system into auto-trading?

## 2. Phase Map

### P32-A: Evidence Artifact Registry

Collect and summarize existing governance artifacts.

### P32-B: Controlled Evidence Generation Dry Run

Validate generation requests and produce a dry-run manifest. P32-B does not actually run diagnostics, training, portfolio simulation, or execution analysis.

### P33: Signal Family Edge Review

Use the P32 registry to review whether a signal/factor/shadow family has enough evidence, net-return support, integrity checks, and execution realism to continue observation or enter human review.

### P34: Boss Governance Daily Brief

Convert P31-P33 outputs into a boss-readable daily governance brief.

## 3. Non-Goals

P32-P34 do not:

- auto-trade
- approve production adoption
- mutate production calibration config
- promote shadow outputs into canonical factor fields
- train models
- run P22/P25/P28 jobs in P32-B v1
- bypass P22 data-integrity gates
- bypass P24-P30 shadow-only or sandbox-only boundaries
- replace the Phase 19 image-report mainline
- tell the boss to follow a trade without human review

All outputs remain governance artifacts, not trade execution instructions.

## 4. Design Principles

### 4.1 Collect before generate

Hermes should first know which artifacts already exist before requesting new work.

### 4.2 Dry-run before execution

P32-B v1 validates generation requests and emits a manifest. Actual artifact generation is deferred to a later phase.

### 4.3 Net evidence before edge claims

P33 must treat net-return evidence as the default. Gross-only evidence is not enough for a positive edge review.

### 4.4 Human review before production

Positive statuses may indicate readiness for human review. They must not imply production approval.

### 4.5 Boss brief without trading authority

P34 is a governance summary. It must not become a buy/sell instruction surface.

## 5. P32-A: Evidence Artifact Registry

### 5.1 Goal

`EvidenceArtifactRegistry` answers:

> Which governance artifacts exist, where are they, what phase do they belong to, and are any expected artifacts missing or stale?

### 5.2 Proposed Module

```text
agent/research_v1/evidence_artifact_registry.py
tests/agent/research_v1/test_evidence_artifact_registry.py
```

### 5.3 Expected Artifact Types

P32-A should recognize these artifact types:

- `p20_factor_snapshot`
- `p22_validity_report`
- `p23_shadow_calibration_report`
- `p24_shadow_experiment_manifest`
- `p25_training_dataset_result`
- `p25_shadow_training_result`
- `p26_shadow_portfolio_report`
- `p28_execution_realism_report`
- `p29_adoption_dossier`
- `p30_advanced_model_admission`
- `p31_version_readiness`
- `p31_signal_family_readiness`
- `p31_daily_governance`

### 5.4 Registry Inputs

The registry should accept:

- `run_date`
- one or more root paths to scan
- expected artifact definitions
- freshness policy in days
- optional family namespace filters

Default scan roots should include:

```text
output/governance/
```

The implementation may also accept explicit artifact records for tests and controlled callers.

### 5.5 Artifact Record Contract

Each artifact record should include:

- `artifact_id`
- `artifact_type`
- `phase_id`
- `path`
- `present`
- `status`
- `family_namespace`
- `created_at`
- `freshness_days`
- `summary`
- `details`

Allowed artifact statuses:

- `present`
- `missing`
- `stale`
- `invalid`

### 5.6 Registry Report Contract

`EvidenceArtifactRegistryReport` should include:

- `run_date`
- `scan_roots`
- `artifact_records`
- `missing_artifact_types`
- `stale_artifact_ids`
- `invalid_artifact_ids`
- `coverage_by_phase`
- `coverage_by_family`
- `next_actions`
- `warnings`

Allowed registry statuses:

- `complete`
- `incomplete_missing_artifacts`
- `incomplete_stale_artifacts`
- `invalid_registry`

### 5.7 P32-A Boundaries

P32-A must not:

- run any diagnostics
- run any training
- run portfolio simulation
- call broker or market execution APIs
- mutate any artifact
- delete or overwrite files

It only scans and summarizes.

## 6. P32-B: Controlled Evidence Generation Dry Run

### 6.1 Goal

`ControlledEvidenceGenerationDryRun` answers:

> If Hermes later needs to generate missing evidence, which requested artifacts are allowed, which are blocked, and what inputs are required?

P32-B v1 is dry-run only.

### 6.2 Proposed Module

```text
agent/research_v1/evidence_generation_dry_run.py
tests/agent/research_v1/test_evidence_generation_dry_run.py
```

### 6.3 Generation Request Contract

`EvidenceGenerationRequest` should include:

- `artifact_type`
- `phase_id`
- `family_namespace`
- `requested_output_dir`
- `input_refs`
- `allow_actual_execution`
- `notes`

For P32-B v1, `allow_actual_execution=True` must be rejected.

### 6.4 Required Input Rules

The dry-run validator should report required inputs by artifact type.

Examples:

- `p22_validity_report`
  - factor snapshot rows
  - forward return observations
  - data integrity policy
- `p25_training_dataset_result`
  - point-in-time factor snapshots
  - target definition
  - feature namespace
- `p25_shadow_training_result`
  - P25 training dataset result
  - walk-forward split manifest
  - registered P24 experiment manifest
- `p28_execution_realism_report`
  - trade intents
  - liquidity inputs
  - alpha edge estimate

### 6.5 Dry-Run Report Contract

`ControlledEvidenceGenerationReport` should include:

- `status`
- `requested_artifacts`
- `allowed_requests`
- `blocked_requests`
- `required_inputs_by_artifact`
- `dry_run_manifest_path`
- `next_actions`
- `warnings`

Allowed statuses:

- `dry_run_complete`
- `blocked_unsafe_request`
- `blocked_missing_inputs`

### 6.6 P32-B Boundaries

P32-B must not:

- actually generate P22/P25/P28 artifacts in v1
- train a model
- mutate production config
- overwrite existing artifacts
- write into production namespaces
- allow `allow_actual_execution=True`

It may write a dry-run manifest under:

```text
output/governance/YYYY-MM-DD/evidence_generation_dry_run.json
output/governance/YYYY-MM-DD/evidence_generation_dry_run.md
```

## 7. P33: Signal Family Edge Review

### 7.1 Goal

`SignalFamilyEdgeReview` answers:

> Does this signal/factor/shadow family have enough evidence to continue observation or enter human review?

It does not train, promote, or change weights.

### 7.2 Proposed Module

```text
agent/research_v1/signal_family_edge_review.py
tests/agent/research_v1/test_signal_family_edge_review.py
```

### 7.3 Review Inputs

P33 should consume:

- `EvidenceArtifactRegistryReport`
- family namespace
- family type
- minimum sample policy
- net-return requirement
- execution realism requirement
- optional P31 family readiness status

### 7.4 Required Evidence Checks

P33 should check:

- P22 diagnostics are present when factor validity is claimed
- net-return basis exists for edge claims
- gross-only edge is blocked or warned
- lookahead/source audit blockers are absent
- P23 shadow calibration or observation evidence exists when calibration quality is claimed
- P25 training/shadow results exist when model-family edge is claimed
- P26 portfolio evidence exists when portfolio-level usefulness is claimed
- P28 execution realism exists when trade implementation quality is claimed
- sample/observation counts satisfy the configured minimum policy
- degradation warnings are surfaced

### 7.5 Edge Review Report Contract

`SignalFamilyEdgeReviewReport` should include:

- `family_namespace`
- `family_type`
- `status`
- `edge_evidence_summary`
- `risk_evidence_summary`
- `integrity_blockers`
- `missing_artifacts`
- `degradation_warnings`
- `execution_cost_warnings`
- `allowed_next_step`
- `promotion_forbidden_reasons`
- `human_review_questions`

Allowed statuses:

- `blocked_missing_evidence`
- `blocked_integrity_failure`
- `shadow_observation_only`
- `ready_for_human_review`
- `rejected_for_now`

Allowed next steps:

- `collect_more_evidence`
- `continue_shadow_observation`
- `prepare_human_review`
- `reject_for_now`

### 7.6 P33 Boundaries

P33 must not:

- train models
- mutate calibration config
- promote shadow outputs
- approve production
- claim profitability from diagnostics alone
- accept gross-only evidence as sufficient for positive edge review

## 8. P34: Boss Governance Daily Brief

### 8.1 Goal

`BossGovernanceDailyBrief` answers:

> What does the boss need to know today about Hermes governance health, missing evidence, review candidates, and risks?

It is a governance brief, not a trade instruction.

### 8.2 Proposed Module

```text
agent/research_v1/boss_governance_brief.py
tests/agent/research_v1/test_boss_governance_brief.py
```

### 8.3 Inputs

P34 should consume:

- P31 daily governance result
- P32 registry report
- P32 generation dry-run report
- P33 family edge review reports

### 8.4 Brief Contract

`BossGovernanceDailyBrief` should include:

- `run_date`
- `overall_status`
- `system_health_summary`
- `missing_evidence_summary`
- `stale_evidence_summary`
- `family_review_candidates`
- `families_in_shadow_observation`
- `blocked_families`
- `risk_warnings`
- `next_actions`
- `forbidden_actions_disclaimer`

Allowed overall statuses:

- `governance_ready_for_review`
- `governance_incomplete`
- `governance_degraded`
- `no_review_candidates`

### 8.5 Output Paths

P34 should write:

```text
output/governance/YYYY-MM-DD/boss_daily_brief.json
output/governance/YYYY-MM-DD/boss_daily_brief.md
```

### 8.6 Boss-Facing Language Rules

The brief may say:

- evidence is missing
- a family is ready for human review
- a family should continue shadow observation
- a blocker or degradation warning exists
- next governance actions are needed

The brief must not say:

- buy this now
- sell this now
- production approved
- model promoted
- follow this trade
- guaranteed edge

### 8.7 P34 Boundaries

P34 must not:

- replace investment reports
- replace Phase 19 image reports
- trigger notifications in v1
- start services
- call market data or broker APIs
- mutate files outside its output directory

## 9. End-to-End Flow

The intended P32-P34 flow is:

```text
P31 daily governance artifacts exist
  -> P32-A scans output/governance and explicit artifact records
  -> P32-A emits registry report
  -> P32-B validates missing-artifact generation requests in dry-run mode
  -> P33 reviews configured signal/factor families against registry evidence
  -> P34 writes boss_daily_brief.json and boss_daily_brief.md
```

## 10. Testing Strategy

### 10.1 P32-A Tests

Required tests:

- present artifact is recorded as `present`
- missing expected artifact is recorded as `missing`
- stale artifact is recorded as `stale`
- invalid artifact path is recorded as `invalid`
- coverage by phase is computed
- coverage by family is computed
- registry report serializes to JSON

### 10.2 P32-B Tests

Required tests:

- dry-run request for known artifact type succeeds when required inputs exist
- missing required inputs block request
- unknown artifact type blocks request
- `allow_actual_execution=True` is rejected
- production namespace output is rejected
- dry-run manifest writes JSON and Markdown

### 10.3 P33 Tests

Required tests:

- missing P22 diagnostics blocks factor edge review
- gross-only edge is not accepted as human-review-ready
- lookahead/source audit blocker produces `blocked_integrity_failure`
- shadow model without P25/P26 evidence remains blocked or observation-only
- execution cost blocker prevents positive review
- mature net evidence can produce `ready_for_human_review`
- promotion forbidden reasons are always present for shadow/model families

### 10.4 P34 Tests

Required tests:

- brief includes system health summary
- brief includes missing and stale evidence summaries
- brief includes human review candidates
- brief excludes trading instructions
- degraded governance input produces `governance_degraded`
- JSON and Markdown are written under `output/governance/YYYY-MM-DD/`

### 10.5 Regression Tests

P32-P34 completion requires:

```text
P31 focused tests pass
P32 focused tests pass
P33 focused tests pass
P34 focused tests pass
P20-P34 governance chain tests pass
```

## 11. Acceptance Criteria

P32 is accepted when:

- existing artifacts can be scanned into a registry
- missing/stale/invalid artifacts are visible
- dry-run generation requests are validated
- unsafe generation requests are blocked
- no actual diagnostics/training/evaluation jobs are run

P33 is accepted when:

- family edge review consumes registry evidence
- missing/integrity-blocked evidence prevents positive review
- net-return requirement is enforced
- execution realism blockers are visible
- no family is promoted or production-approved

P34 is accepted when:

- boss daily brief is generated in JSON and Markdown
- brief summarizes system health, missing evidence, review candidates, risks, and next actions
- brief does not contain trading instructions or production approval language
- outputs remain under `output/governance/YYYY-MM-DD/`

## 12. Future Work

Future phases may add:

- P35 actual controlled evidence generation
- P36 CLI wiring for daily governance bundle
- P37 viewer integration for governance briefs
- P38 notification routing for blockers and newly ready review candidates

Those phases require separate specs before implementation.
