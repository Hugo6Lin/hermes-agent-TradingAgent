"""P20 factor persistence layer: FactorSnapshot, ForwardReturnObservation, UniverseMembershipSnapshot."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from agent.research_v1.contracts import (
    FactorSnapshot,
    ForwardReturnObservation,
    UniverseMembershipSnapshot,
    LLMAdjustment,
    ThesisGateResult,
    ClassificationReason,
    SourceValueRef,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Table initialization
# ---------------------------------------------------------------------------

def initialize_factor_schema(conn: sqlite3.Connection) -> None:
    """Create P20 factor tables if they do not exist.

    Tables:
        - factor_snapshots
        - forward_return_observations
        - universe_membership_snapshots
    """
    cursor = conn.cursor()

    # factor_snapshots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS factor_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            task_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            as_of_timestamp TEXT NOT NULL,
            trading_day TEXT NOT NULL,
            data_as_of_date TEXT NOT NULL,
            universe_id TEXT,
            universe_label TEXT,
            universe_membership_snapshot_id TEXT NOT NULL,
            company_quality_score REAL NOT NULL,
            valuation_attractiveness_score REAL NOT NULL,
            timing_market_fit_score REAL NOT NULL,
            quality_coverage REAL NOT NULL,
            valuation_coverage REAL NOT NULL,
            timing_coverage REAL NOT NULL,
            regime_coverage REAL NOT NULL,
            llm_overlay_coverage REAL NOT NULL,
            llm_adjustment_total REAL NOT NULL,
            llm_adjustments_json TEXT NOT NULL,
            gate_results_json TEXT NOT NULL,
            classification TEXT NOT NULL,
            classification_reason_json TEXT NOT NULL,
            negative_signal_strength_decile INTEGER,
            thresholds_used_json TEXT NOT NULL,
            model_routes_used_json TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            raw_factor_values_json TEXT,
            normalized_factor_values_json TEXT,
            missing_dimensions_json TEXT,
            stale_dimensions_json TEXT,
            fallback_reasons_json TEXT,
            provider_versions_json TEXT,
            prompt_versions_json TEXT,
            sector_id TEXT,
            size_decile INTEGER
        )
    """)

    # forward_return_observations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forward_return_observations (
            observation_id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            trading_day TEXT NOT NULL,
            horizon_days INTEGER NOT NULL,
            return_value REAL NOT NULL,
            return_source TEXT NOT NULL,
            price_start REAL NOT NULL,
            price_end REAL NOT NULL,
            start_price_date TEXT NOT NULL,
            end_price_date TEXT NOT NULL,
            gap_handled INTEGER NOT NULL,
            computed_at TEXT NOT NULL,
            observation_status TEXT,
            missing_reason TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES factor_snapshots(snapshot_id)
        )
    """)

    # Idempotent migration: add P22 cost-awareness columns if not present
    for col_def in [
        "gross_return_pct REAL",
        "net_return_pct REAL",
        "transaction_cost_pct REAL",
        "cost_source TEXT",
    ]:
        try:
            cursor.execute(f"ALTER TABLE forward_return_observations ADD COLUMN {col_def}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc):
                raise  # re-raise unrelated DB errors

    # universe_membership_snapshots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS universe_membership_snapshots (
            universe_membership_snapshot_id TEXT PRIMARY KEY,
            universe_id TEXT NOT NULL,
            universe_label TEXT NOT NULL,
            as_of_timestamp TEXT NOT NULL,
            members_json TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Index for fast lookup of snapshots by ticker+trading_day
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_factor_snapshots_ticker_trading_day
        ON factor_snapshots(ticker, trading_day)
    """)

    # Index for forward returns lookup
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_forward_returns_snapshot
        ON forward_return_observations(snapshot_id)
    """)

    conn.commit()


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _llm_adjustment_to_dict(adj: LLMAdjustment) -> dict:
    return {
        "affected_category": adj.affected_category,
        "delta": adj.delta,
        "max_abs_delta": adj.max_abs_delta,
        "reason": adj.reason,
        "source_refs": adj.source_refs,
        "model_provider": adj.model_provider,
        "model_name": adj.model_name,
        "prompt_version": adj.prompt_version,
    }


def _dict_to_llm_adjustment(d: dict) -> LLMAdjustment:
    return LLMAdjustment(
        affected_category=d["affected_category"],
        delta=d["delta"],
        max_abs_delta=d["max_abs_delta"],
        reason=d["reason"],
        source_refs=d["source_refs"],
        model_provider=d["model_provider"],
        model_name=d["model_name"],
        prompt_version=d["prompt_version"],
    )


def _gate_result_to_dict(g: ThesisGateResult) -> dict:
    return {
        "gate": g.gate,
        "status": g.status,
        "score": g.score,
        "threshold": g.threshold,
        "failing_dimension": g.failing_dimension,
        "reason_code": g.reason_code,
        "recommended_action": g.recommended_action,
    }


def _dict_to_gate_result(d: dict) -> ThesisGateResult:
    return ThesisGateResult(
        gate=d["gate"],
        status=d["status"],
        score=d["score"],
        threshold=d["threshold"],
        failing_dimension=d.get("failing_dimension"),
        reason_code=d["reason_code"],
        recommended_action=d["recommended_action"],
    )


def _classification_reason_to_dict(c: ClassificationReason) -> dict:
    return {
        "classification": c.classification,
        "primary_gate": c.primary_gate,
        "primary_reason_code": c.primary_reason_code,
        "supporting_gates": c.supporting_gates,
        "blocking_gates": c.blocking_gates,
        "recommended_next_action": c.recommended_next_action,
        "human_summary": c.human_summary,
    }


def _dict_to_classification_reason(d: dict) -> ClassificationReason:
    return ClassificationReason(
        classification=d["classification"],
        primary_gate=d["primary_gate"],
        primary_reason_code=d["primary_reason_code"],
        supporting_gates=d["supporting_gates"],
        blocking_gates=d["blocking_gates"],
        recommended_next_action=d["recommended_next_action"],
        human_summary=d["human_summary"],
    )


def _source_value_ref_to_dict(s: SourceValueRef) -> dict:
    return {
        "field_name": s.field_name,
        "value": s.value,
        "source": s.source,
        "fetched_at": s.fetched_at,
        "as_of_date": s.as_of_date,
        "provider": s.provider,
        "quality_flags": s.quality_flags,
    }


def _dict_to_source_value_ref(d: dict) -> SourceValueRef:
    return SourceValueRef(
        field_name=d["field_name"],
        value=d.get("value"),
        source=d["source"],
        fetched_at=d["fetched_at"],
        as_of_date=d["as_of_date"],
        provider=d["provider"],
        quality_flags=d.get("quality_flags", []),
    )


def _optional_list_to_json(v: list | None) -> str | None:
    if v is None:
        return None
    return json.dumps(v)


def _json_to_optional_list(s: str | None) -> list | None:
    if s is None:
        return None
    return json.loads(s)


# ---------------------------------------------------------------------------
# FactorSnapshot persistence
# ---------------------------------------------------------------------------

def save_factor_snapshot(conn: sqlite3.Connection, snapshot: FactorSnapshot) -> None:
    """Persist a FactorSnapshot to the database."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO factor_snapshots (
            snapshot_id, schema_version, task_id, ticker,
            as_of_timestamp, trading_day, data_as_of_date,
            universe_id, universe_label, universe_membership_snapshot_id,
            company_quality_score, valuation_attractiveness_score, timing_market_fit_score,
            quality_coverage, valuation_coverage, timing_coverage,
            regime_coverage, llm_overlay_coverage,
            llm_adjustment_total, llm_adjustments_json,
            gate_results_json, classification, classification_reason_json,
            negative_signal_strength_decile,
            thresholds_used_json, model_routes_used_json, source_refs_json,
            created_at,
            raw_factor_values_json, normalized_factor_values_json,
            missing_dimensions_json, stale_dimensions_json,
            fallback_reasons_json, provider_versions_json, prompt_versions_json,
            sector_id, size_decile
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        snapshot.snapshot_id,
        snapshot.schema_version,
        snapshot.task_id,
        snapshot.ticker,
        snapshot.as_of_timestamp,
        snapshot.trading_day,
        snapshot.data_as_of_date,
        snapshot.universe_id,
        snapshot.universe_label,
        snapshot.universe_membership_snapshot_id,
        snapshot.company_quality_score,
        snapshot.valuation_attractiveness_score,
        snapshot.timing_market_fit_score,
        snapshot.quality_coverage,
        snapshot.valuation_coverage,
        snapshot.timing_coverage,
        snapshot.regime_coverage,
        snapshot.llm_overlay_coverage,
        snapshot.llm_adjustment_total,
        json.dumps([_llm_adjustment_to_dict(a) for a in snapshot.llm_adjustments]),
        json.dumps([_gate_result_to_dict(g) for g in snapshot.gate_results]),
        snapshot.classification,
        json.dumps(_classification_reason_to_dict(snapshot.classification_reason)),
        snapshot.negative_signal_strength_decile,
        json.dumps(snapshot.thresholds_used),
        json.dumps(snapshot.model_routes_used),
        json.dumps([_source_value_ref_to_dict(s) for s in snapshot.source_refs]),
        snapshot.created_at,
        json.dumps(snapshot.raw_factor_values) if snapshot.raw_factor_values else None,
        json.dumps(snapshot.normalized_factor_values) if snapshot.normalized_factor_values else None,
        _optional_list_to_json(snapshot.missing_dimensions),
        _optional_list_to_json(snapshot.stale_dimensions),
        _optional_list_to_json(snapshot.fallback_reasons),
        json.dumps(snapshot.provider_versions) if snapshot.provider_versions else None,
        json.dumps(snapshot.prompt_versions) if snapshot.prompt_versions else None,
        snapshot.sector_id,
        snapshot.size_decile,
    ))
    conn.commit()


