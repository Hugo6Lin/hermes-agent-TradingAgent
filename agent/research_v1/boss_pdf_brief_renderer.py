"""P50 boss-facing PDF brief renderer.

P50 reads existing P49 preview artifacts and renders a visual boss brief. It
does not run research, call providers, instruct trades, or change decisions.

P55 applies the V2.1 brief preview language to the rendered HTML/PDF:

* paper-memo letterhead and editorial spacing
* a top "10-second read" executive strip (verdict / price context / trusted
  evidence / evidence gaps / next review action)
* an evidence-gaps section that is always visible — never collapsed
* PDF-safe typography fallbacks (Georgia / system-ui / ui-monospace)
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Callable

P50_SCHEMA_VERSION = "p50_boss_pdf_brief.1"
P50_DISCLAIMER = (
    "This report is a research co-pilot preview. It does not approve production "
    "adoption, change recommendations, instruct trades, place orders, train "
    "models, schedule jobs, or mutate production configuration."
)
P50_STATUS_READY = "boss_pdf_brief_ready"
P50_STATUS_HTML_READY = "boss_pdf_brief_html_ready"
P50_STATUS_DEGRADED = "boss_pdf_brief_degraded"
P50_STATUS_BLOCKED = "boss_pdf_brief_blocked_invalid_input"
TICKER_RE = re.compile(r"^(US\.)?[A-Z0-9._-]{1,20}$|^HK\.\d{5}$")

OPTIONAL_ARTIFACTS = (
    "p45_market_data_readiness.json",
    "p37_market_regime_snapshot.json",
    "p38_fundamental_quality.json",
    "p39_candidate_pool.json",
    "p40_research_memory_pack.json",
    "p41_decision_journal.json",
    "p42_boss_copilot_daily_brief.json",
    "p44_evidence_freshness_drift_monitor.json",
    "p46_evidence_refresh_plan.json",
    "p47_research_context_pack.json",
    "p48_research_context_prompt_pack.json",
)

FORBIDDEN_MAIN_BODY_TERMS = (
    "canonical_recommendation_outcomes",
    "db_call_failed",
    "phase_failed",
    "artifact_paths",
    "provider_ready",
    "degraded_missing_inputs",
    "prompt_pack_limited",
    "buy this now",
    "sell this now",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "place order",
    "submit order",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def validate_boss_pdf_brief_inputs(
    preview_dir: Path,
    ticker: str,
    output_dir: Path | None,
    max_pages: int,
) -> dict[str, Any]:
    warnings: list[str] = []
    root = Path(preview_dir)
    normalized_ticker = str(ticker).strip().upper()
    if not root.exists():
        warnings.append("preview_dir_missing")
    elif not root.is_dir():
        warnings.append("preview_dir_not_directory")
    if not normalized_ticker or not TICKER_RE.match(normalized_ticker):
        warnings.append(f"invalid_ticker:{ticker}")
    if max_pages <= 0:
        warnings.append("max_pages_must_be_positive")
    if output_dir is not None and Path(output_dir).exists() and not Path(output_dir).is_dir():
        warnings.append("output_dir_not_directory")
    if warnings:
        return {"schema_version": P50_SCHEMA_VERSION, "status": P50_STATUS_BLOCKED, "warnings": warnings}
    return {"status": "valid", "ticker": normalized_ticker, "warnings": []}


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError:
        return None, f"invalid_json:{path.name}"
    except OSError as exc:
        return None, f"read_failed:{path.name}:{exc.__class__.__name__}"


def load_preview_artifacts(preview_dir: Path) -> dict[str, Any]:
    root = Path(preview_dir)
    warnings: list[str] = []
    artifacts: dict[str, Any] = {}
    boss_path = root / "boss_preview.json"
    if not boss_path.exists():
        return {"status": "blocked", "artifacts": {}, "warnings": ["missing:boss_preview.json"]}
    boss, warning = _read_json(boss_path)
    if warning or boss is None:
        return {"status": "blocked", "artifacts": {}, "warnings": [warning or "invalid:boss_preview.json"]}
    artifacts["boss_preview"] = boss
    for name in OPTIONAL_ARTIFACTS:
        key = name.removesuffix(".json")
        path = root / name
        if not path.exists():
            warnings.append(f"missing:{name}")
            continue
        payload, warning = _read_json(path)
        if warning:
            warnings.append(warning)
            continue
        artifacts[key] = payload
    return {"status": "loaded", "artifacts": artifacts, "warnings": warnings}


def _phase(artifacts: dict[str, Any], key: str) -> dict[str, Any]:
    value = artifacts.get(key)
    return value if isinstance(value, dict) else {}


def _live_data_status(p45: dict[str, Any], boss: dict[str, Any]) -> str:
    status = p45.get("status") or boss.get("live_status")
    if status == "provider_ready":
        return "Ready"
    if status:
        return "Limited"
    return "Missing"


def _evidence_base_status(artifacts: dict[str, Any], load_warnings: list[str]) -> str:
    boss = _phase(artifacts, "boss_preview")
    p44 = _phase(artifacts, "p44_evidence_freshness_drift_monitor")
    sample_used = "preview_sample_inputs_used" in boss.get("warnings", [])
    incomplete = p44.get("status") == "monitor_red" or any(w.startswith("missing:") for w in load_warnings)
    if sample_used and incomplete:
        return "Preview-only / Incomplete"
    if sample_used:
        return "Preview-only"
    if incomplete:
        return "Incomplete"
    return "Decision-grade"


def _guardrail_status(artifacts: dict[str, Any]) -> str:
    p41 = _phase(artifacts, "p41_decision_journal")
    p44 = _phase(artifacts, "p44_evidence_freshness_drift_monitor")
    if str(p41.get("status", "")).startswith("blocked"):
        return "Blocked"
    missing_patterns = p44.get("missing_context_patterns") or []
    entries = p41.get("entries") or []
    if missing_patterns or any(e.get("severity") in {"caution", "manual_review"} for e in entries if isinstance(e, dict)):
        return "Caution"
    return "Clear"


def _verdict(live_status: str, evidence_status: str, guardrail_status: str) -> str:
    if live_status == "Missing":
        return "Preview limited; refresh evidence first."
    if guardrail_status == "Blocked":
        return "Blocked: required preview evidence missing."
    if "Incomplete" in evidence_status:
        return "Usable preview, not decision-grade yet."
    if evidence_status == "Preview-only":
        return "Live data ready, evidence base incomplete."
    return "Usable preview, not decision-grade yet."


def _candidate_summary(p39: dict[str, Any], ticker: str) -> dict[str, Any]:
    candidates = p39.get("candidates") or []
    for candidate in candidates:
        if isinstance(candidate, dict) and str(candidate.get("ticker", "")).upper() == ticker:
            return {
                "ticker": ticker,
                "rank": candidate.get("rank"),
                "score": candidate.get("score"),
                "category": candidate.get("category") or candidate.get("label") or "unknown",
            }
    if p39.get("top_candidate"):
        return {
            "ticker": str(p39.get("top_candidate")).upper(),
            "rank": 1,
            "score": p39.get("score"),
            "category": p39.get("category", "unknown"),
        }
    return {"ticker": ticker, "rank": None, "score": None, "category": "unavailable"}


_EVIDENCE_MATRIX_ROWS = [
    ("P45", "p45_market_data_readiness", "Live Data"),
    ("P37", "p37_market_regime_snapshot", "Market Regime"),
    ("P38", "p38_fundamental_quality", "Fundamentals"),
    ("P39", "p39_candidate_pool", "Candidates"),
    ("P40", "p40_research_memory_pack", "Memory"),
    ("P41", "p41_decision_journal", "Guardrails"),
    ("P42", "p42_boss_copilot_daily_brief", "Daily Brief"),
    ("P44", "p44_evidence_freshness_drift_monitor", "Evidence Monitor"),
    ("P46", "p46_evidence_refresh_plan", "Refresh Plan"),
    ("P47", "p47_research_context_pack", "Context Pack"),
    ("P48", "p48_research_context_prompt_pack", "Prompt Pack"),
]


def _evidence_gap_status(artifacts: dict[str, Any], key: str, load_warnings: list[str]) -> str:
    if any(w == f"missing:{key}.json" for w in load_warnings):
        return "Missing"
    if any(w.startswith(f"invalid_json:{key}") for w in load_warnings):
        return "Blocked"
    payload = artifacts.get(key)
    if not isinstance(payload, dict):
        return "Missing"
    status = str(payload.get("status", ""))
    if status.startswith("blocked"):
        return "Blocked"
    if status in ("completed", "brief_ready", "provider_ready", "monitor_green"):
        return "Ready"
    if status == "monitor_red":
        return "Limited"
    if status == "monitor_yellow":
        return "Limited"
    if payload.get("_preview_sample") or "preview_sample" in status:
        return "Sample"
    if status:
        return "Limited"
    return "Missing"


def _build_evidence_gaps(artifacts: dict[str, Any], load_warnings: list[str]) -> list[dict[str, Any]]:
    gaps = []
    for phase_id, key, label in _EVIDENCE_MATRIX_ROWS:
        status = _evidence_gap_status(artifacts, key, load_warnings)
        gaps.append({"phase": phase_id, "label": label, "status": status})
    return gaps


def classify_boss_brief(
    artifacts: dict[str, Any],
    ticker: str,
    preview_dir: Path,
    load_warnings: list[str] | None = None,
) -> dict[str, Any]:
    warnings = list(load_warnings or [])
    boss = _phase(artifacts, "boss_preview")
    p45 = _phase(artifacts, "p45_market_data_readiness")
    p37 = _phase(artifacts, "p37_market_regime_snapshot")
    p39 = _phase(artifacts, "p39_candidate_pool")
    p44 = _phase(artifacts, "p44_evidence_freshness_drift_monitor")
    normalized_ticker = ticker.strip().upper()
    live_status = _live_data_status(p45, boss)
    evidence_status = _evidence_base_status(artifacts, warnings)
    guardrail_status = _guardrail_status(artifacts)
    verdict = _verdict(live_status, evidence_status, guardrail_status)
    candidate = _candidate_summary(p39, normalized_ticker)
    trusted = []
    not_decision_grade = []
    if live_status == "Ready":
        trusted.append("Live market data was available for the preview.")
    else:
        not_decision_grade.append("Live market data was limited or missing.")
    if p37.get("status") == "completed":
        trusted.append("Market regime was computed from available market proxies.")
    else:
        not_decision_grade.append("Market regime is unavailable or degraded.")
    if "Preview-only" in evidence_status:
        not_decision_grade.append("Fundamental/candidate/guardrail evidence includes preview sample inputs.")
    if p44.get("status") == "monitor_red":
        not_decision_grade.append("Evidence monitor is red; outcome history or context is missing.")
    evidence_gaps = _build_evidence_gaps(artifacts, warnings)
    source_seed = {"ticker": normalized_ticker, "artifacts": artifacts, "warnings": warnings}
    return {
        "schema_version": P50_SCHEMA_VERSION,
        "brief_id": f"p50-{normalized_ticker}-{_sha(source_seed)[:12]}",
        "ticker": normalized_ticker,
        "as_of_date": boss.get("as_of_date") or preview_dir.name,
        "created_at": _now(),
        "preview_dir": str(preview_dir),
        "verdict": verdict,
        "live_data_status": live_status,
        "market_regime_label": p37.get("regime_label", "Unavailable"),
        "market_regime_confidence": p37.get("confidence"),
        "evidence_base_status": evidence_status,
        "guardrail_status": guardrail_status,
        "candidate": candidate,
        "evidence_gaps": evidence_gaps,
        "trusted_points": trusted,
        "not_decision_grade_points": not_decision_grade,
        "next_actions": [
            "Load verified fundamentals before treating quality scores as decision-grade.",
            "Create or refresh recommendation outcome tracking for this ticker.",
            "Refresh evidence monitor after fundamentals and outcomes are populated.",
            "Use the full research pipeline only after the evidence base is ready.",
        ],
        "phase_statuses": {
            "P45": p45.get("status", "missing"),
            "P37": p37.get("status", "missing"),
            "P39": p39.get("status", "missing"),
            "P44": p44.get("status", "missing"),
        },
        "warnings": sorted(set(warnings + boss.get("warnings", []))),
        "source_hash": _sha(source_seed),
        "disclaimer": P50_DISCLAIMER,
    }


def _score_pct(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if number <= 1:
        number *= 100
    return max(0, min(100, int(round(number))))


def _badge_class(value: str) -> str:
    lower = (value or "").lower()
    if "ready" in lower or lower == "clear":
        return "ready"
    if "blocked" in lower or "missing" in lower:
        return "blocked"
    if "preview" in lower or "incomplete" in lower or "caution" in lower or "limited" in lower:
        return "limited"
    if "stale" in lower:
        return "stale"
    return "sample"


def _evidence_matrix_html(gaps: list[dict[str, Any]]) -> str:
    rows = []
    for gap in gaps:
        status = gap.get("status", "Missing")
        label = gap.get("label", "")
        badge_cls = _badge_class(status)
        rows.append(
            f'<tr><td>{escape(label)}</td>'
            f'<td><span class="badge {badge_cls}">{escape(status)}</span></td></tr>'
        )
    return "".join(rows)


def _evidence_gaps_detail_html(gaps: list[dict[str, Any]]) -> str:
    """Render the always-visible evidence-gaps detail table.

    Per V2.1 brief preview, evidence gaps must remain visible — never
    collapsed — and must surface a one-line reason when possible.
    """

    rows = []
    for gap in gaps:
        status = gap.get("status", "Missing")
        if status == "Ready":
            continue
        label = gap.get("label", "")
        badge_cls = _badge_class(status)
        if status == "Missing":
            reason = "Phase artifact not produced for this preview."
        elif status == "Blocked":
            reason = "Phase artifact present but reports a blocked state."
        elif status == "Sample":
            reason = "Preview sample inputs used — not decision-grade."
        elif status == "Limited":
            reason = "Phase produced but evidence is partial or degraded."
        else:
            reason = "Evidence is not in a ready state."
        rows.append(
            f'<tr>'
            f'<td><span class="badge {badge_cls}">{escape(status)}</span></td>'
            f'<td class="gap-label">{escape(label)}</td>'
            f'<td class="gap-reason">{escape(reason)}</td>'
            f'</tr>'
        )
    if not rows:
        return (
            '<tr><td colspan="3" class="gap-reason" '
            'style="color: var(--text-muted, #6b7785);">'
            'No outstanding evidence gaps detected.</td></tr>'
        )
    return "".join(rows)


def _ten_second_read(brief: dict[str, Any]) -> str:
    """Render the V2.1 top-third "10-second read" executive strip.

    Five cells, top to bottom of the brief:
      Verdict · Price context · Trusted evidence · Evidence gaps · Next review
    """

    gaps = brief.get("evidence_gaps", []) or []
    ready_count = sum(1 for g in gaps if g.get("status") == "Ready")
    gap_count = sum(1 for g in gaps if g.get("status") != "Ready")
    total = len(gaps)
    verdict = brief.get("verdict", "")
    live = brief.get("live_data_status", "Missing")
    regime_label = str(brief.get("market_regime_label", "Unavailable"))
    regime_confidence = _score_pct(brief.get("market_regime_confidence"))
    next_actions = brief.get("next_actions", []) or []
    next_review = next_actions[0] if next_actions else "Refresh evidence and re-grade."

    live_badge_cls = _badge_class(live)
    gap_badge_cls = "blocked" if gap_count else "ready"

    return f"""
    <section class="ten-second-read" aria-label="10-second read">
      <div class="cell">
        <div class="meta">Verdict</div>
        <div class="value verdict-text">{escape(verdict)}</div>
      </div>
      <div class="cell">
        <div class="meta">Price context</div>
        <div class="value mono"><span class="badge {live_badge_cls}">{escape(live)}</span></div>
        <div class="sub mono">Regime: {escape(regime_label)} · {regime_confidence}%</div>
      </div>
      <div class="cell">
        <div class="meta">Trusted evidence</div>
        <div class="value mono">{ready_count} of {total}</div>
        <div class="sub mono">Phases marked Ready</div>
      </div>
      <div class="cell">
        <div class="meta">Evidence gaps</div>
        <div class="value mono"><span class="badge {gap_badge_cls}">{gap_count} visible</span></div>
        <div class="sub mono">Detail below — not collapsed</div>
      </div>
      <div class="cell">
        <div class="meta">Next review action</div>
        <div class="value next-review">{escape(next_review)}</div>
      </div>
    </section>
    """


# ---------------------------------------------------------------------------
# Stylesheet — PDF-safe, single-file inline.
# ---------------------------------------------------------------------------

_BRIEF_STYLE = """
@page { size: Letter; margin: 0.55in; }
:root {
  --paper-bg: #fffaf0;
  --paper-deep: #fdf2dc;
  --ink: #1c1916;
  --secondary: #564f47;
  --muted: #6b7785;
  --border-soft: rgba(36, 33, 31, 0.10);
  --border-strong: rgba(36, 33, 31, 0.25);
  --accent-rust: #b5543e;
  --accent-blue: #2878bd;
  --status-ready: #2f7a55;
  --status-ready-bg: rgba(47, 122, 85, 0.10);
  --status-ready-border: rgba(47, 122, 85, 0.25);
  --status-limited: #b07a1f;
  --status-limited-bg: rgba(176, 122, 31, 0.12);
  --status-limited-border: rgba(176, 122, 31, 0.28);
  --status-blocked: #a13d3d;
  --status-blocked-bg: rgba(161, 61, 61, 0.10);
  --status-blocked-border: rgba(161, 61, 61, 0.26);
  --status-sample: #5d6573;
  --status-sample-bg: rgba(93, 101, 115, 0.10);
  --status-sample-border: rgba(93, 101, 115, 0.24);
  --status-stale: #876733;
  --status-stale-bg: rgba(135, 103, 51, 0.10);
  --status-stale-border: rgba(135, 103, 51, 0.26);
  --font-display: Georgia, "Times New Roman", "Iowan Old Style", serif;
  --font-ui: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  --font-data: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
}
* { box-sizing: border-box; }
body {
  font-family: var(--font-ui);
  color: var(--ink);
  margin: 0;
  background: #1f1c18;
}
main {
  max-width: 920px;
  margin: 0 auto;
  background: var(--paper-bg);
  padding: 48px 56px;
  background-image: radial-gradient(120% 80% at 0% 0%, #fff8ea 0%, var(--paper-bg) 100%);
}
.letterhead {
  display: flex; justify-content: space-between; align-items: flex-end;
  border-bottom: 2px solid var(--ink);
  padding-bottom: 12px;
}
.letterhead .wordmark {
  font-family: var(--font-display);
  font-size: 32px; font-weight: 500; letter-spacing: -0.02em;
  margin: 0;
}
.letterhead .memo-tag {
  font-size: 10.5px; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--secondary);
  margin-top: 4px;
}
.letterhead .paper-meta {
  text-align: right;
  font-family: var(--font-data);
  font-size: 11px; color: var(--muted);
}
.letterhead .paper-meta div { margin-bottom: 2px; }

