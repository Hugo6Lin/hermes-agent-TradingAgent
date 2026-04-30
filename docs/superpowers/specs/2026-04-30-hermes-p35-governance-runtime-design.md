# Hermes P35 Governance Runtime and Documentation Closure Spec

Date: 2026-04-30
Status: Approved direction for implementation planning
Scope: P35 governance runtime entrypoint, artifact-driven daily orchestration, and doc standards closure

## 1. Purpose

P31-P34 built a governance evidence loop:

```text
P31 DailyGovernanceRun
  -> P32-A EvidenceArtifactRegistry
  -> P32-B ControlledEvidenceGenerationDryRun
  -> P33 SignalFamilyEdgeReview
  -> P34 BossGovernanceDailyBrief
```

The loop is implemented as pure modules, but it is not yet easy to run as a
single operator workflow. P35 turns the loop into a controlled local runtime
entrypoint while keeping all existing hard boundaries intact.

P35 also closes the known documentation-standard gaps so the governance code is
easier for future review models and implementation models to navigate.

## 2. Phase Map

### P35-A: Governance Runtime Entrypoint

Add a stdlib-only governance runtime module that can assemble and run the
P31-P34 artifacts from explicit local configuration.

### P35-B: CLI Wiring

Expose the runtime through the existing `hermes-research` argparse CLI as a
governance subcommand.

### P35-C: Documentation Standards Closure

Fix the known `test_doc_standards.py` failures:

- add a Data Flow / How It Fits section to `agent/research_v1/README.md`
- add `agent/research_v1/report_templates/README.md`

### P35-D: Regression Verification

Run focused P35 tests, doc standards, P31-P35 governance tests, and the full
P20-P35 chain.

## 3. Non-Goals

P35 must not:

- auto-trade
- send broker orders
- approve production adoption
- mutate production calibration config
- promote shadow model outputs into canonical factor fields
- train models
- run P22/P25/P28 evidence generation jobs
- convert P32-B dry-run requests into real execution
- schedule recurring jobs
- send notifications
- add a web viewer
- bypass P22 data-integrity checks
- bypass P24-P30 shadow-only or sandbox-only boundaries

P35 is a runtime wrapper around governance artifacts, not a trading or production
promotion system.

## 4. Design Principles

### 4.1 Explicit Inputs Before Automation

The runtime should accept explicit JSON configuration and local paths. It should
not infer production readiness from ambient state or hidden defaults.

### 4.2 One Command, No New Authority

The command may assemble reports and write governance artifacts. It must not gain
new powers beyond P31-P34.

### 4.3 Reuse Existing Contracts

P35 should reuse:

- `DailyGovernanceRequest`
- `VersionReadinessRequest`
- `SignalFamilyReadinessRequest`
- `EvidenceArtifactRegistryRequest`
- `EvidenceGenerationRequest`
- `SignalFamilyEdgeReviewRequest`
- `BossGovernanceBriefRequest`

The runtime should adapt JSON into those contracts instead of creating a parallel
governance model.

### 4.4 Deterministic Outputs

Given the same config, run date, and files, P35 should produce stable JSON and
Markdown outputs under:

```text
output/governance/YYYY-MM-DD/
```

### 4.5 Human-Review Language

Boss-facing output and CLI output may say "ready for human review". They must not
say "buy", "sell", "production approved", "model promoted", or anything that
turns the system into a follow-trading surface.

## 5. P35-A: Governance Runtime Entrypoint

### 5.1 Goal

Add:

```text
agent/research_v1/governance_runtime.py
tests/agent/research_v1/test_governance_runtime.py
```

The runtime answers:

> Can an operator run the current governance loop from one local config file and
> receive a boss daily brief plus machine-readable artifacts?

### 5.2 Runtime Request Contract

`GovernanceRuntimeRequest` should include:

- `run_date`
- `repo_root`
- `output_root`
- `config_path`
- `freshness_policy_days`

The config file supplies:

- `version_readiness`
- `signal_families`
- `expected_artifacts`
- `generation_requests`
- `edge_reviews`

