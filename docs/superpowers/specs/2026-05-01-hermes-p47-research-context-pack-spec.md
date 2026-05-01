# Hermes P47 Research Context Pack Spec

Date: 2026-05-01
Scope: Read-only research context packs from P36-P46 evidence, append-only persistence, local CLI, and documentation
Branch: `codex/quant-governance-p20-p30`

## 1. Purpose

P36-P46 gave Hermes outcome tracking, market regime, fundamentals quality, candidate discovery, memory, decision guardrails, daily co-pilot briefs, static console indexes, evidence health, Futu readiness, and dry-run refresh planning.

P47 answers the next product question:

```text
Before the boss or a future research flow studies a ticker, what audited context already exists, what is missing, and what should not be trusted yet?
```

P47 creates deterministic research context packs. A context pack is a read-only bundle of prior evidence for one or more tickers plus system-level evidence health. It is safe for a human reviewer or a future prompt-building phase to inspect, but P47 does not inject it into `JudgeInputPacket` and does not change any recommendation.

## 2. Product Intent

The boss/reviewer should see:

- current market regime context from P37;
- ticker business-quality context from P38;
- candidate-discovery context from P39;
- prior recommendation outcome context from P36;
- research-memory context from P40;
- behavioral guardrail context from P41;
- daily priority context from P42;
- artifact-navigation context from P43;
- evidence-health context from P44;
- market-data-provider readiness from P45;
- dry-run refresh-plan context from P46;
- exact source references and missing-context reasons.

The output should read like a pre-research dossier, not like an instruction to buy, sell, or execute anything.

## 3. Non-Goals And Hard Boundaries

P47 must not:

- auto-trade;
- submit broker orders;
- approve production adoption;
- mutate production configuration;
- train models;
- schedule jobs;
- send notifications;
- start a dynamic viewer/server;
- call Futu or any market-data provider;
- call P36-P46 runtime functions;
- mutate P36-P46 evidence;
- call `HermesResearchApp.run()`;
- call `final_judge`;
- create `CanonicalSignal` or `CanonicalReport`;
- mutate or instantiate `JudgeInputPacket`;
- inject context into analyst prompts or judge prompts in v1;
- use LLMs to summarize or rank evidence.

P47 may read persisted P36-P46 tables and P36-P46 JSON artifacts. P47 may write only its own append-only table and its own artifacts under `output/governance/YYYY-MM-DD/`.

## 4. Phase Map

### P47-A: Context Pack Builder

Create `research_context_pack.py` with deterministic pack assembly, ticker/system context extraction, status classification, source hashing, forbidden-language checks, and JSON/Markdown writers.

### P47-B: Persistence Layer

Extend `ResearchDatabase` with append-only `research_context_packs` persistence and latest-as-of helper reads for the P36-P46 evidence needed by P47.

### P47-C: CLI

Add `research-context-pack-run` to `batch_cli.py`.

### P47-D: Docs + Regression

Update root and research README docs, then run focused P47, P36-P46 regression, governance-adjacent, CLI, and doc-standard tests.

## 5. Input Contract

CLI:

```bash
python -m agent.research_v1.batch_cli research-context-pack-run \
  --as-of-date 2026-05-01 \
  --tickers AAPL,MSFT,NVDA \
  --lookback-days 180 \
  --max-items-per-ticker 8 \
  --governance-root output/governance \
  --output-root output/governance
```

Arguments:

```text
--as-of-date             required YYYY-MM-DD
--tickers                required comma-separated symbols
--lookback-days          optional positive integer, default 180
--max-items-per-ticker   optional positive integer, default 8
--governance-root        optional, default output/governance, relative to --app-root
--output-root            optional, default output/governance, relative to --app-root
```

Runtime:

```python
run_research_context_pack(
    db: ResearchDatabase,
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    tickers: list[str],
    lookback_days: int = 180,
    max_items_per_ticker: int = 8,
) -> dict
```

Invalid date, empty ticker list, non-positive lookback, non-positive max-items, or non-directory governance root returns `blocked_invalid_input`.

Ticker normalization:

```text
strip whitespace
uppercase
deduplicate while preserving first-seen order
reject symbols outside [A-Z0-9._-]{1,20}
```

## 6. Evidence Inputs

P47 should prefer persisted rows at or before `as_of_date`. If a table is absent or empty, P47 may use JSON artifacts from `governance_root` at or before `as_of_date`.

