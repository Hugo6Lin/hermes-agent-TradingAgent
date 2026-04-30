"""Tests for P36 recommendation outcome tracking."""

from __future__ import annotations

from pathlib import Path

from agent.research_v1.contracts import CanonicalReport, CanonicalSignal, ResearchMode, ResearchTask
from agent.research_v1.data.database import ResearchDatabase


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_research_core()
    db.initialize_canonical_outcome_schema()
    return db


def _task() -> ResearchTask:
    return ResearchTask(
        task_id="task_p36_aapl",
        request_text="Research AAPL",
        tickers=["AAPL"],
        research_mode=ResearchMode.STANDARD,
    )


def _signal() -> CanonicalSignal:
    return CanonicalSignal(
        ticker="AAPL",
        rating="BUY",
        confidence=0.82,
        priority_score=88.0,
        entry_price=100.0,
        stop_loss=92.0,
        take_profit=115.0,
        holding_horizon="60d",
        decision_reason="P36 fixture",
    )


def _seed_signal(db: ResearchDatabase) -> str:
    task = _task()
    signal = _signal()
    db.save_research_task(task)
    return db.save_canonical_signal(signal, task.task_id)


def _seed_report_with_decision_card(db: ResearchDatabase, primary_action: str = "Buy Stock") -> None:
    """Seed a canonical report whose deserialized decision_card has primary_action."""
    from agent.research_v1.contracts import CanonicalReport
    task = _task()
    db.save_research_task(task)
    report = CanonicalReport(
        title="AAPL report",
        executive_summary="summary",
        bottom_line="line",
        why_now="now",
        bull_case="bull",
        bear_case="bear",
        trade_plan=None,
        risk_watch=[],
        key_evidence=[],
        appendix={},
        decision_card={"primary_action": primary_action, "confidence": 0.9},
        instrument_rec=None,
        options_structure=None,
        early_exit=None,
    )
    db.save_canonical_report(report, task.task_id, "AAPL")


def _outcome_payload(signal_id: str, data_hash: str = "hash_a") -> dict:
    return {
        "schema_version": "p36_recommendation_outcome.1",
        "signal_id": signal_id,
        "task_id": "task_p36_aapl",
        "ticker": "AAPL",
        "action": "Buy Stock",
        "rating": "BUY",
        "horizon_days": 5,
        "calendar": "XNYS",
        "entry_rule": "next_open",
        "entry_price": 101.0,
        "entry_date": "2026-04-01",
        "exit_price": 110.0,
        "exit_date": "2026-04-08",
        "target_reached": False,
        "stop_breached": False,
        "target_reached_before_stop": False,
        "benchmark_return_pct": None,
        "gross_return_pct": 0.0891089109,
        "net_return_pct": 0.0891089109,
        "max_drawdown_pct": -0.01,
        "win": True,
        "win_definition": "net_return_positive",
        "status": "evaluated",
        "evaluation_proxy": "none",
        "cost_basis": "none",
        "cost_bps": 0.0,
        "data_source": "fake_provider",
        "price_adjustment": "adjusted",
        "data_source_hash": data_hash,
        "path_precision": "ohlc",
        "evaluated_for_date": "2026-04-30",
        "evaluated_at": "2026-04-30T12:00:00Z",
    }


def test_canonical_outcome_schema_persists_rows(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)

    outcome_id = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id))
    rows = db.list_canonical_outcomes_by_signal(signal_id)

    assert outcome_id
    assert len(rows) == 1
    assert rows[0]["schema_version"] == "p36_recommendation_outcome.1"
    assert rows[0]["status"] == "evaluated"
    assert rows[0]["action"] == "Buy Stock"
    assert rows[0]["evaluated_for_date"] == "2026-04-30"
    assert rows[0]["evaluated_at"] == "2026-04-30T12:00:00Z"


def test_canonical_outcome_natural_key_noops_same_data(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)

    first = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="same_hash"))
    second = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="same_hash"))
    rows = db.list_canonical_outcomes_by_signal(signal_id)

    assert first == second
    assert len(rows) == 1