### 5.3 Runtime Result Contract

`GovernanceRuntimeResult` should include:

- `status`
- `run_date`
- `output_dir`
- `daily_governance_status`
- `registry_status`
- `generation_status`
- `boss_brief_status`
- `artifacts_written`
- `warnings`

Allowed statuses:

- `completed`
- `completed_with_warnings`
- `governance_degraded`
- `blocked_invalid_config`

### 5.4 Config Format

The config should be JSON-only in P35.

Minimum shape:

```json
{
  "version_readiness": {
    "version_id": "p35-local",
    "branch": "codex/quant-governance-p20-p30",
    "commit": "local",
    "evidence": {
      "p20_p30_regression_passed": true,
      "p31_p34_regression_passed": true,
      "doc_standards_passed": false
    },
    "notes": "local governance runtime dry run"
  },
  "signal_families": [],
  "expected_artifacts": [],
  "generation_requests": [],
  "edge_reviews": []
}
```

### 5.5 Output Files

P35 should write or preserve these files under `output/governance/YYYY-MM-DD/`:

- P31 daily governance files:
  - `version_readiness.json`
  - `version_readiness.md`
  - `signal_families.json`
  - `signal_families.md`
  - `daily_summary.json`
  - `daily_summary.md`
- P32 dry-run files:
  - `evidence_generation_dry_run.json`
  - `evidence_generation_dry_run.md`
- P34 files:
  - `boss_daily_brief.json`
  - `boss_daily_brief.md`
- P35 runtime file:
  - `governance_runtime_summary.json`

### 5.6 Error Handling

Invalid config should return `blocked_invalid_config` when the runtime is called
programmatically and should return a non-zero CLI exit code when called from the
CLI.

Write failures should return `governance_degraded` without mutating production
configuration or deleting partial governance artifacts.

## 6. P35-B: CLI Wiring

### 6.1 Goal

Add an argparse subcommand to the existing CLI:

```bash
python -m agent.research_v1.batch_cli governance-run \
  --config path/to/governance_config.json \
  --run-date 2026-04-30 \
  --output-root output/governance
```

### 6.2 CLI Behavior

On success, the CLI should print:

- runtime status
- output directory
- boss brief status
- artifact paths

On invalid config, the CLI should print a concise error and return a non-zero
exit code.

The CLI should not start a server, schedule work, call a broker, or run evidence
generation jobs.

## 7. P35-C: Documentation Standards Closure

### 7.1 Goal

Make `test_doc_standards.py` pass for the known documentation gaps.

### 7.2 Required Changes

`agent/research_v1/README.md` should add a section whose heading matches the
doc-standard Data Flow pattern. It should reflect the current P31-P34 governance
loop and P35 runtime direction.

`agent/research_v1/report_templates/README.md` should describe:

- what the directory is
- core files
- how it relates to the report pipeline
- how it fits into data flow
- what to update when templates change

## 8. Testing Requirements

P35 focused tests:

- valid config runs all governance stages and writes summary files
- invalid config returns `blocked_invalid_config`
- CLI success returns `0`
- CLI invalid config returns non-zero
- CLI output contains governance status and output path
- doc standards pass

Regression tests:

- P31-P35 governance loop tests pass
- P20-P35 full chain passes

## 9. Acceptance Criteria

P35 is complete when:

- the runtime can produce a boss governance brief from a local config
- the CLI can invoke the runtime
- P32-B remains dry-run only
- no trading, production adoption, model promotion, or training behavior is added
- doc standards pass
- P31-P35 and P20-P35 regression chains pass
- implementation commits are split by phase:
  - P35-A runtime
  - P35-B CLI
  - P35-C docs
  - P35-D regression, if needed

## 10. Future Phases

P36 should consider controlled evidence generation execution. That phase must
have its own spec because it changes P32-B from dry-run validation into carefully
bounded work submission.

P37 should consider a governance viewer or scheduled local run only after P35
proves the one-command local workflow is stable.