P47 may read:

```text
canonical_recommendation_outcomes
market_regime_snapshots
fundamental_quality_reports
candidate_pool_runs and candidate_pool_items
research_memory_packs
decision_journal_entries
boss_copilot_daily_briefs
copilot_console_indexes
evidence_freshness_drift_reports
market_data_readiness_reports
evidence_refresh_plans
output/governance/YYYY-MM-DD/*.json
```

P47 must not call any runtime to create missing upstream evidence.

## 7. Output Files

Successful and limited runs write:

```text
output/governance/YYYY-MM-DD/p47_research_context_pack.json
output/governance/YYYY-MM-DD/p47_research_context_pack.md
```

Invalid input returns a structured result and writes no artifacts.

## 8. Top-Level Pack Schema

```text
schema_version
pack_id
as_of_date
created_at
status
tickers
lookback_days
max_items_per_ticker
system_context
ticker_contexts
source_refs
missing_context
warnings
source_hash
disclaimer
```

Allowed top-level `status`:

```text
context_pack_ready
context_pack_limited
context_pack_missing
blocked_invalid_input
```

Status rules:

- `context_pack_ready`: at least one ticker has P38 quality or P40 memory context, and system context has at least one of P44/P45/P46.
- `context_pack_limited`: some usable context exists but one or more requested tickers have missing core context or system context is incomplete.
- `context_pack_missing`: no usable ticker context and no usable system context were found.
- `blocked_invalid_input`: input contract failed before evidence lookup.

## 9. Ticker Context Schema

Each item in `ticker_contexts`:

```text
ticker
context_status
market_regime
fundamental_quality
candidate_context
outcome_context
memory_context
decision_guardrails
refresh_context
evidence_health
source_refs
missing_context
warnings
prompt_context
```

Allowed `context_status`:

```text
context_ready
context_limited
context_missing
```

`prompt_context` is a deterministic plain-data object for future use. It must not be wired into any research prompt in P47.

## 10. System Context Schema

```text
market_regime_status
provider_status
evidence_health_status
refresh_plan_status
latest_boss_brief_status
latest_console_index_status
blocked_refresh_count
refresh_candidate_count
source_refs
warnings
```

P47 should surface provider degradation from P45 and evidence degradation from P44/P46 as warnings, never as commands.

## 11. Source References

Every non-empty context section must include source references:

```text
phase_id
artifact_type
source_id
as_of_date
created_at
source_hash
path
```

If a context section is populated from a JSON artifact, `path` is required. If it is populated from a DB row, `source_id` and `source_hash` are required when available.

## 12. Source Hash And Idempotence

`source_hash` is SHA-256 over canonical JSON with sorted keys. The seed must include:

- schema version;
- normalized tickers;
- as-of date;
- lookback days;
- max-items-per-ticker;
- system context values;
- ticker context values;
- all source references;
- missing-context reasons;
- warnings.

Append-only idempotence key:

```text
(as_of_date, tickers_key, source_hash)
```

Same inputs and same evidence produce a no-op rerun. Revised upstream evidence produces a new row.

## 13. Markdown Contract

Markdown must include:

```text
# P47 Research Context Pack
Status
System Context
Ticker Contexts
Missing Context
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

## 14. Persistence

Add table:

```sql
CREATE TABLE IF NOT EXISTS research_context_packs (
    pack_id TEXT PRIMARY KEY,
    as_of_date TEXT NOT NULL,
    tickers_key TEXT NOT NULL,
    status TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    source_refs_json TEXT NOT NULL,
    missing_context_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(as_of_date, tickers_key, source_hash)
);
```

`tickers_key` is the pipe-joined normalized ticker list in request order.

## 15. Acceptance Criteria

P47 is accepted when:

- focused P47 tests pass;
- CLI tests pass;
- P36-P46 regression tests pass;
- governance-adjacent tests pass;
- doc standards pass;
- context packs are deterministic and append-only;
- invalid input returns `blocked_invalid_input`;
- P47 reads P36-P46 evidence only;
- P47 writes only P47 artifacts/table rows;
- P47 does not call market-data providers, research runtime, judge, model training, broker, scheduler, or notification code.

## 16. Expected Commit Split

1. `feat: add research context pack builder`
2. `feat: persist research context packs`
3. `feat: add research context pack cli`
4. `docs: document p47 research context pack`