def test_canonical_outcome_revised_data_hash_appends_row(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)

    first = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="hash_a"))
    second = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="hash_b"))
    rows = db.list_canonical_outcomes_by_signal(signal_id)

    assert first != second
    assert len(rows) == 2


def test_canonical_outcome_summaries_group_by_action_rating_ticker_and_horizon(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)
    db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="hash_a"))

    assert db.summarize_outcomes_by("action")[0]["group"] == "Buy Stock"
    assert db.summarize_outcomes_by("rating")[0]["group"] == "BUY"
    assert db.summarize_outcomes_by("ticker")[0]["group"] == "AAPL"
    assert db.summarize_outcomes_by("horizon")[0]["group"] == 5


# ── P36-B computation tests ──────────────────────────────────────────────────

from datetime import date

from agent.research_v1.recommendation_outcomes import (
    P36_ARTIFACT_DISCLAIMER,
    build_distribution_summary,
    compute_data_source_hash,
    evaluate_recommendation_signal,
    normalize_price_rows,
    resolve_calendar,
    resolve_signal_action,
    run_recommendation_outcome_tracking,
    write_recommendation_outcome_artifacts,
)


class FakeHistoryProvider:
    data_source = "fake_provider"
    price_adjustment = "adjusted"

    def __init__(self, rows):
        self.rows = rows

    def fetch_history(self, symbol, start_date, end_date):
        return self.rows


def _rows(start=100.0, count=70):
    rows = []
    for idx in range(count):
        price = start + idx
        rows.append({
            "date": f"2026-04-{idx + 1:02d}" if idx < 30 else f"2026-05-{idx - 29:02d}",
            "open": price,
            "high": price + 2.0,
            "low": price - 2.0,
            "close": price + 1.0,
            "price_adjustment": "adjusted",
        })
    return rows


def test_buy_stock_evaluates_default_horizons_with_ohlc_data():
    outcomes = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_1",
            "task_id": "task_1",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": 92.0,
            "take_profit": 115.0,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(_rows()),
        evaluated_for_date=date(2026, 4, 30),
    )

    assert [row["horizon_days"] for row in outcomes] == [5, 20, 60]
    assert all(row["status"] == "evaluated" for row in outcomes)
    assert outcomes[0]["entry_rule"] == "next_open"
    # Entry is next trading day after signal date (2026-04-01 signal -> 2026-04-02 open)
    assert outcomes[0]["entry_price"] == 101.0
    assert outcomes[0]["path_precision"] == "ohlc"


def test_buy_call_uses_underlying_price_proxy():
    outcomes = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_2",
            "task_id": "task_2",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Call",
        provider=FakeHistoryProvider(_rows()),
        evaluated_for_date=date(2026, 4, 30),
    )

    assert all(row["status"] == "evaluated" for row in outcomes)
    assert all(row["evaluation_proxy"] == "underlying_price_proxy" for row in outcomes)


def test_option_income_and_spread_structures_are_not_evaluable_in_v1():
    for action in ["Bull Call Spread", "Sell Cash-Secured Put", "Covered Call"]:
        outcomes = evaluate_recommendation_signal(
            signal={
                "signal_id": f"signal_{action}",
                "task_id": "task_struct",
                "ticker": "AAPL",
                "rating": "BUY",
                "entry_price": 100.0,
                "stop_loss": None,
                "take_profit": None,
                "created_at": "2026-04-01T20:00:00Z",
            },
            action=action,
            provider=FakeHistoryProvider(_rows()),
            evaluated_for_date=date(2026, 4, 30),
        )
        assert {row["status"] for row in outcomes} == {"not_evaluable_in_v1"}


