"""P36 canonical recommendation outcome tracking."""

from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

P36_SCHEMA_VERSION = "p36_recommendation_outcome.1"

P36_EVALUATED_ACTIONS = frozenset({"Buy Stock", "Buy Call"})
P36_NOT_EVALUABLE_ACTIONS = frozenset({
    "Bull Call Spread",
    "Sell Cash-Secured Put",
    "Covered Call",
})
P36_NOT_APPLICABLE_ACTIONS = frozenset({"Watchlist", "No Trade"})

P36_STATUS_EVALUATED = "evaluated"
P36_STATUS_NOT_EVALUABLE = "not_evaluable_in_v1"
P36_STATUS_NOT_APPLICABLE = "not_applicable"
P36_STATUS_INSUFFICIENT_DATA = "insufficient_data"
P36_STATUS_INVALID_SIGNAL = "invalid_signal"

P36_ENTRY_RULE_NEXT_OPEN = "next_open"
P36_DEFAULT_HORIZONS = (5, 20, 60)

PRICE_ADJUSTMENT_ADJUSTED = "adjusted"
PRICE_ADJUSTMENT_UNADJUSTED = "unadjusted"
PRICE_ADJUSTMENT_UNKNOWN = "unknown"

PATH_PRECISION_OHLC = "ohlc"
PATH_PRECISION_CLOSE_ONLY = "close_only"

COST_BASIS_NONE = "none"
COST_BASIS_FLAT_BPS = "flat_bps"

P36_ARTIFACT_DISCLAIMER = (
    "P36 is recommendation outcome tracking only. It does not approve production "
    "adoption, instruct trades, place orders, train models, schedule jobs, or "
    "mutate production configuration. Artifacts are written under output/governance."
)


# ── Calendar Resolution ──────────────────────────────────────────────────────

def resolve_calendar(ticker: str) -> str:
    if ticker.startswith("HK."):
        return "XHKG"
    return "XNYS"


# ── Price Row Normalization ──────────────────────────────────────────────────

_HASH_FIELDS = ("date", "open", "high", "low", "close", "price_adjustment")


def normalize_price_rows(
    rows: list[dict[str, Any]],
    default_price_adjustment: str = PRICE_ADJUSTMENT_UNKNOWN,
) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        normalized.append({
            "date": str(row["date"]),
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "price_adjustment": row.get("price_adjustment", default_price_adjustment),
        })
    normalized.sort(key=lambda r: r["date"])
    return normalized


