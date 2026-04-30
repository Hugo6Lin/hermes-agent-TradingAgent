# P47 Research Context Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only P47 research context pack that aggregates P36-P46 evidence into deterministic ticker/system dossiers without injecting context into research decisions.

**Architecture:** Add a standalone `research_context_pack.py` module that assembles plain dictionaries from persisted evidence and artifact fallbacks. Extend `ResearchDatabase` with append-only pack persistence and read helpers, then add a local CLI that writes JSON/Markdown under `output/governance/YYYY-MM-DD/`.

**Tech Stack:** Python standard library, SQLite through existing `ResearchDatabase`, pytest, existing `batch_cli.py` argparse patterns.

---

## File Structure

- Create `agent/research_v1/research_context_pack.py`: P47 constants, input validation, evidence extraction, context assembly, source hashing, JSON/Markdown writers, runtime orchestration.
- Modify `agent/research_v1/data/database.py`: add `research_context_packs` table, save/list helpers, and P47 latest-as-of read helpers only where current helpers are missing.
- Modify `agent/research_v1/batch_cli.py`: add `research-context-pack-run`.
- Create `tests/agent/research_v1/test_research_context_pack.py`: focused P47 unit/runtime/persistence tests.
- Modify `tests/agent/research_v1/test_batch_cli.py`: P47 CLI tests.
- Modify `README.md`: add P47 overview, command, verification counts.
- Modify `agent/research_v1/README.md`: add P47 data-flow section.

## Commit Split

1. `feat: add research context pack builder`
2. `feat: persist research context packs`
3. `feat: add research context pack cli`
4. `docs: document p47 research context pack`

## Task 1: P47-A Builder

**Files:**
- Create: `agent/research_v1/research_context_pack.py`
- Test: `tests/agent/research_v1/test_research_context_pack.py`

- [ ] **Step 1: Write focused builder tests**

Add tests that assert:

```python
def test_normalize_tickers_deduplicates_and_preserves_order():
    from agent.research_v1.research_context_pack import normalize_tickers
    assert normalize_tickers([" aapl ", "MSFT", "AAPL"]) == ["AAPL", "MSFT"]


def test_invalid_ticker_rejected():
    from agent.research_v1.research_context_pack import validate_request_inputs
    result = validate_request_inputs("2026-05-01", ["AAPL;DROP"], 180, 8, governance_root_is_dir=True)
    assert result["status"] == "blocked_invalid_input"
    assert "invalid_ticker:AAPL;DROP" in result["warnings"]


def test_build_pack_limited_with_missing_ticker_context(tmp_path):
    from agent.research_v1.research_context_pack import build_research_context_pack
    pack = build_research_context_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        lookback_days=180,
        max_items_per_ticker=8,
        evidence={
            "system": {"provider_status": "provider_ready"},
            "tickers": {},
        },
    )
    assert pack["status"] == "context_pack_limited"
    assert pack["ticker_contexts"][0]["context_status"] == "context_missing"
    assert "missing_ticker_context:AAPL" in pack["missing_context"]
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_context_pack.py -q
```

Expected: import errors for missing P47 module/functions.

- [ ] **Step 3: Implement builder**

Create `agent/research_v1/research_context_pack.py` with:

```python
"""P47 read-only research context pack."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

P47_SCHEMA_VERSION = "p47_research_context_pack.1"
P47_DISCLAIMER = (
    "P47 is read-only research context evidence. It does not instruct trades, "
    "submit orders, approve production adoption, train models, schedule jobs, "
    "or change research decisions."
)
FORBIDDEN_RENDER_TERMS = (
    "buy this now",
    "sell this now",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "execute trade",
    "place order",
    "unlock_trade",
)
TICKER_RE = re.compile(r"^[A-Z0-9._-]{1,20}$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_tickers(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in tickers:
        ticker = str(raw).strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            out.append(ticker)
    return out


def validate_request_inputs(
    as_of_date: str,
    tickers: list[str],
    lookback_days: int,
    max_items_per_ticker: int,
    governance_root_is_dir: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        date.fromisoformat(as_of_date)
    except ValueError:
        warnings.append(f"invalid_as_of_date:{as_of_date}")
    normalized = normalize_tickers(tickers)
    if not normalized:
        warnings.append("empty_ticker_list")
    for ticker in normalized:
        if not TICKER_RE.match(ticker):
            warnings.append(f"invalid_ticker:{ticker}")
    if lookback_days <= 0:
        warnings.append("lookback_days_must_be_positive")
    if max_items_per_ticker <= 0:
        warnings.append("max_items_per_ticker_must_be_positive")
    if not governance_root_is_dir:
        warnings.append("governance_root_not_a_directory")
    if warnings:
        return {
            "schema_version": P47_SCHEMA_VERSION,
            "status": "blocked_invalid_input",
            "warnings": warnings,
            "tickers": normalized,
        }
    return {"status": "valid", "tickers": normalized, "warnings": []}


def _sha256_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ticker_context(ticker: str, evidence: dict[str, Any], max_items: int) -> dict[str, Any]:
    ticker_evidence = evidence.get("tickers", {}).get(ticker, {})
    source_refs = ticker_evidence.get("source_refs", [])[:max_items]
    sections = {
        "market_regime": ticker_evidence.get("market_regime"),
        "fundamental_quality": ticker_evidence.get("fundamental_quality"),
        "candidate_context": ticker_evidence.get("candidate_context"),
        "outcome_context": ticker_evidence.get("outcome_context"),
        "memory_context": ticker_evidence.get("memory_context"),
        "decision_guardrails": ticker_evidence.get("decision_guardrails"),
        "refresh_context": ticker_evidence.get("refresh_context"),
        "evidence_health": ticker_evidence.get("evidence_health"),
    }
    non_empty = {k: v for k, v in sections.items() if v}
    missing = [] if non_empty else [f"missing_ticker_context:{ticker}"]
    status = "context_ready" if len(non_empty) >= 3 else "context_limited" if non_empty else "context_missing"
    return {
        "ticker": ticker,
        "context_status": status,
        **sections,
        "source_refs": source_refs,
        "missing_context": missing,
        "warnings": ticker_evidence.get("warnings", []),
        "prompt_context": {
            "ticker": ticker,
            "status": status,
            "facts": non_empty,
            "not_wired_to_research_prompts": True,
        },
    }


def build_research_context_pack(
    *,
    as_of_date: str,
    tickers: list[str],
    lookback_days: int,
    max_items_per_ticker: int,
    evidence: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    created = created_at or utc_now_iso()
    normalized = normalize_tickers(tickers)
    system_context = evidence.get("system", {})
    ticker_contexts = [_ticker_context(t, evidence, max_items_per_ticker) for t in normalized]
    missing_context: list[str] = []
    warnings: list[str] = []
    source_refs = list(system_context.get("source_refs", []))
    for ctx in ticker_contexts:
        missing_context.extend(ctx["missing_context"])
        warnings.extend(ctx["warnings"])
        source_refs.extend(ctx["source_refs"])
    has_system = any(system_context.get(k) for k in ("provider_status", "evidence_health_status", "refresh_plan_status"))
    ready_tickers = [ctx for ctx in ticker_contexts if ctx["context_status"] == "context_ready"]
    any_ticker = any(ctx["context_status"] != "context_missing" for ctx in ticker_contexts)
    if ready_tickers and has_system and not missing_context:
        status = "context_pack_ready"
    elif any_ticker or has_system:
        status = "context_pack_limited"
    else:
        status = "context_pack_missing"
    seed = {
        "schema_version": P47_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "tickers": normalized,
        "lookback_days": lookback_days,
        "max_items_per_ticker": max_items_per_ticker,
        "system_context": system_context,
        "ticker_contexts": ticker_contexts,
        "source_refs": source_refs,
        "missing_context": sorted(set(missing_context)),
        "warnings": sorted(set(warnings)),
    }
    source_hash = _sha256_json(seed)
    pack_id = f"p47-{as_of_date}-{source_hash[:12]}"
    return {
        "schema_version": P47_SCHEMA_VERSION,
        "pack_id": pack_id,
        "as_of_date": as_of_date,
        "created_at": created,
        "status": status,
        "tickers": normalized,
        "lookback_days": lookback_days,
        "max_items_per_ticker": max_items_per_ticker,
        "system_context": system_context,
        "ticker_contexts": ticker_contexts,
        "source_refs": source_refs,
        "missing_context": sorted(set(missing_context)),
        "warnings": sorted(set(warnings)),
        "source_hash": source_hash,
        "disclaimer": P47_DISCLAIMER,
    }
```

