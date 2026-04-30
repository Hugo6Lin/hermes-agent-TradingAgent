# P48 Research Context Prompt Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dry-run prompt-context pack that converts P47 research context into deterministic role-specific context previews without injecting them into live research.

**Architecture:** Add a standalone `research_context_prompt_pack.py` module that loads the latest P47 context pack from DB or artifact, maps ticker context to analyst roles, and writes JSON/Markdown plus a dry-run injection manifest. Extend `ResearchDatabase` with append-only P48 persistence and a P47 latest-as-of helper, then add a local CLI.

**Tech Stack:** Python standard library, SQLite through existing `ResearchDatabase`, pytest, existing `batch_cli.py` argparse patterns.

---

## File Structure

- Create `agent/research_v1/research_context_prompt_pack.py`: constants, validation, P47 loading, role mapping, truncation, source hashing, markdown/JSON writers, runtime orchestration.
- Modify `agent/research_v1/data/database.py`: add `research_context_prompt_packs` table, save/list helpers, and `list_research_context_packs_as_of`.
- Modify `agent/research_v1/batch_cli.py`: add `research-context-prompt-pack-run`.
- Create `tests/agent/research_v1/test_research_context_prompt_pack.py`: focused P48 tests.
- Modify `tests/agent/research_v1/test_batch_cli.py`: P48 CLI tests.
- Modify `README.md`: add P48 overview, command, verification counts.
- Modify `agent/research_v1/README.md`: add P48 data-flow section.

## Commit Split

1. `feat: add research context prompt pack builder`
2. `feat: persist research context prompt packs`
3. `feat: add research context prompt pack cli`
4. `docs: document p48 research context prompt pack`

## Task 1: P48-A Builder

**Files:**
- Create: `agent/research_v1/research_context_prompt_pack.py`
- Test: `tests/agent/research_v1/test_research_context_prompt_pack.py`

- [ ] **Step 1: Write focused builder tests**

Create `tests/agent/research_v1/test_research_context_prompt_pack.py` with:

```python
"""Tests for P48 research context prompt pack dry-run."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.research_context_prompt_pack import (
    P48_DISCLAIMER,
    build_research_context_prompt_pack,
    normalize_roles,
    render_research_context_prompt_pack_markdown,
    validate_prompt_pack_inputs,
    write_research_context_prompt_pack,
)


def _source_pack() -> dict:
    return {
        "pack_id": "p47-2026-05-01-source",
        "as_of_date": "2026-05-01",
        "source_hash": "p47-source-hash",
        "tickers": ["AAPL"],
        "system_context": {"provider_status": "provider_ready", "evidence_health_status": "monitor_green"},
        "ticker_contexts": [
            {
                "ticker": "AAPL",
                "context_status": "context_ready",
                "market_regime": {"regime_label": "neutral"},
                "fundamental_quality": {"quality_score": 82, "quality_label": "strong"},
                "candidate_context": {"candidate_status": "candidate"},
                "outcome_context": {"win_rate": 0.6},
                "memory_context": {"memory_status": "memory_ready"},
                "decision_guardrails": {"severity": "info"},
                "refresh_context": {"refresh_candidate_count": 1},
                "evidence_health": {"status": "monitor_green"},
                "source_refs": [{"phase_id": "P38", "artifact_type": "fundamental_quality", "source_hash": "q"}],
                "missing_context": [],
                "warnings": [],
            }
        ],
        "source_refs": [{"phase_id": "P47", "artifact_type": "research_context_pack", "source_hash": "p47-source-hash"}],
        "missing_context": [],
        "warnings": [],
    }


def test_normalize_roles_deduplicates_and_preserves_order():
    assert normalize_roles([" Risk ", "fundamentals", "risk"]) == ["risk", "fundamentals"]


def test_validate_prompt_pack_inputs_rejects_unknown_role():
    result = validate_prompt_pack_inputs("2026-05-01", ["AAPL"], ["wizard"], 1200, True)
    assert result["status"] == "blocked_invalid_input"
    assert "unknown_role:wizard" in result["warnings"]


def test_build_prompt_pack_creates_role_context_and_manifest():
    pack = build_research_context_prompt_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        roles=["fundamentals", "risk"],
        max_block_chars=1200,
        source_pack=_source_pack(),
    )
    assert pack["status"] == "prompt_pack_ready"
    assert len(pack["role_contexts"]) == 2
    assert pack["dry_run_injection_manifest"][0]["dry_run_only"] is True
    assert pack["dry_run_injection_manifest"][0]["target_object"] == "SubagentTask.required_context"
    assert pack["role_contexts"][0]["required_context_preview"]["not_injected"] is True


def test_truncation_marks_limited_and_omitted_context():
    source = _source_pack()
    source["ticker_contexts"][0]["fundamental_quality"] = {"long": "x" * 500}
    pack = build_research_context_prompt_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        roles=["fundamentals"],
        max_block_chars=80,
        source_pack=source,
    )
    assert pack["status"] == "prompt_pack_limited"
    assert pack["role_contexts"][0]["context_status"] == "role_context_limited"
    assert any(item.startswith("omitted_section:AAPL:fundamentals") for item in pack["omitted_context"])


def test_markdown_renderer_includes_required_sections():
    pack = build_research_context_prompt_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        roles=["risk"],
        max_block_chars=1200,
        source_pack=_source_pack(),
    )
    md = render_research_context_prompt_pack_markdown(pack)
    assert "# P48 Research Context Prompt Pack" in md
    assert "## Dry-Run Injection Manifest" in md
    assert "## Disclaimer" in md
    assert P48_DISCLAIMER in md


def test_write_research_context_prompt_pack_creates_files(tmp_path: Path):
    pack = build_research_context_prompt_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        roles=["risk"],
        max_block_chars=1200,
        source_pack=_source_pack(),
    )
    artifacts = write_research_context_prompt_pack(pack, tmp_path)
    assert len(artifacts) == 2
    loaded = json.loads((tmp_path / "2026-05-01" / "p48_research_context_prompt_pack.json").read_text())
    assert loaded["prompt_pack_id"] == pack["prompt_pack_id"]
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_context_prompt_pack.py -q
```

