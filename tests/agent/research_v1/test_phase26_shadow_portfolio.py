"""Phase 26 shadow portfolio simulation and governance tests."""

import json
from dataclasses import dataclass, asdict

import pytest

from agent.research_v1.phase26_shadow_portfolio import (
    PortfolioSimulationError,
    PortfolioSimulationRequest,
    run_shadow_portfolio_simulation,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@dataclass
class FakePhase25Decision:
    decision: str
    training_run_id: str = "train_run_001"
    experiment_id: str = "exp_xgb_v1"
    candidate_namespace: str = "shadow_meta_model.xgb_v1"
    apply_to_production: bool = False
    production_config_changes: dict = None

    def __post_init__(self):
        if self.production_config_changes is None:
            self.production_config_changes = {}

    def to_dict(self):
        return asdict(self)


@dataclass
class FakePhase25Report:
    schema_version: str = "phase25_model_evaluation.1"
    evaluation_id: str = "eval_001"
    training_run_id: str = "train_run_001"
    experiment_id: str = "exp_xgb_v1"
    candidate_namespace: str = "shadow_meta_model.xgb_v1"
    model_family: str = "linear_baseline"
    total_windows: int = 4
    evaluated_windows: int = 4
    blocked_windows: int = 0
    total_validation_predictions: int = 20
    aggregate_model_rank_ic: float = 1.0
    aggregate_baseline_rank_ic: float = 0.0
    aggregate_rank_ic_improvement: float = 1.0
    aggregate_model_hit_rate: float = 1.0
    aggregate_baseline_hit_rate: float = 0.0
    aggregate_hit_rate_improvement: float = 1.0
    aggregate_model_spread_return: float = 0.065
    aggregate_baseline_spread_return: float = 0.0
    aggregate_spread_return_improvement: float = 0.065
    window_results: list = None
    safety_violations: list = None
    warnings: list = None
    baseline_source: str = "generated_zero"
    created_at: str = "2026-04-25T00:00:00+00:00"

    def __post_init__(self):
        if self.window_results is None:
            self.window_results = []
        if self.safety_violations is None:
            self.safety_violations = []
        if self.warnings is None:
            self.warnings = []

    def to_dict(self):
        return asdict(self)


@dataclass
class FakePhase25Result:
    evaluation_report: FakePhase25Report
    readiness_decision: FakePhase25Decision

    def to_dict(self):
        return {
            "evaluation_report": self.evaluation_report.to_dict(),
            "readiness_decision": self.readiness_decision.to_dict(),
        }


def _pred(window_id, ticker, value, target, sector="TECH"):
    return {
        "window_id": window_id,
        "snapshot_id": f"{window_id}_{ticker}",
        "ticker": ticker,
        "sector": sector,
        "prediction_value": value,
        "actual_target_value": target,
        "trading_day": "2026-01-01",
        "candidate_namespace": "shadow_meta_model.xgb_v1",
    }


def _prediction_rows(windows=4, preds_per_window=5, directional=1.0):
    # All values have same sign as directional: positive -> positive, negative -> negative
    rows = []
    for w in range(windows):
        window_id = f"w{w}"
        for t, val, tgt in [
            ("AAPL", 0.9 * directional, 0.05 * directional),
            ("MSFT", 0.7 * directional, 0.03 * directional),
            ("GOOG", 0.5 * directional, 0.02 * directional),
            ("META", 0.2 * directional, 0.01 * directional),
            ("NVDA", 0.8 * directional, 0.04 * directional),
        ][:preds_per_window]:
            rows.append(_pred(window_id, t, val, tgt, sector="TECH" if t in ("AAPL", "MSFT", "GOOG") else "CONSUMER"))
    return rows


# Disjoint tickers across windows: used to generate non-zero turnover
_WINDOW_TICKER_SETS = [
    [("AAPL", 0.9, 0.05), ("MSFT", 0.7, 0.03), ("GOOG", 0.5, 0.02)],
    [("TSLA", 0.9, 0.05), ("META", 0.7, 0.03), ("NVDA", 0.5, 0.02)],
    [("JPM",  0.9, 0.05), ("GS",   0.7, 0.03), ("BAC",  0.5, 0.02)],
    [("XOM",  0.9, 0.05), ("CVX",  0.7, 0.03), ("SLB",  0.5, 0.02)],
]

def _prediction_rows_disjoint(windows=4, directional=1.0):
    rows = []
    for w in range(min(windows, len(_WINDOW_TICKER_SETS))):
        window_id = f"w{w}"
        for t, val, tgt in _WINDOW_TICKER_SETS[w]:
            rows.append(_pred(window_id, t, val * directional, tgt * directional, sector="TECH"))
    return rows


def _phase25_ready():
    return FakePhase25Result(
        evaluation_report=FakePhase25Report(),
        readiness_decision=FakePhase25Decision(decision="ready_for_phase26_shadow_portfolio"),
    )


def _phase25_blocked():
    return FakePhase25Result(
        evaluation_report=FakePhase25Report(),
        readiness_decision=FakePhase25Decision(decision="rejected_underperforms_baseline"),
    )


def _request(**overrides):
    values = dict(
        simulation_id="sim_001",
        training_run_id="train_run_001",
        experiment_id="exp_xgb_v1",
        candidate_namespace="shadow_meta_model.xgb_v1",
        portfolio_mode="long_only_top_rank",
        initial_capital=1_000_000.0,
        max_positions=3,
        max_single_name_weight=0.30,
        max_sector_weight=0.60,
        gross_exposure_limit=1.5,
        turnover_limit=1.0,
        min_prediction_value=0.0,
        rebalance_frequency="window",
        cost_basis="net_target",
        governance_review_enabled=True,
        notes="phase26 test",
    )
    values.update(overrides)
    return PortfolioSimulationRequest(**values)


# ─── Request Validation ──────────────────────────────────────────────────────

def test_request_rejects_unsafe_values():
    with pytest.raises(PortfolioSimulationError, match="candidate_namespace must start"):
        _request(candidate_namespace="production.bad")
    with pytest.raises(PortfolioSimulationError, match="portfolio_mode not allowed"):
        _request(portfolio_mode="balanced")
    with pytest.raises(PortfolioSimulationError, match="initial_capital must be > 0"):
        _request(initial_capital=0)
    with pytest.raises(PortfolioSimulationError, match="max_positions must be >= 1"):
        _request(max_positions=0)
    with pytest.raises(PortfolioSimulationError, match="max_single_name_weight must be in"):
        _request(max_single_name_weight=1.5)
    with pytest.raises(PortfolioSimulationError, match="turnover_limit must be in"):
        _request(turnover_limit=-0.1)
    with pytest.raises(PortfolioSimulationError, match="rebalance_frequency not allowed"):
        _request(rebalance_frequency="daily")
    with pytest.raises(PortfolioSimulationError, match="cost_basis not allowed"):
        _request(cost_basis="gross")
    with pytest.raises(PortfolioSimulationError, match="governance_review_enabled must be true"):
        _request(governance_review_enabled=False)


# ─── Admission Gate ──────────────────────────────────────────────────────────

def test_phase25_not_ready_blocks_simulation():
    result = run_shadow_portfolio_simulation(_phase25_blocked(), [], _request())

    assert result.governance_decision.decision == "blocked_by_phase25"


def test_ready_phase25_produces_report():
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows(), _request())

    assert result.schema_version == "phase26_shadow_portfolio.0"
    assert result.governance_decision.decision in {
        "ready_for_manual_production_review",
        "watch_more_shadow_windows",
        "rejected_portfolio_underperforms",
        "blocked_by_constraints",
        "blocked_by_safety",
    }


