# Phase 27 Factor Expansion Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add shadow-only macro, event-surprise, and sector-relation candidate factor builders with point-in-time and source-audit gates.

**Architecture:** Create one focused module, `agent/research_v1/phase27_factor_expansion.py`, and one acceptance test file, `tests/agent/research_v1/test_phase27_factor_expansion.py`. The module builds diagnostics-ready candidate observations only; it does not write canonical factor snapshots or production configs.

**Tech Stack:** Python 3.11 standard library, dataclasses, pytest.

---

## Files

- Create: `agent/research_v1/phase27_factor_expansion.py`
- Create: `tests/agent/research_v1/test_phase27_factor_expansion.py`

## Tasks

### Task 1: Contracts and Request Validation

- [ ] Add `FactorExpansionRequest`, `CandidateFactorObservation`, `CandidateFactorSet`, and `FactorExpansionReport`.
- [ ] Validate namespace starts with `shadow_candidate_factor.`.
- [ ] Add `to_dict()` methods.
- [ ] Tests: unsafe namespace rejected, JSON serialization works.

### Task 2: Macro Candidate Builder

- [ ] Implement macro PIT check: `source_as_of_date <= trading_day` and release timestamp present.
- [ ] Emit `macro_regime_score` and `macro_momentum_score` using deterministic simple transforms.
- [ ] Count missing release/source/PIT violations.
- [ ] Tests: valid macro row included; future-dated macro row blocked.

### Task 3: Event Surprise Builder

- [ ] Require `event_timestamp`, `taxonomy_version`, label consistency, and source refs.
- [ ] Emit event surprise/sentiment/novelty scores.
- [ ] Tests: missing taxonomy/source blocks; valid event emits diagnostics row.

### Task 4: Sector Relation Baseline

- [ ] Require ticker, sector, peer group, trading day, and source date.
- [ ] Emit sector relative strength, peer relation, and dispersion scores.
- [ ] Tests: missing peer group blocks; valid relation row emitted.

### Task 5: Diagnostics-Ready Output

- [ ] Implement `build_factor_expansion_candidates(...)`.
- [ ] Ensure each emitted row includes candidate family/name, trading_day, ticker when applicable, score_value, PIT/source flags, schema_version.
- [ ] Tests: diagnostics rows are shadow-only and never canonical.

### Task 6: Regression and Handoff

- [ ] Run `python3.11 -m pytest tests/agent/research_v1/test_phase27_factor_expansion.py -q`.
- [ ] Run current P20-Phase27 regression bundle.
- [ ] Handoff with checklist from spec.