.subject {
  display: grid; grid-template-columns: 1fr auto;
  gap: 24px; align-items: flex-end;
  margin-top: 24px;
}
.subject .meta-label {
  font-size: 10.5px; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted);
}
.subject h1 {
  font-family: var(--font-display);
  font-size: 36px; font-weight: 500; letter-spacing: -0.02em;
  margin: 4px 0 0;
}
.subject .as-of {
  font-family: var(--font-data); font-size: 12px; color: var(--muted);
  text-align: right;
}

.ten-second-read {
  margin-top: 24px;
  padding: 16px 18px;
  background: linear-gradient(180deg, #fff8e8 0%, var(--paper-deep) 100%);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  display: grid;
  grid-template-columns: 1.6fr 1fr 1fr 1fr 1.4fr;
  gap: 14px;
}
.ten-second-read .cell {
  border-right: 1px solid var(--border-soft);
  padding-right: 12px;
}
.ten-second-read .cell:last-child { border-right: 0; padding-right: 0; }
.ten-second-read .meta {
  font-size: 9.5px; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted);
}
.ten-second-read .value {
  font-family: var(--font-display);
  font-size: 15px; font-weight: 500;
  margin-top: 4px; line-height: 1.3;
}
.ten-second-read .value.mono { font-family: var(--font-data); font-size: 14px; font-weight: 600; }
.ten-second-read .sub {
  font-size: 11px; color: var(--muted); margin-top: 4px;
}

