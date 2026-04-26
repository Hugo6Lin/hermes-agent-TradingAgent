"""Tests for Phase 28 execution realism pack."""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

from agent.research_v1.phase28_execution_realism import (
    ADV_PARTICIPATION_LIMIT,
    MIN_EXECUTION_LOG_COUNT,
    ExecutionRealismError,
    ExecutionRealismReport,
    ExecutionRealismRequest,
    LiquidityStressScenario,
    MarketLiquidity,
    PPOAdmissionRequest,
    PPOExecutionAdmissionDecision,
    SlippageEstimate,
    TradeIntent,
    _get_stress_scenario,
    _STRESS_SCENARIOS,
    estimate_execution_costs,
    evaluate_ppo_execution_admission,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _ticker_liq(
    ticker: str = "AAPL",
    adv: float = 10_000_000.0,
    spread_bps: float = 5.0,
    daily_vol_bps: float = 150.0,
    volume: float = 8_000_000.0,
) -> tuple[str, MarketLiquidity]:
    return (ticker, MarketLiquidity(
        adv=adv,
        spread_bps=spread_bps,
        daily_volatility_bps=daily_vol_bps,
        volume=volume,
    ))


def _trade_intent(
    ticker: str = "AAPL",
    direction: str = "long",
    quantity: float = 100_000.0,
    price: float = 150.0,
    market_cap: float = 2_000_000_000_000.0,
) -> TradeIntent:
    return TradeIntent(
        ticker=ticker,
        direction=direction,
        quantity=quantity,
        price=price,
        market_cap=market_cap,
    )


# ─── Contract existence tests ──────────────────────────────────────────────────

class TestContracts:
    def test_execution_realism_request_contract(self):
        req = ExecutionRealismRequest(
            trade_intents=(_trade_intent(),),
            market_liquidity_by_ticker=(_ticker_liq(),),
            alpha_edge_bps=20.0,
        )
        d = req.to_dict()
        assert d["alpha_edge_bps"] == 20.0
        assert d["stress_scenario"] == "normal"

    def test_slippage_estimate_contract(self):
        se = SlippageEstimate(
            ticker="AAPL",
            direction="long",
            commission_bps=0.5,
            half_spread_bps=2.5,
            impact_bps=1.0,
            adv_participation=0.01,
            volatility_penalty_bps=0.75,
            liquidity_stress_penalty_bps=0.0,
            total_cost_bps=4.75,
            adv_limit_exceeded=False,
            spread_missing=False,
            liquidity_data_missing=False,
            stress_cost_exceeds_edge=False,
        )
        d = se.to_dict()
        assert d["ticker"] == "AAPL"
        assert d["commission_bps"] == 0.5
        assert d["total_cost_bps"] == 4.75
        assert d["adv_limit_exceeded"] is False

    def test_liquidity_stress_scenario_contract(self):
        scenario = _get_stress_scenario("severe")
        assert scenario.name == "severe"
        assert scenario.spread_multiplier == 2.0
        assert scenario.impact_multiplier == 1.8
        d = scenario.to_dict()
        assert d["spread_multiplier"] == 2.0

    def test_execution_realism_report_contract(self):
        report = ExecutionRealismReport(
            request_config=(("alpha_edge_bps", 20.0),),
            slippage_estimates=(),
            stress_scenario=_get_stress_scenario("normal"),
            portfolio_liquidity_warnings=(),
            average_trade_cost_bps=0.0,
            weighted_portfolio_cost_bps=0.0,
            constrained_slippage_count=0,
            stress_cost_exceeds_edge_count=0,
        )
        d = report.to_dict()
        assert "request_config" in d
        assert d["average_trade_cost_bps"] == 0.0
        assert d["weighted_portfolio_cost_bps"] == 0.0

    def test_ppo_execution_admission_decision_contract(self):
        dec = PPOExecutionAdmissionDecision(
            admitted=True,
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_logs_sufficient=True,
            no_live_trading_effect=True,
            decision_reasons=("all_gates_passed",),
            sub_scores=(("objective_execution_cost_reduction", 1.0),),
        )
        d = dec.to_dict()
        assert d["admitted"] is True
        assert d["objective"] == "execution_cost_reduction"

    def test_to_dict_json_round_trip(self):
        se = SlippageEstimate(
            ticker="AAPL", direction="long",
            commission_bps=0.5, half_spread_bps=2.5, impact_bps=1.0,
            adv_participation=0.01, volatility_penalty_bps=0.75,
            liquidity_stress_penalty_bps=0.0, total_cost_bps=4.75,
            adv_limit_exceeded=False, spread_missing=False,
            liquidity_data_missing=False, stress_cost_exceeds_edge=False,
        )
        d = se.to_dict()
        parsed = json.loads(json.dumps(d))
        assert parsed["ticker"] == "AAPL"
        assert parsed["total_cost_bps"] == 4.75


# ─── Request validation ───────────────────────────────────────────────────────

class TestRequestValidation:
    def test_rejects_invalid_alpha_edge(self):
        with pytest.raises(ExecutionRealismError):
            ExecutionRealismRequest(
                trade_intents=(_trade_intent(),),
                market_liquidity_by_ticker=(_ticker_liq(),),
                alpha_edge_bps=-5.0,
            )

    def test_rejects_unknown_stress_scenario(self):
        with pytest.raises(ExecutionRealismError):
            ExecutionRealismRequest(
                trade_intents=(_trade_intent(),),
                market_liquidity_by_ticker=(_ticker_liq(),),
                alpha_edge_bps=20.0,
                stress_scenario="unknown",
            )

    def test_rejects_invalid_adv_participation_limit(self):
        with pytest.raises(ExecutionRealismError):
            ExecutionRealismRequest(
                trade_intents=(_trade_intent(),),
                market_liquidity_by_ticker=(_ticker_liq(),),
                alpha_edge_bps=20.0,
                adv_participation_limit=1.5,
            )

    def test_liquidity_map_method(self):
        req = ExecutionRealismRequest(
            trade_intents=(_trade_intent(ticker="AAPL"), _trade_intent(ticker="MSFT")),
            market_liquidity_by_ticker=(
                _ticker_liq(ticker="AAPL", adv=10_000_000),
                _ticker_liq(ticker="MSFT", adv=8_000_000),
            ),
            alpha_edge_bps=20.0,
        )
        m = req.liquidity_map()
        assert m["AAPL"].adv == 10_000_000.0
        assert m["MSFT"].adv == 8_000_000.0


# ─── Cost component tests ─────────────────────────────────────────────────────

class TestCommission:
    def test_commission_bps_from_intent(self):
        intent = _trade_intent(quantity=100_000, price=150.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(_ticker_liq(),),
            alpha_edge_bps=20.0,
        )
        report = estimate_execution_costs(
            (intent,),
            (_ticker_liq(),),
            req,
        )
        est = report.slippage_estimates[0]
        assert est.commission_bps == intent.estimated_commission_bps


class TestHalfSpread:
    def test_half_spread_bps(self):
        liq = _ticker_liq(spread_bps=10.0)
        intent = _trade_intent(ticker="AAPL")
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
        )
        report = estimate_execution_costs((intent,), (liq,), req)
        est = report.slippage_estimates[0]
        assert est.half_spread_bps == 5.0  # half of 10 bps

    def test_zero_spread_flagged(self):
        liq = _ticker_liq(spread_bps=0.0)
        intent = _trade_intent(ticker="AAPL")
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
        )
        report = estimate_execution_costs((intent,), (liq,), req)
        est = report.slippage_estimates[0]
        assert est.spread_missing is True
        assert est.half_spread_bps == 0.0


