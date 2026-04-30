"""Transaction cost model for P20/P22 net-return evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CostModel:
    """Estimate round-trip transaction costs for signal outcome analysis."""

    commission_bps: float = 0.5
    half_spread_bps: float = 1.0
    impact_coefficient_bps: float = 0.0
    illiquidity_penalty_threshold: float = 0.05
    illiquidity_penalty_bps: float = 0.0

    def estimate(
        self,
        adv_shares_20d: Optional[float] = None,
        position_shares: Optional[float] = None,
    ) -> dict:
        adv = float(adv_shares_20d or 0.0)
        position = float(position_shares or 0.0)
        position_as_pct_of_adv = position / adv if adv > 0 else 0.0
        impact_bps = self.impact_coefficient_bps * position_as_pct_of_adv
        liquidity_flags: list = []
        illiquidity_penalty_bps = 0.0
        if adv <= 0 and position > 0:
            liquidity_flags.append("missing_adv")
        if position_as_pct_of_adv > self.illiquidity_penalty_threshold:
            liquidity_flags.append("position_exceeds_adv_threshold")
            illiquidity_penalty_bps = self.illiquidity_penalty_bps
        total_bps = (
            self.commission_bps
            + self.half_spread_bps
            + impact_bps
            + illiquidity_penalty_bps
        )
        return {
            "commission_bps": round(self.commission_bps, 6),
            "half_spread_bps": round(self.half_spread_bps, 6),
            "impact_bps": round(impact_bps, 6),
            "illiquidity_penalty_bps": round(illiquidity_penalty_bps, 6),
            "transaction_cost_pct": round(total_bps / 10_000.0, 10),
            "position_as_pct_of_adv": round(position_as_pct_of_adv, 10),
            "liquidity_flags": liquidity_flags,
        }

    def apply(
        self,
        gross_return_pct: float,
        adv_shares_20d: Optional[float] = None,
        position_shares: Optional[float] = None,
    ) -> dict:
        estimate = self.estimate(
            adv_shares_20d=adv_shares_20d,
            position_shares=position_shares,
        )
        net_return = gross_return_pct - estimate["transaction_cost_pct"]
        return {
            **estimate,
            "gross_return_pct": round(gross_return_pct, 10),
            "net_return_pct": round(net_return, 10),
        }
