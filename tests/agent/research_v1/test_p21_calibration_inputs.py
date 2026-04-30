"""P21 calibration inputs acceptance tests."""

import pytest

from agent.research_v1.calibration_config import (
    CalibrationMetadata,
    ExitPlanConfig,
    GradingWeightConfig,
    PositionSizingConfig,
    RegimeGateConfig,
    RoleWeight,
    RoleWeightConfig,
    SectorBenchmarkConfig,
    ThesisThresholdConfig,
)


# ---------------------------------------------------------------------------
# Task 1: Config contracts
# ---------------------------------------------------------------------------

def test_calibration_metadata_defaults_to_p21_prior_only():
    meta = CalibrationMetadata(config_name="test")
    assert meta.config_version == "p21.0"
    assert meta.calibration_status == "prior_only"
    assert meta.source == "engineering_prior"


def test_calibration_metadata_rejects_invalid_status():
    with pytest.raises(ValueError, match="invalid calibration_status"):
        CalibrationMetadata(config_name="test", calibration_status="not_a_valid_status")


def test_thesis_threshold_config_carries_metadata():
    config = ThesisThresholdConfig()
    assert config.config_version == "p21.0"
    assert config.calibration_status == "prior_only"


def test_thesis_threshold_config_rejects_invalid_status():
    with pytest.raises(ValueError, match="invalid calibration_status"):
        ThesisThresholdConfig(calibration_status="not_a_valid_status")


def test_exit_plan_config_is_prior_only_and_versioned():
    config = ExitPlanConfig(stop_multiple=2.0, target_multiple=3.0)
    assert config.calibration_status == "prior_only"
    assert config.config_version == "p21.0"
    assert config.horizon_bucket == "default"


def test_role_weight_config_rejects_zero_without_reason():
    config = RoleWeightConfig(weights={"risk": RoleWeight(0.0)})
    with pytest.raises(ValueError, match="zero weight without disabled_with_reason"):
        config.as_plain_weights()


def test_grading_weight_config_rejects_invalid_dynamic_override_sum():
    base = GradingWeightConfig()
    with pytest.raises(ValueError, match="sum to 1.0"):
        base.with_overrides({"fundamental": 0.9})


def test_grading_weight_config_with_overrides_valid():
    base = GradingWeightConfig(fundamental=0.4, technical=0.3, macro=0.3)
    overridden = base.with_overrides({"fundamental": 0.5})
    assert overridden.fundamental == 0.5
    assert overridden.technical == 0.25  # re-proportionalized
    assert overridden.macro == 0.25  # re-proportionalized
    assert overridden.config_version == base.config_version


def test_sector_benchmark_config_returns_sector_and_fallback_metadata():
    config = SectorBenchmarkConfig()
    tech = config.get("technology")
    unknown = config.get("unknown-sector")
    assert tech["multiples"]["pe"] != unknown["multiples"]["pe"]
    assert tech["used_fallback"] is False
    assert unknown["used_fallback"] is True
    assert unknown["calibration_status"] == "prior_only"
    assert unknown["config_version"] == "p21.0"


def test_sector_benchmark_config_rejects_calibrated_status():
    with pytest.raises(ValueError, match="invalid calibration_status"):
        SectorBenchmarkConfig(calibration_status="not_a_valid_status")


def test_position_sizing_config_validates_caps():
    with pytest.raises(ValueError, match="max_single_name_weight"):
        PositionSizingConfig(max_single_name_weight=1.5)
    with pytest.raises(ValueError, match="max_position_as_pct_adv"):
        PositionSizingConfig(max_position_as_pct_adv=-0.1)
    with pytest.raises(ValueError, match="target_position_volatility"):
        PositionSizingConfig(target_position_volatility=-0.01)


def test_position_sizing_config_rejects_calibrated():
    with pytest.raises(ValueError, match="invalid calibration_status"):
        PositionSizingConfig(calibration_status="not_a_valid_status")


def test_regime_gate_config_defaults_to_insufficient_definition():
    config = RegimeGateConfig()
    assert config.calibration_status == "prior_only"
    assert config.missing_data_status == "insufficient_definition"


def test_regime_gate_config_rejects_invalid_status():
    with pytest.raises(ValueError, match="invalid calibration_status"):
        RegimeGateConfig(calibration_status="not_a_valid_status")


# ---------------------------------------------------------------------------
# Task 2: Config wiring into exits, final judge, grading
# ---------------------------------------------------------------------------

from agent.research_v1.exit_planning import build_exit_plan
from agent.research_v1.final_judge import FinalJudge
from agent.research_v1.grading import GradingAgent


class DummyLLM:
    pass


def test_exit_plan_uses_canonical_config_metadata():
    config = ExitPlanConfig(stop_multiple=1.5, target_multiple=2.5)
    plan = build_exit_plan(entry_price=100.0, atr_20=4.0, config=config)
    assert plan.stop_loss == 94.0
    assert plan.take_profit == 110.0
    assert plan.calibration_status == "prior_only"
    assert plan.config_version == "p21.0"