def test_report_is_json_serializable():
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows(), _request())
    json.dumps(result.to_dict())


# ─── Long-Only Portfolio Construction ─────────────────────────────────────────

def test_top_predictions_become_holdings():
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows(), _request())

    assert len(result.window_results) == 4
    for wr in result.window_results:
        assert wr.holding_count <= 3


def test_max_positions_caps_holdings():
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows(), _request(max_positions=2)
    )
    for wr in result.window_results:
        assert wr.holding_count <= 2


def test_single_name_cap_applied():
    # 3 positions, equal weight ~0.333 each; with cap 0.30, capped < raw
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows(), _request(max_positions=3, max_single_name_weight=0.20)
    )
    for wr in result.window_results:
        for h in wr.holdings:
            assert h.capped_weight <= 0.20 + 1e-9


def test_sector_cap_applied():
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows(), _request(max_positions=3, max_sector_weight=0.40)
    )
    for wr in result.window_results:
        assert wr.max_sector_weight <= 0.40 + 1e-9


def test_min_prediction_value_filters():
    rows = _prediction_rows()
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), rows, _request(min_prediction_value=0.5)
    )
    for wr in result.window_results:
        for h in wr.holdings:
            assert h.prediction_value >= 0.5


# ─── Return Computation ───────────────────────────────────────────────────────