Expected: import errors for missing P48 module/functions.

- [ ] **Step 3: Implement builder**

Create `agent/research_v1/research_context_prompt_pack.py`:

```python
"""P48 research context prompt pack dry-run."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

P48_SCHEMA_VERSION = "p48_research_context_prompt_pack.1"
P48_DISCLAIMER = (
    "P48 is a dry-run prompt-context pack only. It does not call analysts, "
    "call LLMs, inject prompts, submit orders, approve production adoption, "
    "train models, schedule jobs, or change research decisions."
)
SUPPORTED_ROLES = ("fundamentals", "technical", "news", "sentiment", "industry", "options", "risk", "valuation")
TICKER_RE = re.compile(r"^[A-Z0-9._-]{1,20}$")
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
ROLE_SECTION_MAP = {
    "fundamentals": ("fundamental_quality", "memory_context", "outcome_context", "evidence_health"),
    "technical": ("market_regime", "outcome_context", "candidate_context", "evidence_health"),
    "news": ("memory_context", "candidate_context", "evidence_health"),
    "sentiment": ("memory_context", "decision_guardrails", "outcome_context"),
    "industry": ("market_regime", "candidate_context", "fundamental_quality"),
    "options": ("market_regime", "outcome_context", "decision_guardrails", "provider_status"),
    "risk": ("decision_guardrails", "outcome_context", "evidence_health", "refresh_context"),
    "valuation": ("fundamental_quality", "outcome_context", "memory_context"),
}


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


def normalize_roles(roles: list[str] | None) -> list[str]:
    source = list(roles) if roles else list(SUPPORTED_ROLES)
    seen: set[str] = set()
    out: list[str] = []
    for raw in source:
        role = str(raw).strip().lower()
        if role and role not in seen:
            seen.add(role)
            out.append(role)
    return out


def validate_prompt_pack_inputs(as_of_date: str, tickers: list[str], roles: list[str] | None, max_block_chars: int, governance_root_is_dir: bool) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        date.fromisoformat(as_of_date)
    except (TypeError, ValueError):
        warnings.append(f"invalid_as_of_date:{as_of_date}")
    normalized_tickers = normalize_tickers(tickers)
    if not normalized_tickers:
        warnings.append("empty_ticker_list")
    for ticker in normalized_tickers:
        if not TICKER_RE.match(ticker):
            warnings.append(f"invalid_ticker:{ticker}")
    normalized_roles = normalize_roles(roles)
    for role in normalized_roles:
        if role not in SUPPORTED_ROLES:
            warnings.append(f"unknown_role:{role}")
    if max_block_chars <= 0:
        warnings.append("max_block_chars_must_be_positive")
    if not governance_root_is_dir:
        warnings.append("governance_root_not_a_directory")
    if warnings:
        return {"schema_version": P48_SCHEMA_VERSION, "status": "blocked_invalid_input", "warnings": warnings, "tickers": normalized_tickers, "roles": normalized_roles}
    return {"status": "valid", "tickers": normalized_tickers, "roles": normalized_roles, "warnings": []}


def _sha256_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _find_ticker_context(source_pack: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    for ctx in source_pack.get("ticker_contexts", []):
        if str(ctx.get("ticker", "")).upper() == ticker:
            return ctx
    return None


def _build_role_context(source_pack: dict[str, Any], ticker: str, role: str, max_block_chars: int) -> dict[str, Any]:
    ticker_ctx = _find_ticker_context(source_pack, ticker) or {}
    system = source_pack.get("system_context", {})
    sections: dict[str, Any] = {}
    omitted: list[str] = []
    warnings: list[str] = []
    for section_name in ROLE_SECTION_MAP[role]:
        value = system.get(section_name) if section_name == "provider_status" else ticker_ctx.get(section_name)
        if not value:
            omitted.append(f"missing_section:{ticker}:{role}:{section_name}")
            continue
        candidate = dict(sections)
        candidate[section_name] = value
        if len(json.dumps(candidate, sort_keys=True, default=str)) <= max_block_chars:
            sections[section_name] = value
        else:
            omitted.append(f"omitted_section:{ticker}:{role}:{section_name}:max_block_chars")
            warnings.append(f"context_truncated:{ticker}:{role}")
    if sections and warnings:
        status = "role_context_limited"
    elif sections:
        status = "role_context_ready"
    else:
        status = "role_context_missing"
    preview = {
        "schema_version": P48_SCHEMA_VERSION,
        "ticker": ticker,
        "role": role,
        "as_of_date": source_pack.get("as_of_date"),
        "source_context_pack_id": source_pack.get("pack_id"),
        "context_status": status,
        "context_blocks": sections,
        "not_injected": True,
    }
    block_hash = _sha256_json(preview)
    return {
        "ticker": ticker,
        "role": role,
        "context_status": status,
        "context_blocks": sections,
        "required_context_preview": preview,
        "source_refs": ticker_ctx.get("source_refs", []) + source_pack.get("source_refs", []),
        "omitted_context": omitted,
        "warnings": sorted(set(warnings)),
        "block_hash": block_hash,
    }


def build_research_context_prompt_pack(as_of_date: str, tickers: list[str], roles: list[str] | None, max_block_chars: int, source_pack: dict[str, Any], created_at: str | None = None) -> dict[str, Any]:
    normalized_tickers = normalize_tickers(tickers)
    normalized_roles = normalize_roles(roles)
    role_contexts = [_build_role_context(source_pack, ticker, role, max_block_chars) for ticker in normalized_tickers for role in normalized_roles]
    manifest = [
        {
            "ticker": ctx["ticker"],
            "role": ctx["role"],
            "dry_run_only": True,
            "target_object": "SubagentTask.required_context",
            "target_key": "research_context_pack",
            "would_set_keys": sorted(ctx["required_context_preview"].keys()),
            "context_status": ctx["context_status"],
            "block_hash": ctx["block_hash"],
        }
        for ctx in role_contexts
    ]
    omitted = sorted({item for ctx in role_contexts for item in ctx.get("omitted_context", [])})
    warnings = sorted({item for ctx in role_contexts for item in ctx.get("warnings", [])})
    if all(ctx["context_status"] == "role_context_ready" for ctx in role_contexts):
        status = "prompt_pack_ready"
    elif any(ctx["context_status"] != "role_context_missing" for ctx in role_contexts):
        status = "prompt_pack_limited"
    else:
        status = "blocked_missing_context"
    seed = {
        "schema_version": P48_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "tickers": normalized_tickers,
        "roles": normalized_roles,
        "max_block_chars": max_block_chars,
        "source_context_pack_id": source_pack.get("pack_id", ""),
        "source_context_hash": source_pack.get("source_hash", ""),
        "role_contexts": role_contexts,
        "dry_run_injection_manifest": manifest,
        "omitted_context": omitted,
        "warnings": warnings,
    }
    source_hash = _sha256_json(seed)
    return {
        "schema_version": P48_SCHEMA_VERSION,
        "prompt_pack_id": f"p48-{as_of_date}-{source_hash[:12]}",
        "as_of_date": as_of_date,
        "created_at": created_at or utc_now_iso(),
        "status": status,
        "tickers": normalized_tickers,
        "roles": normalized_roles,
        "max_block_chars": max_block_chars,
        "source_context_pack_id": source_pack.get("pack_id", ""),
        "source_context_hash": source_pack.get("source_hash", ""),
        "role_contexts": role_contexts,
        "dry_run_injection_manifest": manifest,
        "source_refs": source_pack.get("source_refs", []),
        "omitted_context": omitted,
        "warnings": warnings,
        "source_hash": source_hash,
        "disclaimer": P48_DISCLAIMER,
    }
```

