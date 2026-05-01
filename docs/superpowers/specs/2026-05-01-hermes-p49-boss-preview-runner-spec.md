# Hermes P49 Boss Preview Runner Spec

Date: 2026-05-01
Scope: One-command boss preview from tickers, live Futu readiness, valid sample evidence, boss-readable preview report, optional repo-local skill draft, local CLI, and documentation
Branch: `codex/quant-governance-p20-p30`

## 1. Purpose

The first boss-preview dry run exposed four product problems:

- the execution model did not pass `--live`, so P45 reported `provider_not_tested_live`;
- P37 failed on Futu symbol mapping for `VIX`;
- P38/P39 were fed malformed synthetic inputs, causing empty or blocked artifacts;
- the final report was an engineering artifact table, not a boss-readable preview.

P49 creates a single guided preview runner where the boss only gives tickers. Hermes chooses safe defaults, runs the appropriate read-only/append-only co-pilot phases, generates valid preview inputs when live fundamentals are absent, normalizes output paths, and writes a concise boss-facing preview report.

## 2. Product Intent

The boss should be able to say:

```text
Preview Hermes on AMZN, ALAB, NVDA, ORCL, QCOM, SOFI
```

The system should produce:

- a live Futu readiness report when OpenD is available;
- a market regime attempt that avoids known Futu symbol traps;
- valid sample P38/P39 inputs when real fundamentals/candidate features are not present;
- P40-P48 artifacts chained from the preview evidence;
- one `boss_preview.md` and `boss_preview.json` that explain results in plain language;
- a clear distinction between live data, database data, and synthetic/sample preview data;
- exact hard-boundary compliance.

## 3. Non-Goals And Hard Boundaries

P49 must not:

- auto-trade;
- submit broker orders;
- approve production adoption;
- mutate production configuration;
- train models;
- schedule jobs;
- send notifications;
- start a dynamic viewer/server;
- call `HermesResearchApp.run()`;
- call `SubagentExecutor`;
- call an LLM client;
- call `final_judge`;
- create `CanonicalSignal` or `CanonicalReport`;
- instantiate or mutate `JudgeInputPacket`;
- mutate live `SubagentTask.required_context`;
- invoke broker/order/trade/unlock APIs.

P49 may call read-only/append-only P37-P48 runtime functions. P49 may call Futu market-data provider readiness through P45 with live quote calls enabled by default. P49 may use injected fake providers in tests.

## 4. Phase Map

### P49-A: Preview Runner Model

Create `boss_preview_runner.py` with ticker normalization, output-root normalization, live/readiness orchestration, safe phase status capture, boss summary rendering, source hashing, and artifact writing.

### P49-B: Valid Preview Input Builders

Add deterministic builders for P38 fundamental-quality sample input, P39 candidate-pool sample input, and P41 decision-journal sample input. Inputs must be clearly marked as preview sample data.

### P49-C: CLI And Skill Draft

Add `boss-preview-run` to `batch_cli.py`. Create a repo-local skill draft at `docs/skills/hermes-boss-preview/SKILL.md` so future agents know that the boss only supplies tickers and the runner does the rest.

### P49-D: Docs + Regression

Update README files, run focused P49 tests, P45/P47/P48 regressions, CLI tests, and doc standards.

## 5. Input Contract

CLI:

```bash
python -m agent.research_v1.batch_cli boss-preview-run \
  --tickers AMZN,ALAB,NVDA,ORCL,QCOM,SOFI
```

Optional arguments:

```text
--as-of-date             optional YYYY-MM-DD, default today in local date
--output-root            optional, default output/governance
--governance-root        optional, default output/governance
--live / --no-live       optional, default live
--max-candidates         optional positive integer, default 8
--preview-mode           optional, default boss
```

Runtime:

```python
run_boss_preview(
    db: ResearchDatabase,
    tickers: list[str],
    as_of_date: str,
    output_root: Path,
    governance_root: Path,
    live: bool = True,
    max_candidates: int = 8,
    provider: Any | None = None,
) -> dict
```

Invalid date, empty tickers, invalid ticker format, non-positive max candidates, or non-directory governance root returns `blocked_invalid_input`.

Ticker normalization:

```text
strip whitespace
uppercase
deduplicate while preserving first-seen order
accept plain US symbols like NVDA
accept prefixed symbols like US.NVDA and HK.00700
```

For Futu readiness, plain US symbols are converted to `US.<ticker>`.

## 6. Output Path Rule

Operators pass only the root:

```text
output/governance
```

P49 writes to:

```text
output/governance/YYYY-MM-DD/
```

If the caller accidentally passes a date-suffixed output root ending in `YYYY-MM-DD`, P49 must normalize it back to its parent root and add warning:

```text
normalized_date_suffixed_output_root
```

This prevents `output/governance/YYYY-MM-DD/YYYY-MM-DD/`.

## 7. Preview Sequence

P49 runs these steps in order. Each step records `phase_id`, `status`, `data_source`, `artifact_paths`, `warnings`, `exit_semantics`, and `boss_summary`.