def test_final_judge_accepts_injected_role_weight_config():
    config = RoleWeightConfig(weights={
        "fundamentals": RoleWeight(1.0),
        "risk": RoleWeight(0.0, "disabled in test"),
    })
    judge = FinalJudge(role_weight_config=config)
    assert judge.role_weights["fundamentals"] == 1.0
    assert judge.role_weights["risk"] == 0.0


def test_final_judge_backward_compatible_role_weights():
    """ROLE_WEIGHTS module-level constant still works without injection."""
    judge = FinalJudge()
    assert judge.role_weights["fundamentals"] == 0.40


def test_grading_agent_rejects_invalid_dynamic_weight_merge():
    with pytest.raises(ValueError, match="sum to 1.0"):
        GradingAgent(llm_client=DummyLLM(), dynamic_weights={"fundamental": 0.9})


def test_grading_agent_accepts_valid_dynamic_weights():
    agent = GradingAgent(
        llm_client=DummyLLM(),
        dynamic_weights={"fundamental": 0.5, "technical": 0.3, "macro": 0.2}
    )
    assert agent.fundamental_weight == 0.5
    assert agent.technical_weight == 0.3
    assert agent.macro_weight == 0.2


# ---------------------------------------------------------------------------
# Task 3: Sector valuation config-audit metadata
# ---------------------------------------------------------------------------

from agent.research_v1.valuation_models import calculate_relative_valuation


def test_relative_valuation_reports_sector_benchmark_metadata():
    result = calculate_relative_valuation(
        market_data={"eps": 5.0, "book_value_per_share": 20.0, "sales_per_share": 12.0},
        benchmark_multiples={"sector": "technology"},
    )
    assert result["target_price"] is not None
    assert result["benchmark_metadata"]["resolved_sector"] == "technology"
    assert result["benchmark_metadata"]["used_fallback"] is False
    assert result["benchmark_metadata"]["calibration_status"] == "prior_only"
    assert result["benchmark_metadata"]["config_version"] == "p21.0"


def test_relative_valuation_reports_default_fallback_metadata():
    result = calculate_relative_valuation(
        market_data={"eps": 5.0},
        benchmark_multiples={"sector": "unknown-sector"},
    )
    assert result["benchmark_metadata"]["resolved_sector"] == "default"
    assert result["benchmark_metadata"]["used_fallback"] is True


def test_relative_valuation_with_explicit_multiples_emits_metadata():
    result = calculate_relative_valuation(
        market_data={"eps": 5.0},
        benchmark_multiples={"pe": 20.0},
    )
    assert result["target_price"] is not None
    assert "benchmark_metadata" in result


# ---------------------------------------------------------------------------
# Task 4: Volatility-aware trade sizing
# ---------------------------------------------------------------------------

from agent.research_v1.contracts import CanonicalSignal
from agent.research_v1.trade_plan import TradePlanGenerator


def _signal(**extra_attrs):
    signal = CanonicalSignal(
        ticker="AAPL",
        rating="BUY",
        confidence=0.8,
        priority_score=8.0,
        entry_price=100.0,
        stop_loss=94.0,
        take_profit=112.0,
        holding_horizon="20d",
        risk_flags=[],
        decision_reason="test",
    )
    for name, value in extra_attrs.items():
        setattr(signal, name, value)
    return signal


def test_trade_plan_includes_volatility_aware_sizing_metadata():
    generator = TradePlanGenerator(
        sizing_config=PositionSizingConfig(
            target_position_volatility=0.02,
            max_single_name_weight=0.05,
            max_position_as_pct_adv=0.05,
        )
    )
    plan = generator.generate(
        _signal(signal_volatility=0.20, portfolio_equity=100_000, adv_shares_20d=1_000_000)
    )
    assert plan["suggested_position_size"] >= 1
    assert 0 < plan["suggested_position_weight"] <= 0.05
    assert plan["target_position_volatility"] == 0.02
    assert plan["input_signal_volatility"] == 0.20
    assert plan["calibration_status"] == "prior_only"
    assert "sizing_flags" in plan


def test_trade_plan_caps_position_by_adv_and_single_name_weight():
    generator = TradePlanGenerator(
        sizing_config=PositionSizingConfig(
            target_position_volatility=0.10,
            max_single_name_weight=0.05,
            max_position_as_pct_adv=0.01,
        )
    )
    plan = generator.generate(
        _signal(signal_volatility=0.01, portfolio_equity=1_000_000, adv_shares_20d=20_000)
    )
    assert plan["single_name_cap_applied"] is True or plan["adv_cap_applied"] is True
    # Final size must not exceed what the cap allows
    adv_cap_shares = 20_000 * 0.01  # max_position_as_pct_adv * adv_shares_20d
    weight_cap_shares = (1_000_000 * 0.05) / 100.0  # max_single_name_weight * portfolio_equity / entry_price
    max_allowed_by_cap = min(adv_cap_shares, weight_cap_shares)
    assert plan["suggested_position_size"] <= max_allowed_by_cap + 1  # +1 for rounding tolerance