def test_watchlist_and_no_trade_are_not_applicable():
    for action in ["Watchlist", "No Trade"]:
        outcomes = evaluate_recommendation_signal(
            signal={
                "signal_id": f"signal_{action}",
                "task_id": "task_na",
                "ticker": "AAPL",
                "rating": "HOLD",
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "created_at": "2026-04-01T20:00:00Z",
            },
            action=action,
            provider=FakeHistoryProvider(_rows()),
            evaluated_for_date=date(2026, 4, 30),
        )
        assert {row["status"] for row in outcomes} == {"not_applicable"}


def test_missing_action_or_entry_price_is_invalid_signal():
    missing_action = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_missing_action",
            "task_id": "task_invalid",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action=None,
        provider=FakeHistoryProvider(_rows()),
        evaluated_for_date=date(2026, 4, 30),
    )
    missing_entry = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_missing_entry",
            "task_id": "task_invalid",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(_rows()),
        evaluated_for_date=date(2026, 4, 30),
    )

    assert {row["status"] for row in missing_action} == {"invalid_signal"}
    assert {row["status"] for row in missing_entry} == {"invalid_signal"}


def test_missing_next_open_or_horizon_row_is_insufficient_data():
    no_open_rows = _rows()
    # Entry is next trading day (> signal date), so set open=None on row 1
    no_open_rows[1] = {**no_open_rows[1], "open": None}
    no_open = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_no_open",
            "task_id": "task_data",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(no_open_rows),
        evaluated_for_date=date(2026, 4, 30),
    )
    short_history = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_short_history",
            "task_id": "task_data",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(_rows(count=6)),
        evaluated_for_date=date(2026, 4, 30),
    )

    assert {row["status"] for row in no_open} == {"insufficient_data"}
    assert any(row["horizon_days"] == 20 and row["status"] == "insufficient_data" for row in short_history)


def test_resolve_signal_action_reads_deserialized_decision_card(tmp_path: Path):
    """P1-1: get_canonical_reports_by_task deserializes decision_card_json into
    decision_card. resolve_signal_action must read the deserialized key."""
    db = _db(tmp_path)
    _seed_report_with_decision_card(db, primary_action="Buy Call")
    action = resolve_signal_action(db, "task_p36_aapl")
    assert action == "Buy Call"


def test_resolve_signal_action_reads_instrument_rec_when_no_decision_card(tmp_path: Path):
    """P1-1b: Falls back to instrument_rec when decision_card has no primary_action."""
    db = _db(tmp_path)
    task = _task()
    db.save_research_task(task)
    report = CanonicalReport(
        title="AAPL fallback",
        executive_summary="summary",
        bottom_line="line",
        why_now="now",
        bull_case="bull",
        bear_case="bear",
        trade_plan=None,
        risk_watch=[],
        key_evidence=[],
        appendix={},
        decision_card=None,
        instrument_rec={"primary_action": "Sell Cash-Secured Put"},
        options_structure=None,
        early_exit=None,
    )
    db.save_canonical_report(report, task.task_id, "AAPL")
    action = resolve_signal_action(db, "task_p36_aapl")
    assert action == "Sell Cash-Secured Put"


def test_run_outcome_tracking_uses_injected_provider(tmp_path: Path):
    """P1-2: run_recommendation_outcome_tracking must accept an injectable
    provider and use it for history fetching."""
    db = _db(tmp_path)
    task = _task()
    signal = _signal()
    db.save_research_task(task)
    db.save_canonical_signal(signal, task.task_id)
    _seed_report_with_decision_card(db, primary_action="Buy Stock")

    provider = FakeHistoryProvider(_rows())
    result = run_recommendation_outcome_tracking(
        db=db,
        evaluated_for_date=date(2026, 4, 30),
        limit=10,
        provider=provider,
    )

    # With 70 rows and entry at next day, horizons 5 and 20 are evaluated;
    # horizon 60 may be insufficient_data depending on available rows.
    assert result["evaluated_count"] > 0