class TestMarketImpact:
    def test_impact_bps_grows_with_adv_participation(self):
        # Small trade: low impact
        liq_small = _ticker_liq(adv=10_000_000, spread_bps=5.0)
        intent_small = _trade_intent(ticker="AAPL", quantity=50_000, price=150.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent_small,),
            market_liquidity_by_ticker=(liq_small,),
            alpha_edge_bps=20.0,
            illiquidity_coefficient=1.0,
        )
        report_small = estimate_execution_costs((intent_small,), (liq_small,), req)
        impact_small = report_small.slippage_estimates[0].impact_bps

        # Large trade: high impact (10x notional)
        liq_large = _ticker_liq(adv=10_000_000, spread_bps=5.0)
        intent_large = _trade_intent(ticker="AAPL", quantity=500_000, price=150.0)
        req2 = ExecutionRealismRequest(
            trade_intents=(intent_large,),
            market_liquidity_by_ticker=(liq_large,),
            alpha_edge_bps=20.0,
            illiquidity_coefficient=1.0,
        )
        report_large = estimate_execution_costs((intent_large,), (liq_large,), req2)
        impact_large = report_large.slippage_estimates[0].impact_bps

        assert impact_large > impact_small


class TestADVParticipation:
    def test_adv_participation_calculation(self):
        # notional = 100_000 * 150 = 15,000,000
        # adv_dollar = 10_000_000 * 150 = 1,500,000,000
        # participation = 15M / 1500M = 0.01
        liq = _ticker_liq(adv=10_000_000.0)
        intent = _trade_intent(ticker="AAPL", quantity=100_000.0, price=150.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
        )
        report = estimate_execution_costs((intent,), (liq,), req)
        est = report.slippage_estimates[0]
        assert abs(est.adv_participation - 0.01) < 1e-9

    def test_adv_limit_exceeded_flag(self):
        # 5% ADV limit: 0.05 * 10_000_000 = 500_000 shares
        # Trade 1M shares -> 10% ADV -> exceeds limit
        liq = _ticker_liq(adv=10_000_000.0)
        intent = _trade_intent(ticker="AAPL", quantity=1_000_000.0, price=150.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
            adv_participation_limit=0.05,
        )
        report = estimate_execution_costs((intent,), (liq,), req)
        est = report.slippage_estimates[0]
        assert est.adv_limit_exceeded is True

    def test_adv_limit_not_exceeded_under_limit(self):
        liq = _ticker_liq(adv=10_000_000.0)
        intent = _trade_intent(ticker="AAPL", quantity=100_000.0, price=150.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
            adv_participation_limit=0.05,
        )
        report = estimate_execution_costs((intent,), (liq,), req)
        est = report.slippage_estimates[0]
        assert est.adv_limit_exceeded is False


