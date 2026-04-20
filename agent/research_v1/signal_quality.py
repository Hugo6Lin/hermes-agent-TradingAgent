"""Signal ranking and evidence-quality helpers for P3."""


def rank_signals_with_portfolio_context(
    signals: list[dict],
    open_positions: list[dict],
) -> list[dict]:
    """Rank signals by priority with a sector-overlap penalty."""
    sector_exposure: dict[str, int] = {}
    for position in open_positions:
        if position.get("status") != "open":
            continue
        sector = position.get("sector", "UNKNOWN")
        sector_exposure[sector] = sector_exposure.get(sector, 0) + 1

    ranked = []
    for signal in signals:
        base_priority = float(signal.get("priority_score", 0.0))
        sector = signal.get("sector", "UNKNOWN")
        overlap_count = sector_exposure.get(sector, 0)
        overlap_penalty = min(15.0, overlap_count * 5.0)
        adjusted_priority = max(0.0, base_priority - overlap_penalty)
        enriched = dict(signal)
        enriched["overlap_penalty"] = overlap_penalty
        enriched["adjusted_priority"] = adjusted_priority
        ranked.append(enriched)

    return sorted(ranked, key=lambda item: item["adjusted_priority"], reverse=True)


def detect_evidence_conflicts(source_fields: dict, analyst_views: dict) -> dict:
    """Detect conflicting source fields and return confidence penalty."""
    conflicts = []
    confidence_penalty = 0.0

    # Cross-source field disagreement detection.
    field_values: dict[str, list[tuple[str, float]]] = {}
    for source, payload in source_fields.items():
        for field, value in payload.items():
            if isinstance(value, (int, float)):
                field_values.setdefault(field, []).append((source, float(value)))

    for field, values in field_values.items():
        if len(values) < 2:
            continue
        numeric = [value for _, value in values]
        baseline = min(numeric) if min(numeric) != 0 else 1.0
        spread_ratio = (max(numeric) - min(numeric)) / abs(baseline)
        if spread_ratio >= 0.05:
            conflicts.append({
                "field": field,
                "sources": [source for source, _ in values],
                "spread_ratio": round(spread_ratio, 4),
            })
            confidence_penalty += 0.05

    technical_signal = analyst_views.get("technical_summary", {}).get("signal")
    if technical_signal == "buy":
        momentum = source_fields.get("yahoo", {}).get("momentum")
        if momentum is not None and momentum < 0:
            conflicts.append({
                "field": "momentum",
                "sources": ["yahoo", "technical_summary"],
                "spread_ratio": 1.0,
            })
            confidence_penalty += 0.03

    confidence_penalty = min(0.35, round(confidence_penalty, 4))
    return {
        "has_conflict": len(conflicts) > 0,
        "conflicts": conflicts,
        "confidence_penalty": confidence_penalty,
    }
