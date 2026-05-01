# P46 Controlled Evidence Refresh Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dry-run refresh planner that consumes P44 freshness/drift evidence and P45 Futu readiness, then outputs prioritized manual refresh candidates without executing any refresh.

**Architecture:** Add a focused `evidence_refresh_planner.py` module for deterministic plan-item generation, dependency gating, source hashing, artifact writing, and runtime orchestration. Extend `ResearchDatabase` with append-only P46 plan persistence and latest-as-of helpers for P44/P45 reports. Wire a local CLI command that writes JSON/Markdown under `output/governance/YYYY-MM-DD/`.

**Tech Stack:** Python 3.11, pathlib, json, hashlib, datetime, sqlite3, argparse, pytest, existing P44/P45 persisted report rows and artifacts.

---

## File Structure

- Create `agent/research_v1/evidence_refresh_planner.py`
  - Plan-item model, P44/P45 selection, dependency gating, scoring, source hash, artifact writer, runtime.
- Modify `agent/research_v1/data/database.py`
  - Add `evidence_refresh_plans` table.
  - Add save/list helpers.
  - Add latest-as-of helpers for P44 and P45 reports if not already present.
- Modify `agent/research_v1/batch_cli.py`
  - Add `evidence-refresh-plan-run`.
- Create `tests/agent/research_v1/test_evidence_refresh_planner.py`
  - Focused P46 tests.
- Modify `tests/agent/research_v1/test_batch_cli.py`
  - P46 CLI tests.
- Modify `README.md`
  - Add P46 overview and commands.
- Modify `agent/research_v1/README.md`
  - Add P46 data flow.

Expected commits:

1. `feat: add evidence refresh planner`
2. `feat: persist evidence refresh plans`
3. `feat: add evidence refresh planner cli`
4. `docs: document p46 evidence refresh planner`

---

## Task 1: P46-A Core Planner

**Files:**
- Create: `agent/research_v1/evidence_refresh_planner.py`
- Test: `tests/agent/research_v1/test_evidence_refresh_planner.py`

- [ ] **Step 1: Add focused failing tests**

Create `tests/agent/research_v1/test_evidence_refresh_planner.py`:

```python
"""Tests for P46 controlled evidence refresh planner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.evidence_refresh_planner import (
    P46_SCHEMA_VERSION,
    build_evidence_refresh_plan,
    write_evidence_refresh_plan_artifacts,
)


def _monitor(status: str = "monitor_yellow", phase_overrides: dict | None = None) -> dict:
    phase_overrides = phase_overrides or {}
    phases = []
    for phase_id, phase_name in [
        ("P36", "recommendation_outcomes"),
        ("P37", "market_regime"),
        ("P38", "fundamental_quality"),
        ("P39", "candidate_pool"),
        ("P40", "research_memory"),
        ("P41", "decision_journal"),
        ("P42", "boss_copilot_brief"),
        ("P43", "copilot_console_index"),
    ]:
        base = {
            "phase_id": phase_id,
            "phase_name": phase_name,
            "latest_evidence_date": "2026-04-30",
            "latest_source_hash": f"{phase_id}-hash",
            "freshness_status": "fresh",
            "coverage_status": "complete",
            "churn_status": "stable",
            "recommended_action": "none",
            "warnings": [],
        }
        base.update(phase_overrides.get(phase_id, {}))
        phases.append(base)
    return {
        "schema_version": "p44_evidence_freshness_drift_monitor.1",
        "report_id": "p44-report",
        "as_of_date": "2026-04-30",
        "status": status,
        "source_hash": "p44-hash",
        "phase_monitors": phases,
        "missing_context_patterns": [],
    }


def _provider(status: str = "provider_ready") -> dict:
    return {
        "schema_version": "p45_market_data_readiness.1",
        "report_id": "p45-report",
        "as_of_date": "2026-04-30",
        "status": status,
        "source_hash": f"p45-{status}",
        "recommended_actions": [],
    }


def _item(plan: dict, phase_id: str) -> dict:
    return next(item for item in plan["items"] if item["phase_id"] == phase_id)


def test_missing_monitor_blocks_plan(tmp_path: Path):
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=None,
        provider_report=_provider("provider_ready"),
    )

    assert plan["schema_version"] == P46_SCHEMA_VERSION
    assert plan["status"] == "refresh_plan_blocked"
    assert any(item["plan_status"] == "blocked_missing_monitor" for item in plan["items"])


def test_provider_unavailable_blocks_market_data_phases(tmp_path: Path):
    monitor = _monitor(phase_overrides={
        "P36": {"freshness_status": "stale", "coverage_status": "partial"},
        "P37": {"freshness_status": "stale", "coverage_status": "partial"},
    })
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_unavailable"),
    )

    assert _item(plan, "P36")["plan_status"] == "blocked_provider_unavailable"
    assert _item(plan, "P37")["plan_status"] == "blocked_provider_unavailable"


def test_provider_ready_allows_stale_market_data_refresh_candidate(tmp_path: Path):
    monitor = _monitor(phase_overrides={"P36": {"freshness_status": "stale", "coverage_status": "partial"}})
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )

    item = _item(plan, "P36")
    assert item["plan_status"] == "refresh_candidate"
    assert item["priority"] in {"medium", "high"}
    assert "freshness_stale" in item["reason_codes"]


def test_provider_degraded_allows_candidate_with_warning(tmp_path: Path):
    monitor = _monitor(phase_overrides={"P37": {"freshness_status": "stale", "coverage_status": "partial"}})
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_degraded"),
    )

    item = _item(plan, "P37")
    assert item["plan_status"] == "refresh_candidate"
    assert "market_data_provider_degraded" in item["warnings"]


def test_invalid_phase_becomes_blocked_invalid_artifact(tmp_path: Path):
    monitor = _monitor(phase_overrides={"P42": {"freshness_status": "invalid", "coverage_status": "invalid"}})
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )

    item = _item(plan, "P42")
    assert item["plan_status"] == "blocked_invalid_artifact"
    assert "freshness_invalid" in item["reason_codes"]


def test_non_market_phase_does_not_require_provider(tmp_path: Path):
    monitor = _monitor(phase_overrides={"P38": {"freshness_status": "stale", "coverage_status": "partial"}})
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_unavailable"),
    )

    assert _item(plan, "P38")["plan_status"] == "refresh_candidate"


def test_source_hash_changes_when_provider_hash_changes(tmp_path: Path):
    monitor = _monitor(phase_overrides={"P36": {"freshness_status": "stale", "coverage_status": "partial"}})
    first = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )
    second_provider = _provider("provider_ready")
    second_provider["source_hash"] = "changed"
    second = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=second_provider,
    )

    assert first["source_hash"] != second["source_hash"]


def test_writer_emits_json_and_markdown(tmp_path: Path):
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=_monitor(),
        provider_report=_provider("provider_ready"),
    )

    paths = write_evidence_refresh_plan_artifacts(plan, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p46_evidence_refresh_plan.json"
    assert paths["md"].name == "p46_evidence_refresh_plan.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == P46_SCHEMA_VERSION


def test_markdown_rejects_forbidden_language():
    from agent.research_v1.evidence_refresh_planner import _markdown

    plan = {
        "as_of_date": "2026-04-30",
        "status": "refresh_plan_ready",
        "items": [],
        "selected_monitor": {},
        "selected_provider_readiness": {},
        "summary": {},
        "disclaimer": "buy this now",
    }
    with pytest.raises(ValueError, match="forbidden"):
        _markdown(plan)
```