def compute_data_source_hash(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=lambda r: r["date"])
    canonical = json.dumps(
        [{k: row.get(k) for k in _HASH_FIELDS} for row in ordered],
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Action Resolution ────────────────────────────────────────────────────────

def resolve_signal_action(db: Any, task_id: str) -> str | None:
    reports = db.get_canonical_reports_by_task(task_id)
    if not reports:
        return None
    reports.sort(key=lambda r: (r.get("created_at", ""), r.get("report_id", "")))
    latest = reports[-1]
    # DB deserializes decision_card_json -> decision_card and
    # instrument_rec_json -> instrument_rec.  Check both deserialized
    # keys and raw JSON keys so resolution works regardless of source.
    for field in ("decision_card", "instrument_rec", "decision_card_json", "instrument_rec_json"):
        obj = latest.get(field)
        if isinstance(obj, str):
            try:
                obj = json.loads(obj)
            except (json.JSONDecodeError, TypeError):
                obj = None
        if isinstance(obj, dict) and obj.get("primary_action"):
            return obj["primary_action"]
    return None


# ── Outcome Evaluation ───────────────────────────────────────────────────────

def evaluate_recommendation_signal(
    signal: dict[str, Any],
    action: str | None,
    provider: Any,
    evaluated_for_date: date,
    flat_cost_bps: float = 0.0,
    horizons: tuple[int, ...] = P36_DEFAULT_HORIZONS,
) -> list[dict[str, Any]]:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ticker = signal.get("ticker", "")
    signal_id = signal.get("signal_id", "")
    task_id = signal.get("task_id", "")
    rating = signal.get("rating", "")
    entry_price = signal.get("entry_price")
    stop_loss = signal.get("stop_loss")
    take_profit = signal.get("take_profit")
    created_at = signal.get("created_at", "")

    calendar = resolve_calendar(ticker)
    if calendar not in ("XNYS", "XHKG"):
        return _emit_all_horizons(
            signal_id, task_id, ticker, rating, action or "",
            horizons, calendar, P36_STATUS_INVALID_SIGNAL,
            evaluated_for_date, now_utc, flat_cost_bps,
        )

    if action is None or action not in (P36_EVALUATED_ACTIONS | P36_NOT_EVALUABLE_ACTIONS | P36_NOT_APPLICABLE_ACTIONS):
        return _emit_all_horizons(
            signal_id, task_id, ticker, rating, action or "",
            horizons, calendar, P36_STATUS_INVALID_SIGNAL,
            evaluated_for_date, now_utc, flat_cost_bps,
        )

    if action in P36_NOT_APPLICABLE_ACTIONS:
        return _emit_all_horizons(
            signal_id, task_id, ticker, rating, action,
            horizons, calendar, P36_STATUS_NOT_APPLICABLE,
            evaluated_for_date, now_utc, flat_cost_bps,
        )

    if action in P36_NOT_EVALUABLE_ACTIONS:
        return _emit_all_horizons(
            signal_id, task_id, ticker, rating, action,
            horizons, calendar, P36_STATUS_NOT_EVALUABLE,
            evaluated_for_date, now_utc, flat_cost_bps,
        )

    if entry_price is None:
        return _emit_all_horizons(
            signal_id, task_id, ticker, rating, action,
            horizons, calendar, P36_STATUS_INVALID_SIGNAL,
            evaluated_for_date, now_utc, flat_cost_bps,
        )

    eval_proxy = "underlying_price_proxy" if action == "Buy Call" else "none"

    start_dt = date.fromisoformat(created_at[:10]) if created_at else evaluated_for_date
    raw_rows = provider.fetch_history(ticker, start_dt, evaluated_for_date)
    rows = normalize_price_rows(raw_rows, getattr(provider, "price_adjustment", PRICE_ADJUSTMENT_UNKNOWN))
    data_hash = compute_data_source_hash(rows)

    has_ohlc = any(r.get("open") is not None and r.get("high") is not None and r.get("low") is not None for r in rows)
    path_precision = PATH_PRECISION_OHLC if has_ohlc else PATH_PRECISION_CLOSE_ONLY

    entry_index = _find_entry_index(rows, created_at)
    if entry_index is None:
        return _emit_evaluated_horizons(
            signal_id, task_id, ticker, rating, action, eval_proxy,
            horizons, calendar, P36_STATUS_INSUFFICIENT_DATA,
            entry_price, None, None, None,
            rows, data_hash, path_precision, flat_cost_bps,
            evaluated_for_date, now_utc, stop_loss, take_profit,
        )

    entry_row = rows[entry_index]
    ep = entry_row.get("open")
    if ep is None:
        return _emit_evaluated_horizons(
            signal_id, task_id, ticker, rating, action, eval_proxy,
            horizons, calendar, P36_STATUS_INSUFFICIENT_DATA,
            entry_price, None, None, None,
            rows, data_hash, path_precision, flat_cost_bps,
            evaluated_for_date, now_utc, stop_loss, take_profit,
        )

    entry_date = entry_row["date"]
    cost_bps_val = flat_cost_bps if flat_cost_bps > 0 else 0.0
    cost_basis_val = COST_BASIS_FLAT_BPS if flat_cost_bps > 0 else COST_BASIS_NONE

    outcomes = []
    for h in horizons:
        exit_index = entry_index + h
        if exit_index >= len(rows):
            outcomes.append(_make_outcome_row(
                signal_id, task_id, ticker, rating, action, eval_proxy,
                h, calendar, P36_STATUS_INSUFFICIENT_DATA,
                ep, entry_date, None, None,
                rows, data_hash, path_precision,
                cost_basis_val, cost_bps_val,
                evaluated_for_date, now_utc, stop_loss, take_profit,
            ))
            continue

        exit_row = rows[exit_index]
        xp = exit_row.get("close")
        if xp is None:
            outcomes.append(_make_outcome_row(
                signal_id, task_id, ticker, rating, action, eval_proxy,
                h, calendar, P36_STATUS_INSUFFICIENT_DATA,
                ep, entry_date, None, None,
                rows, data_hash, path_precision,
                cost_basis_val, cost_bps_val,
                evaluated_for_date, now_utc, stop_loss, take_profit,
            ))
            continue

        exit_date = exit_row["date"]
        gross_ret = (xp - ep) / ep
        round_trip_cost = 2 * cost_bps_val / 10000 if cost_bps_val > 0 else 0.0
        net_ret = gross_ret - round_trip_cost

        path_rows = rows[entry_index:exit_index + 1]
        max_dd = _compute_max_drawdown(path_rows, ep, has_ohlc)

        target_reached, stop_breached, target_before_stop = _check_target_stop(
            path_rows, ep, stop_loss, take_profit,
        )

        if stop_loss is not None and take_profit is not None:
            win = target_before_stop
            win_def = "target_reached_before_stop"
        else:
            win = net_ret > 0
            win_def = "net_return_positive"

        outcomes.append({
            "schema_version": P36_SCHEMA_VERSION,
            "signal_id": signal_id,
            "task_id": task_id,
            "ticker": ticker,
            "action": action,
            "rating": rating,
            "horizon_days": h,
            "calendar": calendar,
            "entry_rule": P36_ENTRY_RULE_NEXT_OPEN,
            "entry_price": ep,
            "entry_date": entry_date,
            "exit_price": xp,
            "exit_date": exit_date,
            "target_reached": target_reached,
            "stop_breached": stop_breached,
            "target_reached_before_stop": target_before_stop,
            "benchmark_return_pct": None,
            "gross_return_pct": gross_ret,
            "net_return_pct": net_ret,
            "max_drawdown_pct": max_dd,
            "win": win,
            "win_definition": win_def,
            "status": P36_STATUS_EVALUATED,
            "evaluation_proxy": eval_proxy,
            "cost_basis": cost_basis_val,
            "cost_bps": cost_bps_val,
            "data_source": getattr(provider, "data_source", "unknown"),
            "price_adjustment": rows[0].get("price_adjustment", PRICE_ADJUSTMENT_UNKNOWN) if rows else PRICE_ADJUSTMENT_UNKNOWN,
            "data_source_hash": data_hash,
            "path_precision": path_precision,
            "evaluated_for_date": str(evaluated_for_date),
            "evaluated_at": now_utc,
        })
    return outcomes


def _find_entry_index(rows: list[dict], created_at: str) -> int | None:
    if not created_at:
        return None
    signal_date = created_at[:10]
    for i, row in enumerate(rows):
        if row["date"] > signal_date:
            return i
    return None


def _compute_max_drawdown(
    path_rows: list[dict], entry_price: float, has_ohlc: bool,
) -> float:
    peak = entry_price
    max_dd = 0.0
    for row in path_rows:
        if has_ohlc and row.get("low") is not None:
            low = row["low"]
        elif row.get("close") is not None:
            low = row["close"]
        else:
            continue
        if low < peak:
            dd = (low - peak) / peak
            if dd < max_dd:
                max_dd = dd
        high = row.get("high") or row.get("close")
        if high is not None and high > peak:
            peak = high
    return max_dd


def _check_target_stop(
    path_rows: list[dict],
    entry_price: float,
    stop_loss: float | None,
    take_profit: float | None,
) -> tuple[bool, bool, bool]:
    """Scan path rows and return (target_reached, stop_breached, target_before_stop).

    The first event wins: if the target is hit on a row before any stop breach,
    ``target_before_stop`` is True even if a later row breaches the stop.
    """
    target_reached = False
    stop_breached = False
    target_before_stop = False
    for row in path_rows:
        high = row.get("high") or row.get("close")
        low = row.get("low") or row.get("close")
        hit_target = take_profit is not None and high is not None and high >= take_profit
        hit_stop = stop_loss is not None and low is not None and low <= stop_loss
        if hit_target and not target_reached and not stop_breached:
            target_before_stop = True
        if hit_target:
            target_reached = True
        if hit_stop:
            stop_breached = True
    return target_reached, stop_breached, target_before_stop


def _make_outcome_row(
    signal_id, task_id, ticker, rating, action, eval_proxy,
    horizon, calendar, status,
    entry_price, entry_date, exit_price, exit_date,
    rows, data_hash, path_precision,
    cost_basis, cost_bps,
    evaluated_for_date, evaluated_at,
    stop_loss, take_profit,
) -> dict:
    return {
        "schema_version": P36_SCHEMA_VERSION,
        "signal_id": signal_id,
        "task_id": task_id,
        "ticker": ticker,
        "action": action,
        "rating": rating,
        "horizon_days": horizon,
        "calendar": calendar,
        "entry_rule": P36_ENTRY_RULE_NEXT_OPEN,
        "entry_price": entry_price,
        "entry_date": entry_date,
        "exit_price": exit_price,
        "exit_date": exit_date,
        "target_reached": False,
        "stop_breached": False,
        "target_reached_before_stop": False,
        "benchmark_return_pct": None,
        "gross_return_pct": None,
        "net_return_pct": None,
        "max_drawdown_pct": None,
        "win": False,
        "win_definition": "net_return_positive",
        "status": status,
        "evaluation_proxy": eval_proxy,
        "cost_basis": cost_basis,
        "cost_bps": cost_bps,
        "data_source": "",
        "price_adjustment": rows[0].get("price_adjustment", PRICE_ADJUSTMENT_UNKNOWN) if rows else PRICE_ADJUSTMENT_UNKNOWN,
        "data_source_hash": data_hash,
        "path_precision": path_precision,
        "evaluated_for_date": str(evaluated_for_date),
        "evaluated_at": evaluated_at,
    }


def _emit_all_horizons(
    signal_id, task_id, ticker, rating, action,
    horizons, calendar, status,
    evaluated_for_date, evaluated_at, flat_cost_bps,
) -> list[dict]:
    cost_basis = COST_BASIS_FLAT_BPS if flat_cost_bps > 0 else COST_BASIS_NONE
    # Deterministic hash so non-evaluated rows satisfy the natural-key
    # UNIQUE constraint and can be persisted.
    status_hash = hashlib.sha256(
        f"status:{status}".encode("utf-8")
    ).hexdigest()
    return [
        {
            "schema_version": P36_SCHEMA_VERSION,
            "signal_id": signal_id,
            "task_id": task_id,
            "ticker": ticker,
            "action": action,
            "rating": rating,
            "horizon_days": h,
            "calendar": calendar,
            "entry_rule": P36_ENTRY_RULE_NEXT_OPEN,
            "entry_price": None,
            "entry_date": None,
            "exit_price": None,
            "exit_date": None,
            "target_reached": False,
            "stop_breached": False,
            "target_reached_before_stop": False,
            "benchmark_return_pct": None,
            "gross_return_pct": None,
            "net_return_pct": None,
            "max_drawdown_pct": None,
            "win": False,
            "win_definition": "net_return_positive",
            "status": status,
            "evaluation_proxy": "none",
            "cost_basis": cost_basis,
            "cost_bps": flat_cost_bps,
            "data_source": "",
            "price_adjustment": PRICE_ADJUSTMENT_UNKNOWN,
            "data_source_hash": status_hash,
            "path_precision": PATH_PRECISION_CLOSE_ONLY,
            "evaluated_for_date": str(evaluated_for_date),
            "evaluated_at": evaluated_at,
        }
        for h in horizons
    ]


def _emit_evaluated_horizons(
    signal_id, task_id, ticker, rating, action, eval_proxy,
    horizons, calendar, status,
    entry_price, entry_date, exit_price, exit_date,
    rows, data_hash, path_precision, flat_cost_bps,
    evaluated_for_date, evaluated_at, stop_loss, take_profit,
) -> list[dict]:
    cost_basis = COST_BASIS_FLAT_BPS if flat_cost_bps > 0 else COST_BASIS_NONE
    return [
        _make_outcome_row(
            signal_id, task_id, ticker, rating, action, eval_proxy,
            h, calendar, status,
            entry_price, entry_date, exit_price, exit_date,
            rows, data_hash, path_precision,
            cost_basis, flat_cost_bps,
            evaluated_for_date, evaluated_at,
            stop_loss, take_profit,
        )
        for h in horizons
    ]


# ── Distribution Summary ─────────────────────────────────────────────────────

def build_distribution_summary(outcomes: list[dict]) -> list[dict]:
    groups: dict[tuple[str, Any], list[dict]] = {}
    for row in outcomes:
        if row["status"] != P36_STATUS_EVALUATED:
            continue
        for group_type, key in [
            ("action", row.get("action")),
            ("rating", row.get("rating")),
            ("horizon", row.get("horizon_days")),
        ]:
            groups.setdefault((group_type, key), []).append(row)

    summaries = []
    for (group_type, key), rows in sorted(groups.items()):
        net_returns = [r["net_return_pct"] for r in rows if r.get("net_return_pct") is not None]
        drawdowns = [r["max_drawdown_pct"] for r in rows if r.get("max_drawdown_pct") is not None]
        wins = [r for r in rows if r.get("win")]
        losses = [r for r in rows if not r.get("win")]
        n = len(rows)

        if not net_returns:
            continue

        sorted_ret = sorted(net_returns)
        p25_idx = max(0, len(sorted_ret) // 4 - 1) if len(sorted_ret) >= 4 else 0
        p75_idx = min(len(sorted_ret) - 1, 3 * len(sorted_ret) // 4) if len(sorted_ret) >= 4 else len(sorted_ret) - 1

        win_returns = [r["net_return_pct"] for r in wins if r.get("net_return_pct") is not None]
        loss_returns = [r["net_return_pct"] for r in losses if r.get("net_return_pct") is not None]

        summaries.append({
            "group_type": group_type,
            "group": key,
            "sample_size": n,
            "hit_rate": len(wins) / n if n else 0.0,
            "median_net_return": statistics.median(net_returns),
            "p25_net_return": sorted_ret[p25_idx],
            "p75_net_return": sorted_ret[p75_idx],
            "mean_win": statistics.mean(win_returns) if win_returns else None,
            "mean_loss": statistics.mean(loss_returns) if loss_returns else None,
            "average_drawdown": statistics.mean(drawdowns) if drawdowns else None,
        })
    return summaries


# ── Run Orchestration ────────────────────────────────────────────────────────

def run_recommendation_outcome_tracking(
    db: Any,
    evaluated_for_date: date,
    limit: int = 50,
    flat_cost_bps: float = 0.0,
    output_root: Path | None = None,
    provider: Any | None = None,
) -> dict[str, Any]:
    db.initialize_canonical_outcome_schema()
    signals = db.list_canonical_signals(limit=limit)
    warnings: list[str] = []
    total_written = 0
    total_skipped = 0
    counts = {
        P36_STATUS_EVALUATED: 0,
        P36_STATUS_NOT_APPLICABLE: 0,
        P36_STATUS_NOT_EVALUABLE: 0,
        P36_STATUS_INSUFFICIENT_DATA: 0,
        P36_STATUS_INVALID_SIGNAL: 0,
    }
    all_outcomes: list[dict] = []

    for sig in signals:
        action = resolve_signal_action(db, sig["task_id"])
        if action is None:
            action = None

        sig_provider = provider or _DbProvider(db, sig["ticker"])
        outcomes = evaluate_recommendation_signal(
            signal=sig,
            action=action,
            provider=sig_provider,
            evaluated_for_date=evaluated_for_date,
            flat_cost_bps=flat_cost_bps,
        )

        for row in outcomes:
            existing = db.list_canonical_outcomes_by_signal(row["signal_id"])
            dup = any(
                e["horizon_days"] == row["horizon_days"]
                and e["evaluated_for_date"] == row["evaluated_for_date"]
                and e["data_source_hash"] == row["data_source_hash"]
                for e in existing
            )
            if dup:
                total_skipped += 1
            else:
                db.save_canonical_outcome(row)
                total_written += 1
            counts[row["status"]] = counts.get(row["status"], 0) + 1
            all_outcomes.append(row)

    dist_summary = build_distribution_summary(all_outcomes)
    evaluated_rows = [r for r in all_outcomes if r["status"] == P36_STATUS_EVALUATED and r.get("net_return_pct") is not None]
    extreme_pos = sorted(evaluated_rows, key=lambda r: r["net_return_pct"], reverse=True)[:5]
    extreme_neg = sorted(evaluated_rows, key=lambda r: r["net_return_pct"])[:5]

    result = {
        "run_date": str(evaluated_for_date),
        "evaluated_for_date": str(evaluated_for_date),
        "schema_version": P36_SCHEMA_VERSION,
        "status": "completed",
        "signals_considered": len(signals),
        "outcome_rows_written": total_written,
        "duplicate_rows_skipped": total_skipped,
        "evaluated_count": counts[P36_STATUS_EVALUATED],
        "not_applicable_count": counts[P36_STATUS_NOT_APPLICABLE],
        "not_evaluable_count": counts[P36_STATUS_NOT_EVALUABLE],
        "insufficient_data_count": counts[P36_STATUS_INSUFFICIENT_DATA],
        "invalid_signal_count": counts[P36_STATUS_INVALID_SIGNAL],
        "warnings": warnings,
        "distribution_summary": dist_summary,
        "extreme_examples": {"largest_positive": extreme_pos, "largest_negative": extreme_neg},
        "disclaimer": P36_ARTIFACT_DISCLAIMER,
    }

    if output_root:
        output_dir = output_root / str(evaluated_for_date)
        write_recommendation_outcome_artifacts(result, output_dir)
        result["output_dir"] = str(output_dir)

    return result


class _DbProvider:
    def __init__(self, db: Any, ticker: str):
        self._db = db
        self._ticker = ticker
        self.data_source = "canonical_db"
        self.price_adjustment = PRICE_ADJUSTMENT_UNKNOWN

    def fetch_history(self, symbol: str, start_date: date, end_date: date) -> list[dict]:
        return []


# ── Artifact Writer ──────────────────────────────────────────────────────────

def write_recommendation_outcome_artifacts(
    report: dict[str, Any], output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p36_recommendation_outcomes.json"
    md_path = output_dir / "p36_recommendation_outcomes.md"

    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md_lines = [
        "# P36 Recommendation Outcome Report",
        "",
        f"**Run date:** {report['run_date']}",
        f"**Evaluated for date:** {report['evaluated_for_date']}",
        f"**Schema version:** {report['schema_version']}",
        f"**Status:** {report['status']}",
        "",
        "## Summary",
        "",
        f"- Signals considered: {report['signals_considered']}",
        f"- Outcome rows written: {report['outcome_rows_written']}",
        f"- Duplicate rows skipped: {report['duplicate_rows_skipped']}",
        f"- Evaluated: {report['evaluated_count']}",
        f"- Not applicable: {report['not_applicable_count']}",
        f"- Not evaluable in v1: {report['not_evaluable_count']}",
        f"- Insufficient data: {report['insufficient_data_count']}",
        f"- Invalid signal: {report['invalid_signal_count']}",
        "",
    ]

    if report.get("distribution_summary"):
        md_lines.append("## Distribution Summary")
        md_lines.append("")
        md_lines.append("| Group Type | Group | Sample Size | Hit Rate | Median Net Return | P25 | P75 | Mean Win | Mean Loss | Avg Drawdown |")
        md_lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for g in report["distribution_summary"]:
            mw = f"{g['mean_win']:.4f}" if g.get('mean_win') is not None else "N/A"
            ml = f"{g['mean_loss']:.4f}" if g.get('mean_loss') is not None else "N/A"
            ad = f"{g['average_drawdown']:.4f}" if g.get('average_drawdown') is not None else "N/A"
            md_lines.append(
                f"| {g['group_type']} | {g['group']} | {g['sample_size']} | "
                f"{g['hit_rate']:.2%} | {g['median_net_return']:.4f} | "
                f"{g['p25_net_return']:.4f} | {g['p75_net_return']:.4f} | "
                f"{mw} | {ml} | {ad} |"
            )
        md_lines.append("")

    if report.get("extreme_examples"):
        extremes = report["extreme_examples"]
        if extremes.get("largest_positive"):
            md_lines.append("## Largest Positive Net Returns")
            md_lines.append("")
            for ex in extremes["largest_positive"]:
                md_lines.append(f"- {ex.get('ticker')} {ex.get('action')} {ex.get('horizon_days')}d: {ex.get('net_return_pct'):.4f}")
            md_lines.append("")
        if extremes.get("largest_negative"):
            md_lines.append("## Largest Negative Net Returns")
            md_lines.append("")
            for ex in extremes["largest_negative"]:
                md_lines.append(f"- {ex.get('ticker')} {ex.get('action')} {ex.get('horizon_days')}d: {ex.get('net_return_pct'):.4f}")
            md_lines.append("")

    md_lines.append("---")
    md_lines.append("")
    md_lines.append(f"*{report.get('disclaimer', P36_ARTIFACT_DISCLAIMER)}*")
    md_lines.append("")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return {"json": json_path, "md": md_path}