def get_factor_snapshot(conn: sqlite3.Connection, snapshot_id: str) -> FactorSnapshot | None:
    """Retrieve a FactorSnapshot by ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM factor_snapshots WHERE snapshot_id = ?", (snapshot_id,))
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return _row_to_factor_snapshot(dict(zip(columns, row)))


def get_latest_factor_snapshot(
    conn: sqlite3.Connection,
    ticker: str,
    trading_day: str,
    universe_membership_snapshot_id: str | None = None,
) -> FactorSnapshot | None:
    """Get the latest FactorSnapshot for a ticker+trading_day (deduplication key).

    When universe_membership_snapshot_id is provided, scope the query to that specific
    universe to avoid cross-universe leakage (e.g. same ticker in SP500 vs Nasdaq100).
    """
    cursor = conn.cursor()
    if universe_membership_snapshot_id is not None:
        cursor.execute("""
            SELECT * FROM factor_snapshots
            WHERE ticker = ? AND trading_day = ? AND universe_membership_snapshot_id = ?
            ORDER BY created_at DESC, snapshot_id DESC
            LIMIT 1
        """, (ticker, trading_day, universe_membership_snapshot_id))
    else:
        cursor.execute("""
            SELECT * FROM factor_snapshots
            WHERE ticker = ? AND trading_day = ?
            ORDER BY created_at DESC, snapshot_id DESC
            LIMIT 1
        """, (ticker, trading_day))
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return _row_to_factor_snapshot(dict(zip(columns, row)))


def _row_to_factor_snapshot(row: dict) -> FactorSnapshot:
    d = dict(row)
    llm_adjustments = [_dict_to_llm_adjustment(a) for a in json.loads(d.pop("llm_adjustments_json"))]
    gate_results = [_dict_to_gate_result(g) for g in json.loads(d.pop("gate_results_json"))]
    classification_reason = _dict_to_classification_reason(json.loads(d.pop("classification_reason_json")))
    source_refs = [_dict_to_source_value_ref(s) for s in json.loads(d.pop("source_refs_json"))]
    thresholds_used = json.loads(d.pop("thresholds_used_json"))
    model_routes_used = json.loads(d.pop("model_routes_used_json"))

    raw_factor_values = json.loads(d["raw_factor_values_json"]) if d.get("raw_factor_values_json") else None
    normalized_factor_values = json.loads(d["normalized_factor_values_json"]) if d.get("normalized_factor_values_json") else None
    missing_dimensions = _json_to_optional_list(d.get("missing_dimensions_json"))
    stale_dimensions = _json_to_optional_list(d.get("stale_dimensions_json"))
    fallback_reasons = _json_to_optional_list(d.get("fallback_reasons_json"))
    provider_versions = json.loads(d["provider_versions_json"]) if d.get("provider_versions_json") else None
    prompt_versions = json.loads(d["prompt_versions_json"]) if d.get("prompt_versions_json") else None

    return FactorSnapshot(
        snapshot_id=d["snapshot_id"],
        schema_version=d["schema_version"],
        task_id=d["task_id"],
        ticker=d["ticker"],
        as_of_timestamp=d["as_of_timestamp"],
        trading_day=d["trading_day"],
        data_as_of_date=d["data_as_of_date"],
        universe_id=d.get("universe_id"),
        universe_label=d.get("universe_label"),
        universe_membership_snapshot_id=d["universe_membership_snapshot_id"],
        company_quality_score=d["company_quality_score"],
        valuation_attractiveness_score=d["valuation_attractiveness_score"],
        timing_market_fit_score=d["timing_market_fit_score"],
        quality_coverage=d["quality_coverage"],
        valuation_coverage=d["valuation_coverage"],
        timing_coverage=d["timing_coverage"],
        regime_coverage=d["regime_coverage"],
        llm_overlay_coverage=d["llm_overlay_coverage"],
        llm_adjustment_total=d["llm_adjustment_total"],
        llm_adjustments=llm_adjustments,
        gate_results=gate_results,
        classification=d["classification"],
        classification_reason=classification_reason,
        negative_signal_strength_decile=d.get("negative_signal_strength_decile"),
        thresholds_used=thresholds_used,
        model_routes_used=model_routes_used,
        source_refs=source_refs,
        created_at=d["created_at"],
        raw_factor_values=raw_factor_values,
        normalized_factor_values=normalized_factor_values,
        missing_dimensions=missing_dimensions,
        stale_dimensions=stale_dimensions,
        fallback_reasons=fallback_reasons,
        provider_versions=provider_versions,
        prompt_versions=prompt_versions,
        sector_id=d.get("sector_id"),
        size_decile=d.get("size_decile"),
    )


# ---------------------------------------------------------------------------
# ForwardReturnObservation persistence
# ---------------------------------------------------------------------------

def save_forward_return_observation(conn: sqlite3.Connection, obs: ForwardReturnObservation) -> None:
    """Persist a ForwardReturnObservation."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO forward_return_observations (
            observation_id, snapshot_id, ticker, trading_day,
            horizon_days, return_value, return_source,
            price_start, price_end, start_price_date, end_price_date,
            gap_handled, computed_at, observation_status, missing_reason,
            gross_return_pct, net_return_pct, transaction_cost_pct, cost_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        obs.observation_id,
        obs.snapshot_id,
        obs.ticker,
        obs.trading_day,
        obs.horizon_days,
        obs.return_value,
        obs.return_source,
        obs.price_start,
        obs.price_end,
        obs.start_price_date,
        obs.end_price_date,
        int(obs.gap_handled),
        obs.computed_at,
        obs.observation_status,
        obs.missing_reason,
        obs.gross_return_pct,
        obs.net_return_pct,
        obs.transaction_cost_pct,
        obs.cost_source,
    ))
    conn.commit()