def test_next_open_enters_after_signal_date():
    """P1-3: Entry must be the first trading row AFTER the signal date,
    not the signal day itself (which may have already closed)."""
    rows = _rows(start=100.0, count=70)
    # Signal created on 2026-04-01. The first row is also 2026-04-01.
    # Entry should be at 2026-04-02 (the next trading row), not 2026-04-01.
    outcomes = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_next_open",
            "task_id": "task_next_open",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(rows),
        evaluated_for_date=date(2026, 4, 30),
    )
    # Entry should be at 2026-04-02 open (101.0), not 2026-04-01 open (100.0)
    assert outcomes[0]["entry_date"] == "2026-04-02"
    assert outcomes[0]["entry_price"] == 101.0


def test_target_before_stop_respects_event_order():
    """P1-4: If target is reached before stop is breached, it's a win."""
    # Use enough rows so price reaches target (> signal date entry at row 1).
    # With count=25, entry at row 1 (open=101), horizon 5 exit at row 6
    # (close=107), path max high at row 6 is 108. Need count>=15 so that
    # within the 5-day path the high exceeds target 110.
    # Actually use count=25 and check horizon 5 path: rows 1-6 have highs
    # 103,104,105,106,107,108.  Target 110 not reached.  So use a lower
    # target or more rows.
    rows = _rows(start=100.0, count=25)
    outcomes = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_order",
            "task_id": "task_order",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": 95.0,
            "take_profit": 105.0,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(rows),
        evaluated_for_date=date(2026, 4, 30),
    )
    # Entry at row 1 (open=101). Path highs: 103,104,105 -> target 105
    # reached at row 3 high=105.  Stop 95 never breached (lowest low=99).
    assert outcomes[0]["target_reached"] is True
    assert outcomes[0]["win"] is True
    assert outcomes[0]["target_reached_before_stop"] is True


def test_non_evaluated_outcome_rows_are_persisted(tmp_path: Path):
    """P2-1: Rows with not_applicable/not_evaluable/invalid_signal status
    must be persisted with a deterministic status-based hash."""
    db = _db(tmp_path)
    signal_id = _seed_signal(db)
    task = _task()
    db.save_research_task(task)

    # Seed a report with an action that maps to not_applicable
    report = CanonicalReport(
        title="AAPL watchlist",
        executive_summary="summary",
        bottom_line="line",
        why_now="now",
        bull_case="bull",
        bear_case="bear",
        trade_plan=None,
        risk_watch=[],
        key_evidence=[],
        appendix={},
        decision_card={"primary_action": "Watchlist"},
        instrument_rec=None,
        options_structure=None,
        early_exit=None,
    )
    db.save_canonical_report(report, task.task_id, "AAPL")

    result = run_recommendation_outcome_tracking(
        db=db,
        evaluated_for_date=date(2026, 4, 30),
        limit=10,
    )

    # not_applicable rows should be persisted, not just counted
    assert result["not_applicable_count"] > 0
    rows = db.list_canonical_outcomes_by_signal(signal_id)
    assert any(r["status"] == "not_applicable" for r in rows)


def test_artifact_writer_handles_distribution_summary_with_mean_values(tmp_path: Path):
    """P2-2: Markdown writer must not crash when distribution rows have
    non-None mean_win/mean_loss values."""
    outcomes = [
        {**_outcome_payload("signal_a", "hash_a"), "action": "Buy Stock", "net_return_pct": 0.10, "max_drawdown_pct": -0.02, "win": True},
        {**_outcome_payload("signal_b", "hash_b"), "action": "Buy Stock", "net_return_pct": -0.04, "max_drawdown_pct": -0.08, "win": False},
        {**_outcome_payload("signal_c", "hash_c"), "action": "Buy Stock", "net_return_pct": 0.06, "max_drawdown_pct": -0.03, "win": True},
    ]
    summary = build_distribution_summary(outcomes)

    report = {
        "run_date": "2026-04-30",
        "evaluated_for_date": "2026-04-30",
        "schema_version": "p36_recommendation_outcome.1",
        "status": "completed",
        "signals_considered": 3,
        "outcome_rows_written": 3,
        "duplicate_rows_skipped": 0,
        "evaluated_count": 3,
        "not_applicable_count": 0,
        "not_evaluable_count": 0,
        "insufficient_data_count": 0,
        "invalid_signal_count": 0,
        "warnings": [],
        "distribution_summary": summary,
        "extreme_examples": {"largest_positive": [], "largest_negative": []},
        "disclaimer": P36_ARTIFACT_DISCLAIMER,
    }

    paths = write_recommendation_outcome_artifacts(report, tmp_path / "out")
    md_text = paths["md"].read_text()
    assert "Buy Stock" in md_text
    assert "Distribution Summary" in md_text