def test_portfolio_net_return_computed():
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows(directional=1.0), _request())
    for wr in result.window_results:
        assert wr.portfolio_net_return != 0.0


def test_turnover_computed():
    # Disjoint tickers across windows -> non-zero turnover from window 1 onward
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows_disjoint(), _request())
    # Window 0 has no prior -> turnover = 0; subsequent windows should be non-zero
    for wr in result.window_results[1:]:
        assert wr.turnover > 0.0, f"turnover for {wr.window_id} should be non-zero with disjoint tickers"
    # Avg turnover should also be non-zero
    assert result.risk_summary.average_turnover > 0.0


# ─── Risk Summary ───────────────────────────────────────────────────────────

def test_cumulative_net_return_computed():
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows(), _request())
    assert result.risk_summary.cumulative_net_return != 0.0


def test_max_drawdown_computed():
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows(), _request())
    assert result.risk_summary.max_drawdown <= 0.0


def test_hit_rate_computed():
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows(), _request())
    assert 0.0 <= result.risk_summary.hit_rate <= 1.0


# ─── Governance Decisions ─────────────────────────────────────────────────────

def test_forbidden_live_fields_block():
    phase25 = _phase25_ready()
    bad_rows = [_pred("w0", "AAPL", 0.9, 0.05)]
    bad_rows[0]["live_trade_signal"] = "BUY"
    result = run_shadow_portfolio_simulation(phase25, bad_rows, _request())
    assert result.governance_decision.decision == "blocked_by_safety"


def test_turnover_limit_violation_blocks_constraints():
    # Disjoint tickers across windows produce non-zero turnover
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows_disjoint(), _request(turnover_limit=0.01)
    )
    assert result.governance_decision.decision == "blocked_by_constraints"


def test_long_short_mode_emits_shadow_warning():
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows(), _request(portfolio_mode="long_short_rank_shadow")
    )
    assert "shadow_only_short_analysis" in result.warnings


def test_rejected_portfolio_underperforms():
    # Negative directional = negative returns -> rejected
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows(directional=-1.0), _request()
    )
    assert result.governance_decision.decision == "rejected_portfolio_underperforms"


def test_ready_for_manual_production_review():
    # Positive directional with stable returns; use max_single_name_weight=0.40
    # so equal-weight 3-position portfolio (0.333 each) doesn't trigger the cap.
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows(directional=1.0),
        _request(max_single_name_weight=0.40, max_sector_weight=0.80)
    )
    assert result.governance_decision.decision == "ready_for_manual_production_review"


def test_production_config_changes_always_empty():
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows(), _request())
    assert result.governance_decision.production_config_changes == {}


def test_apply_to_production_always_false():
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows(), _request())
    assert result.governance_decision.apply_to_production is False


# ─── P26 Regression Tests ─────────────────────────────────────────────────────

def test_single_name_cap_binds_but_not_blocked():
    # P26-1: cap applied (informational) is not a constraint violation
    # 3 positions at 0.333 each; cap=0.20 -> cap applied, but decision is ready
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows(), _request(max_positions=3, max_single_name_weight=0.20)
    )
    assert result.governance_decision.decision == "ready_for_manual_production_review"
    # No single_name_cap_exceeded violation (only cap applied flag on holdings)
    for wr in result.window_results:
        assert "single_name_cap_exceeded" not in wr.constraint_violations


def test_sector_cap_pro_rata_distribution():
    # P26-2: sector cap distributes excess pro-rata, no holding is zeroed
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows(), _request(max_positions=3, max_sector_weight=0.40)
    )
    for wr in result.window_results:
        # Each TECH holding should have some positive weight (not zeroed)
        tech_holdings = [h for h in wr.holdings if h.sector == "TECH"]
        for h in tech_holdings:
            assert h.capped_weight > 0.0, f"{h.ticker} should not be zeroed by sector cap"


def test_sector_cap_renorm_preserves_sector_limit():
    # P26-RR1: re-normalization after sector cap must not reintroduce sector violation
    # 3 TECH holdings at 0.333 each; sector cap=0.40 drops each to 0.1333 (total=0.40).
    # Re-normalization with loose single-name cap (0.50) should NOT apply (sector check fails).
    # Post-cap sector exposure must remain ≤ 0.40.
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows(),
        _request(max_positions=3, max_single_name_weight=0.50, max_sector_weight=0.40)
    )
    assert result.governance_decision.decision == "ready_for_manual_production_review"
    for wr in result.window_results:
        assert wr.max_sector_weight <= 0.40 + 1e-9


