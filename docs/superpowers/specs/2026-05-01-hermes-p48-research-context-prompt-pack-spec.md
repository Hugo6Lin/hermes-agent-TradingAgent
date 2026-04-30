# Hermes P48 Research Context Prompt Pack Dry-Run Spec

Date: 2026-05-01
Scope: Role-specific prompt-context packs derived from P47, dry-run injection manifest, append-only persistence, local CLI, and documentation
Branch: `codex/quant-governance-p20-p30`

## 1. Purpose

P47 assembles audited research context from P36-P46. P48 answers the next safe integration question:

```text
If Hermes later gives P47 context to analyst roles, exactly what context would each role see, what evidence supports it, and what would remain omitted?
```

P48 creates deterministic role-specific prompt-context packs and a dry-run injection manifest. It does not inject anything into live research, does not call analysts, does not call an LLM, and does not change any recommendation.

## 2. Product Intent

The reviewer should be able to inspect:

- the latest P47 context pack used as source evidence;
- one role-specific context block per requested ticker and role;
- source references for every included context block;
- omitted sections and truncation reasons;
- dry-run `SubagentTask.required_context` keys that a future phase could add;
- a clear statement that no prompt, analyst, judge, or trade path was executed.

This makes future research-context integration reviewable before any production path changes.

## 3. Non-Goals And Hard Boundaries

P48 must not:

- auto-trade;
- submit broker orders;
- approve production adoption;
- mutate production configuration;
- train models;
- schedule jobs;
- send notifications;
- start a dynamic viewer/server;
- call Futu or any market-data provider;
- call P36-P47 runtime functions;
- mutate P36-P47 evidence;
- call `HermesResearchApp.run()`;
- call `SubagentExecutor`;
- call an LLM client;
- call `final_judge`;
- create `CanonicalSignal` or `CanonicalReport`;
- instantiate or mutate `JudgeInputPacket`;
- mutate any real `SubagentTask`;
- write to `required_context` in any live task;
- use LLMs to summarize or rank context.

P48 may read persisted P47 rows and P47 JSON artifacts. P48 may write only its own append-only table and artifacts under `output/governance/YYYY-MM-DD/`.

## 4. Phase Map

### P48-A: Prompt Pack Builder

Create `research_context_prompt_pack.py` with deterministic P47 loading, role selection, context-block assembly, truncation, source hashing, forbidden-language checks, and JSON/Markdown writers.

### P48-B: Persistence Layer

Extend `ResearchDatabase` with append-only `research_context_prompt_packs` persistence and latest-as-of helper reads for P47 packs.

### P48-C: CLI

Add `research-context-prompt-pack-run` to `batch_cli.py`.

### P48-D: Docs + Regression

Update root and research README docs, then run focused P48, P47 regression, P36-P46 regression, governance-adjacent, CLI, and doc-standard tests.

## 5. Input Contract

CLI:

```bash
python -m agent.research_v1.batch_cli research-context-prompt-pack-run \
  --as-of-date 2026-05-01 \
  --tickers AAPL,MSFT \
  --roles fundamentals,technical,risk,options \
  --max-block-chars 1200 \
  --governance-root output/governance \
  --output-root output/governance
```

Arguments:

```text
--as-of-date       required YYYY-MM-DD
--tickers          required comma-separated symbols
--roles            optional comma-separated roles, default all supported roles
--max-block-chars  optional positive integer, default 1200
--governance-root  optional, default output/governance, relative to --app-root
--output-root      optional, default output/governance, relative to --app-root
```

Runtime:

```python
run_research_context_prompt_pack(
    db: ResearchDatabase,
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    tickers: list[str],
    roles: list[str] | None = None,
    max_block_chars: int = 1200,
) -> dict
```

Invalid date, empty ticker list, unknown role, non-positive max-block size, or non-directory governance root returns `blocked_invalid_input`.

## 6. Supported Roles

P48 supports these role strings:

```text
fundamentals
technical
news
sentiment
industry
options
risk
valuation
```

Role names are normalized by trimming whitespace and lowercasing. Duplicate roles are removed while preserving first-seen order.

## 7. Evidence Inputs

P48 should prefer persisted P47 rows at or before `as_of_date`, filtered by requested tickers when possible. If no DB row is available, P48 may load:

```text
output/governance/YYYY-MM-DD/p47_research_context_pack.json
```

P48 must not call `run_research_context_pack()` to create missing P47 evidence.

If no P47 context exists, P48 returns `blocked_missing_context` and writes no artifacts.

## 8. Output Files

Successful and limited runs write:

```text
output/governance/YYYY-MM-DD/p48_research_context_prompt_pack.json
output/governance/YYYY-MM-DD/p48_research_context_prompt_pack.md
```

Invalid input and missing P47 context write no artifacts.

## 9. Top-Level Prompt Pack Schema