class TestVolatilityPenalty:
    def test_volatility_penalty_proportional_to_participation(self):
        liq = _ticker_liq(daily_vol_bps=100.0)
        intent_low = _trade_intent(ticker="AAPL", quantity=50_000.0, price=150.0)
        intent_high = _trade_intent(ticker="AAPL", quantity=500_000.0, price=150.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent_low,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
        )
        req_high = ExecutionRealismRequest(
            trade_intents=(intent_high,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
        )
        r_low = estimate_execution_costs((intent_low,), (liq,), req)
        r_high = estimate_execution_costs((intent_high,), (liq,), req_high)
        assert r_high.slippage_estimates[0].volatility_penalty_bps > r_low.slippage_estimates[0].volatility_penalty_bps


# ─── Liquidity stress tests ───────────────────────────────────────────────────

class TestLiquidityStress:
    def test_all_stress_scenarios_defined(self):
        for name in ("normal", "moderate", "severe", "extreme"):
            s = _get_stress_scenario(name)
            assert s.name == name

    def test_stress_multipliers_increase_with_severity(self):
        normal = _get_stress_scenario("normal")
        moderate = _get_stress_scenario("moderate")
        severe = _get_stress_scenario("severe")
        extreme = _get_stress_scenario("extreme")
        assert normal.spread_multiplier == 1.0
        assert moderate.spread_multiplier == 1.5
        assert severe.spread_multiplier == 2.0
        assert extreme.spread_multiplier == 3.0

    def test_stress_cost_exceeds_edge_flag(self):
        # Normal scenario: total cost 2.5 bps < 20 bps edge -> not exceeded
        liq = _ticker_liq(spread_bps=10.0)
        intent = _trade_intent(ticker="AAPL", quantity=50_000, price=150.0)
        req_normal = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
            stress_scenario="normal",
        )
        r_normal = estimate_execution_costs((intent,), (liq,), req_normal)
        assert r_normal.slippage_estimates[0].stress_cost_exceeds_edge is False

    def test_stress_cost_exceeds_edge_in_extreme(self):
        liq = _ticker_liq(spread_bps=5.0)
        intent = _trade_intent(ticker="AAPL", quantity=1_000_000, price=150.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
            stress_scenario="extreme",
        )
        r = estimate_execution_costs((intent,), (liq,), req)
        # In extreme, even a small spread gets multiplied; cost should exceed edge
        assert r.slippage_estimates[0].stress_cost_exceeds_edge is True

    def test_stress_scenario_in_report(self):
        liq = _ticker_liq()
        intent = _trade_intent()
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
            stress_scenario="severe",
        )
        report = estimate_execution_costs((intent,), (liq,), req)
        assert report.stress_scenario.name == "severe"
        assert report.stress_scenario.spread_multiplier == 2.0

    def test_liquidity_stress_penalty_bps_accumulates(self):
        liq = _ticker_liq(spread_bps=10.0, daily_vol_bps=100.0)
        intent = _trade_intent(ticker="AAPL", quantity=500_000, price=150.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
            stress_scenario="severe",
        )
        report = estimate_execution_costs((intent,), (liq,), req)
        est = report.slippage_estimates[0]
        # severe: spread_multiplier 2.0, impact_multiplier 1.8, vol_multiplier 1.6
        # half_spread = 5.0, stress_pen = 5.0*(2-1) + impact*(1.8-1) + vol_pen*(1.6-1)
        assert est.liquidity_stress_penalty_bps > 0.0

    def test_liquidity_data_missing_flagged(self):
        intent = _trade_intent(ticker="AAPL")
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(),  # empty
            alpha_edge_bps=20.0,
        )
        report = estimate_execution_costs((intent,), (), req)
        est = report.slippage_estimates[0]
        assert est.liquidity_data_missing is True
        assert "liquidity_data_missing:AAPL" in report.portfolio_liquidity_warnings


