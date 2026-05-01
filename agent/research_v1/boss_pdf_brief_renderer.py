"""P50 boss-facing PDF brief renderer.

P50 reads existing P49 preview artifacts and renders a visual boss brief. It
does not run research, call providers, instruct trades, or change decisions.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
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
    lower = value.lower()
    if "ready" in lower or lower == "clear":
        return "ready"
    if "blocked" in lower or "missing" in lower:
        return "blocked"
    if "preview" in lower or "incomplete" in lower or "caution" in lower or "limited" in lower:
        return "limited"
    return "sample"


def render_boss_brief_html(brief: dict[str, Any]) -> str:
    ticker = escape(brief["ticker"])
    title = f"{ticker} Boss Brief"
    candidate = brief.get("candidate", {})
    candidate_score = _score_pct(candidate.get("score"))
    regime_confidence = _score_pct(brief.get("market_regime_confidence"))
    trusted_items = "".join(f"<li>{escape(item)}</li>" for item in brief.get("trusted_points", [])) or "<li>No trusted points available.</li>"
    limited_items = "".join(f"<li>{escape(item)}</li>" for item in brief.get("not_decision_grade_points", [])) or "<li>No major evidence gaps detected.</li>"
    next_actions = "".join(f"<li>{escape(item)}</li>" for item in brief.get("next_actions", []))
    phases = "".join(
        f"<tr><td>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>"
        for k, v in brief.get("phase_statuses", {}).items()
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <style>
    @page {{ size: Letter; margin: 0.45in; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17202a; margin: 0; background: #f4f6f8; }}
    main {{ max-width: 980px; margin: 0 auto; background: white; padding: 28px; }}
    h1 {{ font-size: 30px; margin: 0 0 4px; letter-spacing: 0; }}
    h2 {{ font-size: 17px; margin: 22px 0 10px; border-bottom: 1px solid #d9e1e8; padding-bottom: 6px; }}
    .subtitle {{ color: #566573; margin-bottom: 18px; }}
    .verdict {{ font-size: 20px; font-weight: 700; padding: 14px 16px; background: #eef6ff; border-left: 5px solid #2878bd; margin: 16px 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
    .card {{ border: 1px solid #d9e1e8; border-radius: 8px; padding: 12px; background: #fbfcfd; }}
    .label {{ color: #6b7785; font-size: 11px; text-transform: uppercase; font-weight: 700; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 5px 9px; font-size: 12px; font-weight: 700; margin-top: 8px; }}
    .ready {{ background: #e8f7ef; color: #176b3a; }}
    .limited {{ background: #fff5df; color: #875a00; }}
    .blocked {{ background: #fdeaea; color: #9b1c1c; }}
    .sample {{ background: #edf0f7; color: #344563; }}
    .split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .score-bar {{ height: 10px; background: #e5e9ef; border-radius: 999px; overflow: hidden; margin-top: 8px; }}
    .score-fill {{ height: 100%; background: #2f80ed; width: var(--score); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    td, th {{ border-bottom: 1px solid #e5e9ef; text-align: left; padding: 7px; }}
    ul {{ margin-top: 8px; padding-left: 20px; }}
    .appendix {{ page-break-before: always; }}
    .disclaimer {{ font-size: 11px; color: #6b7785; margin-top: 20px; }}
    @media print {{ body {{ background: white; }} main {{ padding: 0; }} .appendix {{ page-break-before: always; }} }}
  </style>
</head>
<body>
<main>
  <section>
    <h1>{title}</h1>
    <div class="subtitle">As of {escape(str(brief.get("as_of_date", "")))} · Generated {escape(str(brief.get("created_at", "")))}</div>
    <div class="verdict">{escape(brief.get("verdict", ""))}</div>
    <div class="grid">
      <div class="card"><div class="label">Live Data</div><span class="badge {_badge_class(brief.get("live_data_status", ""))}">{escape(brief.get("live_data_status", ""))}</span></div>
      <div class="card"><div class="label">Market Regime</div><strong>{escape(str(brief.get("market_regime_label", "Unavailable")))}</strong><div class="score-bar"><div class="score-fill" style="--score:{regime_confidence}%"></div></div></div>
      <div class="card"><div class="label">Evidence Base</div><span class="badge {_badge_class(brief.get("evidence_base_status", ""))}">{escape(brief.get("evidence_base_status", ""))}</span></div>
      <div class="card"><div class="label">Guardrails</div><span class="badge {_badge_class(brief.get("guardrail_status", ""))}">{escape(brief.get("guardrail_status", ""))}</span></div>
    </div>
    <h2>Candidate Snapshot</h2>
    <div class="card">
      <strong>{escape(str(candidate.get("ticker", ticker)))}</strong> · Rank {escape(str(candidate.get("rank") or "n/a"))} · {escape(str(candidate.get("category", "unavailable")))}
      <div class="score-bar"><div class="score-fill" style="--score:{candidate_score}%"></div></div>
    </div>
  </section>
  <section>
    <h2>Trusted vs Not Decision-Grade Yet</h2>
    <div class="split">
      <div class="card"><h3>Trusted</h3><ul>{trusted_items}</ul></div>
      <div class="card"><h3>Not Decision-Grade Yet</h3><ul>{limited_items}</ul></div>
    </div>
    <h2>Next Actions</h2>
    <div class="card"><ul>{next_actions}</ul></div>
  </section>
  <section class="appendix">
    <h2>Appendix: Phase Status</h2>
    <table><tbody>{phases}</tbody></table>
    <p class="disclaimer">{escape(brief.get("disclaimer", P50_DISCLAIMER))}</p>
  </section>
</main>
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