.verdict {
  font-size: 18px; font-weight: 700;
  padding: 14px 16px;
  background: rgba(40, 120, 189, 0.08);
  border-left: 5px solid var(--accent-blue);
  margin: 22px 0 16px;
}

.status-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
}
.card {
  border: 1px solid var(--border-soft);
  border-radius: 6px; padding: 12px;
  background: white;
}
.label {
  color: var(--muted); font-size: 11px;
  text-transform: uppercase; font-weight: 700; letter-spacing: 0.06em;
}
.score-bar {
  height: 8px; background: rgba(36,33,31,0.08);
  border-radius: 999px; overflow: hidden; margin-top: 8px;
}
.score-fill {
  height: 100%; background: var(--accent-blue);
  width: var(--score, 0%);
}

.split {
  display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
  margin-top: 12px;
}

.evidence-gaps-detail {
  border: 1px solid var(--status-limited-border);
  background: var(--status-limited-bg);
  border-radius: 6px;
  padding: 12px 14px;
}
.evidence-gaps-detail h2 { margin: 0 0 8px; }
.evidence-gaps-detail table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.evidence-gaps-detail td { padding: 7px 8px; vertical-align: top; }
.evidence-gaps-detail .gap-label { font-weight: 600; }
.evidence-gaps-detail .gap-reason { color: var(--secondary); }

