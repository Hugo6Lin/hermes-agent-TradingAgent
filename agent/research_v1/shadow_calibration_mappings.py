"""Conservative factor-to-shadow-parameter mappings for P23."""

from __future__ import annotations


def map_factor_to_shadow_parameters(factor_name: str, horizon_days: int) -> list[dict]:
    mappings = [{"parameter_family": "ranking_hint", "parameter_name": factor_name}]
    if factor_name == "company_quality_score":
        mappings.append({"parameter_family": "role_weight", "parameter_name": "fundamentals"})
        if horizon_days >= 21:
            mappings.append({"parameter_family": "thesis_threshold", "parameter_name": "investable_quality_threshold"})
    elif factor_name == "valuation_attractiveness_score":
        mappings.append({"parameter_family": "role_weight", "parameter_name": "valuation"})
        if horizon_days >= 21:
            mappings.append({"parameter_family": "thesis_threshold", "parameter_name": "investable_valuation_threshold"})
    elif factor_name == "timing_market_fit_score":
        mappings.append({"parameter_family": "role_weight", "parameter_name": "technical"})
        if horizon_days <= 5:
            mappings.append({"parameter_family": "exit_multiple", "parameter_name": "timing_exit_responsiveness"})
    elif factor_name == "llm_adjustment_total":
        mappings.append({"parameter_family": "role_weight", "parameter_name": "sentiment"})
    elif factor_name == "negative_signal_strength_decile":
        mappings.append({"parameter_family": "ranking_hint", "parameter_name": "negative_signal_filter"})
    return mappings
