"""Dynamic analyst weighting from historical usefulness signals."""


class AnalystWeightEngine:
    """Rebalance analyst weights while preserving normalized totals."""

    def __init__(self, base_weights: dict[str, float], floor: float = 0.05):
        self.base_weights = dict(base_weights)
        self.floor = floor

    def rebalance(self, usefulness: dict[str, float]) -> dict[str, float]:
        """Derive normalized weights from base weights and usefulness scores."""
        raw_weights: dict[str, float] = {}
        for analyst, base_weight in self.base_weights.items():
            usefulness_score = max(0.0, float(usefulness.get(analyst, 0.5)))
            raw_weights[analyst] = max(self.floor, base_weight * usefulness_score)

        total = sum(raw_weights.values())
        if total <= 0:
            uniform = 1.0 / len(raw_weights)
            return {key: uniform for key in raw_weights}

        return {
            analyst: value / total
            for analyst, value in raw_weights.items()
        }
