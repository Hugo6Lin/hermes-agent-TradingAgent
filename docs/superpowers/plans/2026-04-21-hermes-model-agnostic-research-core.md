# Hermes Model-Agnostic Research Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Hermes into a contract-first research core where orchestrator controls workflow, subagents produce evidence, and final judge produces canonical final outputs.

**Architecture:** Introduce stable contracts and new execution roles without breaking the existing boss-facing product surfaces. Migrate in phases so current research, viewer, PDF, and persistence code continues to work while the new core is inserted beside existing modules and then gradually becomes the default path.

**Tech Stack:** Python 3.11, SQLite, existing Hermes research modules, existing viewer/PDF stack, pytest

---

## Scope

This plan covers only the first implementation of:

- `orchestrator + final_judge`

with explicit interface reservation for future:

- `orchestrator + final_judge + reviewer`

This plan does not cover:

- autonomous trading
- multi-user access control
- complete prompt engineering standardization for all model vendors
- full reviewer implementation

---

## File Structure

### New files

- `agent/research_v1/contracts.py`
  - canonical objects and lightweight validation helpers
- `agent/research_v1/task_router.py`
  - converts user/product requests into `ResearchTask`
- `agent/research_v1/orchestrator.py`
  - decomposes work, enforces required steps, assembles judge packets
- `agent/research_v1/evidence_store.py`
  - normalizes subagent outputs into canonical evidence items
- `agent/research_v1/final_judge.py`
  - converts judge packets into canonical signal and canonical report
- `tests/agent/research_v1/test_contracts.py`
- `tests/agent/research_v1/test_task_router.py`
- `tests/agent/research_v1/test_orchestrator.py`
- `tests/agent/research_v1/test_evidence_store.py`
- `tests/agent/research_v1/test_final_judge.py`

### Existing files to modify

- `agent/research_v1/data/database.py`
  - add storage for tasks, subtasks, evidence, judge packets, canonical outputs
- `agent/research_v1/signal_pipeline.py`
  - reposition around canonical output persistence
- `agent/research_v1/grading.py`
  - extract useful logic or adapt it under final judge path
- `agent/research_v1/reviewer.py`
  - reserve future reviewer interface, no full reviewer implementation required
- `agent/research_v1/app.py`
  - add minimal commands or code paths for routing tasks into the new core
- `agent/research_v1/viewer.py`
  - consume canonical output records rather than implementation-specific bundles
- `agent/research_v1/report_pdf.py`
  - render canonical reports
- `agent/research_v1/trade_plan.py`
  - consume canonical signal input
- `README.md`
  - document the new architecture and lifecycle

---

## Phase Gate Rules

The executing model must implement this plan **phase by phase**.

Rules:

1. Complete one phase at a time.
2. After each phase:
   - run the exact verification commands
   - summarize changed files
   - explain how the phase matches the spec
   - stop and hand off to the reviewer model
3. Do not start the next phase until reviewer approval is received.
4. If reviewer requests changes, fix only those changes before retrying the same phase.

---

## Phase 1: Contracts Layer

**Purpose:** Introduce the system’s canonical language before changing execution flow.

**Files:**
- Create: `agent/research_v1/contracts.py`
- Test: `tests/agent/research_v1/test_contracts.py`

- [ ] Define `ResearchTask`
- [ ] Define `SubagentTask`
- [ ] Define `EvidenceItem`
- [ ] Define `EvidenceBundle`
- [ ] Define `JudgeInputPacket`
- [ ] Define `CanonicalSignal`
- [ ] Define `CanonicalReport`
- [ ] Add lightweight constructors or validators so required fields are enforced
- [ ] Write tests that instantiate each object and verify required fields are preserved
- [ ] Run: `pytest tests/agent/research_v1/test_contracts.py -q`
- [ ] Stop for reviewer approval

**Reviewer acceptance criteria:**
- object names match the spec
- role boundaries are reflected in object shapes
- no final-output fields leak into subagent task objects
- no workflow-control fields leak into final report objects

---

## Phase 2: Task Routing

**Purpose:** Normalize boss requests into `ResearchTask`.

