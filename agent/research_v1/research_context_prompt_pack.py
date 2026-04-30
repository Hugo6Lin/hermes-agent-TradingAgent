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


def validate_prompt_pack_inputs(
    as_of_date: str,
    tickers: list[str],
    roles: list[str] | None,
    max_block_chars: int,
    governance_root_is_dir: bool,
) -> dict[str, Any]:
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
        return {
            "schema_version": P48_SCHEMA_VERSION,
            "status": "blocked_invalid_input",
            "warnings": warnings,
            "tickers": normalized_tickers,
            "roles": normalized_roles,
        }
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


def build_research_context_prompt_pack(
    *,
    as_of_date: str,
    tickers: list[str],
    roles: list[str] | None,
    max_block_chars: int,
    source_pack: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    normalized_tickers = normalize_tickers(tickers)
    normalized_roles = normalize_roles(roles)
    role_contexts = [
        _build_role_context(source_pack, ticker, role, max_block_chars)
        for ticker in normalized_tickers
        for role in normalized_roles
    ]
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
    else:
        status = "prompt_pack_limited"
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


def _pack_covers_tickers(pack: dict[str, Any], requested: set[str]) -> bool:
    pack_tickers = {str(t).upper() for t in pack.get("tickers", [])}
    return bool(pack_tickers & requested)


def _load_p47_artifact_as_of(governance_root: Path, as_of_date: str, tickers: set[str] | None = None, lookback_days: int = 30) -> dict[str, Any] | None:
    for offset in range(lookback_days + 1):
        day = (date.fromisoformat(as_of_date) - timedelta(days=offset)).isoformat()
        path = governance_root / day / "p47_research_context_pack.json"
        if path.exists():
            try:
                pack = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
            if tickers is None or _pack_covers_tickers(pack, tickers):
                return pack
    return None


def load_source_context_pack(db: Any, governance_root: Path, as_of_date: str, tickers: list[str] | None = None) -> tuple[dict[str, Any] | None, bool]:
    """Return (pack, any_pack_exists). pack is None when no ticker-matching pack is found.
    any_pack_exists is True when at least one P47 pack exists at or before as_of_date
    (even if it doesn't cover the requested tickers)."""
    requested = {str(t).upper() for t in tickers} if tickers else set()
    any_exists = False
    method = getattr(db, "list_research_context_packs_as_of", None)
    if method:
        try:
            rows = method(as_of_date)
        except Exception:
            rows = []
        if rows:
            any_exists = True
        if requested:
            for row in rows:
                if _pack_covers_tickers(row, requested):
                    return row, True
        elif rows:
            return rows[0], True
    artifact = _load_p47_artifact_as_of(Path(governance_root), as_of_date, requested or None)
    if artifact:
        return artifact, True
    # Check if any artifact exists without ticker filter
    if requested:
        any_artifact = _load_p47_artifact_as_of(Path(governance_root), as_of_date, None)
        if any_artifact:
            return None, True
    return None, any_exists


def run_research_context_prompt_pack(
    db: Any,
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    tickers: list[str],
    roles: list[str] | None = None,
    max_block_chars: int = 1200,
) -> dict[str, Any]:
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
    source_pack, any_pack_exists = load_source_context_pack(db, governance_root, as_of_date, validation["tickers"])
    if not source_pack and not any_pack_exists:
        return {
            "schema_version": P48_SCHEMA_VERSION,
            "status": "blocked_missing_context",
            "as_of_date": as_of_date,
            "tickers": validation["tickers"],
            "roles": validation["roles"],
            "warnings": ["missing_p47_research_context_pack"],
        }
    if not source_pack:
        # P47 packs exist but none cover the requested tickers
        empty_source = {
            "pack_id": "",
            "as_of_date": as_of_date,
            "source_hash": "",
            "tickers": validation["tickers"],
            "system_context": {},
            "ticker_contexts": [],
            "source_refs": [],
            "missing_context": [],
            "warnings": [],
        }
        pack = build_research_context_prompt_pack(
            as_of_date=as_of_date,
            tickers=validation["tickers"],
            roles=validation["roles"],
            max_block_chars=max_block_chars,
            source_pack=empty_source,
        )
    else:
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