.evidence-matrix { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }
.evidence-matrix td { border-bottom: 1px solid var(--border-soft); padding: 7px 8px; }
.evidence-matrix td:first-child { font-weight: 600; width: 220px; }

h2 {
  font-family: var(--font-display);
  font-size: 18px; font-weight: 500; letter-spacing: -0.005em;
  margin: 26px 0 8px;
  border-bottom: 1px solid var(--border-soft);
  padding-bottom: 4px;
}

ul, ol { margin-top: 8px; padding-left: 20px; }

.badge {
  display: inline-block;
  border-radius: 999px;
  padding: 3px 9px;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: 1px solid transparent;
  font-family: var(--font-ui);
}
.badge.ready    { color: var(--status-ready);   background: var(--status-ready-bg);   border-color: var(--status-ready-border); }
.badge.limited  { color: var(--status-limited); background: var(--status-limited-bg); border-color: var(--status-limited-border); }
.badge.blocked  { color: var(--status-blocked); background: var(--status-blocked-bg); border-color: var(--status-blocked-border); }
.badge.sample   { color: var(--status-sample);  background: var(--status-sample-bg);  border-color: var(--status-sample-border); }
.badge.stale    { color: var(--status-stale);   background: var(--status-stale-bg);   border-color: var(--status-stale-border); }