def test_calendar_hash_adjustment_cost_and_win_semantics():
    assert resolve_calendar("HK.00700") == "XHKG"
    assert resolve_calendar("US.AAPL") == "XNYS"
    assert resolve_calendar("AAPL") == "XNYS"

    rows = normalize_price_rows([
        {"date": "2026-04-01", "open": 100.0, "high": 102.0, "low": 98.0, "close": 101.0},
        {"date": "2026-04-02", "open": 101.0, "high": 120.0, "low": 99.0, "close": 119.0},
    ], default_price_adjustment="unknown")
    assert rows[0]["price_adjustment"] == "unknown"
    assert compute_data_source_hash(rows) == compute_data_source_hash(list(reversed(rows)))

    outcomes = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_win",
            "task_id": "task_win",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(_rows()),
        evaluated_for_date=date(2026, 4, 30),
        flat_cost_bps=10.0,
    )

    assert outcomes[0]["cost_basis"] == "flat_bps"
    assert outcomes[0]["cost_bps"] == 10.0
    assert outcomes[0]["net_return_pct"] < outcomes[0]["gross_return_pct"]
    assert outcomes[0]["win_definition"] == "target_reached_before_stop"


# ── P36-C artifact and hard-boundary tests ───────────────────────────────────


def test_distribution_summary_leads_with_central_tendency():
    outcomes = [
        {**_outcome_payload("signal_a", "hash_a"), "action": "Buy Stock", "net_return_pct": 0.10, "max_drawdown_pct": -0.02, "win": True},
        {**_outcome_payload("signal_b", "hash_b"), "action": "Buy Stock", "net_return_pct": -0.04, "max_drawdown_pct": -0.08, "win": False},
    ]

    summary = build_distribution_summary(outcomes)

    assert summary
    assert summary[0]["group_type"] in {"action", "rating", "horizon"}
    assert "median_net_return" in summary[0]
    assert "p25_net_return" in summary[0]
    assert "p75_net_return" in summary[0]


def test_artifact_writer_outputs_json_and_markdown(tmp_path: Path):
    report = {
        "run_date": "2026-04-30",
        "evaluated_for_date": "2026-04-30",
        "schema_version": "p36_recommendation_outcome.1",
        "status": "completed",
        "signals_considered": 1,
        "outcome_rows_written": 1,
        "duplicate_rows_skipped": 0,
        "evaluated_count": 1,
        "not_applicable_count": 0,
        "not_evaluable_count": 0,
        "insufficient_data_count": 0,
        "invalid_signal_count": 0,
        "warnings": [],
        "distribution_summary": [],
        "extreme_examples": [],
        "disclaimer": P36_ARTIFACT_DISCLAIMER,
    }

    paths = write_recommendation_outcome_artifacts(report, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p36_recommendation_outcomes.json"
    assert paths["md"].name == "p36_recommendation_outcomes.md"
    assert paths["json"].exists()
    assert paths["md"].exists()
    assert "does not approve production adoption" in paths["md"].read_text()


def test_p36_hard_boundaries_are_explicit():
    from agent.research_v1 import recommendation_outcomes as p36

    forbidden_names = {
        "broker",
        "order",
        "scheduler",
        "notification",
        "train_model",
        "run_governance_runtime",
    }
    module_names = set(p36.__dict__)

    assert not (forbidden_names & module_names)
    assert "governance" in p36.P36_ARTIFACT_DISCLAIMER