```text
schema_version
prompt_pack_id
as_of_date
created_at
status
tickers
roles
max_block_chars
source_context_pack_id
source_context_hash
role_contexts
dry_run_injection_manifest
source_refs
omitted_context
warnings
source_hash
disclaimer
```

Allowed top-level `status`:

```text
prompt_pack_ready
prompt_pack_limited
blocked_missing_context
blocked_invalid_input
```

Status rules:

- `prompt_pack_ready`: every requested ticker-role pair has at least one included context block.
- `prompt_pack_limited`: at least one ticker-role pair has context, but one or more pairs are missing or truncated.
- `blocked_missing_context`: no P47 source context exists at or before `as_of_date`.
- `blocked_invalid_input`: input contract failed before evidence lookup.

## 10. Role Context Schema

Each item in `role_contexts`:

```text
ticker
role
context_status
context_blocks
required_context_preview
source_refs
omitted_context
warnings
block_hash
```

Allowed `context_status`:

```text
role_context_ready
role_context_limited
role_context_missing
```

`required_context_preview` is the exact plain-data shape that a future phase could place under:

```text
SubagentTask.required_context["research_context_pack"]
```

P48 must not mutate any live `SubagentTask`.

## 11. Role Mapping

Role context should include only relevant P47 sections:

```text
fundamentals -> fundamental_quality, memory_context, outcome_context, evidence_health
technical -> market_regime, outcome_context, candidate_context, evidence_health
news -> memory_context, candidate_context, evidence_health
sentiment -> memory_context, decision_guardrails, outcome_context
industry -> market_regime, candidate_context, fundamental_quality
options -> market_regime, outcome_context, decision_guardrails, provider_status
risk -> decision_guardrails, outcome_context, evidence_health, refresh_context
valuation -> fundamental_quality, outcome_context, memory_context
```

Every role also receives:

```text
ticker
as_of_date
context_status
source_context_pack_id
not_injected: true
```

## 12. Truncation And Omission

Each role block must stay under `max_block_chars`.

If a block would exceed the limit:

- keep deterministic priority order from the role mapping;
- include as many sections as fit;
- append omitted section names to `omitted_context`;
- set `context_status` to `role_context_limited`;
- add warning `context_truncated:<ticker>:<role>`.

P48 must not use an LLM to compress content.

## 13. Dry-Run Injection Manifest

The manifest is a list of entries:

```text
ticker
role
dry_run_only
target_object
target_key
would_set_keys
context_status
block_hash
```

Required values:

```text
dry_run_only = true
target_object = "SubagentTask.required_context"
target_key = "research_context_pack"
```

The manifest is documentation of a possible future integration, not an action.

## 14. Source Hash And Idempotence

`source_hash` is SHA-256 over canonical JSON with sorted keys. The seed must include:

- schema version;
- normalized tickers;
- normalized roles;
- as-of date;
- max-block chars;
- source P47 pack id/hash;
- role contexts;
- dry-run manifest;
- source refs;
- omitted context;
- warnings.

Append-only idempotence key:

```text
(as_of_date, tickers_key, roles_key, source_hash)
```

Same inputs and same P47 evidence produce a no-op rerun. Revised P47 evidence or changed role selection produces a new row.

## 15. Markdown Contract

Markdown must include:

```text
# P48 Research Context Prompt Pack
Status
Source P47 Context
Role Contexts
Dry-Run Injection Manifest
Omitted Context
Warnings
Source References
Disclaimer
```

The renderer must reject forbidden terms:

```text
buy this now
sell this now
follow this trade
guaranteed edge
production approved
model promoted
execute trade
place order
unlock_trade
```

## 16. Persistence

Add table:

```sql
CREATE TABLE IF NOT EXISTS research_context_prompt_packs (
    prompt_pack_id TEXT PRIMARY KEY,
    as_of_date TEXT NOT NULL,
    tickers_key TEXT NOT NULL,
    roles_key TEXT NOT NULL,
    status TEXT NOT NULL,
    source_context_pack_id TEXT NOT NULL,
    source_context_hash TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    omitted_context_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(as_of_date, tickers_key, roles_key, source_hash)
);
```

## 17. Acceptance Criteria

P48 is accepted when:

- focused P48 tests pass;
- CLI tests pass;
- P47 focused regression passes;
- P36-P46 regression tests pass;
- governance-adjacent tests pass;
- doc standards pass;
- prompt packs are deterministic and append-only;
- missing P47 context returns `blocked_missing_context`;
- invalid input returns `blocked_invalid_input`;
- P48 reads P47 evidence only;
- P48 writes only P48 artifacts/table rows;
- P48 does not call providers, research runtime, subagent executor, LLMs, judge, model training, broker, scheduler, or notification code.

## 18. Expected Commit Split

1. `feat: add research context prompt pack builder`
2. `feat: persist research context prompt packs`
3. `feat: add research context prompt pack cli`
4. `docs: document p48 research context prompt pack`
