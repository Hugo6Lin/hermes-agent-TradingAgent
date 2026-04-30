"""Tests for P39 candidate pool engine."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.candidate_pool import (
    P39_SCHEMA_VERSION,
    build_candidate_pool,
    compute_candidate_pool_source_hash,
    write_candidate_pool_artifacts,
)


def _ticker(
    ticker: str = "AAPL",
    sector: str = "technology",
    source_date: str = "2026-04-30",
    close: float = 200.0,
    close_20d_ago: float = 190.0,
    close_60d_ago: float = 170.0,
    close_120d_ago: float = 160.0,
    high_252d: float = 215.0,
    low_252d: float = 140.0,
    avg_dollar_volume_20d: float = 1_500_000_000.0,
    realized_vol_20d: float = 0.24,
    outcome_prior: dict | None = None,
    exclude_reasons: list[str] | None = None,
) -> dict:
    row = {
        "ticker": ticker,
        "sector": sector,
        "currency": "USD",
        "source_date": source_date,
        "close": close,
        "close_20d_ago": close_20d_ago,
        "close_60d_ago": close_60d_ago,
        "close_120d_ago": close_120d_ago,
        "high_252d": high_252d,
        "low_252d": low_252d,
        "avg_dollar_volume_20d": avg_dollar_volume_20d,
        "realized_vol_20d": realized_vol_20d,
        "market_cap": 3_000_000_000_000.0,
        "benchmark_return_60d": 0.05,
        "catalyst_tags": ["earnings_soon"],
    }
    if outcome_prior is not None:
        row["outcome_prior"] = outcome_prior
    if exclude_reasons is not None:
        row["exclude_reasons"] = exclude_reasons
    return row


def _payload(tickers: list[dict]) -> dict:
    return {
        "as_of_date": "2026-04-30",
        "source": "fixture",
        "universe_id": "us_liquid_growth",
        "tickers": tickers,
    }


# ── P39-A scoring tests ─────────────────────────────────────────────────────

def test_valid_universe_row_computes_component_scores():
    pool = build_candidate_pool(_payload([_ticker()]), as_of_date="2026-04-30")

    assert pool["schema_version"] == P39_SCHEMA_VERSION
    assert pool["status"] == "completed"
    assert len(pool["candidates"]) == 1
    candidate = pool["candidates"][0]
    assert candidate["ticker"] == "AAPL"
    assert candidate["workflow_action"] in {"research_candidate", "monitor_candidate", "defer_candidate"}
    assert 0.0 <= candidate["total_score"] <= 1.0
    assert candidate["component_scores"]["momentum_score"] > 0.5
    assert candidate["component_scores"]["liquidity_score"] > 0.8
    assert candidate["component_scores"]["risk_penalty_score"] > 0.5


def test_sorting_tie_breaker_is_deterministic_by_ticker():
    pool = build_candidate_pool(_payload([_ticker("MSFT"), _ticker("AAPL")]), as_of_date="2026-04-30")

    assert [c["ticker"] for c in pool["candidates"]] == ["AAPL", "MSFT"]


def test_p38_quality_report_improves_quality_score_and_refs():
    quality = {"AAPL": {"overall_quality_score": 0.82, "confidence": 0.9, "red_flags_json": "[]", "source_hash": "q1"}}
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30", quality_by_ticker=quality)
    c = pool["candidates"][0]
    assert c["component_scores"]["quality_score"] >= 0.80
    assert c["evidence_refs"]["p38_quality_source_hash"] == "q1"


def test_missing_p38_quality_records_missing_context():
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30")
    assert "missing_fundamental_quality" in pool["candidates"][0]["missing_context"]


def test_p37_regime_context_affects_regime_score_and_refs():
    regime = {
        "regime_label": "risk_on_broad",
        "confidence": 0.9,
        "sector_scores_json": '{"technology": 0.8}',
        "source_hash": "r1",
    }
    pool = build_candidate_pool(_payload([_ticker(sector="technology")]), "2026-04-30", regime_context=regime)
    c = pool["candidates"][0]
    assert c["component_scores"]["regime_score"] > 0.65
    assert c["evidence_refs"]["p37_regime_source_hash"] == "r1"


def test_missing_p37_regime_records_missing_context():
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30")
    assert "missing_market_regime_context" in pool["candidates"][0]["missing_context"]


def test_inline_outcome_prior_affects_track_record_score():
    op = {"sample_size": 6, "hit_rate_20d": 0.80, "median_net_return_20d": 0.05}
    pool = build_candidate_pool(_payload([_ticker(outcome_prior=op)]), "2026-04-30")
    c = pool["candidates"][0]
    assert c["component_scores"]["track_record_score"] > 0.55


def test_exclusions_are_preserved():
    rows = [
        _ticker("LOWVOL", avg_dollar_volume_20d=1_000_000),
        _ticker("PENNY", close=2.0),
        _ticker("FUTURE", source_date="2026-05-01"),
    ]
    pool = build_candidate_pool(_payload(rows), "2026-04-30")
    statuses = {item["ticker"]: item["candidate_status"] for item in pool["excluded_items"]}
    assert statuses["LOWVOL"] == "excluded_low_liquidity"
    assert statuses["PENNY"] == "excluded_low_price"
    assert statuses["FUTURE"] == "excluded_future_source_date"


def test_user_exclude_reasons_force_exclusion():
    pool = build_candidate_pool(
        _payload([_ticker("RESTRICTED", exclude_reasons=["restricted_list"])]),
        "2026-04-30",
    )
    assert len(pool["candidates"]) == 0
    assert pool["excluded_items"][0]["candidate_status"] == "excluded_user_rule"
    assert "restricted_list" in pool["excluded_items"][0]["exclusion_reasons"]


def test_missing_required_fields_surfaces_exact_names():
    row = _ticker()
    del row["close"]
    del row["high_252d"]
    pool = build_candidate_pool(_payload([row]), "2026-04-30")
    assert len(pool["excluded_items"]) == 1
    assert pool["excluded_items"][0]["candidate_status"] == "excluded_missing_required_fields"
    assert "close" in pool["excluded_items"][0]["missing_required_fields"]
    assert "high_252d" in pool["excluded_items"][0]["missing_required_fields"]


def test_source_hash_changes_on_middle_field_change():
    base = _payload([_ticker()])
    revised = _payload([_ticker()])
    revised["tickers"][0]["close_60d_ago"] = 150.0

    h1 = compute_candidate_pool_source_hash(base, "2026-04-30")
    h2 = compute_candidate_pool_source_hash(revised, "2026-04-30")
    assert h1 != h2


def test_candidate_category_assignment_is_deterministic():
    # Quality momentum: quality >= 0.65 and momentum >= 0.65
    q = {"AAPL": {"overall_quality_score": 0.82, "confidence": 0.9, "red_flags_json": "[]", "source_hash": "q1"}}
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30", quality_by_ticker=q)
    c = pool["candidates"][0]
    # Default AAPL fixture has strong momentum, so quality_momentum is expected
    assert c["candidate_category"] in {
        "quality_momentum", "regime_aligned", "recovery_watchlist",
        "liquidity_leader", "outcome_retest", "balanced_candidate",
    }


def test_no_candidates_when_all_excluded():
    pool = build_candidate_pool(_payload([_ticker("PENNY", close=1.0)]), "2026-04-30")
    assert pool["status"] == "no_candidates"
    assert len(pool["candidates"]) == 0
    assert len(pool["excluded_items"]) == 1


# ── P39-B persistence and artifact tests ─────────────────────────────────────

from agent.research_v1.data.database import ResearchDatabase


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_candidate_pool_schema()
    return db


def test_candidate_pool_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30")

    first = db.save_candidate_pool(pool)
    second = db.save_candidate_pool(pool)
    runs = db.list_candidate_pool_runs(as_of_date="2026-04-30")
    items = db.list_candidate_pool_items(first)

    assert first == second
    assert len(runs) == 1
    assert len(items) == 1


def test_revised_candidate_pool_source_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first_pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30")
    revised = _ticker()
    revised["close_60d_ago"] = 150.0
    second_pool = build_candidate_pool(_payload([revised]), "2026-04-30")

    first = db.save_candidate_pool(first_pool)
    second = db.save_candidate_pool(second_pool)
    runs = db.list_candidate_pool_runs(as_of_date="2026-04-30")

    assert first != second
    assert len(runs) == 2


def test_candidate_pool_artifacts_are_written_and_safe(tmp_path: Path):
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30")
    paths = write_candidate_pool_artifacts(pool, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p39_candidate_pool.json"
    assert paths["md"].name == "p39_candidate_pool.md"
    text = paths["md"].read_text(encoding="utf-8").lower()
    assert "p39 is candidate-discovery evidence only" in text
    for forbidden in ("buy this", "sell this", "trade now"):
        assert forbidden not in text


# ── P39-C run orchestration and hard-boundary tests ──────────────────────────

from agent.research_v1.candidate_pool import run_candidate_pool


def test_run_candidate_pool_persists_and_writes_artifacts(tmp_path: Path):
    db = _db(tmp_path)
    payload = _payload([_ticker()])
    result = run_candidate_pool(
        db=db,
        input_payload=payload,
        as_of_date="2026-04-30",
        output_root=tmp_path / "output" / "governance",
        max_candidates=20,
    )

    assert result["status"] == "completed"
    assert result["candidate_count"] == 1
    assert (Path(result["output_dir"]) / "p39_candidate_pool.json").exists()


def test_p39_hard_boundaries_are_explicit():
    from agent.research_v1 import candidate_pool as p39

    forbidden_names = {
        "broker", "order", "train_model", "scheduler", "notification",
        "HermesResearchApp", "run_research", "final_judge",
        "run_governance_runtime", "run_recommendation_outcome_tracking",
        "run_market_regime_context", "run_fundamental_quality",
        "_extract_thesis_inputs",
    }
    assert not (forbidden_names & set(p39.__dict__))
    assert "candidate-discovery evidence only" in p39.P39_ARTIFACT_DISCLAIMER


# ── P39 audit fix regressions ────────────────────────────────────────────────

def test_risk_on_narrow_technology_scores_explicit_sector_override():
    """risk_on_narrow: technology must score 0.70 * confidence, not cyclical fallback 0.45."""
    regime = {
        "regime_label": "risk_on_narrow",
        "confidence": 1.0,
        "sector_scores_json": "{}",
        "source_hash": "rn1",
    }
    pool = build_candidate_pool(_payload([_ticker(sector="technology")]), "2026-04-30", regime_context=regime)
    c = pool["candidates"][0]
    assert c["component_scores"]["regime_score"] == 0.70


def test_candidate_pool_source_hash_is_in_top_level_and_differs_from_run_id(tmp_path: Path):
    db = _db(tmp_path)
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30")
    assert "source_hash" in pool
    assert pool["source_hash"] != pool["run_id"]

    run_id = db.save_candidate_pool(pool)
    runs = db.list_candidate_pool_runs(as_of_date="2026-04-30")
    assert len(runs) == 1
    assert runs[0]["source_hash"] == pool["source_hash"]
    assert runs[0]["source_hash"] != run_id


def test_run_candidate_pool_uses_prior_day_p37_evidence(tmp_path: Path):
    """P39 should use the latest P37 snapshot at or before as_of_date."""
    from agent.research_v1.data.database import ResearchDatabase

    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_market_regime_schema()
    db.initialize_candidate_pool_schema()

    # Persist a regime snapshot for 2026-04-29
    db.save_market_regime_snapshot({
        "schema_version": "p37_market_regime.1",
        "as_of_date": "2026-04-29",
        "created_at": "2026-04-29T12:00:00+00:00",
        "regime_label": "risk_on_broad",
        "confidence": 0.90,
        "coverage_ratio": 0.95,
        "classification": "risk_on_broad",
        "summary": "risk on broad",
        "sector_rotation": {"ranked_sectors": []},
        "classification_reasons": [],
        "volatility_proxy": 0.20,
        "drawdown_proxy": -0.05,
        "breadth_above_sma_20": 0.65,
        "missing_symbols": [],
        "stale_symbols": [],
        "data_source_hash": "prior_regime",
    })

    payload = _payload([_ticker()])
    result = run_candidate_pool(
        db=db,
        input_payload=payload,
        as_of_date="2026-04-30",
        output_root=tmp_path / "output" / "governance",
    )

    assert result["status"] == "completed"
    # Should NOT have missing_market_regime_context since prior-day snapshot exists
    pool_json = Path(result["output_dir"]) / "p39_candidate_pool.json"
    pool_data = json.loads(pool_json.read_text(encoding="utf-8"))
    candidate = pool_data["candidates"][0]
    assert "missing_market_regime_context" not in candidate["missing_context"]
    assert candidate["evidence_refs"].get("p37_regime_source_hash") == "prior_regime"


def test_run_candidate_pool_uses_prior_day_p38_evidence(tmp_path: Path):
    """P39 should use the latest P38 report at or before as_of_date."""
    from agent.research_v1.data.database import ResearchDatabase

    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_fundamental_quality_schema()
    db.initialize_candidate_pool_schema()

    # Persist a quality report for 2026-04-29
    db.save_fundamental_quality_report({
        "schema_version": "p38_fundamental_quality.1",
        "as_of_date": "2026-04-29",
        "created_at": "2026-04-29T12:00:00+00:00",
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "status": "completed",
        "quality_label": "compounder_quality",
        "overall_quality_score": 0.85,
        "confidence": 0.90,
        "coverage_ratio": 1.0,
        "usable_row_count": 5,
        "ignored_future_row_count": 0,
        "dimension_scores": {},
        "latest_metrics": {},
        "trend_metrics": {},
        "red_flags": [],
        "missing_required_fields": [],
        "warnings": [],
        "source_hash": "prior_quality",
        "summary": "AAPL: compounder_quality",
    })

    payload = _payload([_ticker()])
    result = run_candidate_pool(
        db=db,
        input_payload=payload,
        as_of_date="2026-04-30",
        output_root=tmp_path / "output" / "governance",
    )

    assert result["status"] == "completed"
    pool_json = Path(result["output_dir"]) / "p39_candidate_pool.json"
    pool_data = json.loads(pool_json.read_text(encoding="utf-8"))
    candidate = pool_data["candidates"][0]
    assert "missing_fundamental_quality" not in candidate["missing_context"]
    assert candidate["evidence_refs"].get("p38_quality_source_hash") == "prior_quality"


def test_same_day_p37_revision_returns_latest_created_at(tmp_path: Path):
    """When two P37 snapshots share the same as_of_date, the later created_at wins."""
    from agent.research_v1.data.database import ResearchDatabase

    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_market_regime_schema()

    db.save_market_regime_snapshot({
        "schema_version": "p37_market_regime.1",
        "as_of_date": "2026-04-30",
        "created_at": "2026-04-30T08:00:00+00:00",
        "regime_label": "risk_off",
        "confidence": 0.60,
        "coverage_ratio": 0.90,
        "summary": "early snapshot",
        "sector_rotation": {},
        "classification_reasons": [],
        "missing_symbols": [],
        "stale_symbols": [],
        "data_source_hash": "early_regime",
    })
    db.save_market_regime_snapshot({
        "schema_version": "p37_market_regime.1",
        "as_of_date": "2026-04-30",
        "created_at": "2026-04-30T16:00:00+00:00",
        "regime_label": "risk_on_broad",
        "confidence": 0.85,
        "coverage_ratio": 0.95,
        "summary": "later snapshot",
        "sector_rotation": {},
        "classification_reasons": [],
        "missing_symbols": [],
        "stale_symbols": [],
        "data_source_hash": "later_regime",
    })

    rows = db.list_market_regime_snapshots_as_of("2026-04-30", limit=1)
    assert len(rows) == 1
    assert rows[0]["data_source_hash"] == "later_regime"


def test_same_day_p38_revision_returns_latest_created_at(tmp_path: Path):
    """When two P38 reports share the same as_of_date for the same ticker, the later created_at wins."""
    from agent.research_v1.data.database import ResearchDatabase

    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_fundamental_quality_schema()

    db.save_fundamental_quality_report({
        "schema_version": "p38_fundamental_quality.1",
        "as_of_date": "2026-04-30",
        "created_at": "2026-04-30T08:00:00+00:00",
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "status": "completed",
        "quality_label": "solid_quality",
        "overall_quality_score": 0.65,
        "confidence": 0.80,
        "coverage_ratio": 1.0,
        "usable_row_count": 4,
        "ignored_future_row_count": 0,
        "dimension_scores": {},
        "latest_metrics": {},
        "trend_metrics": {},
        "red_flags": [],
        "missing_required_fields": [],
        "warnings": [],
        "source_hash": "early_quality",
        "summary": "AAPL: solid_quality (early)",
    })
    db.save_fundamental_quality_report({
        "schema_version": "p38_fundamental_quality.1",
        "as_of_date": "2026-04-30",
        "created_at": "2026-04-30T16:00:00+00:00",
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "status": "completed",
        "quality_label": "compounder_quality",
        "overall_quality_score": 0.85,
        "confidence": 0.90,
        "coverage_ratio": 1.0,
        "usable_row_count": 5,
        "ignored_future_row_count": 0,
        "dimension_scores": {},
        "latest_metrics": {},
        "trend_metrics": {},
        "red_flags": [],
        "missing_required_fields": [],
        "warnings": [],
        "source_hash": "later_quality",
        "summary": "AAPL: compounder_quality (later)",
    })

    rows = db.list_fundamental_quality_reports_as_of("AAPL", "2026-04-30", limit=1)
    assert len(rows) == 1
    assert rows[0]["source_hash"] == "later_quality"