- [ ] **Step 4: Add writers and forbidden-language checks**

Add:

```python
def _assert_safe_rendered(text: str) -> None:
    lowered = text.lower()
    for term in FORBIDDEN_RENDER_TERMS:
        if term in lowered:
            raise ValueError(f"forbidden research context pack term rendered:{term}")


def render_research_context_pack_markdown(pack: dict[str, Any]) -> str:
    lines = [
        "# P47 Research Context Pack",
        "",
        f"Status: {pack['status']}",
        f"As Of: {pack['as_of_date']}",
        "",
        "## System Context",
    ]
    for key, value in sorted(pack.get("system_context", {}).items()):
        if key != "source_refs":
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## Ticker Contexts"])
    for ctx in pack.get("ticker_contexts", []):
        lines.append(f"- {ctx['ticker']}: {ctx['context_status']}")
        for reason in ctx.get("missing_context", []):
            lines.append(f"  - missing: {reason}")
    lines.extend(["", "## Missing Context"])
    lines.extend([f"- {item}" for item in pack.get("missing_context", [])] or ["- none"])
    lines.extend(["", "## Warnings"])
    lines.extend([f"- {item}" for item in pack.get("warnings", [])] or ["- none"])
    lines.extend(["", "## Source References"])
    for ref in pack.get("source_refs", []):
        lines.append(f"- {ref.get('phase_id', 'unknown')} {ref.get('artifact_type', 'artifact')} {ref.get('as_of_date', '')}")
    lines.extend(["", "## Disclaimer", "", pack.get("disclaimer", P47_DISCLAIMER), ""])
    text = "\n".join(lines)
    _assert_safe_rendered(text)
    return text


def write_research_context_pack(pack: dict[str, Any], output_root: Path) -> list[str]:
    output_dir = output_root / pack["as_of_date"]
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p47_research_context_pack.json"
    md_path = output_dir / "p47_research_context_pack.md"
    json_path.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_research_context_pack_markdown(pack), encoding="utf-8")
    return [str(json_path), str(md_path)]
```

- [ ] **Step 5: Run focused builder tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_context_pack.py -q
```

Expected: focused tests pass.

- [ ] **Step 6: Commit P47-A**

```bash
git add agent/research_v1/research_context_pack.py tests/agent/research_v1/test_research_context_pack.py
git commit -m "feat: add research context pack builder"
```

## Task 2: P47-B Persistence And Runtime

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `agent/research_v1/research_context_pack.py`
- Test: `tests/agent/research_v1/test_research_context_pack.py`

- [ ] **Step 1: Add persistence tests**

Add tests for:

```python
def test_save_research_context_pack_is_idempotent(tmp_path):
    from agent.research_v1.data.database import ResearchDatabase
    from agent.research_v1.research_context_pack import build_research_context_pack
    db = ResearchDatabase(tmp_path / "research.db")
    pack = build_research_context_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        lookback_days=180,
        max_items_per_ticker=8,
        evidence={"system": {"provider_status": "provider_ready"}, "tickers": {}},
        created_at="2026-05-01T00:00:00+00:00",
    )
    first = db.save_research_context_pack(pack)
    second = db.save_research_context_pack(pack)
    rows = db.list_research_context_packs("2026-05-01")
    assert first == second
    assert len(rows) == 1
    assert rows[0]["source_hash"] == pack["source_hash"]
```

- [ ] **Step 2: Implement DB table and helpers**

In `ResearchDatabase._initialize_schema()`, add:

```python
cur.execute(
    """
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
    )
    """
)
```

Add methods:

```python
def save_research_context_pack(self, pack: dict[str, Any]) -> str:
    tickers_key = "|".join(pack.get("tickers", []))
    with self._connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO research_context_packs (
                pack_id, as_of_date, tickers_key, status, source_hash,
                source_refs_json, missing_context_json, warnings_json,
                payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pack["pack_id"],
                pack["as_of_date"],
                tickers_key,
                pack["status"],
                pack["source_hash"],
                json.dumps(pack.get("source_refs", []), sort_keys=True),
                json.dumps(pack.get("missing_context", []), sort_keys=True),
                json.dumps(pack.get("warnings", []), sort_keys=True),
                json.dumps(pack, sort_keys=True),
                pack["created_at"],
            ),
        )
    return pack["pack_id"]


