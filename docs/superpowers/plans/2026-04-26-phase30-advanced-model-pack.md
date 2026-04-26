# Phase 30 Advanced Model Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add evidence-gated admission and sandbox manifests for advanced model candidates.

**Architecture:** Create `agent/research_v1/phase30_advanced_model_pack.py` and tests. This phase gates advanced models; it does not promote them.

**Tech Stack:** Python 3.11 standard library, dataclasses, pytest.

---

## Tasks

### Task 1: Contracts
- [ ] Implement admission request, sandbox manifest, comparison report, governance decision contracts.

### Task 2: Family-Specific Gates
- [ ] XGBoost requires Phase 25/26 evidence.
- [ ] GNN requires relation data sufficiency.
- [ ] Sequence model requires historical sequence sufficiency.
- [ ] LLM event model requires taxonomy/label consistency.
- [ ] PPO requires execution-only objective and no stock-selection role.

### Task 3: Sandbox Manifest
- [ ] Build shadow-only sandbox manifest for admitted candidates.
- [ ] Block production write paths.

### Task 4: Tests and Regression
- [ ] Add acceptance tests for each family gate.
- [ ] Run Phase 30 tests and regression bundle.