.appendix { page-break-before: always; }
.disclaimer {
  font-size: 10.5px; color: var(--muted); margin-top: 22px;
}
.footer-rule {
  margin-top: 28px; padding-top: 12px;
  border-top: 1px solid var(--border-soft);
  font-size: 10.5px; color: var(--muted);
  letter-spacing: 0.04em;
  display: flex; justify-content: space-between;
}
@media print {
  body { background: white; }
  main { box-shadow: none; padding: 0; }
}
"""


def render_boss_brief_html(brief: dict[str, Any]) -> str:
    ticker = escape(brief["ticker"])
    title = escape(brief.get("title") or f"{ticker} Boss Brief")
    candidate = brief.get("candidate", {})
    candidate_score = _score_pct(candidate.get("score"))
    regime_confidence = _score_pct(brief.get("market_regime_confidence"))
    trusted_items = "".join(
        f"<li>{escape(item)}</li>" for item in brief.get("trusted_points", [])
    ) or "<li>No trusted points available.</li>"
    limited_items = "".join(
        f"<li>{escape(item)}</li>" for item in brief.get("not_decision_grade_points", [])
    ) or "<li>No major evidence gaps detected.</li>"
    next_actions_html = "".join(
        f"<li>{escape(item)}</li>" for item in brief.get("next_actions", [])
    )
    phases = "".join(
        f"<tr><td>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>"
        for k, v in brief.get("phase_statuses", {}).items()
    )
    evidence_gaps = brief.get("evidence_gaps", []) or []
    evidence_matrix = _evidence_matrix_html(evidence_gaps)
    evidence_gaps_detail = _evidence_gaps_detail_html(evidence_gaps)
    ten_second_read = _ten_second_read(brief)

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <style>{_BRIEF_STYLE}</style>
</head>
<body>
<main>
  <header class="letterhead">
    <div>
      <div class="wordmark">Hermes</div>
      <div class="memo-tag">Boss brief · single-name memo</div>
    </div>
    <div class="paper-meta">
      <div>{escape(str(brief.get("brief_id", "")))}</div>
      <div>As of {escape(str(brief.get("as_of_date", "")))}</div>
      <div>Generated {escape(str(brief.get("created_at", "")))}</div>
    </div>
  </header>

  <section class="subject">
    <div>
      <div class="meta-label">Subject</div>
      <h1>{title}</h1>
    </div>
    <div class="as-of">
      <div class="meta-label">Status</div>
      <span class="badge {_badge_class(brief.get("evidence_base_status", ""))}">{escape(brief.get("evidence_base_status", ""))}</span>
    </div>
  </section>

  {ten_second_read}

  <div class="verdict">{escape(brief.get("verdict", ""))}</div>

  <section class="status-grid">
    <div class="card"><div class="label">Live Data</div><div style="margin-top:6px;"><span class="badge {_badge_class(brief.get("live_data_status", ""))}">{escape(brief.get("live_data_status", ""))}</span></div></div>
    <div class="card"><div class="label">Market Regime</div><strong style="display:block; margin-top:6px;">{escape(str(brief.get("market_regime_label", "Unavailable")))}</strong><div class="score-bar"><div class="score-fill" style="--score:{regime_confidence}%"></div></div></div>
    <div class="card"><div class="label">Evidence Base</div><div style="margin-top:6px;"><span class="badge {_badge_class(brief.get("evidence_base_status", ""))}">{escape(brief.get("evidence_base_status", ""))}</span></div></div>
    <div class="card"><div class="label">Guardrails</div><div style="margin-top:6px;"><span class="badge {_badge_class(brief.get("guardrail_status", ""))}">{escape(brief.get("guardrail_status", ""))}</span></div></div>
  </section>

  <h2>Candidate snapshot</h2>
  <div class="card">
    <strong>{escape(str(candidate.get("ticker", ticker)))}</strong> · Rank {escape(str(candidate.get("rank") or "n/a"))} · {escape(str(candidate.get("category", "unavailable")))}
    <div class="score-bar"><div class="score-fill" style="--score:{candidate_score}%"></div></div>
  </div>

  <h2>Trusted vs Not Decision-Grade Yet</h2>
  <div class="split">
    <div class="card"><h3 style="margin:0 0 6px;">Trusted</h3><ul>{trusted_items}</ul></div>
    <div class="card"><h3 style="margin:0 0 6px;">Not Decision-Grade Yet</h3><ul>{limited_items}</ul></div>
  </div>

  <h2>Evidence gaps · do not hide</h2>
  <div class="evidence-gaps-detail">
    <table>
      <thead>
        <tr>
          <th style="text-align:left; font-size:10.5px; color: var(--muted); text-transform:uppercase; letter-spacing:0.06em; padding-bottom:6px;">Status</th>
          <th style="text-align:left; font-size:10.5px; color: var(--muted); text-transform:uppercase; letter-spacing:0.06em; padding-bottom:6px;">Pillar</th>
          <th style="text-align:left; font-size:10.5px; color: var(--muted); text-transform:uppercase; letter-spacing:0.06em; padding-bottom:6px;">Reason</th>
        </tr>
      </thead>
      <tbody>{evidence_gaps_detail}</tbody>
    </table>
  </div>

  <h2>Next Actions</h2>
  <div class="card"><ol>{next_actions_html}</ol></div>

  <h2>Evidence Matrix</h2>
  <table class="evidence-matrix"><tbody>{evidence_matrix}</tbody></table>

  <div class="footer-rule">
    <span>Hermes · single-name memo · for boss desk only</span>
    <span>{escape(str(brief.get("brief_id", "")))}</span>
  </div>
</main>

<section class="appendix">
  <main>
    <h2>Appendix · Phase Status</h2>
    <table class="evidence-matrix"><tbody>{phases}</tbody></table>
    <p class="disclaimer">{escape(brief.get("disclaimer", P50_DISCLAIMER))}</p>
  </main>
</section>
</body>
</html>"""

    main_body = html.split('<section class="appendix">', 1)[0]
    for term in FORBIDDEN_MAIN_BODY_TERMS:
        if term in main_body:
            raise ValueError(f"forbidden_main_body_term:{term}")
    return html