def list_research_context_packs(self, as_of_date: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM research_context_packs"
    params: list[Any] = []
    if as_of_date:
        sql += " WHERE as_of_date = ?"
        params.append(as_of_date)
    sql += " ORDER BY as_of_date DESC, created_at DESC, pack_id ASC"
    with self._connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
```

- [ ] **Step 3: Add runtime orchestration**

Add a deterministic runtime in `research_context_pack.py`:

```python
def collect_research_context_evidence(db: Any, governance_root: Path, as_of_date: str, tickers: list[str], lookback_days: int) -> dict[str, Any]:
    evidence: dict[str, Any] = {"system": {}, "tickers": {ticker: {} for ticker in tickers}}
    for method_name, target_key in (
        ("list_market_data_readiness_reports_as_of", "provider_status"),
        ("list_evidence_freshness_drift_reports_as_of", "evidence_health_status"),
        ("list_evidence_refresh_plans_as_of", "refresh_plan_status"),
    ):
        method = getattr(db, method_name, None)
        if method:
            rows = method(as_of_date)
            if rows:
                row = rows[0]
                evidence["system"][target_key] = row.get("status") or row.get("provider_status")
                evidence["system"].setdefault("source_refs", []).append({
                    "phase_id": target_key,
                    "artifact_type": method_name,
                    "source_id": row.get("report_id") or row.get("plan_id"),
                    "as_of_date": row.get("as_of_date"),
                    "created_at": row.get("created_at"),
                    "source_hash": row.get("source_hash"),
                    "path": row.get("artifact_path"),
                })
    for ticker in tickers:
        quality_method = getattr(db, "list_fundamental_quality_reports_as_of", None)
        if quality_method:
            rows = quality_method(ticker, as_of_date)
            if rows:
                row = rows[0]
                evidence["tickers"][ticker]["fundamental_quality"] = {
                    "quality_score": row.get("quality_score"),
                    "quality_bucket": row.get("quality_bucket"),
                    "as_of_date": row.get("as_of_date"),
                }
                evidence["tickers"][ticker].setdefault("source_refs", []).append({
                    "phase_id": "P38",
                    "artifact_type": "fundamental_quality_report",
                    "source_id": row.get("report_id"),
                    "as_of_date": row.get("as_of_date"),
                    "created_at": row.get("created_at"),
                    "source_hash": row.get("source_hash"),
                    "path": row.get("artifact_path"),
                })
    return evidence


def run_research_context_pack(db: Any, governance_root: Path, output_root: Path, as_of_date: str, tickers: list[str], lookback_days: int = 180, max_items_per_ticker: int = 8) -> dict[str, Any]:
    validation = validate_request_inputs(as_of_date, tickers, lookback_days, max_items_per_ticker, governance_root.is_dir())
    if validation["status"] == "blocked_invalid_input":
        return validation
    normalized = validation["tickers"]
    evidence = collect_research_context_evidence(db, governance_root, as_of_date, normalized, lookback_days)
    pack = build_research_context_pack(
        as_of_date=as_of_date,
        tickers=normalized,
        lookback_days=lookback_days,
        max_items_per_ticker=max_items_per_ticker,
        evidence=evidence,
    )
    artifacts = write_research_context_pack(pack, output_root)
    if hasattr(db, "save_research_context_pack"):
        db.save_research_context_pack(pack)
    pack["artifacts"] = artifacts
    return pack
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_context_pack.py -q
```

Expected: focused tests pass.

- [ ] **Step 5: Commit P47-B**

```bash
git add agent/research_v1/research_context_pack.py agent/research_v1/data/database.py tests/agent/research_v1/test_research_context_pack.py
git commit -m "feat: persist research context packs"
```

## Task 3: P47-C CLI

**Files:**
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Add CLI tests**

Add tests that run:

```bash
research-context-pack-run --as-of-date 2026-05-01 --tickers AAPL,MSFT
```

Assert exit code `0`, stdout contains `Research context pack status:`, and JSON/Markdown artifacts exist. Add invalid-date and empty-ticker tests that assert exit code `2`.

- [ ] **Step 2: Wire CLI**

Add parser:

```python
context_parser = subparsers.add_parser("research-context-pack-run", help="Run P47 research context pack.")
context_parser.add_argument("--as-of-date", required=True)
context_parser.add_argument("--tickers", required=True)
context_parser.add_argument("--lookback-days", type=int, default=180)
context_parser.add_argument("--max-items-per-ticker", type=int, default=8)
context_parser.add_argument("--governance-root", default="output/governance")
context_parser.add_argument("--output-root", default="output/governance")
context_parser.set_defaults(func=_cmd_research_context_pack_run)
```

Add handler:

```python
def _cmd_research_context_pack_run(args: argparse.Namespace) -> int:
    from pathlib import Path
    from agent.research_v1.data.database import ResearchDatabase
    from agent.research_v1.research_context_pack import run_research_context_pack

    paths = _resolve_paths(args)
    governance_root = Path(args.governance_root)
    output_root = Path(args.output_root)
    if not governance_root.is_absolute():
        governance_root = paths.app_root / governance_root
    if not output_root.is_absolute():
        output_root = paths.app_root / output_root
    tickers = [part for part in args.tickers.split(",") if part.strip()]
    db = ResearchDatabase(paths.db_path)
    result = run_research_context_pack(
        db=db,
        governance_root=governance_root,
        output_root=output_root,
        as_of_date=args.as_of_date,
        tickers=tickers,
        lookback_days=args.lookback_days,
        max_items_per_ticker=args.max_items_per_ticker,
    )
    print(f"Research context pack status: {result.get('status')}")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")
    for artifact in result.get("artifacts", []):
        print(f"Artifact: {artifact}")
    return 2 if result.get("status") == "blocked_invalid_input" else 0
```

- [ ] **Step 3: Run CLI tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "research_context_pack or research-context-pack"
```

Expected: P47 CLI tests pass.

- [ ] **Step 4: Commit P47-C**

```bash
git add agent/research_v1/batch_cli.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add research context pack cli"
```

## Task 4: P47-D Docs And Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update docs**

Add a P47 section:

````markdown
### P47 Research Context Pack

P47 aggregates P36-P46 evidence into a read-only pre-research context pack:

```bash
/opt/homebrew/bin/python3.11 -m agent.research_v1.batch_cli research-context-pack-run \
  --as-of-date 2026-05-01 \
  --tickers AAPL,MSFT \
  --lookback-days 180 \
  --output-root output/governance
```

It writes `p47_research_context_pack.json` and `.md` under `output/governance/YYYY-MM-DD/`. P47 does not call market-data providers, invoke research, inject context into prompts, change recommendations, or submit orders.
````

- [ ] **Step 2: Run verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_context_pack.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "research_context_pack or research-context-pack"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_research_memory_pack.py tests/agent/research_v1/test_decision_journal_guardrails.py tests/agent/research_v1/test_boss_copilot_daily_brief.py tests/agent/research_v1/test_copilot_console_index.py tests/agent/research_v1/test_evidence_freshness_drift_monitor.py tests/agent/research_v1/test_market_data_readiness.py tests/agent/research_v1/test_evidence_refresh_planner.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Expected: focused, CLI, P36-P46, and doc-standard suites pass, except known host-specific gaps explicitly listed by test name.

- [ ] **Step 3: Commit P47-D**

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p47 research context pack"
```

## Final Report Template

```text
P47 Implementation Complete

Status Summary
Phase   Status   Commit
P47-A   PASS     <commit> feat: add research context pack builder
P47-B   PASS     <commit> feat: persist research context packs
P47-C   PASS     <commit> feat: add research context pack cli
P47-D   PASS     <commit> docs: document p47 research context pack

Verification
- P47 focused: <N> passed
- P47 CLI: <N> passed
- P36-P46 regression: <N> passed
- Governance-adjacent regression: <N> passed
- Doc standards: <N> passed
- Full P20-P47 chain: <N> passed, known host-specific gaps listed separately

Hard Boundary Compliance
- no auto-trading
- no broker orders
- no production approval
- no production config mutation
- no model training
- no scheduling or notifications
- no viewer/server
- no Futu/provider calls
- no P36-P46 runtime invocation
- no P36-P46 evidence mutation
- no final_judge changes
- no HermesResearchApp.run invocation
- no CanonicalSignal or CanonicalReport creation
- no JudgeInputPacket mutation
- no prompt injection into research or judge
```