def test_explicit_cost_field_reduces_net_return():
    # P26-4: cost_basis=explicit_cost_field subtracts estimated_cost_pct
    rows = [
        _pred("w0", "AAPL", 0.9, 0.10),
        _pred("w0", "MSFT", 0.7, 0.06),
        _pred("w0", "GOOG", 0.5, 0.04),
        _pred("w1", "AAPL", 0.9, 0.10),
        _pred("w1", "MSFT", 0.7, 0.06),
        _pred("w1", "GOOG", 0.5, 0.04),
    ]
    # Add estimated_cost_pct = 0.02 to each row
    for row in rows:
        row["estimated_cost_pct"] = 0.02
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), rows, _request(cost_basis="explicit_cost_field")
    )
    # Net return should be (target - cost) * weight, lower than gross
    for wr in result.window_results:
        assert wr.portfolio_net_return < wr.portfolio_gross_return


def test_explicit_cost_field_missing_cost_warns():
    # P26-4: missing estimated_cost_pct emits cost_field_missing warning
    rows = [_pred("w0", "AAPL", 0.9, 0.10), _pred("w0", "MSFT", 0.7, 0.06)]
    # No estimated_cost_pct field
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), rows, _request(cost_basis="explicit_cost_field")
    )
    assert "cost_field_missing" in result.warnings


def test_max_drawdown_first_window_is_peak():
    # P26-5: peak initialized to 1.0, not first return
    # Returns: [-0.10, 0.0, 0.0] -> drawdown should be -0.10 (first drop from 1.0)
    from agent.research_v1.phase26_shadow_portfolio import _max_drawdown
    assert _max_drawdown([-0.10, 0.0, 0.0]) == pytest.approx(-0.10, abs=1e-9)


def test_max_drawdown_three_negative_windows():
    # P26-5: returns [-0.10, -0.10, -0.10] -> true drawdown ≈ -0.271
    from agent.research_v1.phase26_shadow_portfolio import _max_drawdown
    dd = _max_drawdown([-0.10, -0.10, -0.10])
    assert dd < -0.25  # True value ≈ -0.271


def test_long_short_not_blocked_by_shadow_warning():
    # P26-6: shadow_only_short_analysis is a warning, not a constraint violation
    # Use generous limits so no other constraints fire
    result = run_shadow_portfolio_simulation(
        _phase25_ready(), _prediction_rows(),
        _request(portfolio_mode="long_short_rank_shadow",
                 max_single_name_weight=0.60, max_sector_weight=1.0)
    )
    assert "shadow_only_short_analysis" in result.warnings
    # Decision should NOT be blocked_by_constraints purely from this label
    assert result.governance_decision.decision != "blocked_by_constraints"


def test_phase25_apply_to_production_true_blocks():
    # P26-7: Phase 25 with apply_to_production=True must be blocked
    phase25 = _phase25_ready()
    # Mutate through the inner object
    phase25.readiness_decision.apply_to_production = True
    result = run_shadow_portfolio_simulation(phase25, _prediction_rows(), _request())
    assert result.governance_decision.decision == "blocked_by_safety"


def test_phase25_production_config_changes_non_empty_blocks():
    # P26-7: Phase 25 with non-empty production_config_changes must be blocked
    phase25 = _phase25_ready()
    phase25.readiness_decision.production_config_changes = {"forged": 1}
    result = run_shadow_portfolio_simulation(phase25, _prediction_rows(), _request())
    assert result.governance_decision.decision == "blocked_by_safety"


def test_report_to_dict_defensive_copy():
    # P26-8: to_dict() returns defensive copies; mutating the returned dict doesn't affect the report
    result = run_shadow_portfolio_simulation(_phase25_ready(), _prediction_rows(), _request())
    d1 = result.to_dict()
    d1["safety_flags"]["forged"] = True
    d1["warnings"].append("forged")
    d2 = result.to_dict()
    assert d2["safety_flags"] == dict(result.safety_flags)
    assert d2["warnings"] == list(result.warnings)


# ─── No Model/Optimizer Libraries ───────────────────────────────────────────

def test_no_model_or_optimizer_libraries_imported():
    import agent.research_v1.phase26_shadow_portfolio as port_module

    forbidden = {
        "xgboost", "sklearn", "torch", "tensorflow", "stable_baselines3",
        "numpy", "pandas", "scipy", "cvxpy", "ortools", " pulp",
    }
    assert set(port_module.__dict__).isdisjoint(forbidden)
