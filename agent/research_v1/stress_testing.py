"""Extreme-regime stress scenario definitions and evaluation helpers."""


STRESS_SCENARIOS = {
    "2008_crisis": {
        "label": "2008 Financial Crisis",
        "description": "Liquidity shock and broad equity collapse.",
    },
    "2020_covid_crash": {
        "label": "2020 COVID Crash",
        "description": "Fast drawdown and violent recovery conditions.",
    },
    "2022_rate_hike_bear": {
        "label": "2022 Rate Hike Bear",
        "description": "Persistent valuation compression under tightening.",
    },
}


def evaluate_stress_scenarios(
    scenario_results: dict[str, dict],
    max_drawdown_limit: float = -0.25,
    resimulation_enabled: bool = False,
    boss_facing_enabled: bool = False,
) -> dict:
    """Evaluate regime-specific outcomes against a drawdown threshold.

    Args:
        scenario_results: Dict of scenario name -> metrics dict.
        max_drawdown_limit: Threshold below which a warning is generated.
        resimulation_enabled: Whether real regime-window resimulation is available.
        boss_facing_enabled: Whether results should be shown to end users.

    Returns:
        Dict with scenario_count, has_critical_regime, warnings, resimulation_status,
        and boss_facing_enabled fields.
    """
    warnings = []
    for scenario_name, metrics in scenario_results.items():
        max_drawdown = metrics.get("max_drawdown", 0.0)
        if max_drawdown <= max_drawdown_limit:
            warnings.append({
                "scenario": scenario_name,
                "reason": "max_drawdown_breach",
                "max_drawdown": max_drawdown,
                "average_return": metrics.get("average_return"),
                "win_rate": metrics.get("win_rate"),
            })

    return {
        "scenario_count": len(scenario_results),
        "has_critical_regime": len(warnings) > 0,
        "warnings": warnings,
        "resimulation_status": "enabled" if resimulation_enabled else "disabled",
        "boss_facing_enabled": bool(boss_facing_enabled and resimulation_enabled),
    }