- [ ] **Step 4: Add renderer and writer**

Append:

```python
def _assert_safe_rendered(text: str) -> None:
    lowered = text.lower()
    for term in FORBIDDEN_RENDER_TERMS:
        if term in lowered:
            raise ValueError(f"forbidden research context prompt pack term rendered:{term}")


def render_research_context_prompt_pack_markdown(pack: dict[str, Any]) -> str:
    lines = [
        "# P48 Research Context Prompt Pack",
        "",
        f"Status: {pack['status']}",
        f"As Of: {pack['as_of_date']}",
        "",
        "## Source P47 Context",
        f"- pack_id: {pack.get('source_context_pack_id', '')}",
        f"- source_hash: {pack.get('source_context_hash', '')}",
        "",
        "## Role Contexts",
    ]
    for ctx in pack.get("role_contexts", []):
        lines.append(f"- {ctx['ticker']} / {ctx['role']}: {ctx['context_status']}")
    lines.extend(["", "## Dry-Run Injection Manifest"])
    for item in pack.get("dry_run_injection_manifest", []):
        lines.append(f"- {item['ticker']} / {item['role']} -> {item['target_object']}[{item['target_key']}] dry_run={item['dry_run_only']}")
    lines.extend(["", "## Omitted Context"])
    lines.extend([f"- {item}" for item in pack.get("omitted_context", [])] or ["- none"])
    lines.extend(["", "## Warnings"])
    lines.extend([f"- {item}" for item in pack.get("warnings", [])] or ["- none"])
    lines.extend(["", "## Source References"])
    for ref in pack.get("source_refs", []):
        lines.append(f"- {ref.get('phase_id', 'unknown')} {ref.get('artifact_type', 'artifact')} {ref.get('source_hash', '')}")
    lines.extend(["", "## Disclaimer", "", pack.get("disclaimer", P48_DISCLAIMER), ""])
    text = "\n".join(lines)
    _assert_safe_rendered(text)
    return text


def write_research_context_prompt_pack(pack: dict[str, Any], output_root: Path) -> list[str]:
    output_dir = output_root / pack["as_of_date"]
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p48_research_context_prompt_pack.json"
    md_path = output_dir / "p48_research_context_prompt_pack.md"
    json_path.write_text(json.dumps(pack, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_research_context_prompt_pack_markdown(pack), encoding="utf-8")
    return [str(json_path), str(md_path)]
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_context_prompt_pack.py -q
```

