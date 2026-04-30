"""P20 factor contracts and persistence tests."""

import json
import tempfile
import os
import pytest

from agent.research_v1.contracts import (
    FactorSnapshot,
    ForwardReturnObservation,
    UniverseMembershipSnapshot,
    LLMAdjustment,
    ThesisGateResult,
    ClassificationReason,
    SourceValueRef,
)
from agent.research_v1.factor_persistence import (
    initialize_factor_schema,
    save_factor_snapshot,
    get_factor_snapshot,
    get_latest_factor_snapshot,
    save_forward_return_observation,
    get_forward_return_observations,
    get_forward_return_observations_by_ticker,
    save_universe_membership_snapshot,
    get_universe_membership_snapshot,
)
from agent.research_v1.data.database import ResearchDatabase


def _make_conn():
    """Create a temporary in-memory SQLite connection with the factor schema."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    initialize_factor_schema(conn)
    return conn


class TestLLMAdjustment:
    def test_llm_adjustment_validates_bound(self):
        # delta exceeds max_abs_delta -> should raise during construction
        with pytest.raises(ValueError) as exc_info:
            LLMAdjustment(
                affected_category="quality",
                delta=0.20,
                max_abs_delta=0.15,
                reason="test",
                source_refs=["ref1"],
                model_provider="openai",
                model_name="gpt-4",
                prompt_version="v1",
            )
        assert "max_abs_delta" in str(exc_info.value)

    def test_llm_adjustment_accepts_valid_delta(self):
        adj = LLMAdjustment(
            affected_category="quality",
            delta=0.10,
            max_abs_delta=0.15,
            reason="test",
            source_refs=["ref1"],
            model_provider="openai",
            model_name="gpt-4",
            prompt_version="v1",
        )
        assert adj.delta == 0.10


class TestFactorSnapshot:
    def test_factor_snapshot_roundtrip(self):
        conn = _make_conn()
        ss = FactorSnapshot(
            snapshot_id="snap_001",
            schema_version="p20.1",
            task_id="task_001",
            ticker="AAPL",
            as_of_timestamp="2026-04-24T10:00:00Z",
            trading_day="2026-04-24",
            data_as_of_date="2026-04-23",
            universe_id="sp500",
            universe_label="S&P 500",
            universe_membership_snapshot_id="um_001",
            company_quality_score=0.75,
            valuation_attractiveness_score=0.60,
            timing_market_fit_score=0.65,
            quality_coverage=0.80,
            valuation_coverage=0.70,
            timing_coverage=0.60,
            regime_coverage=0.90,
            llm_overlay_coverage=0.50,
            llm_adjustment_total=0.05,
            llm_adjustments=[
                LLMAdjustment(
                    affected_category="quality",
                    delta=0.05,
                    max_abs_delta=0.15,
                    reason="management quality observation",
                    source_refs=["earnings_call_q1"],
                    model_provider="openai",
                    model_name="gpt-4",
                    prompt_version="v1",
                )
            ],
            gate_results=[
                ThesisGateResult(
                    gate="coverage",
                    status="passed",
                    score=0.80,
                    threshold=0.50,
                    failing_dimension=None,
                    reason_code="sufficient_data",
                    recommended_action="none",
                )
            ],
            classification="Investable",
            classification_reason=ClassificationReason(
                classification="Investable",
                primary_gate="quality",
                primary_reason_code="quality_threshold_met",
                supporting_gates=["valuation", "timing"],
                blocking_gates=[],
                recommended_next_action="proceed_to_instrument_selection",
                human_summary="AAPL meets quality threshold with strong fundamentals and reasonable valuation.",
            ),
            negative_signal_strength_decile=3,
            thresholds_used={"no_trade_quality_threshold": 0.35, "investable_quality_threshold": 0.65},
            model_routes_used={"analyst": "fundamental_v1"},
            source_refs=[
                SourceValueRef(
                    field_name="profitability",
                    value=0.80,
                    source="funda_analyst",
                    fetched_at="2026-04-24T09:00:00Z",
                    as_of_date="2026-04-23",
                    provider="Futu",
                    quality_flags=[],
                )
            ],
            created_at="2026-04-24T10:00:00Z",
        )

        save_factor_snapshot(conn, ss)
        loaded = get_factor_snapshot(conn, "snap_001")

        assert loaded is not None
        assert loaded.snapshot_id == "snap_001"
        assert loaded.ticker == "AAPL"
        assert loaded.company_quality_score == 0.75
        assert loaded.classification == "Investable"
        assert len(loaded.llm_adjustments) == 1
        assert loaded.llm_adjustments[0].delta == 0.05
        assert len(loaded.gate_results) == 1
        assert loaded.gate_results[0].gate == "coverage"
        assert len(loaded.source_refs) == 1
        assert loaded.source_refs[0].field_name == "profitability"

    def test_factor_snapshot_deduplication_by_ticker_trading_day(self):
        conn = _make_conn()
        base = dict(
            schema_version="p20.1",
            task_id="task_001",
            ticker="TSLA",
            as_of_timestamp="2026-04-24T10:00:00Z",
            trading_day="2026-04-24",
            data_as_of_date="2026-04-23",
            universe_id="sp500",
            universe_label="S&P 500",
            universe_membership_snapshot_id="um_001",
            valuation_attractiveness_score=0.60,
            timing_market_fit_score=0.65,
            quality_coverage=0.80,
            valuation_coverage=0.70,
            timing_coverage=0.60,
            regime_coverage=0.90,
            llm_overlay_coverage=0.50,
            llm_adjustment_total=0.0,
            llm_adjustments=[],
            gate_results=[],
            classification="Investable",
            classification_reason=ClassificationReason(
                classification="Investable",
                primary_gate="quality",
                primary_reason_code="test",
                supporting_gates=[],
                blocking_gates=[],
                recommended_next_action="none",
                human_summary="test",
            ),
            negative_signal_strength_decile=None,
            thresholds_used={},
            model_routes_used={},
            source_refs=[],
            created_at="2026-04-24T10:00:00Z",
        )

        # Save first snapshot
        snap1 = FactorSnapshot(snapshot_id="snap_t1", **base, company_quality_score=0.75)
        save_factor_snapshot(conn, snap1)

        # Save second snapshot same ticker+trading_day but different score
        snap2 = FactorSnapshot(snapshot_id="snap_t2", **base, company_quality_score=0.50)
        save_factor_snapshot(conn, snap2)

        # get_latest should return snap_t2 (most recent by created_at)
        latest = get_latest_factor_snapshot(conn, "TSLA", "2026-04-24")
        assert latest.snapshot_id == "snap_t2"
        assert latest.company_quality_score == 0.50

        # Both stored for audit
        assert get_factor_snapshot(conn, "snap_t1") is not None
        assert get_factor_snapshot(conn, "snap_t2") is not None

    def test_universe_filter_prevents_cross_universe_leakage(self):
        """Same ticker+trading_day in different universes must not cross-contaminate."""
        conn = _make_conn()
        base = dict(
            schema_version="p20.1",
            task_id="task_001",
            ticker="AAPL",
            as_of_timestamp="2026-04-24T10:00:00Z",
            trading_day="2026-04-24",
            data_as_of_date="2026-04-23",
            valuation_attractiveness_score=0.60,
            timing_market_fit_score=0.65,
            quality_coverage=0.80,
            valuation_coverage=0.70,
            timing_coverage=0.60,
            regime_coverage=0.90,
            llm_overlay_coverage=0.50,
            llm_adjustment_total=0.0,
            llm_adjustments=[],
            gate_results=[],
            classification="Investable",
            classification_reason=ClassificationReason(
                classification="Investable",
                primary_gate="quality",
                primary_reason_code="test",
                supporting_gates=[],
                blocking_gates=[],
                recommended_next_action="none",
                human_summary="test",
            ),
            negative_signal_strength_decile=None,
            thresholds_used={},
            model_routes_used={},
            source_refs=[],
            created_at="2026-04-24T10:00:00Z",
        )

        # Snapshot in SP500 universe
        snap_sp500 = FactorSnapshot(
            snapshot_id="snap_sp500",
            universe_id="sp500",
            universe_label="S&P 500",
            universe_membership_snapshot_id="um_sp500",
            company_quality_score=0.80,
            **base,
        )
        save_factor_snapshot(conn, snap_sp500)

        # Snapshot in Nasdaq100 universe for same ticker+trading_day
        snap_ndx = FactorSnapshot(
            snapshot_id="snap_ndx",
            universe_id="nasdaq100",
            universe_label="NASDAQ 100",
            universe_membership_snapshot_id="um_ndx",
            company_quality_score=0.75,
            **base,
        )
        save_factor_snapshot(conn, snap_ndx)

        # Query WITHOUT universe filter: returns one of the two (deterministic by created_at+snapshot_id DESC)
        latest_any = get_latest_factor_snapshot(conn, "AAPL", "2026-04-24")
        assert latest_any.ticker == "AAPL"
        assert latest_any.universe_id in ("sp500", "nasdaq100")

        # Query WITH SP500 universe filter: returns SP500 snapshot only
        latest_sp500 = get_latest_factor_snapshot(conn, "AAPL", "2026-04-24", universe_membership_snapshot_id="um_sp500")
        assert latest_sp500.snapshot_id == "snap_sp500"
        assert latest_sp500.universe_id == "sp500"

        # Query WITH Nasdaq100 universe filter: returns Nasdaq100 snapshot only
        latest_ndx = get_latest_factor_snapshot(conn, "AAPL", "2026-04-24", universe_membership_snapshot_id="um_ndx")
        assert latest_ndx.snapshot_id == "snap_ndx"
        assert latest_ndx.universe_id == "nasdaq100"

        # Non-existent universe returns None
        latest_missing = get_latest_factor_snapshot(conn, "AAPL", "2026-04-24", universe_membership_snapshot_id="um_russell")
        assert latest_missing is None


class TestForwardReturnObservation:
    def test_forward_return_observation_roundtrip(self):
        conn = _make_conn()
        obs = ForwardReturnObservation(
            observation_id="fro_001",
            snapshot_id="snap_001",
            ticker="AAPL",
            trading_day="2026-04-24",
            horizon_days=21,
            return_value=0.08,
            return_source="close_to_close",
            price_start=150.0,
            price_end=162.0,
            start_price_date="2026-04-23",
            end_price_date="2026-05-22",
            gap_handled=False,
            computed_at="2026-04-24T16:00:00Z",
            gross_return_pct=0.08,
            net_return_pct=0.075,
            transaction_cost_pct=0.005,
            cost_source="CostModel",
        )

        save_forward_return_observation(conn, obs)
        loaded_list = get_forward_return_observations(conn, "snap_001")

        assert len(loaded_list) == 1
        loaded = loaded_list[0]
        assert loaded.observation_id == "fro_001"
        assert loaded.return_value == 0.08
        assert loaded.horizon_days == 21
        assert loaded.gap_handled is False
        assert loaded.gross_return_pct == 0.08
        assert loaded.net_return_pct == 0.075
        assert loaded.transaction_cost_pct == 0.005
        assert loaded.cost_source == "CostModel"

    def test_forward_return_observation_by_ticker_filtered_by_horizon(self):
        conn = _make_conn()
        for horizon in [1, 5, 21, 63]:
            gross = 0.05 * horizon
            net = gross - 0.001 * horizon
            obs = ForwardReturnObservation(
                observation_id=f"fro_h{horizon}",
                snapshot_id="snap_001",
                ticker="MSFT",
                trading_day="2026-04-24",
                horizon_days=horizon,
                return_value=gross,
                return_source="close_to_close",
                price_start=300.0,
                price_end=300.0 * (1 + gross),
                start_price_date="2026-04-23",
                end_price_date="2026-04-23",
                gap_handled=False,
                computed_at="2026-04-24T16:00:00Z",
                gross_return_pct=gross,
                net_return_pct=net,
                transaction_cost_pct=0.001 * horizon,
                cost_source="CostModel",
            )
            save_forward_return_observation(conn, obs)

        all_obs = get_forward_return_observations_by_ticker(conn, "MSFT")
        assert len(all_obs) == 4

        h21_obs = get_forward_return_observations_by_ticker(conn, "MSFT", horizon_days=21)
        assert len(h21_obs) == 1
        assert h21_obs[0].horizon_days == 21

    def test_missing_horizon_logged_with_reason(self):
        conn = _make_conn()
        obs = ForwardReturnObservation(
            observation_id="fro_missing",
            snapshot_id="snap_001",
            ticker="UNKNOWN",
            trading_day="2026-04-24",
            horizon_days=63,
            return_value=0.0,
            return_source="none",
            price_start=0.0,
            price_end=0.0,
            start_price_date="2026-04-23",
            end_price_date="2026-04-23",
            gap_handled=False,
            computed_at="2026-04-24T16:00:00Z",
            gross_return_pct=0.0,
            net_return_pct=0.0,
            transaction_cost_pct=0.0,
            cost_source=None,
            observation_status="missing_horizon",
            missing_reason="insufficient_price_history_for_63d_horizon",
        )
        save_forward_return_observation(conn, obs)
        loaded = get_forward_return_observations(conn, "snap_001")
        assert loaded[0].observation_status == "missing_horizon"
        assert "insufficient_price_history" in loaded[0].missing_reason


class TestUniverseMembershipSnapshot:
    def test_universe_membership_snapshot_roundtrip(self):
        conn = _make_conn()
        um = UniverseMembershipSnapshot(
            universe_membership_snapshot_id="um_sp500_20260424",
            universe_id="sp500",
            universe_label="S&P 500",
            as_of_timestamp="2026-04-24T08:00:00Z",
            members=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
            source="sp500_constituents",
            created_at="2026-04-24T08:00:00Z",
        )

        save_universe_membership_snapshot(conn, um)
        loaded = get_universe_membership_snapshot(conn, "um_sp500_20260424")

        assert loaded is not None
        assert loaded.universe_membership_snapshot_id == "um_sp500_20260424"
        assert loaded.universe_id == "sp500"
        assert len(loaded.members) == 5
        assert "AAPL" in loaded.members
        assert "GOOGL" in loaded.members


class TestResearchDatabaseIntegration:
    def test_research_database_factor_schema_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_factor.db")
            db = ResearchDatabase(db_path)
            db.initialize_factor_schema()
            # Verify tables exist
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
                "('factor_snapshots', 'forward_return_observations', 'universe_membership_snapshots')"
            )
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            assert set(tables) == {
                "factor_snapshots",
                "forward_return_observations",
                "universe_membership_snapshots",
            }

    def test_save_and_get_factor_snapshot_via_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_factor2.db")
            db = ResearchDatabase(db_path)
            db.initialize_factor_schema()

            ss = FactorSnapshot(
                snapshot_id="snap_db_001",
                schema_version="p20.1",
                task_id="task_001",
                ticker="NVDA",
                as_of_timestamp="2026-04-24T10:00:00Z",
                trading_day="2026-04-24",
                data_as_of_date="2026-04-23",
                universe_id="nasdaq100",
                universe_label="NASDAQ 100",
                universe_membership_snapshot_id="um_ndx_001",
                company_quality_score=0.85,
                valuation_attractiveness_score=0.70,
                timing_market_fit_score=0.75,
                quality_coverage=0.90,
                valuation_coverage=0.80,
                timing_coverage=0.70,
                regime_coverage=0.95,
                llm_overlay_coverage=0.60,
                llm_adjustment_total=0.05,
                llm_adjustments=[],
                gate_results=[],
                classification="Investable",
                classification_reason=ClassificationReason(
                    classification="Investable",
                    primary_gate="quality",
                    primary_reason_code="high_quality_score",
                    supporting_gates=["valuation", "timing"],
                    blocking_gates=[],
                    recommended_next_action="proceed",
                    human_summary="NVDA shows high quality with strong momentum.",
                ),
                negative_signal_strength_decile=2,
                thresholds_used={"no_trade_quality_threshold": 0.35},
                model_routes_used={},
                source_refs=[],
                created_at="2026-04-24T10:00:00Z",
            )

            db.save_factor_snapshot(ss)
            loaded = db.get_factor_snapshot("snap_db_001")

            assert loaded is not None
            assert loaded.ticker == "NVDA"
            assert loaded.company_quality_score == 0.85
            assert loaded.classification == "Investable"