def _default_pdf_renderer(html: str, pdf_path: Path) -> Path:
    from agent.research_v1.report_pdf import _write_html_to_pdf

    return _write_html_to_pdf(html, pdf_path)


def write_boss_brief_outputs(
    brief: dict[str, Any],
    output_dir: Path,
    render_pdf: bool = True,
    pdf_renderer: Callable[[str, Path], Path] | None = None,
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ticker = brief["ticker"]
    html_path = out / f"{ticker}_BOSS_BRIEF.html"
    pdf_path = out / f"{ticker}_BOSS_BRIEF.pdf"
    manifest_path = out / f"{ticker}_BOSS_BRIEF.json"
    html = render_boss_brief_html(brief)
    html_path.write_text(html, encoding="utf-8")
    result = dict(brief)
    result.update({
        "status": P50_STATUS_HTML_READY if not render_pdf else P50_STATUS_READY,
        "output_dir": str(out),
        "html_path": str(html_path),
        "pdf_path": "",
        "manifest_path": str(manifest_path),
    })
    warnings = list(result.get("warnings", []))
    if render_pdf:
        try:
            renderer = pdf_renderer or _default_pdf_renderer
            renderer(html, pdf_path)
            if not pdf_path.exists() or not pdf_path.read_bytes().startswith(b"%PDF-"):
                raise RuntimeError("invalid_pdf_output")
            result["pdf_path"] = str(pdf_path)
            result["status"] = P50_STATUS_READY
        except Exception as exc:
            warnings.append(f"pdf_render_failed:{exc.__class__.__name__}")
            result["status"] = P50_STATUS_DEGRADED
    result["warnings"] = sorted(set(warnings))
    manifest_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def run_boss_pdf_brief(
    preview_dir: Path,
    ticker: str,
    output_dir: Path | None = None,
    title: str | None = None,
    max_pages: int = 3,
    render_pdf: bool = True,
    pdf_renderer: Callable[[str, Path], Path] | None = None,
) -> dict[str, Any]:
    validation = validate_boss_pdf_brief_inputs(preview_dir, ticker, output_dir, max_pages)
    if validation["status"] != "valid":
        return validation
    root = Path(preview_dir)
    loaded = load_preview_artifacts(root)
    if loaded["status"] == "blocked":
        return {"schema_version": P50_SCHEMA_VERSION, "status": P50_STATUS_BLOCKED, "warnings": loaded["warnings"]}
    brief = classify_boss_brief(loaded["artifacts"], validation["ticker"], root, loaded["warnings"])
    if title:
        brief["title"] = title
    out = Path(output_dir) if output_dir is not None else root
    return write_boss_brief_outputs(brief, out, render_pdf=render_pdf, pdf_renderer=pdf_renderer)