Expected: builder tests pass.

- [ ] **Step 6: Commit P48-A**

```bash
git add agent/research_v1/research_context_prompt_pack.py tests/agent/research_v1/test_research_context_prompt_pack.py
git commit -m "feat: add research context prompt pack builder"
```

## Task 2: P48-B Persistence And Runtime

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `agent/research_v1/research_context_prompt_pack.py`
- Test: `tests/agent/research_v1/test_research_context_prompt_pack.py`

- [ ] **Step 1: Add persistence/runtime tests**

Add:

```python
from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.research_context_prompt_pack import run_research_context_prompt_pack


def test_save_research_context_prompt_pack_is_idempotent(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    pack = build_research_context_prompt_pack("2026-05-01", ["AAPL"], ["risk"], 1200, _source_pack(), created_at="2026-05-01T00:00:00+00:00")
    db.save_research_context_prompt_pack(pack)
    db.save_research_context_prompt_pack(pack)
    rows = db.list_research_context_prompt_packs(as_of_date="2026-05-01")
    assert len(rows) == 1
    assert rows[0]["source_hash"] == pack["source_hash"]


def test_run_prompt_pack_loads_p47_artifact_when_db_empty(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    governance_root = tmp_path / "governance"
    day_dir = governance_root / "2026-05-01"
    day_dir.mkdir(parents=True)
    (day_dir / "p47_research_context_pack.json").write_text(json.dumps(_source_pack()), encoding="utf-8")
    result = run_research_context_prompt_pack(db, governance_root, tmp_path / "out", "2026-05-01", ["AAPL"], ["risk"], 1200)
    assert result["status"] == "prompt_pack_ready"
    assert result["source_context_pack_id"] == "p47-2026-05-01-source"


def test_run_prompt_pack_blocks_when_p47_missing(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    governance_root = tmp_path / "governance"
    governance_root.mkdir()
    result = run_research_context_prompt_pack(db, governance_root, tmp_path / "out", "2026-05-01", ["AAPL"], ["risk"], 1200)
    assert result["status"] == "blocked_missing_context"
    assert not (tmp_path / "out" / "2026-05-01" / "p48_research_context_prompt_pack.json").exists()
```