- [ ] **Step 2: Run tests and verify failure**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_refresh_planner.py -q
```

Expected: import failure for `agent.research_v1.evidence_refresh_planner`.

- [ ] **Step 3: Implement core module**

Create `agent/research_v1/evidence_refresh_planner.py`:

```python
"""P46 controlled evidence refresh planner."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

P46_SCHEMA_VERSION = "p46_evidence_refresh_plan.1"

STATUS_READY = "refresh_plan_ready"
STATUS_BLOCKED = "refresh_plan_blocked"
STATUS_NOOP = "refresh_plan_noop"
STATUS_INVALID_INPUT = "blocked_invalid_input"

P46_DISCLAIMER = (
    "P46 is a dry-run evidence refresh planner only. It does not refresh evidence, "
    "call market-data providers, submit orders, approve production adoption, train "
    "models, schedule jobs, or mutate research decisions."
)

FORBIDDEN_TERMS = (
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

PHASES = {
    "P36": ("recommendation_outcomes", "p36_recommendation_outcomes.json"),
    "P37": ("market_regime", "p37_market_regime_snapshot.json"),
    "P38": ("fundamental_quality", "p38_fundamental_quality.json"),
    "P39": ("candidate_pool", "p39_candidate_pool.json"),
    "P40": ("research_memory", "p40_research_memory_pack.json"),
    "P41": ("decision_journal", "p41_decision_journal.json"),
    "P42": ("boss_copilot_brief", "p42_boss_copilot_daily_brief.json"),
    "P43": ("copilot_console_index", "p43_copilot_console_index.json"),
    "P44": ("evidence_freshness_drift_monitor", "p44_evidence_freshness_drift_monitor.json"),
    "P45": ("market_data_readiness", "p45_market_data_readiness.json"),
}

MARKET_DATA_PHASES = {"P36", "P37", "P39", "P42"}

STATUS_ORDER = {
    "refresh_candidate": 0,
    "blocked_invalid_artifact": 1,
    "blocked_provider_unavailable": 2,
    "blocked_missing_monitor": 3,
    "blocked_missing_inputs": 4,
    "defer_no_action": 5,
}


def _sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _priority(score: int) -> str:
    if score >= 100:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 1:
        return "low"
    return "none"


def _command(phase_id: str, as_of_date: str) -> str:
    mapping = {
        "P36": f"python -m agent.research_v1.batch_cli outcome-run --as-of-date {as_of_date}",
        "P37": f"python -m agent.research_v1.batch_cli market-regime-run --as-of-date {as_of_date}",
        "P38": f"python -m agent.research_v1.batch_cli fundamental-quality-run --as-of-date {as_of_date} --input <path>",
        "P39": f"python -m agent.research_v1.batch_cli candidate-pool-run --as-of-date {as_of_date} --universe <path>",
        "P40": f"python -m agent.research_v1.batch_cli research-memory-run --as-of-date {as_of_date} --ticker <ticker>",
        "P41": f"python -m agent.research_v1.batch_cli decision-journal-run --as-of-date {as_of_date} --input <path>",
        "P42": f"python -m agent.research_v1.batch_cli boss-copilot-brief-run --as-of-date {as_of_date}",
        "P43": f"python -m agent.research_v1.batch_cli copilot-console-index-run --as-of-date {as_of_date}",
        "P44": f"python -m agent.research_v1.batch_cli evidence-monitor-run --as-of-date {as_of_date}",
        "P45": f"python -m agent.research_v1.batch_cli market-data-readiness-run --as-of-date {as_of_date} --live",
    }
    return mapping[phase_id]


def _reason_codes(phase: dict[str, Any], missing_context_keys: set[str]) -> list[str]:
    reasons: list[str] = []
    if phase.get("freshness_status") == "missing":
        reasons.append("freshness_missing")
    if phase.get("freshness_status") == "stale":
        reasons.append("freshness_stale")
    if phase.get("freshness_status") == "invalid":
        reasons.append("freshness_invalid")
    if phase.get("coverage_status") == "missing":
        reasons.append("coverage_missing")
    if phase.get("coverage_status") == "partial":
        reasons.append("coverage_partial")
    if phase.get("coverage_status") == "invalid":
        reasons.append("coverage_invalid")
    if phase.get("churn_status") == "high_churn":
        reasons.append("churn_high")
    phase_name = str(phase.get("phase_name", ""))
    artifact = PHASES.get(str(phase.get("phase_id")), ("", ""))[1]
    if phase_name in missing_context_keys or artifact in missing_context_keys:
        reasons.append("missing_context_pattern")
    return sorted(set(reasons))


def _score(reasons: list[str], provider_status: str, market_data_phase: bool) -> int:
    if market_data_phase and provider_status in {"provider_unavailable", "provider_not_tested_live", ""}:
        return 0
    weights = {
        "freshness_invalid": 100,
        "coverage_invalid": 100,
        "freshness_missing": 90,
        "coverage_missing": 80,
        "freshness_stale": 60,
        "coverage_partial": 45,
        "churn_high": 35,
        "missing_context_pattern": 20,
    }
    score = sum(weights.get(reason, 0) for reason in reasons)
    if market_data_phase and provider_status == "provider_degraded":
        score = max(0, score - 15)
    return score


def _plan_item(phase_id: str, phase: dict[str, Any], provider_status: str, missing_context_keys: set[str], as_of_date: str) -> dict[str, Any]:
    phase_name, artifact_name = PHASES[phase_id]
    reasons = _reason_codes(phase, missing_context_keys)
    market_data_phase = phase_id in MARKET_DATA_PHASES
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    plan_status = "defer_no_action"
    if "freshness_invalid" in reasons or "coverage_invalid" in reasons:
        plan_status = "blocked_invalid_artifact"
        blocking_reasons.append("inspect_invalid_artifact_first")
    elif market_data_phase and provider_status in {"provider_unavailable", "provider_not_tested_live", ""}:
        plan_status = "blocked_provider_unavailable"
        blocking_reasons.append(provider_status or "provider_missing")
    elif reasons:
        plan_status = "refresh_candidate"
    if market_data_phase and provider_status == "provider_degraded" and plan_status == "refresh_candidate":
        warnings.append("market_data_provider_degraded")

    command = _command(phase_id, as_of_date)
    required_inputs = []
    if "<path>" in command:
        required_inputs.append("operator_input_path")
    if "<ticker>" in command:
        required_inputs.append("ticker")
    if plan_status == "refresh_candidate" and required_inputs:
        plan_status = "blocked_missing_inputs"
        blocking_reasons.extend(required_inputs)

    priority_score = _score(reasons, provider_status, market_data_phase)
    return {
        "item_id": f"{phase_id.lower()}-{_sha({'phase_id': phase_id, 'reasons': reasons})[:8]}",
        "phase_id": phase_id,
        "phase_name": phase_name,
        "artifact_name": artifact_name,
        "plan_status": plan_status,
        "priority": _priority(priority_score if plan_status == "refresh_candidate" else 0),
        "priority_score": priority_score if plan_status == "refresh_candidate" else 0,
        "reason_codes": reasons,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "warnings": sorted(set(warnings)),
        "manual_command": command,
        "required_inputs": required_inputs,
        "latest_evidence_date": phase.get("latest_evidence_date", ""),
        "latest_source_hash": phase.get("latest_source_hash", ""),
        "source_refs": {"monitor_phase": phase},
    }


def build_evidence_refresh_plan(
    *,
    as_of_date: str,
    lookback_days: int,
    max_items: int,
    monitor_report: dict[str, Any] | None,
    provider_report: dict[str, Any] | None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    provider_status = (provider_report or {}).get("status", "")
    if monitor_report is None:
        for phase_id in PHASES:
            items.append({
                "item_id": f"{phase_id.lower()}-missing-monitor",
                "phase_id": phase_id,
                "phase_name": PHASES[phase_id][0],
                "artifact_name": PHASES[phase_id][1],
                "plan_status": "blocked_missing_monitor",
                "priority": "none",
                "priority_score": 0,
                "reason_codes": ["monitor_missing"],
                "blocking_reasons": ["missing_p44_monitor"],
                "warnings": [],
                "manual_command": _command("P44", as_of_date),
                "required_inputs": [],
                "latest_evidence_date": "",
                "latest_source_hash": "",
                "source_refs": {},
            })
    else:
        missing_context_keys = {str(item.get("key")) for item in monitor_report.get("missing_context_patterns", [])}
        phase_map = {phase["phase_id"]: phase for phase in monitor_report.get("phase_monitors", [])}
        for phase_id in [p for p in PHASES if p not in {"P44", "P45"}]:
            phase = phase_map.get(phase_id, {
                "phase_id": phase_id,
                "phase_name": PHASES[phase_id][0],
                "freshness_status": "missing",
                "coverage_status": "missing",
                "churn_status": "unknown",
            })
            items.append(_plan_item(phase_id, phase, provider_status, missing_context_keys, as_of_date))
        if monitor_report.get("status") in {"monitor_red", "monitor_yellow"}:
            pseudo = {"phase_id": "P44", "phase_name": PHASES["P44"][0], "freshness_status": "stale", "coverage_status": "partial", "churn_status": "unknown"}
            items.append(_plan_item("P44", pseudo, provider_status, missing_context_keys, as_of_date))
        if provider_report is None or provider_status in {"provider_unavailable", "provider_not_tested_live", "provider_degraded"}:
            pseudo = {"phase_id": "P45", "phase_name": PHASES["P45"][0], "freshness_status": "stale", "coverage_status": "partial", "churn_status": "unknown"}
            items.append(_plan_item("P45", pseudo, provider_status, missing_context_keys, as_of_date))

    items = sorted(items, key=lambda item: (STATUS_ORDER.get(item["plan_status"], 99), -item["priority_score"], item["phase_id"]))[:max_items]
    candidate_count = sum(1 for item in items if item["plan_status"] == "refresh_candidate")
    blocked_count = sum(1 for item in items if item["plan_status"].startswith("blocked_"))
    if candidate_count:
        status = STATUS_READY
    elif blocked_count:
        status = STATUS_BLOCKED
    else:
        status = STATUS_NOOP

    selected_monitor = {
        "report_id": (monitor_report or {}).get("report_id", ""),
        "status": (monitor_report or {}).get("status", ""),
        "source_hash": (monitor_report or {}).get("source_hash", ""),
    }
    selected_provider = {
        "report_id": (provider_report or {}).get("report_id", ""),
        "status": provider_status,
        "source_hash": (provider_report or {}).get("source_hash", ""),
    }
    seed = {
        "schema_version": P46_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "max_items": max_items,
        "selected_monitor": selected_monitor,
        "selected_provider_readiness": selected_provider,
        "items": items,
    }
    source_hash = _sha(seed)
    plan_id = hashlib.sha256(f"{as_of_date}|{lookback_days}|{max_items}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": P46_SCHEMA_VERSION,
        "plan_id": plan_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "lookback_days": lookback_days,
        "max_items": max_items,
        "selected_monitor": selected_monitor,
        "selected_provider_readiness": selected_provider,
        "items": items,
        "summary": {"candidate_count": candidate_count, "blocked_count": blocked_count, "item_count": len(items)},
        "source_hash": source_hash,
        "disclaimer": P46_DISCLAIMER,
    }


def _check_forbidden(text: str) -> None:
    lowered = text.lower()
    for term in FORBIDDEN_TERMS:
        if term in lowered:
            raise ValueError(f"forbidden evidence refresh planner term rendered: {term}")


def _markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# P46 Evidence Refresh Plan",
        "",
        f"As of: `{plan.get('as_of_date', '')}`",
        f"Status: `{plan.get('status', '')}`",
        "",
        "## Selected Evidence",
        "",
        f"- P44: `{(plan.get('selected_monitor') or {}).get('status', '')}` / `{(plan.get('selected_monitor') or {}).get('source_hash', '')}`",
        f"- P45: `{(plan.get('selected_provider_readiness') or {}).get('status', '')}` / `{(plan.get('selected_provider_readiness') or {}).get('source_hash', '')}`",
        "",
        "## Refresh Candidates",
        "",
        "| Phase | Priority | Score | Reasons | Command |",
        "|-------|----------|-------|---------|---------|",
    ]
    candidates = [item for item in plan.get("items", []) if item.get("plan_status") == "refresh_candidate"]
    if candidates:
        for item in candidates:
            lines.append(f"| {item['phase_id']} | {item['priority']} | {item['priority_score']} | {', '.join(item['reason_codes'])} | `{item['manual_command']}` |")
    else:
        lines.append("| none | none | 0 | none | none |")
    lines.extend(["", "## Blocked Items", "", "| Phase | Status | Blocking Reasons |", "|-------|--------|------------------|"])
    blocked = [item for item in plan.get("items", []) if str(item.get("plan_status", "")).startswith("blocked_")]
    if blocked:
        for item in blocked:
            lines.append(f"| {item['phase_id']} | {item['plan_status']} | {', '.join(item['blocking_reasons'])} |")
    else:
        lines.append("| none | none | none |")
    lines.extend(["", "---", "", f"> {plan.get('disclaimer', P46_DISCLAIMER)}", ""])
    text = "\n".join(lines)
    _check_forbidden(text)
    return text


def write_evidence_refresh_plan_artifacts(plan: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p46_evidence_refresh_plan.json"
    md_path = output_dir / "p46_evidence_refresh_plan.md"
    json_path.write_text(json.dumps(plan, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(plan), encoding="utf-8")
    return {"json": json_path, "md": md_path}
```

- [ ] **Step 4: Run core tests**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_refresh_planner.py -q
```

Expected: tests in Task 1 pass.

- [ ] **Step 5: Commit P46-A**

```bash
git add agent/research_v1/evidence_refresh_planner.py tests/agent/research_v1/test_evidence_refresh_planner.py
git commit -m "feat: add evidence refresh planner"
```

---

## Task 2: P46-B Persistence And Runtime

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `agent/research_v1/evidence_refresh_planner.py`
- Test: `tests/agent/research_v1/test_evidence_refresh_planner.py`

- [ ] **Step 1: Add persistence/runtime tests**

Append:

```python
from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.evidence_refresh_planner import run_evidence_refresh_planner


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    return db


def test_evidence_refresh_plan_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=_monitor(phase_overrides={"P36": {"freshness_status": "stale", "coverage_status": "partial"}}),
        provider_report=_provider("provider_ready"),
    )

    first = db.save_evidence_refresh_plan(plan)
    second = db.save_evidence_refresh_plan(plan)
    rows = db.list_evidence_refresh_plans(as_of_date="2026-04-30")

    assert first == second
    assert len(rows) == 1


def test_evidence_refresh_plan_revised_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=_monitor(phase_overrides={"P36": {"freshness_status": "stale", "coverage_status": "partial"}}),
        provider_report=_provider("provider_ready"),
    )
    second = dict(first)
    second["source_hash"] = "revised"
    second["plan_id"] = "revised-plan"

    db.save_evidence_refresh_plan(first)
    db.save_evidence_refresh_plan(second)
    rows = db.list_evidence_refresh_plans(as_of_date="2026-04-30")

    assert len(rows) == 2


def test_runtime_rejects_invalid_date(tmp_path: Path):
    db = _db(tmp_path)
    result = run_evidence_refresh_planner(
        db=db,
        governance_root=tmp_path / "output" / "governance",
        output_root=tmp_path / "output" / "governance",
        as_of_date="not-a-date",
        lookback_days=14,
        max_items=12,
    )

    assert result["status"] == "blocked_invalid_input"


def test_runtime_rejects_non_directory_governance_root(tmp_path: Path):
    db = _db(tmp_path)
    root = tmp_path / "governance"
    root.write_text("not-dir", encoding="utf-8")
    result = run_evidence_refresh_planner(
        db=db,
        governance_root=root,
        output_root=tmp_path / "output",
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
    )

    assert result["status"] == "blocked_invalid_input"
    assert "governance_root_not_a_directory" in result["warnings"]


def test_runtime_writes_and_persists_from_latest_db_reports(tmp_path: Path):
    db = _db(tmp_path)
    monitor = _monitor(phase_overrides={"P36": {"freshness_status": "stale", "coverage_status": "partial"}})
    provider = _provider("provider_ready")
    db.save_evidence_freshness_drift_report({
        "report_id": monitor["report_id"],
        "schema_version": monitor["schema_version"],
        "as_of_date": monitor["as_of_date"],
        "created_at": "2026-04-30T12:00:00+00:00",
        "status": monitor["status"],
        "lookback_days": 14,
        "freshness_days": 3,
        "summary": {"phase_count": 8, "red_count": 0, "yellow_count": 1},
        "source_hash": monitor["source_hash"],
        **monitor,
    })
    db.save_market_data_readiness_report({
        "report_id": provider["report_id"],
        "schema_version": provider["schema_version"],
        "as_of_date": provider["as_of_date"],
        "created_at": "2026-04-30T12:00:00+00:00",
        "status": provider["status"],
        "host": "127.0.0.1",
        "port": 11111,
        "symbols": ["US.AAPL"],
        "history_days": 30,
        "option_symbol": "US.AAPL",
        "live": True,
        "source_hash": provider["source_hash"],
        **provider,
    })

    result = run_evidence_refresh_planner(
        db=db,
        governance_root=tmp_path / "output" / "governance",
        output_root=tmp_path / "output" / "governance",
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
    )

    assert result["status"] == "refresh_plan_ready"
    assert Path(result["output_dir"]).joinpath("p46_evidence_refresh_plan.json").exists()
    assert len(db.list_evidence_refresh_plans(as_of_date="2026-04-30")) == 1
```

- [ ] **Step 2: Add database helpers**

In `agent/research_v1/data/database.py`, add:

```python
    # ── P46 Evidence Refresh Planner ────────────────────────────────────

    def initialize_evidence_refresh_plan_schema(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_refresh_plans (
                plan_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                lookback_days INTEGER NOT NULL,
                max_items INTEGER NOT NULL,
                candidate_count INTEGER NOT NULL,
                blocked_count INTEGER NOT NULL,
                source_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                UNIQUE(as_of_date, lookback_days, max_items, source_hash)
            )
        """)
        conn.commit()
        conn.close()

    def save_evidence_refresh_plan(self, plan: dict) -> str:
        self.initialize_evidence_refresh_plan_schema()
        summary = plan.get("summary", {})
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR IGNORE INTO evidence_refresh_plans (
                plan_id, schema_version, as_of_date, created_at, status,
                lookback_days, max_items, candidate_count, blocked_count,
                source_hash, plan_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                plan["plan_id"],
                plan["schema_version"],
                plan["as_of_date"],
                plan.get("created_at", ""),
                plan.get("status", ""),
                int(plan.get("lookback_days", 0)),
                int(plan.get("max_items", 0)),
                int(summary.get("candidate_count", 0)),
                int(summary.get("blocked_count", 0)),
                plan["source_hash"],
                json.dumps(plan, sort_keys=True, default=str),
            ),
        )
        conn.commit()
        conn.close()
        return plan["plan_id"]

    def list_evidence_refresh_plans(self, as_of_date: str | None = None, limit: int = 20) -> list[dict]:
        self.initialize_evidence_refresh_plan_schema()
        conn = self._get_connection()
        cursor = conn.cursor()
        if as_of_date:
            cursor.execute(
                """SELECT * FROM evidence_refresh_plans
                   WHERE as_of_date = ?
                   ORDER BY created_at DESC, plan_id ASC
                   LIMIT ?""",
                (as_of_date, limit),
            )
        else:
            cursor.execute(
                """SELECT * FROM evidence_refresh_plans
                   ORDER BY as_of_date DESC, created_at DESC, plan_id ASC
                   LIMIT ?""",
                (limit,),
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def latest_evidence_freshness_drift_report_as_of(self, as_of_date: str) -> dict | None:
        self.initialize_evidence_freshness_drift_schema()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT report_json FROM evidence_freshness_drift_reports
               WHERE as_of_date <= ?
               ORDER BY as_of_date DESC, created_at DESC, report_id ASC
               LIMIT 1""",
            (as_of_date,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return json.loads(dict(row)["report_json"])

    def latest_market_data_readiness_report_as_of(self, as_of_date: str) -> dict | None:
        self.initialize_market_data_readiness_schema()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT report_json FROM market_data_readiness_reports
               WHERE as_of_date <= ?
               ORDER BY as_of_date DESC, created_at DESC, report_id ASC
               LIMIT 1""",
            (as_of_date,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return json.loads(dict(row)["report_json"])
```

- [ ] **Step 3: Add artifact fallback and runtime**

Append to `evidence_refresh_planner.py`:

```python
def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _load_artifact_as_of(root: Path, as_of_date: str, lookback_days: int, filename: str) -> dict | None:
    base = Path(root)
    for offset in range(lookback_days + 1):
        day = (_parse_date(as_of_date) - timedelta(days=offset)).isoformat()
        path = base / day / filename
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None
    return None


def run_evidence_refresh_planner(
    *,
    db: Any,
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    lookback_days: int = 14,
    max_items: int = 12,
) -> dict[str, Any]:
    try:
        _parse_date(as_of_date)
    except (ValueError, TypeError):
        return {"status": STATUS_INVALID_INPUT, "warnings": ["invalid_date_format"]}
    if lookback_days <= 0:
        return {"status": STATUS_INVALID_INPUT, "warnings": ["lookback_days_must_be_positive"]}
    if max_items <= 0:
        return {"status": STATUS_INVALID_INPUT, "warnings": ["max_items_must_be_positive"]}
    root = Path(governance_root)
    if root.exists() and not root.is_dir():
        return {"status": STATUS_INVALID_INPUT, "warnings": ["governance_root_not_a_directory"]}

    monitor = None
    provider = None
    if hasattr(db, "latest_evidence_freshness_drift_report_as_of"):
        monitor = db.latest_evidence_freshness_drift_report_as_of(as_of_date)
    if hasattr(db, "latest_market_data_readiness_report_as_of"):
        provider = db.latest_market_data_readiness_report_as_of(as_of_date)
    monitor = monitor or _load_artifact_as_of(root, as_of_date, lookback_days, "p44_evidence_freshness_drift_monitor.json")
    provider = provider or _load_artifact_as_of(root, as_of_date, lookback_days, "p45_market_data_readiness.json")

    plan = build_evidence_refresh_plan(
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        max_items=max_items,
        monitor_report=monitor,
        provider_report=provider,
    )
    if hasattr(db, "save_evidence_refresh_plan"):
        db.save_evidence_refresh_plan(plan)
    output_dir = Path(output_root) / as_of_date
    paths = write_evidence_refresh_plan_artifacts(plan, output_dir)
    return {
        "status": plan["status"],
        "output_dir": str(output_dir),
        "plan_id": plan["plan_id"],
        "candidate_count": plan["summary"]["candidate_count"],
        "blocked_count": plan["summary"]["blocked_count"],
        "paths": paths,
    }
```

- [ ] **Step 4: Run tests**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_refresh_planner.py -q
```

Expected: focused P46 tests pass.

- [ ] **Step 5: Commit P46-B**

```bash
git add agent/research_v1/data/database.py agent/research_v1/evidence_refresh_planner.py tests/agent/research_v1/test_evidence_refresh_planner.py
git commit -m "feat: persist evidence refresh plans"
```

---

## Task 3: P46-C CLI

**Files:**
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Add CLI tests**

Append to `tests/agent/research_v1/test_batch_cli.py`:

```python
def test_evidence_refresh_plan_cli_success(monkeypatch, tmp_path, capsys):
    from agent.research_v1 import batch_cli as app

    app_root = tmp_path
    (app_root / "data").mkdir()

    def fake_run(**kwargs):
        return {
            "status": "refresh_plan_ready",
            "output_dir": str(app_root / "output" / "governance" / "2026-04-30"),
            "plan_id": "plan1",
            "candidate_count": 2,
            "blocked_count": 1,
            "paths": {},
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_evidence_refresh_planner", fake_run)
    code = app.main(["--app-root", str(app_root), "evidence-refresh-plan-run", "--as-of-date", "2026-04-30"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Evidence refresh plan status: refresh_plan_ready" in out
    assert "Candidate count: 2" in out


def test_evidence_refresh_plan_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1 import batch_cli as app

    code = app.main(["--app-root", str(tmp_path), "evidence-refresh-plan-run", "--as-of-date", "not-a-date"])

    assert code == 2
    assert "invalid evidence-refresh-plan-run input" in capsys.readouterr().out


def test_evidence_refresh_plan_cli_rejects_non_positive_max_items(tmp_path, capsys):
    from agent.research_v1 import batch_cli as app

    code = app.main(["--app-root", str(tmp_path), "evidence-refresh-plan-run", "--as-of-date", "2026-04-30", "--max-items", "0"])

    assert code == 2
    assert "max-items must be positive" in capsys.readouterr().out
```

- [ ] **Step 2: Wire CLI**

In `batch_cli.py`, import:

```python
from agent.research_v1.evidence_refresh_planner import run_evidence_refresh_planner
```

Add handler:

```python
def _cmd_evidence_refresh_plan_run(
    paths: HermesPaths,
    as_of_date: str,
    lookback_days: int,
    max_items: int,
    governance_root: str,
    output_root: str,
) -> int:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid evidence-refresh-plan-run input: invalid date format '{as_of_date}'")
        return 2
    if lookback_days <= 0:
        print("invalid evidence-refresh-plan-run input: lookback-days must be positive")
        return 2
    if max_items <= 0:
        print("invalid evidence-refresh-plan-run input: max-items must be positive")
        return 2
    governance_path = Path(governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path
    database = _ensure_database(paths)
    result = run_evidence_refresh_planner(
        db=database,
        governance_root=governance_path.resolve(),
        output_root=output_path.resolve(),
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        max_items=max_items,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid evidence-refresh-plan-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Evidence refresh plan status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Plan id: {result['plan_id']}")
    print(f"Candidate count: {result['candidate_count']}")
    print(f"Blocked count: {result['blocked_count']}")
    return 0
```

Add parser:

```python
    refresh_parser = subparsers.add_parser("evidence-refresh-plan-run", help="Run controlled evidence refresh planner.")
    refresh_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
    refresh_parser.add_argument("--lookback-days", default=14, type=int, help="Number of calendar days to inspect.")
    refresh_parser.add_argument("--max-items", default=12, type=int, help="Maximum plan items.")
    refresh_parser.add_argument("--governance-root", default="output/governance", help="Governance artifact root.")
    refresh_parser.add_argument("--output-root", default="output/governance", help="Output root for refresh plan artifacts.")
```

Add dispatch:

```python
    if args.command == "evidence-refresh-plan-run":
        return _cmd_evidence_refresh_plan_run(
            paths,
            as_of_date=args.as_of_date,
            lookback_days=args.lookback_days,
            max_items=args.max_items,
            governance_root=args.governance_root,
            output_root=args.output_root,
        )
```

- [ ] **Step 3: Run CLI tests**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "evidence_refresh_plan or evidence-refresh-plan"
```

Expected: P46 CLI tests pass.

- [ ] **Step 4: Commit P46-C**

```bash
git add agent/research_v1/batch_cli.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add evidence refresh planner cli"
```

---

## Task 4: P46-D Documentation

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update root README**

Add:

~~~markdown
### P46 — Controlled Evidence Refresh Planner

P46 consumes the latest P44 evidence freshness/drift monitor and P45 Futu market-data readiness report, then writes a dry-run refresh plan:

```text
output/governance/YYYY-MM-DD/p46_evidence_refresh_plan.json
output/governance/YYYY-MM-DD/p46_evidence_refresh_plan.md
```

Example:

```bash
/opt/homebrew/bin/python3.11 -m agent.research_v1.batch_cli evidence-refresh-plan-run \
  --as-of-date 2026-04-30 \
  --lookback-days 14 \
  --max-items 12
```

P46 does not refresh evidence, call market-data providers, schedule jobs, or mutate prior evidence. It only produces a manual plan.
~~~

- [ ] **Step 2: Update research README**

Add to data flow:

~~~markdown
P46 sits after P44/P45. P44 says which evidence is stale or missing; P45 says whether Futu market data is ready; P46 converts both into a dry-run manual refresh plan without executing any command.
~~~

- [ ] **Step 3: Run doc standards**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Expected: pass.

- [ ] **Step 4: Commit P46-D**

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p46 evidence refresh planner"
```

---

## Final Verification

Run focused P46:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_refresh_planner.py -q
```

Run P46 CLI:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "evidence_refresh_plan or evidence-refresh-plan"
```

Run P36-P45 regression:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_recommendation_outcomes.py \
  tests/agent/research_v1/test_market_regime_context.py \
  tests/agent/research_v1/test_fundamental_quality.py \
  tests/agent/research_v1/test_candidate_pool.py \
  tests/agent/research_v1/test_research_memory_pack.py \
  tests/agent/research_v1/test_decision_journal_guardrails.py \
  tests/agent/research_v1/test_boss_copilot_daily_brief.py \
  tests/agent/research_v1/test_copilot_console_index.py \
  tests/agent/research_v1/test_evidence_freshness_drift_monitor.py \
  tests/agent/research_v1/test_market_data_readiness.py \
  -q
```

Run governance-adjacent:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_governance_runtime.py \
  tests/agent/research_v1/test_boss_governance_brief.py \
  tests/agent/research_v1/test_signal_family_edge_review.py \
  -q
```

Run docs:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Run diff check:

```bash
git diff --check
```

## Final Report Template

Return:

```text
P46 Implementation Complete

Status Summary
Phase   Status   Commit
P46-A   PASS     <hash> feat: add evidence refresh planner
P46-B   PASS     <hash> feat: persist evidence refresh plans
P46-C   PASS     <hash> feat: add evidence refresh planner cli
P46-D   PASS     <hash> docs: document p46 evidence refresh planner

Verification
- P46 focused: <N> passed
- P46 CLI: <N> passed
- P36-P45 regression: <N> passed
- Governance-adjacent regression: <N> passed
- Doc standards: <N> passed
- Full P20-P46 chain: <N> passed, known host gaps listed separately

Hard Boundary Compliance
- no auto-trading
- no broker orders
- no production approval
- no production config mutation
- no model training
- no scheduling or notifications
- no viewer/server
- no Futu/provider calls
- no P36-P45 runtime invocation
- no P36-P45 evidence mutation
- no final_judge changes
- no HermesResearchApp.run invocation
- no CanonicalSignal or CanonicalReport creation
- no JudgeInputPacket mutation
```