```text
P45 market data readiness
P37 market regime context
P38 fundamental quality
P39 candidate pool
P40 research memory pack
P41 decision journal guardrail sample
P42 boss co-pilot daily brief
P43 console index
P44 evidence freshness/drift monitor
P46 evidence refresh plan
P47 research context pack
P48 research context prompt pack dry-run
```

P36 outcome tracking is not run by default because a fresh preview often has no canonical signals. P49 must report whether P36 evidence is absent.

## 8. Futu And P37 Rules

P45:

- default `live=True`;
- call P45 with symbols derived from requested tickers;
- include `US.AAPL` as fallback option-chain symbol unless no US ticker exists;
- if Futu is unavailable, continue with sample preview steps and mark live market data unavailable.

P37:

- call `run_market_regime_context` with a safe provider adapter that translates P37 symbols to Futu-compatible symbols;
- plain P37 symbols like `SPY`, `QQQ`, `TLT`, `HYG`, `XLK` should become `US.SPY`, `US.QQQ`, etc.;
- `VIX` should use a fallback chain: `US.VIX`, then `US.VXX`, then mark volatility proxy missing instead of crashing;
- any provider exception should produce a degraded P37 step, not abort the preview.

## 9. Preview Sample Inputs

When real DB fundamentals or candidate features are absent, P49 may generate sample inputs.

Sample inputs must:

- include `_preview_sample: true`;
- include `sample_reason`;
- include `as_of_date`;
- use valid P38/P39 schemas;
- be persisted beside preview artifacts;
- be marked as sample in `boss_preview.md`;
- never be described as real fundamentals.

P38 sample input uses five quarterly rows per ticker with required fields populated.

P39 sample input uses valid feature fields:

```text
ticker
sector
currency
source_date
close
close_20d_ago
close_60d_ago
close_120d_ago
high_252d
low_252d
avg_dollar_volume_20d
realized_vol_20d
market_cap
benchmark_return_60d
catalyst_tags
```

P41 sample decision should use the top candidate when available, otherwise the first ticker, and mark itself as preview sample.

## 10. Boss Preview Report Schema

Top-level JSON:

```text
schema_version
preview_id
as_of_date
created_at
status
tickers
live_requested
live_status
top_candidates
boss_summary
phase_results
data_source_breakdown
missing_or_stale_evidence
what_to_inspect_first
hard_boundary_compliance
artifact_paths
warnings
source_hash
disclaimer
```

Allowed statuses:

```text
boss_preview_ready
boss_preview_limited
boss_preview_blocked_invalid_input
```

`boss_preview_ready` requires:

- P45 status `provider_ready` or `provider_degraded`;
- at least one candidate from P39;
- P42 boss brief artifact exists;
- P49 boss preview report exists.

Otherwise, if any artifact was produced, status is `boss_preview_limited`.

## 11. Boss Markdown Contract

Write:

```text
output/governance/YYYY-MM-DD/boss_preview.json
output/governance/YYYY-MM-DD/boss_preview.md
```

Markdown must include:

```text
# Hermes Boss Preview
Plain-English Verdict
Today’s Top Candidates
Market/Data Status
What Hermes Produced
Live vs Sample vs Missing
What The Boss Should Inspect First
Hard Boundary Compliance
Artifact Links
Technical Appendix
Disclaimer
```

The first 20 lines must be readable by a non-engineer. Technical command/status details belong in the appendix.

## 12. Repo-Local Skill Draft

Create:

```text
docs/skills/hermes-boss-preview/SKILL.md
```

Purpose:

- tell future agents that when the boss gives tickers, they should run `boss-preview-run`;
- forbid manual multi-command preview chains unless debugging;
- remind agents to use `--output-root output/governance`;
- require live Futu by default unless the boss says offline;
- require boss-readable summary first and technical appendix second.

This is a repo-local skill draft only. P49 must not install it into `~/.codex/skills`.

## 13. Source Hash And Idempotence

`source_hash` is SHA-256 over canonical JSON with sorted keys. The seed must include:

- schema version;
- normalized tickers;
- as-of date;
- live flag;
- phase statuses;
- artifact paths;
- sample input hashes;
- warnings;
- top candidates.

Preview reports are append-only:

```text
(as_of_date, tickers_key, source_hash)
```

## 14. Acceptance Criteria

P49 is accepted when:

- focused P49 tests pass;
- CLI tests pass;
- P45, P47, and P48 focused regressions pass;
- doc standards pass;
- boss only needs to provide tickers for a useful preview;
- live P45 is attempted by default;
- output root is normalized to avoid double-date paths;
- P37 symbol/provider errors do not abort the preview;
- P38/P39 receive valid sample inputs when real data is absent;
- `boss_preview.md` is understandable without reading JSON;
- hard boundaries are preserved.

## 15. Expected Commit Split

1. `feat: add boss preview runner`
2. `feat: add boss preview sample input builders`
3. `feat: add boss preview cli and skill draft`
4. `docs: document p49 boss preview runner`