- [ ] **Step 2: Implement DB helpers**

In `ResearchDatabase`, add:

```python
def initialize_research_context_prompt_pack_schema(self) -> None:
    conn = self._get_connection()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS research_context_prompt_packs (
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
            )"""
        )
        conn.commit()
    finally:
        conn.close()


def save_research_context_prompt_pack(self, pack: dict) -> str:
    self.initialize_research_context_prompt_pack_schema()
    tickers_key = "|".join(pack.get("tickers", []))
    roles_key = "|".join(pack.get("roles", []))
    conn = self._get_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO research_context_prompt_packs (
                prompt_pack_id, as_of_date, tickers_key, roles_key, status,
                source_context_pack_id, source_context_hash, source_hash,
                omitted_context_json, warnings_json, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pack["prompt_pack_id"],
                pack["as_of_date"],
                tickers_key,
                roles_key,
                pack["status"],
                pack.get("source_context_pack_id", ""),
                pack.get("source_context_hash", ""),
                pack["source_hash"],
                json.dumps(pack.get("omitted_context", []), sort_keys=True),
                json.dumps(pack.get("warnings", []), sort_keys=True),
                json.dumps(pack, sort_keys=True, default=str),
                pack.get("created_at", ""),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return pack["prompt_pack_id"]


def list_research_context_prompt_packs(self, as_of_date: str | None = None, limit: int = 20) -> list[dict]:
    self.initialize_research_context_prompt_pack_schema()
    conn = self._get_connection()
    try:
        if as_of_date:
            rows = conn.execute(
                """SELECT * FROM research_context_prompt_packs
                   WHERE as_of_date = ?
                   ORDER BY created_at DESC, prompt_pack_id ASC
                   LIMIT ?""",
                (as_of_date, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM research_context_prompt_packs
                   ORDER BY as_of_date DESC, created_at DESC, prompt_pack_id ASC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_research_context_packs_as_of(self, as_of_date: str, limit: int = 5) -> list[dict]:
    self.initialize_research_context_pack_schema()
    conn = self._get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM research_context_packs
               WHERE as_of_date <= ?
               ORDER BY as_of_date DESC, created_at DESC, pack_id ASC
               LIMIT ?""",
            (as_of_date, limit),
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                payload = json.loads(d.get("payload_json", "{}"))
                payload.setdefault("pack_id", d.get("pack_id"))
                result.append(payload)
            except (json.JSONDecodeError, TypeError):
                result.append(d)
        return result
    finally:
        conn.close()
```

- [ ] **Step 3: Add source loading and runtime**

Append to `research_context_prompt_pack.py`:

```python
def _load_p47_artifact_as_of(governance_root: Path, as_of_date: str, lookback_days: int = 30) -> dict[str, Any] | None:
    for offset in range(lookback_days + 1):
        day = (date.fromisoformat(as_of_date) - timedelta(days=offset)).isoformat()
        path = governance_root / day / "p47_research_context_pack.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
    return None


def load_source_context_pack(db: Any, governance_root: Path, as_of_date: str) -> dict[str, Any] | None:
    method = getattr(db, "list_research_context_packs_as_of", None)
    if method:
        try:
            rows = method(as_of_date)
        except Exception:
            rows = []
        if rows:
            return rows[0]
    return _load_p47_artifact_as_of(Path(governance_root), as_of_date)


def run_research_context_prompt_pack(db: Any, governance_root: Path, output_root: Path, as_of_date: str, tickers: list[str], roles: list[str] | None = None, max_block_chars: int = 1200) -> dict[str, Any]:
    governance_root = Path(governance_root)
    validation = validate_prompt_pack_inputs(
        as_of_date,
        tickers,
        roles,
        max_block_chars,
        governance_root.is_dir() if governance_root.exists() else True,
    )
    if validation["status"] == "blocked_invalid_input":
        return validation
    source_pack = load_source_context_pack(db, governance_root, as_of_date)
    if not source_pack:
        return {
            "schema_version": P48_SCHEMA_VERSION,
            "status": "blocked_missing_context",
            "as_of_date": as_of_date,
            "tickers": validation["tickers"],
            "roles": validation["roles"],
            "warnings": ["missing_p47_research_context_pack"],
        }
    pack = build_research_context_prompt_pack(
        as_of_date=as_of_date,
        tickers=validation["tickers"],
        roles=validation["roles"],
        max_block_chars=max_block_chars,
        source_pack=source_pack,
    )
    artifacts = write_research_context_prompt_pack(pack, Path(output_root))
    if hasattr(db, "save_research_context_prompt_pack"):
        db.save_research_context_prompt_pack(pack)
    pack["artifacts"] = artifacts
    return pack
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_context_prompt_pack.py -q
```

Expected: focused P48 tests pass.

- [ ] **Step 5: Commit P48-B**

```bash
git add agent/research_v1/research_context_prompt_pack.py agent/research_v1/data/database.py tests/agent/research_v1/test_research_context_prompt_pack.py
git commit -m "feat: persist research context prompt packs"
```

## Task 3: P48-C CLI

**Files:**
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Add CLI tests**

Add tests that monkeypatch `run_research_context_prompt_pack`:

```python
def test_research_context_prompt_pack_cli_success(monkeypatch, tmp_path, capsys):
    from agent.research_v1.batch_cli import main
    (tmp_path / "data").mkdir()
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {
            "status": "prompt_pack_ready",
            "prompt_pack_id": "p48-2026-05-01-abc",
            "tickers": ["AAPL"],
            "roles": ["risk"],
            "omitted_context": [],
            "warnings": [],
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_research_context_prompt_pack", fake_run)
    code = main(["--app-root", str(tmp_path), "research-context-prompt-pack-run", "--as-of-date", "2026-05-01", "--tickers", "AAPL", "--roles", "risk"])
    assert code == 0
    assert captured["roles"] == ["risk"]
    assert "Research context prompt pack status: prompt_pack_ready" in capsys.readouterr().out
```

Add invalid date, unknown role, and non-positive max-block tests with expected exit code `2`.

- [ ] **Step 2: Wire CLI**

Import `run_research_context_prompt_pack`, add parser:

```python
prompt_parser = subparsers.add_parser("research-context-prompt-pack-run", help="Run P48 research context prompt-pack dry-run.")
prompt_parser.add_argument("--as-of-date", required=True)
prompt_parser.add_argument("--tickers", required=True)
prompt_parser.add_argument("--roles", default="")
prompt_parser.add_argument("--max-block-chars", type=int, default=1200)
prompt_parser.add_argument("--governance-root", default="output/governance")
prompt_parser.add_argument("--output-root", default="output/governance")
```

Add command dispatch:

```python
if args.command == "research-context-prompt-pack-run":
    roles = [r.strip() for r in args.roles.split(",") if r.strip()] or None
    return _cmd_research_context_prompt_pack_run(
        paths,
        args.as_of_date,
        args.tickers,
        roles,
        args.max_block_chars,
        args.governance_root,
        args.output_root,
    )
```

