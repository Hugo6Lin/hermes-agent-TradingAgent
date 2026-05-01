# Hermes P43 Read-Only Co-Pilot Console Index Spec

Date: 2026-04-30
Status: Approved for implementation planning
Scope: Static read-only console index over P36-P42 artifacts, append-only console artifacts, local CLI, and documentation

## 1. Purpose

P43 gives Hermes a single local entry point for reading the co-pilot evidence stack.

P36-P42 now produce daily artifacts for outcomes, market regime, fundamentals, candidates, memory, decision guardrails, and boss daily research priorities. P43 does not create new analysis. It scans existing `output/governance/YYYY-MM-DD/` folders and writes a static console index so the boss or reviewer can open one HTML/Markdown page and navigate the current system state.

P43 answers:

```text
What evidence exists for each day, which artifacts are missing, and where is the latest boss co-pilot brief?
```

## 2. Product Intent

The console index should make the system easier to use without making it more autonomous.

The boss should see:

- latest available P42 brief
- daily artifact coverage from P36-P42
- links to JSON/Markdown files
- missing artifact warnings
- stale or partial day warnings
- latest status extracted from known JSON artifacts
- no trading instructions

This is a static index, not a live dashboard.

## 3. Non-Goals

P43 must not:

- auto-trade
- send broker orders
- approve production adoption
- mutate production calibration config
- train models
- schedule jobs
- send notifications
- start a server
- add a dynamic viewer
- call `HermesResearchApp.run()`
- call `run_research`
- call `final_judge`
- create `CanonicalSignal`
- create `CanonicalReport`
- mutate `JudgeInputPacket`
- invoke P36-P42 runtime commands
- mutate P36-P42 evidence artifacts
- rewrite existing daily artifact files
- use LLMs to summarize or rank evidence

P43 is static read-only navigation evidence only.

## 4. Phase Map

### P43-A: Artifact Scanner + Console Model

Create `copilot_console_index.py` to scan governance artifact directories, classify known files, read small JSON status fields, compute coverage, and build a deterministic console-index object.

### P43-B: Static Writers + Optional Persistence

Write `p43_copilot_console_index.json`, `p43_copilot_console_index.md`, and `p43_copilot_console_index.html`. Optionally persist index metadata in SQLite for audit.

### P43-C: CLI

Add `copilot-console-index-run` to `batch_cli.py`. The command reads existing artifact directories and writes the static index.

### P43-D: Docs + Regression

Update docs and run P36-P43, governance-adjacent, CLI, and doc-standard regressions.

## 5. Input Contract

CLI:

```bash
python -m agent.research_v1.batch_cli copilot-console-index-run \
  --as-of-date 2026-04-30 \
  --lookback-days 14 \
  --governance-root output/governance \
  --output-root output/governance
```

Arguments:

```text
--as-of-date        required YYYY-MM-DD
--lookback-days     optional positive integer, default 14
--governance-root   optional, default output/governance, relative to --app-root
--output-root       optional, default output/governance, relative to --app-root
```

Runtime:

```python
run_copilot_console_index(
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    lookback_days: int = 14,
    db: ResearchDatabase | None = None,
) -> dict
```

Invalid date, non-positive lookback, or unreadable governance root returns `blocked_invalid_input`.

## 6. Known Artifacts

P43 must recognize these artifact files:

```text
p36_recommendation_outcomes.json
p37_market_regime_snapshot.json
p38_fundamental_quality.json
p39_candidate_pool.json
p40_research_memory_pack.json
p41_decision_journal.json
p42_boss_copilot_daily_brief.json
```

Markdown companions:

```text
p36_recommendation_outcomes.md
p37_market_regime_snapshot.md
p38_fundamental_quality.md
p39_candidate_pool.md
p40_research_memory_pack.md
p41_decision_journal.md
p42_boss_copilot_daily_brief.md
```

P43 must not require every day to contain every file.

## 7. Console Status

Statuses:

```text
console_ready
console_limited_context
console_no_artifacts
blocked_invalid_input
```

Rules:

- `blocked_invalid_input` for invalid input.
- `console_no_artifacts` when no date directory with known artifacts exists in the lookback window.
- `console_limited_context` when artifacts exist but the latest date lacks P42 or has missing required companion files.
- `console_ready` when artifacts exist and the latest date includes P42 JSON and Markdown.

## 8. Day Entry

Each scanned day entry must include:

```text
date
day_dir
coverage_status
present_artifacts
missing_artifacts
json_links
markdown_links
primary_brief_ref
status_extracts
warnings
```

Coverage statuses:

```text
complete
partial
empty
invalid
```

`primary_brief_ref` points to P42 when present, else P34 boss governance brief if present, else empty.

## 9. Status Extraction