# ─── Total cost tests ─────────────────────────────────────────────────────────

class TestTotalCost:
    def test_total_cost_sums_all_components(self):
        liq = _ticker_liq(spread_bps=10.0, daily_vol_bps=100.0)
        intent = _trade_intent(ticker="AAPL", quantity=100_000, price=150.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
        )
        report = estimate_execution_costs((intent,), (liq,), req)
        est = report.slippage_estimates[0]
        # Total = commission + half_spread*spread_mult + impact*impact_mult + vol_pen*vol_mult
        # In normal: all multipliers = 1.0
        expected = (
            est.commission_bps
            + est.half_spread_bps
            + est.impact_bps
            + est.volatility_penalty_bps
        )
        assert abs(est.total_cost_bps - expected) < 1e-9

    def test_stress_increases_total_cost(self):
        liq = _ticker_liq(spread_bps=10.0, daily_vol_bps=100.0)
        intent = _trade_intent(ticker="AAPL", quantity=100_000, price=150.0)
        req_normal = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
            stress_scenario="normal",
        )
        req_extreme = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
            stress_scenario="extreme",
        )
        r_normal = estimate_execution_costs((intent,), (liq,), req_normal)
        r_extreme = estimate_execution_costs((intent,), (liq,), req_extreme)
        assert r_extreme.slippage_estimates[0].total_cost_bps > r_normal.slippage_estimates[0].total_cost_bps


# ─── PPO Admission Gate tests ─────────────────────────────────────────────────

class TestPPOAdmissionGate:
    def test_execution_cost_reduction_admitted(self):
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_log_count=50,
            live_trading_effect=False,
        )
        dec = evaluate_ppo_execution_admission({}, req)
        assert dec.admitted is True
        assert "all_gates_passed" in dec.decision_reasons

    def test_alpha_objective_blocked(self):
        req = PPOAdmissionRequest(
            objective="alpha_generation",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_log_count=50,
            live_trading_effect=False,
        )
        dec = evaluate_ppo_execution_admission({}, req)
        assert dec.admitted is False
        assert "objective_not_execution_cost_reduction" in dec.decision_reasons

    def test_affects_stock_selection_blocked(self):
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=True,
            portfolio_layer_present=True,
            execution_log_count=50,
            live_trading_effect=False,
        )
        dec = evaluate_ppo_execution_admission({}, req)
        assert dec.admitted is False
        assert "affects_stock_selection_is_true" in dec.decision_reasons

    def test_portfolio_layer_missing_blocked(self):
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=False,
            execution_log_count=50,
            live_trading_effect=False,
        )
        dec = evaluate_ppo_execution_admission({}, req)
        assert dec.admitted is False
        assert "portfolio_layer_missing" in dec.decision_reasons

    def test_insufficient_execution_logs_blocked(self):
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_log_count=5,
            live_trading_effect=False,
        )
        dec = evaluate_ppo_execution_admission({}, req)
        assert dec.admitted is False
        assert "insufficient_execution_logs" in dec.decision_reasons

    def test_live_trading_effect_blocked(self):
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_log_count=50,
            live_trading_effect=True,
        )
        dec = evaluate_ppo_execution_admission({}, req)
        assert dec.admitted is False
        assert "live_trading_effect_present" in dec.decision_reasons

    def test_sub_scores_present(self):
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_log_count=50,
            live_trading_effect=False,
        )
        dec = evaluate_ppo_execution_admission({}, req)
        keys = {k for k, _ in dec.sub_scores}
        expected_keys = {
            "objective_execution_cost_reduction",
            "stock_selection_unchanged",
            "portfolio_layer_present",
            "execution_logs_sufficient",
            "no_live_trading_effect",
        }
        assert expected_keys.issubset(keys)

    def test_minimum_execution_log_count_constant(self):
        assert MIN_EXECUTION_LOG_COUNT == 10