**Files:**
- Create: `agent/research_v1/task_router.py`
- Test: `tests/agent/research_v1/test_task_router.py`

- [ ] Implement parsing of simple research requests into canonical task objects
- [ ] Support at minimum:
  - single ticker research
  - multi ticker compare
  - option idea
  - portfolio review
- [ ] Ensure request text is preserved alongside normalized fields
- [ ] Write tests for representative boss requests
- [ ] Run: `pytest tests/agent/research_v1/test_task_router.py -q`
- [ ] Stop for reviewer approval

**Reviewer acceptance criteria:**
- route output uses `ResearchTask`
- task typing is deterministic
- ticker extraction is explicit
- output mode and research mode are represented cleanly

---

## Phase 3: Evidence Normalization

**Purpose:** Make evidence the primary internal truth unit.

**Files:**
- Create: `agent/research_v1/evidence_store.py`
- Test: `tests/agent/research_v1/test_evidence_store.py`

- [ ] Implement normalization helpers that transform subagent outputs into `EvidenceItem[]`
- [ ] Support both:
  - already structured payloads
  - partially freeform payloads with structured fields
- [ ] Add conflict tagging hooks
- [ ] Add missing-field and missing-step signaling hooks
- [ ] Write tests covering:
  - valid normalization
  - missing required evidence fields
  - mixed-role evidence batches
- [ ] Run: `pytest tests/agent/research_v1/test_evidence_store.py -q`
- [ ] Stop for reviewer approval

**Reviewer acceptance criteria:**
- evidence items are atomic and role-scoped
- raw payload retention exists
- normalization does not silently invent unsupported fields

---

## Phase 4: Orchestrator

**Purpose:** Separate workflow control from final judgment.

**Files:**
- Create: `agent/research_v1/orchestrator.py`
- Test: `tests/agent/research_v1/test_orchestrator.py`

- [ ] Implement orchestration that maps `ResearchTask` to `SubagentTask[]`
- [ ] Encode required subagent sets by task type
- [ ] Add workflow audit that checks:
  - required roles present
  - missing steps
  - conflict flags
  - readiness for judging
- [ ] Implement `JudgeInputPacket` assembly
- [ ] Keep orchestrator free of final rating/report generation
- [ ] Write tests for:
  - required step enforcement
  - packet assembly
  - no-final-judgment behavior
- [ ] Run: `pytest tests/agent/research_v1/test_orchestrator.py -q`
- [ ] Stop for reviewer approval

**Reviewer acceptance criteria:**
- orchestrator does not emit final rating
- orchestrator does not emit canonical report
- orchestrator clearly enforces workflow state

---

## Phase 5: Final Judge

**Purpose:** Introduce a bounded final synthesis role.

**Files:**
- Create: `agent/research_v1/final_judge.py`
- Modify: `agent/research_v1/grading.py`
- Test: `tests/agent/research_v1/test_final_judge.py`

- [ ] Implement final judge input consumption from `JudgeInputPacket`
- [ ] Produce `CanonicalSignal`
- [ ] Produce `CanonicalReport`
- [ ] Reuse or adapt useful grading logic where appropriate, but do not let grading remain the architecture center
- [ ] Ensure final judge consumes bounded packet input rather than arbitrary upstream runtime state
- [ ] Write tests for:
  - signal generation
  - report generation
  - conflict handling
  - bounded-input behavior
- [ ] Run: `pytest tests/agent/research_v1/test_final_judge.py -q`
- [ ] Stop for reviewer approval

**Reviewer acceptance criteria:**
- final judge is the only new final-decision role
- canonical outputs match spec fields
- grading logic is subordinate to final-judge role, not vice versa

---

## Phase 6: Database and Persistence

**Purpose:** Persist the new object model without breaking existing useful history.

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `agent/research_v1/signal_pipeline.py`
- Add tests in existing database test files or new dedicated tests

- [ ] Add tables or storage paths for:
  - research tasks
  - subagent tasks
  - evidence items
  - judge packets
  - canonical signals
  - canonical reports
