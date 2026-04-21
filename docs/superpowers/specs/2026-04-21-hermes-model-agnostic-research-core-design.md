# Hermes Model-Agnostic Research Core Design

## Goal

Turn Hermes from a model-coupled trading research implementation into a **model-agnostic research operating core**.

The new Hermes core must let different models participate in the same research system while still producing:

- one canonical task format
- one canonical evidence format
- one canonical final signal format
- one canonical final report format
- one stable downstream product surface for viewer, PDF, monitoring, and trade-planning

This design explicitly separates:

- **Orchestrator**: workflow controller and process auditor
- **Subagents**: scoped research workers
- **Final Judge**: final synthesis and final decision maker

The system must support future extension to:

- `orchestrator + final_judge + reviewer`

but the first implementation target is:

- `orchestrator + final_judge`

---

## Why This Change

Current Hermes is valuable, but its architecture is still closer to:

- a built-in research pipeline
- with fixed analyst roles
- feeding a grading layer
- feeding signal persistence

That is useful for one implementation, but not sufficient as a general-purpose model substrate.

The biggest current limitations are:

1. **Workflow and judgment are too tightly coupled**
   A single system path can plan work, interpret work, and produce the final output. This increases the chance of self-reinforcing model bias.

2. **Intermediate outputs are not yet the primary system contract**
   Hermes already has structured signal outputs, but the intermediate research products are still too implementation-specific and text-oriented.

3. **The product layer is stronger than the orchestration layer**
   Viewer, PDF, persistence, and signal concepts are already emerging as stable outputs, but the upstream architecture is not yet standardized enough to support multiple models cleanly.

4. **The current core is still “pipeline-first” rather than “contract-first”**
   We need Hermes to become a system that models plug into, not a system that assumes one fixed reasoning shape.

---

## Non-Goals

This design does **not** aim to:

- optimize for one specific model family
- standardize prompt writing for every vendor
- build a DAG orchestration platform in this phase
- implement a multi-user platform
- build autonomous order execution
- solve model capability differences

This design **does** aim to:

- standardize the system contracts
- make outputs stable regardless of model choice
- reduce single-role hallucination risk
- make future reviewer-based governance possible without a major redesign

---

## Architecture Decision

### Chosen Structure

Hermes will adopt a **three-role logical architecture**, with only the first two roles required in phase one:

1. **Orchestrator**
   - owns workflow control
   - decomposes tasks
   - checks required steps
   - validates completeness
   - assembles evidence packets
   - does **not** produce the final investment judgment

2. **Subagents**
   - each owns one scoped research function
   - produces local evidence only
   - does **not** produce the final cross-domain decision

3. **Final Judge**
   - consumes standardized evidence
   - resolves conflicts
   - produces the canonical signal
   - produces the canonical report

### Future Extension

The architecture must reserve a clean interface for:

4. **Reviewer**
   - audits final judge conclusions
   - detects unsupported claims
   - detects missing evidence coverage
   - challenges weak synthesis

The reviewer is not required in the first implementation, but the design must leave a clean insertion point.

---

## Core Principle

**The same role must not simultaneously own both workflow control and final judgment.**

This is the central architectural principle for hallucination risk reduction.

Why:

- An orchestrator that also decides the final answer can selectively privilege its own workflow assumptions.
- A final judge that also controls upstream decomposition can bias the evidence collection path toward its preferred conclusion.
- Separating process control and decision synthesis reduces “same-model, same-role, same-bias” amplification.

Therefore:

- orchestrator is a **process authority**
- final judge is a **decision authority**
- subagents are **domain evidence authorities**

---

## Canonical Object Model

Hermes must reorganize around stable objects instead of around one hard-coded sequence of classes.

### 1. ResearchTask

Purpose:

- canonical system entry object
- normalized from boss request or API request

Required fields:

- `task_id`
- `request_text`
- `task_type`
- `tickers`
- `markets`
- `research_mode`
- `time_horizon`
- `output_mode`
- `constraints`
- `created_at`
- `status`

Examples of `task_type`:

- `single_ticker_research`
- `multi_ticker_compare`
- `option_idea`
- `portfolio_review`
- `position_management`

Examples of `output_mode`:

- `signal_only`
- `report_only`
- `signal_and_report`
- `signal_report_pdf_viewer`

### 2. SubagentTask

Purpose:

- one orchestrator-issued work unit
- scoped to one role and one objective

Required fields:

- `subtask_id`
- `task_id`
- `agent_role`
- `ticker`
- `objective`
- `required_context`
- `expected_schema`
- `priority`
- `deadline_hint`
- `status`

Examples of `agent_role`:

- `fundamentals`
- `technical`
- `news`
- `sentiment`
- `industry`
- `options`
- `risk`
- `valuation`

### 3. EvidenceItem

Purpose:

- canonical subagent output atom
- primary system truth unit

Required fields:

- `evidence_id`
- `task_id`
- `subtask_id`
- `ticker`
- `agent_role`
- `claim_type`
- `claim`
- `value`
- `confidence`
- `direction`
- `importance`
- `source_refs`
- `raw_payload`
- `created_at`

Notes:

- Subagents may still return freeform text, but Hermes must immediately normalize those outputs into `EvidenceItem[]`.
- The evidence layer is the system’s main internal language.

### 4. EvidenceBundle

Purpose:

- normalized collection of evidence prepared by orchestrator for final judging

Required fields:

- `task_id`
- `ticker`
- `evidence_items`
- `coverage_summary`
- `missing_steps`
- `conflict_flags`
- `context_snapshot`

### 5. JudgeInputPacket

Purpose:

- exact bounded input contract for final judge

Required fields:

- `task_id`
- `ticker`
- `task_summary`
- `evidence_bundle`
- `required_outputs`
- `conflict_flags`
- `missing_steps`
- `orchestrator_notes`

Important:

- Final judge should not read arbitrary upstream runtime state.
- Final judge should consume only the bounded packet prepared by orchestrator.

### 6. CanonicalSignal

Purpose:

- unified final signal contract for all downstream product surfaces

Required fields:

- `ticker`
- `rating`
- `confidence`
- `priority_score`
- `entry_price`
- `stop_loss`
- `take_profit`
- `holding_horizon`
- `signal_valid_until`
- `risk_flags`
- `decision_reason`

### 7. CanonicalReport

Purpose:

- unified final boss-facing report contract

Required fields:

- `title`
- `executive_summary`
- `bottom_line`
- `why_now`
- `bull_case`
- `bear_case`
- `trade_plan`
- `risk_watch`
- `key_evidence`
- `appendix`

---

## Execution Flow

Hermes should be restructured into the following execution flow.

### Step 1: Request Ingestion

Input:

- natural language request
- structured API request
- CLI command

Output:

- `ResearchTask`

### Step 2: Orchestrator Planning

Input:

- `ResearchTask`

Responsibility:

- determine required subagents
- create `SubagentTask[]`
- define required steps
- define expected schemas
- define which subtasks can run in parallel

Output:

- `SubagentTask[]`

### Step 3: Subagent Execution

Input:

- `SubagentTask`

Responsibility:

- produce local evidence only
- do not issue final portfolio-wide or ticker-wide final verdicts

Output:

- `EvidenceItem[]`

### Step 4: Evidence Normalization

Responsibility:

- validate schemas
- normalize fields
- deduplicate claims
- preserve raw payloads
- attach source metadata

Output:

- normalized evidence store rows

### Step 5: Orchestrator Audit

Responsibility:

- verify required subtasks completed
- detect missing evidence classes
- detect structural conflicts
- decide whether to request additional subtasks
- assemble `JudgeInputPacket`

Output:

- `JudgeInputPacket`

### Step 6: Final Judge Decision

Responsibility:

- consume judge packet
- synthesize across evidence classes
- produce final trade view
- produce canonical output objects

Output:

- `CanonicalSignal`
- `CanonicalReport`

### Step 7: Product Rendering

Downstream surfaces must consume canonical output objects only:

- viewer
- PDF
- monitoring
- signal persistence
- trade planning

### Step 8: Persistence and History

Persist:

- task
- subtasks
- evidence
- judge input packet
- canonical signal
- canonical report
- revisions and versions

---

## Role Boundaries

### Orchestrator Responsibilities

Orchestrator must:

- accept normalized tasks
- decompose work into subtasks
- enforce required workflow steps
- validate completeness
- assemble evidence packets
- request retries or supplemental subtasks
- prepare final-judge inputs

Orchestrator must not:

- produce final rating
- produce final report conclusion
- collapse all evidence into a final investment judgment

### Subagent Responsibilities

Subagents must:

- execute a scoped research function
- produce bounded evidence
- report uncertainty explicitly
- include source references when available

Subagents must not:

- bypass the evidence contract
- directly populate canonical final outputs
- override other subagents
- act as final judge

### Final Judge Responsibilities

Final judge must:

- read only the bounded judge packet
- synthesize across evidence classes
- resolve cross-domain conflicts
- produce canonical final outputs

Final judge must not:

- directly orchestrate workflow
- decide which upstream steps to skip
- own subtask execution policy

### Future Reviewer Responsibilities

Reviewer will eventually:

- audit final outputs
- challenge unsupported conclusions
- check whether all required evidence was considered
- emit review findings before final publication

The first implementation must not require reviewer, but must leave a clean insertion point after final judge and before publication if desired.

---

## Product Surface Rules

### Viewer

Viewer must read canonical signal/report objects only.

Viewer should not reconstruct final meaning directly from raw subagent outputs.

### PDF

PDF export must render canonical report objects only.

### Trade Planning

Trade planning must depend on canonical signal objects only.

### Monitoring

Monitoring must use canonical signal fields, positions, and risk flags, not model-specific ad hoc outputs.

---

## Mapping from Current Hermes to New Architecture

### Keep as first-wave built-in subagents

- `agent/research_v1/analysts/fundamentals.py`
- `agent/research_v1/analysts/technical.py`
- `agent/research_v1/analysts/news.py`
- `agent/research_v1/analysts/sentiment.py`
- `agent/research_v1/analysts/industry.py`

These should become built-in subagent implementations.

### Keep as product/output infrastructure

- `agent/research_v1/trade_plan.py`
- `agent/research_v1/paper_trade.py`
- `agent/research_v1/monitor.py`
- `agent/research_v1/viewer.py`
- `agent/research_v1/report_pdf.py`

These should be refactored to read canonical outputs.

### Keep and elevate as infrastructure

- `agent/research_v1/data/database.py`
- `agent/research_v1/data/providers.py`
- `agent/research_v1/data/quality.py`
- `agent/research_v1/app.py`
- `agent/research_v1/paths.py`

### Reposition

- `agent/research_v1/grading.py`
  - should evolve into or feed final judge logic
- `agent/research_v1/reviewer.py`
  - should become the seed of future reviewer role
- `agent/research_v1/researchers/*`
  - should become optional subagent strategies, not architecture center
- `agent/research_v1/signal_pipeline.py`
  - should become canonical-output persistence infrastructure

### New Modules Required

- `agent/research_v1/contracts.py`
- `agent/research_v1/task_router.py`
- `agent/research_v1/orchestrator.py`
- `agent/research_v1/evidence_store.py`
- `agent/research_v1/final_judge.py`
- `agent/research_v1/subagent_registry.py`

---

## Recommended Delivery Sequence

### Phase 1: Contracts First

Goal:

- define canonical system language without changing all implementations at once

Deliverables:

- contracts module
- object schemas
- storage mapping definitions

### Phase 2: Insert Orchestrator and Final Judge

Goal:

- establish the process/decion split

Deliverables:

- task router
- orchestrator
- final judge
- initial subagent task flow using existing analysts

### Phase 3: Evidence Layer

Goal:

- make evidence the primary internal language

Deliverables:

- evidence store
- evidence normalization
- evidence bundle assembly
- judge packet generation

### Phase 4: Product Surface Migration

Goal:

- make downstream layers canonical-output only

Deliverables:

- viewer migration
- PDF migration
- trade-plan migration
- monitor migration

### Phase 5: Reviewer Interface Reservation

Goal:

- leave an explicit insertion point for reviewer-based governance

Deliverables:

- reviewer input contract
- review result contract
- optional publication gate hook

---

## Success Criteria

The design is successful when:

1. Different models can be used for subagents without changing viewer/PDF/trade outputs.
2. Final reports and signals remain structurally identical across model choices.
3. Orchestrator does not produce final judgment.
4. Final judge consumes bounded evidence packets rather than raw implementation state.
5. Product outputs depend on canonical outputs, not on model-specific text blobs.
6. Hermes can later insert reviewer as a separate governance role without architectural breakage.

---

## Risks and Mitigations

### Risk: Over-abstraction before product value

Mitigation:

- preserve current product surfaces
- phase the migration
- do not replace all existing analysts at once

### Risk: Evidence schema becomes too heavy

Mitigation:

- keep evidence atomic
- avoid premature taxonomy expansion
- start with the minimum fields listed here

### Risk: Final judge becomes a hidden orchestrator

Mitigation:

- enforce judge input packet boundary
- keep workflow control out of final judge

### Risk: Reviewer path gets blocked later

Mitigation:

- reserve packet-level and output-level interfaces now
- do not fuse final publication directly into final judge

---

## Final Design Decision

Hermes should evolve into a **contract-first, evidence-driven, model-agnostic research core** with:

- orchestrator controlling process
- subagents producing scoped evidence
- final judge producing final outputs
- future reviewer interface reserved but not required in the first delivery

This design preserves Hermes’ strongest current value:

- structured signals
- boss-facing reports
- viewer/PDF outputs
- monitoring/trade-plan integration

while making the research core reusable across model providers and future orchestration strategies.