# ─── Edge / missing data tests ───────────────────────────────────────────────

class TestMissingData:
    def test_missing_liquidity_warnings_in_report(self):
        intent_a = _trade_intent(ticker="AAPL")
        intent_m = _trade_intent(ticker="MSFT")
        liq = _ticker_liq(ticker="AAPL")
        req = ExecutionRealismRequest(
            trade_intents=(intent_a, intent_m),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
        )
        report = estimate_execution_costs(
            (intent_a, intent_m),
            (liq,),
            req,
        )
        assert "liquidity_data_missing:MSFT" in report.portfolio_liquidity_warnings

    def test_zero_adv_handled(self):
        liq = _ticker_liq(adv=0.0)
        intent = _trade_intent(ticker="AAPL", quantity=100_000, price=150.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(liq,),
            alpha_edge_bps=20.0,
        )
        report = estimate_execution_costs((intent,), (liq,), req)
        est = report.slippage_estimates[0]
        assert est.adv_participation == 0.0
        assert est.adv_limit_exceeded is False

    def test_empty_trade_intents_returns_zero_cost(self):
        req = ExecutionRealismRequest(
            trade_intents=(),
            market_liquidity_by_ticker=(),
            alpha_edge_bps=20.0,
        )
        report = estimate_execution_costs((), (), req)
        assert report.average_trade_cost_bps == 0.0
        assert report.weighted_portfolio_cost_bps == 0.0
        assert len(report.slippage_estimates) == 0


# ─── Missing liquidity regression (P28-2) ─────────────────────────────────────

class TestMissingLiquidityStressFlag:
    def test_missing_liquidity_fires_stress_cost_exceeds_edge(self):
        # When no liquidity row exists, stress_cost_exceeds_edge must fire
        # regardless of how small the numeric cost is, so that downstream
        # filters on stress_cost_exceeds_edge=False cannot silently include
        # unknown-cost tickers.
        intent = _trade_intent(ticker="AAPL", quantity=1000, price=100.0)
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(),  # empty — no AAPL liquidity
            alpha_edge_bps=20.0,
            stress_scenario="extreme",
        )
        report = estimate_execution_costs((intent,), (), req)
        est = report.slippage_estimates[0]
        assert est.liquidity_data_missing is True
        assert est.stress_cost_exceeds_edge is True

    def test_missing_liquidity_in_extreme_stress_still_flags_edge(self):
        intent = _trade_intent(ticker="AAPL")
        req = ExecutionRealismRequest(
            trade_intents=(intent,),
            market_liquidity_by_ticker=(),
            alpha_edge_bps=100.0,  # very large edge
            stress_scenario="extreme",
        )
        report = estimate_execution_costs((intent,), (), req)
        # Even with 100bps edge, missing liquidity fires the flag
        assert report.slippage_estimates[0].stress_cost_exceeds_edge is True


# ─── Average vs weighted cost (P28-3) ─────────────────────────────────────────

class TestWeightedCost:
    def test_weighted_cost_differs_from_average(self):
        # Large notional trade at 10bps + small notional trade at 100bps
        # Weighted should be close to 10bps; average would be 55bps
        liq = _ticker_liq(adv=10_000_000.0, spread_bps=5.0)
        large = _trade_intent(ticker="AAPL", quantity=1_000_000, price=100.0)
        small = _trade_intent(ticker="MSFT", quantity=1_000, price=100.0)
        req = ExecutionRealismRequest(
            trade_intents=(large, small),
            market_liquidity_by_ticker=(liq, _ticker_liq(ticker="MSFT")),
            alpha_edge_bps=200.0,
        )
        report = estimate_execution_costs(
            (large, small),
            (liq, _ticker_liq(ticker="MSFT")),
            req,
        )
        # average_trade_cost_bps = simple mean; weighted_portfolio_cost_bps = notional-weighted
        assert report.weighted_portfolio_cost_bps != report.average_trade_cost_bps
        # Weighted should be much closer to the large trade's cost
        large_cost = report.slippage_estimates[0].total_cost_bps
        assert abs(report.weighted_portfolio_cost_bps - large_cost) < abs(
            report.average_trade_cost_bps - large_cost
        )


# ─── TradeIntent validation (P28-4) ─────────────────────────────────────────