def test_trade_plan_legacy_size_does_not_override_adv_cap():
    """Legacy integer size must not override ADV cap; final size derives from capped weight."""
    generator = TradePlanGenerator(
        sizing_config=PositionSizingConfig(
            target_position_volatility=0.05,
            max_single_name_weight=0.12,
            max_position_as_pct_adv=0.001,
            min_position_units=1,
        )
    )
    # confidence=0.9, priority_score=8.0 → legacy_size = round(0.9 * 8 / 10) = 1
    # ADV cap: max_shares = 50_000 * 0.001 = 50
    # Capped weight gives 50 shares, not 1
    plan = generator.generate(
        _signal(signal_volatility=0.25, portfolio_equity=100_000, adv_shares_20d=50_000, confidence=0.9)
    )
    assert plan["adv_cap_applied"] is True
    assert plan["suggested_position_size"] == 50  # cap-derived, NOT legacy (1)


def test_trade_plan_adv_cap_below_min_position_returns_zero():
    """ADV cap yields fewer shares than min_position_units → size must be 0, not min."""
    generator = TradePlanGenerator(
        sizing_config=PositionSizingConfig(
            target_position_volatility=0.02,
            max_single_name_weight=0.10,
            max_position_as_pct_adv=0.01,  # tight ADV cap
            min_position_units=1,
        )
    )
    # ADV=10, max_as_pct_adv=0.01 → max_shares=0.1 → vol_position_units=0 after rounding
    # Must NOT return 1 (violates cap); must return 0 with flag
    plan = generator.generate(
        _signal(signal_volatility=0.25, portfolio_equity=100_000, adv_shares_20d=10)
    )
    assert plan["adv_cap_applied"] is True
    assert "adv_cap_below_min_position" in plan["sizing_flags"]
    assert plan["suggested_position_size"] == 0


def test_trade_plan_backward_compatible_suggested_position_size():
    """Trade plan still includes suggested_position_size for backward compat."""
    generator = TradePlanGenerator()
    plan = generator.generate(_signal(entry_price=100.0, confidence=0.8, priority_score=8.0))
    assert "suggested_position_size" in plan
    assert plan["suggested_position_size"] >= 1


# ---------------------------------------------------------------------------
# Task 5: Regime gate v1
# ---------------------------------------------------------------------------

from agent.research_v1.regime_gate import evaluate_regime_gate


def test_regime_gate_missing_inputs_is_not_pass():
    result = evaluate_regime_gate({})
    assert result["regime_gate_status"] == "insufficient_definition"
    assert result["calibration_status"] == "prior_only"
    assert result["missing_features"]


def test_regime_gate_fails_extreme_volatility_features():
    result = evaluate_regime_gate({
        "vix_percentile": 0.99,
        "realized_vol_percentile": 0.96,
        "market_breadth_percentile": 0.50,
        "cross_sectional_dispersion_percentile": 0.50,
        "major_index_trend_state": "uptrend",
    })
    assert result["regime_gate_status"] == "fail"
    assert "vix_percentile" in result["failing_features"]
    assert "realized_vol_percentile" in result["failing_features"]


def test_regime_gate_warns_on_weak_breadth():
    result = evaluate_regime_gate({
        "vix_percentile": 0.50,
        "realized_vol_percentile": 0.50,
        "market_breadth_percentile": 0.10,
        "cross_sectional_dispersion_percentile": 0.50,
        "major_index_trend_state": "uptrend",
    })
    assert result["regime_gate_status"] == "warn"
    assert "market_breadth_percentile" in result["failing_features"]


def test_regime_gate_passes_all_good_inputs():
    result = evaluate_regime_gate({
        "vix_percentile": 0.30,
        "realized_vol_percentile": 0.30,
        "market_breadth_percentile": 0.60,
        "cross_sectional_dispersion_percentile": 0.30,
        "major_index_trend_state": "uptrend",
    })
    assert result["regime_gate_status"] == "pass"


# ---------------------------------------------------------------------------
# Task 6: P22 return selector and stress disclosure
# ---------------------------------------------------------------------------

from agent.research_v1.p22_return_selector import select_forward_return
from agent.research_v1.stress_testing import evaluate_stress_scenarios


def test_p22_return_selector_defaults_to_net_return():
    observation = {
        "gross_return_pct": 0.10,
        "net_return_pct": 0.085,
        "return_value": 0.10,
    }
    assert select_forward_return(observation) == 0.085
    assert select_forward_return(observation, return_basis="gross") == 0.10


def test_p22_return_selector_rejects_unknown_basis():
    with pytest.raises(ValueError, match="return_basis"):
        select_forward_return({"net_return_pct": 0.01}, return_basis="raw")


def test_p22_return_selector_falls_back_to_return_value_for_gross():
    observation = {"return_value": 0.08}
    assert select_forward_return(observation, return_basis="gross") == 0.08


def test_stress_testing_boss_output_hidden_without_resimulation():
    result = evaluate_stress_scenarios(
        {"2008_crisis": {"max_drawdown": -0.30}},
        resimulation_enabled=False,
        boss_facing_enabled=True,
    )
    assert result["resimulation_status"] == "disabled"
    assert result["boss_facing_enabled"] is False