- [ ] Add public persistence methods for the new core objects
- [ ] Reposition signal persistence around canonical outputs
- [ ] Preserve compatibility with current product data where practical
- [ ] Run targeted DB tests
- [ ] Stop for reviewer approval

**Reviewer acceptance criteria:**
- persistence model reflects the spec object model
- public APIs exist for new core objects
- signal pipeline is now canonical-output aware

---

## Phase 7: Product Surface Migration

**Purpose:** Make viewer, PDF, and trade outputs consume canonical outputs only.

**Files:**
- Modify: `agent/research_v1/viewer.py`
- Modify: `agent/research_v1/report_pdf.py`
- Modify: `agent/research_v1/trade_plan.py`
- Possibly modify related tests

- [ ] Refactor viewer to render canonical output records
- [ ] Refactor PDF export to render canonical reports
- [ ] Refactor trade plan generation to consume canonical signal input
- [ ] Add or update tests proving downstream surfaces no longer depend on implementation-specific intermediate blobs
- [ ] Run relevant tests
- [ ] Stop for reviewer approval

**Reviewer acceptance criteria:**
- product outputs are canonical-output driven
- no direct dependence on raw subagent text blobs remains in final surfaces

---

## Phase 8: Reviewer Extension Point Reservation

**Purpose:** Leave explicit interfaces for future reviewer insertion without implementing the full reviewer loop now.

**Files:**
- Modify: `agent/research_v1/reviewer.py`
- Modify: `agent/research_v1/contracts.py`
- Add or update tests as needed

- [ ] Define reviewer-facing contracts or hook points
- [ ] Ensure final publication path can later insert reviewer checks
- [ ] Do not force reviewer into the first working runtime path
- [ ] Add tests for interface presence only
- [ ] Stop for reviewer approval

**Reviewer acceptance criteria:**
- reviewer insertion point is explicit
- current runtime still supports orchestrator + final judge without reviewer required

---

## Phase 9: Entry Point and Docs

**Purpose:** Make the new core discoverable and usable.

**Files:**
- Modify: `agent/research_v1/app.py`
- Modify: `README.md`
- Add docs if needed under `docs/`

- [ ] Add minimal app entry path into the new task router/orchestrator/final judge flow
- [ ] Document architecture roles
- [ ] Document the phase-1 supported task types
- [ ] Document the future reviewer reservation
- [ ] Stop for reviewer approval

**Reviewer acceptance criteria:**
- docs match spec
- entry point reflects the new architecture
- docs do not overclaim reviewer implementation

---

## Final Verification Phase

**Files:**
- all changed files

- [ ] Run the full relevant regression set
- [ ] Report exact commands and outputs
- [ ] Summarize architecture coverage against spec sections
- [ ] Stop for final reviewer sign-off

Suggested verification set:

```bash
pytest tests/agent/research_v1/test_contracts.py \
       tests/agent/research_v1/test_task_router.py \
       tests/agent/research_v1/test_evidence_store.py \
       tests/agent/research_v1/test_orchestrator.py \
       tests/agent/research_v1/test_final_judge.py \
       tests/agent/research_v1/test_app.py -q
```

Plus any updated integration/database/viewer/PDF tests affected by the implementation.

---

## Reviewer Workflow

The executing model must hand off after every phase using this exact structure:

1. `Phase completed: <phase name>`
2. `Files changed:`
3. `Verification run:`
4. `How this matches the spec:`
5. `Open risks or uncertainties:`
6. `Waiting for reviewer approval before next phase.`

The reviewer model should evaluate:

- spec fidelity
- boundary correctness
- naming consistency
- hidden coupling
- missing tests
- accidental overreach beyond the current phase

---

## Executor Restrictions

The executing model must not:

- collapse orchestrator and final judge back into one role
- skip contracts and jump directly into implementation details
- wire viewer/PDF directly to raw subagent output in the new path
- implement reviewer as a hard requirement in the first pass
- skip phase review gates

---

## Expected End State

At the end of this plan Hermes should:

- accept normalized tasks
- decompose them through orchestrator
- collect evidence from role-scoped subagents
- assemble bounded judge packets
- produce canonical signal/report through final judge
- render product outputs from canonical records
- preserve a clean future insertion point for reviewer