def get_forward_return_observations(
    conn: sqlite3.Connection,
    snapshot_id: str,
) -> list[ForwardReturnObservation]:
    """Retrieve all ForwardReturnObservations for a snapshot."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM forward_return_observations
        WHERE snapshot_id = ?
        ORDER BY horizon_days
    """, (snapshot_id,))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [_row_to_forward_return_obs(dict(zip(columns, row))) for row in rows]


def get_forward_return_observations_by_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    horizon_days: int | None = None,
) -> list[ForwardReturnObservation]:
    """Retrieve forward return observations for a ticker, optionally filtered by horizon."""
    cursor = conn.cursor()
    if horizon_days is not None:
        cursor.execute("""
            SELECT * FROM forward_return_observations
            WHERE ticker = ? AND horizon_days = ?
            ORDER BY trading_day
        """, (ticker, horizon_days))
    else:
        cursor.execute("""
            SELECT * FROM forward_return_observations
            WHERE ticker = ?
            ORDER BY horizon_days, trading_day
        """, (ticker,))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [_row_to_forward_return_obs(dict(zip(columns, row))) for row in rows]


def _row_to_forward_return_obs(row: dict) -> ForwardReturnObservation:
    return ForwardReturnObservation(
        observation_id=row["observation_id"],
        snapshot_id=row["snapshot_id"],
        ticker=row["ticker"],
        trading_day=row["trading_day"],
        horizon_days=row["horizon_days"],
        return_value=row["return_value"],
        return_source=row["return_source"],
        price_start=row["price_start"],
        price_end=row["price_end"],
        start_price_date=row["start_price_date"],
        end_price_date=row["end_price_date"],
        gap_handled=bool(row["gap_handled"]),
        computed_at=row["computed_at"],
        gross_return_pct=row.get("gross_return_pct"),
        net_return_pct=row.get("net_return_pct"),
        transaction_cost_pct=row.get("transaction_cost_pct"),
        cost_source=row.get("cost_source"),
        observation_status=row.get("observation_status"),
        missing_reason=row.get("missing_reason"),
    )