P43 may parse JSON files, but only to extract small metadata fields:

```text
schema_version
status
overall_status
as_of_date
run_date
summary
source_hash
```

If JSON is invalid, mark that artifact as `invalid_json:<filename>` and continue.

P43 must not interpret ticker recommendations, prices, or trade plans.

## 10. Source Hash

`source_hash` must be deterministic SHA-256 over canonical JSON containing:

- `schema_version`
- `as_of_date`
- `lookback_days`
- selected date entries
- artifact filenames
- artifact file size
- artifact modification timestamp
- extracted upstream source hashes where available

Changing any scanned artifact content or selected date window must change the hash.

## 11. Persistence

Add `copilot_console_indexes`:

```text
index_id
schema_version
as_of_date
created_at
status
lookback_days
day_count
latest_day
source_hash
index_json
```

Natural key:

```text
(as_of_date, lookback_days, source_hash)
```

Same source hash is idempotent. Revised artifacts append a distinguishable index row.

## 12. Artifacts

Write under:

```text
output/governance/YYYY-MM-DD/
```

Files:

```text
p43_copilot_console_index.json
p43_copilot_console_index.md
p43_copilot_console_index.html
```

The HTML file must be static and self-contained:

- no remote JavaScript
- no remote CSS
- no network calls
- no forms that submit
- no broker/order language
- relative links to local artifacts only

## 13. Markdown and HTML Sections

Required sections:

1. Console metadata
2. Latest boss co-pilot brief
3. Daily coverage table
4. Missing artifacts
5. Invalid JSON warnings
6. Artifact links
7. Disclaimer

Forbidden rendered terms:

```text
buy this now
sell this now
follow this trade
guaranteed edge
production approved
model promoted
trade now
order ticket
place order
execute trade
```

Required disclaimer:

```text
P43 is a static read-only evidence index. It does not recommend trades, place orders, schedule jobs, send notifications, or mutate research decisions.
```

## 14. CLI Output

Successful CLI output:

```text
Co-pilot console index status: <status>
Output dir: <path>
Day count: <n>
Latest day: <date>
Missing artifact count: <n>
Invalid artifact count: <n>
```

Exit codes:

- `0` for `console_ready`, `console_limited_context`, or `console_no_artifacts`.
- `2` for `blocked_invalid_input`.

## 15. Hard Boundary Test

Add a hard-boundary test asserting P43 does not expose or call:

```text
broker
order
train_model
scheduler
notification
HermesResearchApp
run_research
final_judge
JudgeInputPacket
CanonicalSignal
CanonicalReport
run_governance_runtime
run_recommendation_outcome_tracking
run_market_regime_context
run_fundamental_quality
run_candidate_pool
run_research_memory_pack
run_decision_journal_guardrails
run_boss_copilot_daily_brief
_extract_thesis_inputs
```

## 16. Required Tests

Focused P43 tests must cover:

1. Empty governance root returns `console_no_artifacts`.
2. Latest day with P42 JSON/MD returns `console_ready`.
3. Latest day missing P42 returns `console_limited_context`.
4. Day coverage classifies present and missing artifacts.
5. Invalid JSON is recorded and does not crash scanning.
6. Source hash changes when a scanned artifact changes.
7. Source hash changes when lookback window changes.
8. Persistence is idempotent for same natural key.
9. Revised source hash appends a new index row.
10. Writers emit JSON, Markdown, and HTML.
11. HTML uses only relative artifact links.
12. Markdown/HTML reject forbidden trading language.
13. CLI success writes under app root for relative output root.
14. CLI rejects invalid date.
15. CLI rejects non-positive lookback.
16. Hard boundaries are explicit.

## 17. Regression Requirements

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_copilot_console_index.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "copilot_console or copilot-console"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_research_memory_pack.py tests/agent/research_v1/test_decision_journal_guardrails.py tests/agent/research_v1/test_boss_copilot_daily_brief.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Run the full P20-P43 chain after implementation. Host-specific PDF/Futu gaps may be reported separately if unrelated.

## 18. Commit Split

Expected implementation commits:

1. `feat: add copilot console index scanner`
2. `feat: persist copilot console indexes`
3. `feat: add copilot console index cli`
4. `docs: document p43 copilot console index`

## 19. Acceptance Criteria

P43 is complete when:

- It scans existing P36-P42 artifacts without mutating them.
- It writes static JSON/Markdown/HTML console index artifacts.
- It handles missing and invalid artifacts explicitly.
- It validates CLI inputs.
- It persists append-only index metadata.
- It blocks forbidden trading language in rendered output.
- It never invokes P36-P42 runtimes or research/trading authority.
- P36-P42 regressions pass.
- Governance-adjacent and doc standards pass.