Add handler:

```python
def _cmd_research_context_prompt_pack_run(paths, as_of_date, tickers, roles, max_block_chars, governance_root, output_root) -> int:
    from datetime import date as _date
    try:
        _date.fromisoformat(as_of_date)
    except (TypeError, ValueError):
        print(f"invalid research-context-prompt-pack-run input: invalid date format '{as_of_date}'")
        return 2
    if not tickers:
        print("invalid research-context-prompt-pack-run input: tickers required")
        return 2
    if max_block_chars <= 0:
        print("invalid research-context-prompt-pack-run input: max-block-chars must be positive")
        return 2
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    governance_path = Path(governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path
    database = _ensure_database(paths)
    result = run_research_context_prompt_pack(database, governance_path.resolve(), output_path.resolve(), as_of_date, ticker_list, roles, max_block_chars)
    if result.get("status") in {"blocked_invalid_input", "blocked_missing_context"}:
        print(f"invalid research-context-prompt-pack-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Research context prompt pack status: {result['status']}")
    print(f"Prompt pack id: {result['prompt_pack_id']}")
    print(f"Tickers: {', '.join(result['tickers'])}")
    print(f"Roles: {', '.join(result['roles'])}")
    print(f"Omitted context: {len(result['omitted_context'])}")
    print(f"Warnings: {len(result['warnings'])}")
    return 0
```

- [ ] **Step 3: Run CLI tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "research_context_prompt_pack or research-context-prompt-pack"
```

Expected: P48 CLI tests pass.

- [ ] **Step 4: Commit P48-C**

```bash
git add agent/research_v1/batch_cli.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add research context prompt pack cli"
```

## Task 4: P48-D Docs And Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update docs**

Add:

````markdown
### P48 Research Context Prompt Pack Dry-Run

P48 converts the latest P47 research context pack into role-specific prompt-context previews:

```bash
/opt/homebrew/bin/python3.11 -m agent.research_v1.batch_cli research-context-prompt-pack-run \
  --as-of-date 2026-05-01 \
  --tickers AAPL,MSFT \
  --roles fundamentals,risk \
  --max-block-chars 1200 \
  --output-root output/governance
```

It writes `p48_research_context_prompt_pack.json` and `.md` under `output/governance/YYYY-MM-DD/`. P48 is dry-run only: it does not call analysts, LLMs, `HermesResearchApp.run()`, `final_judge`, providers, or broker/order APIs, and it does not mutate `SubagentTask.required_context`.
````

- [ ] **Step 2: Run verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_context_prompt_pack.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "research_context_prompt_pack or research-context-prompt-pack"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_context_pack.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_refresh_planner.py tests/agent/research_v1/test_market_data_readiness.py tests/agent/research_v1/test_evidence_freshness_drift_monitor.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Expected: focused P48, CLI, P47 regression, selected P44-P46 regression, and doc-standard suites pass. List known host-specific gaps separately.

- [ ] **Step 3: Commit P48-D**

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p48 research context prompt pack"
```

## Final Report Template

```text
P48 Implementation Complete

Status Summary
Phase   Status   Commit
P48-A   PASS     <commit> feat: add research context prompt pack builder
P48-B   PASS     <commit> feat: persist research context prompt packs
P48-C   PASS     <commit> feat: add research context prompt pack cli
P48-D   PASS     <commit> docs: document p48 research context prompt pack

Verification
- P48 focused: <N> passed
- P48 CLI: <N> passed
- P47 regression: <N> passed
- P36-P46 regression: <N> passed
- Governance-adjacent regression: <N> passed
- Doc standards: <N> passed
- Full P20-P48 chain: <N> passed, known host-specific gaps listed separately

Hard Boundary Compliance
- no auto-trading
- no broker orders
- no production approval
- no production config mutation
- no model training
- no scheduling or notifications
- no viewer/server
- no Futu/provider calls
- no P36-P47 runtime invocation
- no P36-P47 evidence mutation
- no LLM calls
- no SubagentExecutor calls
- no final_judge changes
- no HermesResearchApp.run invocation
- no CanonicalSignal or CanonicalReport creation
- no JudgeInputPacket mutation
- no live SubagentTask mutation
- no prompt injection into research or judge
```