# ---------------------------------------------------------------------------
# UniverseMembershipSnapshot persistence
# ---------------------------------------------------------------------------

def save_universe_membership_snapshot(
    conn: sqlite3.Connection,
    snapshot: UniverseMembershipSnapshot,
) -> None:
    """Persist a UniverseMembershipSnapshot."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO universe_membership_snapshots (
            universe_membership_snapshot_id, universe_id, universe_label,
            as_of_timestamp, members_json, source, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        snapshot.universe_membership_snapshot_id,
        snapshot.universe_id,
        snapshot.universe_label,
        snapshot.as_of_timestamp,
        json.dumps(snapshot.members),
        snapshot.source,
        snapshot.created_at,
    ))
    conn.commit()


def get_universe_membership_snapshot(
    conn: sqlite3.Connection,
    snapshot_id: str,
) -> UniverseMembershipSnapshot | None:
    """Retrieve a UniverseMembershipSnapshot by ID."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM universe_membership_snapshots WHERE universe_membership_snapshot_id = ?",
        (snapshot_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return _row_to_universe_membership(dict(zip(columns, row)))


def _row_to_universe_membership(row: dict) -> UniverseMembershipSnapshot:
    return UniverseMembershipSnapshot(
        universe_membership_snapshot_id=row["universe_membership_snapshot_id"],
        universe_id=row["universe_id"],
        universe_label=row["universe_label"],
        as_of_timestamp=row["as_of_timestamp"],
        members=json.loads(row["members_json"]),
        source=row["source"],
        created_at=row["created_at"],
    )