class TestTradeIntentValidation:
    def test_rejects_invalid_direction(self):
        with pytest.raises(ExecutionRealismError, match="direction must be"):
            TradeIntent(ticker="AAPL", direction="BANANA", quantity=100, price=150.0, market_cap=1e12)

    def test_rejects_negative_quantity(self):
        with pytest.raises(ExecutionRealismError, match="quantity must be"):
            TradeIntent(ticker="AAPL", direction="long", quantity=-100, price=150.0, market_cap=1e12)

    def test_rejects_zero_quantity(self):
        with pytest.raises(ExecutionRealismError, match="quantity must be"):
            TradeIntent(ticker="AAPL", direction="long", quantity=0, price=150.0, market_cap=1e12)

    def test_rejects_negative_price(self):
        with pytest.raises(ExecutionRealismError, match="price must be"):
            TradeIntent(ticker="AAPL", direction="long", quantity=100, price=-10.0, market_cap=1e12)

    def test_rejects_zero_price(self):
        with pytest.raises(ExecutionRealismError, match="price must be"):
            TradeIntent(ticker="AAPL", direction="long", quantity=100, price=0.0, market_cap=1e12)

    def test_rejects_negative_market_cap(self):
        with pytest.raises(ExecutionRealismError, match="market_cap must be"):
            TradeIntent(ticker="AAPL", direction="long", quantity=100, price=150.0, market_cap=-1e12)

    def test_accepts_short_direction(self):
        t = TradeIntent(ticker="AAPL", direction="short", quantity=100, price=150.0, market_cap=1e12)
        assert t.direction == "short"


# ─── PPO evidence gate (P28-5) ───────────────────────────────────────────────

class TestPPOEvidenceGate:
    def test_evidence_inconsistent_rejects(self):
        # evidence says objective=alpha_generation but request says execution_cost_reduction
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_log_count=50,
            live_trading_effect=False,
        )
        evidence = {"objective": "alpha_generation"}
        dec = evaluate_ppo_execution_admission(evidence, req)
        assert dec.admitted is False
        assert "evidence_inconsistent_with_request" in dec.decision_reasons

    def test_evidence_live_trading_mismatch_rejects(self):
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_log_count=50,
            live_trading_effect=False,
        )
        evidence = {"live_trading_effect": True}
        dec = evaluate_ppo_execution_admission(evidence, req)
        assert dec.admitted is False
        assert "evidence_inconsistent_with_request" in dec.decision_reasons

    def test_evidence_log_count_below_request_rejects(self):
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_log_count=50,
            live_trading_effect=False,
        )
        evidence = {"execution_log_count": 5}
        dec = evaluate_ppo_execution_admission(evidence, req)
        assert dec.admitted is False
        assert "evidence_inconsistent_with_request" in dec.decision_reasons

    def test_evidence_consistent_with_request_admits(self):
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_log_count=50,
            live_trading_effect=False,
        )
        evidence = {
            "objective": "execution_cost_reduction",
            "live_trading_effect": False,
            "execution_log_count": 100,
        }
        dec = evaluate_ppo_execution_admission(evidence, req)
        assert dec.admitted is True
        assert "evidence_inconsistent_with_request" not in dec.decision_reasons

    def test_sub_scores_contains_evidence_consistent(self):
        req = PPOAdmissionRequest(
            objective="execution_cost_reduction",
            affects_stock_selection=False,
            portfolio_layer_present=True,
            execution_log_count=50,
            live_trading_effect=False,
        )
        dec = evaluate_ppo_execution_admission({}, req)
        keys = {k for k, _ in dec.sub_scores}
        assert "evidence_consistent" in keys


# ─── Forbidden library scan ───────────────────────────────────────────────────

class TestNoForbiddenImports:
    def test_no_model_libraries_in_source(self):
        import pathlib
        src_path = (
            pathlib.Path(__file__).resolve().parents[3]
            / "agent" / "research_v1" / "phase28_execution_realism.py"
        )
        src = src_path.read_text()
        tree = ast.parse(src)
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.add(node.module.split(".")[0])
        forbidden = {"torch", "tensorflow", "xgboost", "sklearn", "scipy", "cvxpy", "ortools", "numpy", "pandas"}
        found = forbidden & names
        assert not found, f"Forbidden imports found: {sorted(found)}"


# ─── ADV participation limit constant ───────────────────────────────────────

class TestADVConstants:
    def test_adv_participation_limit_value(self):
        assert ADV_PARTICIPATION_LIMIT == 0.05
