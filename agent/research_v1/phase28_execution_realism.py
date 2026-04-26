"""Phase 28 execution realism pack: slippage, liquidity stress, ADV realism, and execution-only PPO admission gate."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


# ─── Errors ───────────────────────────────────────────────────────────────────

class ExecutionRealismError(ValueError):
    """Raised for unsafe Phase 28 execution realism requests."""


# ─── Constants ────────────────────────────────────────────────────────────────

ADV_PARTICIPATION_LIMIT = 0.05          # 5% ADV hard limit
MIN_EXECUTION_LOG_COUNT = 10            # minimum execution log rows for PPO gate
STRESS_SCENARIO_NAMES = frozenset({"normal", "moderate", "severe", "extreme"})

# P28-9: Impact model uses quadratic scaling: k * participation^2 * 10000.
# Rationale: Conservative upper-bound estimator. Industry literature often uses
# square-root impact (k * sqrt(participation) * vol), which is less severe at
# low participation and more severe at high participation. The quadratic form
# is retained here as the conservative choice per spec §2 (Phase 28 must not
# understate execution costs).
ILLIQUIDITY_COEFFICIENT_DEFAULT = 1.0


# ─── Trade Intent ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TradeIntent:
    ticker: str
    direction: str          # "long" or "short"
    quantity: float         # must be > 0; use direction="short" for short trades
    price: float           # must be > 0
    market_cap: float      # must be > 0
    estimated_commission_bps: float = 0.5

    def __post_init__(self) -> None:
        if self.direction not in {"long", "short"}:
            raise ExecutionRealismError(
                f"direction must be 'long' or 'short', got {self.direction!r}"
            )
        if self.quantity <= 0:
            raise ExecutionRealismError(f"quantity must be > 0, got {self.quantity}")
        if self.price <= 0:
            raise ExecutionRealismError(f"price must be > 0, got {self.price}")
        if self.market_cap <= 0:
            raise ExecutionRealismError(f"market_cap must be > 0, got {self.market_cap}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "direction": self.direction,
            "quantity": self.quantity,
            "price": self.price,
            "market_cap": self.market_cap,
            "estimated_commission_bps": self.estimated_commission_bps,
        }


# ─── Market Liquidity ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MarketLiquidity:
    adv: float              # average daily volume (shares)
    spread_bps: float       # bid-ask spread in basis points
    daily_volatility_bps: float  # daily volatility in bps
    volume: float           # trading volume for the day

    def to_dict(self) -> dict[str, Any]:
        return {
            "adv": self.adv,
            "spread_bps": self.spread_bps,
            "daily_volatility_bps": self.daily_volatility_bps,
            "volume": self.volume,
        }


# ─── Request ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExecutionRealismRequest:
    trade_intents: tuple[TradeIntent, ...]
    market_liquidity_by_ticker: tuple[tuple[str, MarketLiquidity], ...]
    alpha_edge_bps: float   # expected alpha in bps; used to detect stress_cost_exceeds_edge
    stress_scenario: str = "normal"
    adv_participation_limit: float = ADV_PARTICIPATION_LIMIT
    illiquidity_coefficient: float = ILLIQUIDITY_COEFFICIENT_DEFAULT
    notes: str = ""

    def __post_init__(self) -> None:
        if not (0 < self.alpha_edge_bps):
            raise ExecutionRealismError("alpha_edge_bps must be > 0")
        if self.stress_scenario not in STRESS_SCENARIO_NAMES:
            raise ExecutionRealismError(
                f"stress_scenario must be one of {sorted(STRESS_SCENARIO_NAMES)}"
            )
        if not (0 < self.adv_participation_limit <= 1):
            raise ExecutionRealismError("adv_participation_limit must be in (0, 1]")

    def liquidity_map(self) -> dict[str, MarketLiquidity]:
        return dict(self.market_liquidity_by_ticker)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_intents": [t.to_dict() for t in self.trade_intents],
            "market_liquidity_by_ticker": {k: v.to_dict() for k, v in self.market_liquidity_by_ticker},
            "alpha_edge_bps": self.alpha_edge_bps,
            "stress_scenario": self.stress_scenario,
            "adv_participation_limit": self.adv_participation_limit,
            "illiquidity_coefficient": self.illiquidity_coefficient,
            "notes": self.notes,
        }


# ─── Slippage Estimate ────────────────────────────────────────────────────────
# Component fields (commission_bps, half_spread_bps, impact_bps, volatility_penalty_bps)
# represent unstressed base values.  total_cost_bps applies stress multipliers
# (spread_multiplier, impact_multiplier, volatility_multiplier) to produce the
# final stressed cost.  This follows spec §5.

@dataclass(frozen=True)
class SlippageEstimate:
    ticker: str
    direction: str
    commission_bps: float           # base commission (unstressed)
    half_spread_bps: float          # base half-spread (unstressed)
    impact_bps: float              # base market impact (unstressed)
    adv_participation: float       # fraction of ADV
    volatility_penalty_bps: float  # base volatility penalty (unstressed)
    liquidity_stress_penalty_bps: float  # additional penalty from stress scenario
    total_cost_bps: float          # stressed total = sum of stressed components
    adv_limit_exceeded: bool        # True when adv_participation > limit (strict >; P28-8)
    spread_missing: bool           # True when spread_bps <= 0 or no liquidity row (P28-7)
    liquidity_data_missing: bool   # True when no MarketLiquidity row exists for ticker
    stress_cost_exceeds_edge: bool  # True when total_cost_bps > alpha_edge_bps

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "direction": self.direction,
            "commission_bps": self.commission_bps,
            "half_spread_bps": self.half_spread_bps,
            "impact_bps": self.impact_bps,
            "adv_participation": self.adv_participation,
            "volatility_penalty_bps": self.volatility_penalty_bps,
            "liquidity_stress_penalty_bps": self.liquidity_stress_penalty_bps,
            "total_cost_bps": self.total_cost_bps,
            "adv_limit_exceeded": self.adv_limit_exceeded,
            "spread_missing": self.spread_missing,
            "liquidity_data_missing": self.liquidity_data_missing,
            "stress_cost_exceeds_edge": self.stress_cost_exceeds_edge,
        }


# ─── Liquidity Stress ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LiquidityStressScenario:
    name: str
    spread_multiplier: float
    impact_multiplier: float
    volatility_multiplier: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "spread_multiplier": self.spread_multiplier,
            "impact_multiplier": self.impact_multiplier,
            "volatility_multiplier": self.volatility_multiplier,
            "description": self.description,
        }


_STRESS_SCENARIOS: tuple[LiquidityStressScenario, ...] = (
    LiquidityStressScenario(
        name="normal",
        spread_multiplier=1.0,
        impact_multiplier=1.0,
        volatility_multiplier=1.0,
        description="Baseline market conditions.",
    ),
    LiquidityStressScenario(
        name="moderate",
        spread_multiplier=1.5,
        impact_multiplier=1.3,
        volatility_multiplier=1.2,
        description="Elevated but manageable liquidity conditions.",
    ),
    LiquidityStressScenario(
        name="severe",
        spread_multiplier=2.0,
        impact_multiplier=1.8,
        volatility_multiplier=1.6,
        description="Significant liquidity stress; spreads widen materially.",
    ),
    LiquidityStressScenario(
        name="extreme",
        spread_multiplier=3.0,
        impact_multiplier=2.5,
        volatility_multiplier=2.0,
        description="Crisis-level conditions; execution costs spike.",
    ),
)


def _get_stress_scenario(name: str) -> LiquidityStressScenario:
    for s in _STRESS_SCENARIOS:
        if s.name == name:
            return s
    raise ExecutionRealismError(f"Unknown stress scenario: {name}")


# ─── Execution Realism Report ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ExecutionRealismReport:
    request_config: tuple[tuple[str, Any], ...]   # key-value audit trail
    slippage_estimates: tuple[SlippageEstimate, ...]
    stress_scenario: LiquidityStressScenario
    portfolio_liquidity_warnings: tuple[str, ...]
    average_trade_cost_bps: float        # simple arithmetic mean per-trade cost (P28-3)
    weighted_portfolio_cost_bps: float   # notional-weighted aggregate cost (P28-3)
    constrained_slippage_count: int
    stress_cost_exceeds_edge_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_config": dict(self.request_config),
            "slippage_estimates": [s.to_dict() for s in self.slippage_estimates],
            "stress_scenario": self.stress_scenario.to_dict(),
            "portfolio_liquidity_warnings": list(self.portfolio_liquidity_warnings),
            "average_trade_cost_bps": self.average_trade_cost_bps,
            "weighted_portfolio_cost_bps": self.weighted_portfolio_cost_bps,
            "constrained_slippage_count": self.constrained_slippage_count,
            "stress_cost_exceeds_edge_count": self.stress_cost_exceeds_edge_count,
        }


# ─── PPO Admission ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PPOExecutionAdmissionDecision:
    admitted: bool
    objective: str
    affects_stock_selection: bool
    portfolio_layer_present: bool
    execution_logs_sufficient: bool
    no_live_trading_effect: bool
    decision_reasons: tuple[str, ...]
    sub_scores: tuple[tuple[str, float], ...]

    def to_dict(self) -> dict[str, Any]:
        # P28-6: defensive rebuild — advisory decisions must not survive
        # serialization with a forged admitted flag
        return {
            "admitted": self.admitted,
            "objective": self.objective,
            "affects_stock_selection": self.affects_stock_selection,
            "portfolio_layer_present": self.portfolio_layer_present,
            "execution_logs_sufficient": self.execution_logs_sufficient,
            "no_live_trading_effect": self.no_live_trading_effect,
            "decision_reasons": list(self.decision_reasons),
            "sub_scores": dict(self.sub_scores),
        }


@dataclass(frozen=True)
class PPOAdmissionRequest:
    objective: str
    affects_stock_selection: bool
    portfolio_layer_present: bool
    execution_log_count: int
    live_trading_effect: bool
    notes: str = ""


# ─── Core Estimation Logic ─────────────────────────────────────────────────────

def estimate_execution_costs(
    trade_intents: tuple[TradeIntent, ...],
    market_liquidity: tuple[tuple[str, MarketLiquidity], ...],
    request: ExecutionRealismRequest,
) -> ExecutionRealismReport:
    liquidity_map = dict(market_liquidity)
    scenario = _get_stress_scenario(request.stress_scenario)

    slippage_estimates: list[SlippageEstimate] = []
    warnings: list[str] = []
    stress_cost_exceeds_count = 0
    constrained_count = 0
    total_notional = 0.0
    weighted_cost_sum = 0.0

    for intent in trade_intents:
        ticker = intent.ticker
        liq = liquidity_map.get(ticker)

        # Commission BPS (from intent)
        commission_bps = intent.estimated_commission_bps

        # Spread / half-spread
        # P28-7: spread_missing fires for two distinct cases:
        #   (a) no liquidity row exists for ticker (liquidity_data_missing=True), OR
        #   (b) liquidity row exists but spread_bps <= 0
        if liq is None:
            spread_missing = True
            half_spread_bps = 0.0
            warnings.append(f"liquidity_data_missing:{ticker}")
        else:
            spread_missing = liq.spread_bps <= 0.0
            half_spread_bps = max(0.0, liq.spread_bps / 2.0)

        # ADV participation
        # P28-8: strict > (not >=) — participation exactly at the limit is NOT exceeded
        if liq is None or liq.adv <= 0.0:
            adv_participation = 0.0
            adv_limit_exceeded = False
        else:
            notional = intent.quantity * intent.price
            adv_dollar = liq.adv * intent.price
            adv_participation = notional / adv_dollar if adv_dollar > 0 else 0.0
            adv_limit_exceeded = adv_participation > request.adv_participation_limit

        # Market impact BPS: k * participation^2 * 10000 (quadratic; P28-9)
        impact_bps = request.illiquidity_coefficient * (adv_participation ** 2) * 10000.0

        # Volatility penalty BPS: 0.5 * daily_volatility_bps * adv_participation
        if liq is None:
            volatility_penalty_bps = 0.0
        else:
            volatility_penalty_bps = 0.5 * liq.daily_volatility_bps * adv_participation

        # Liquidity stress penalty: apply scenario multipliers
        spread_pen = half_spread_bps * (scenario.spread_multiplier - 1.0)
        impact_pen = impact_bps * (scenario.impact_multiplier - 1.0)
        vol_pen = volatility_penalty_bps * (scenario.volatility_multiplier - 1.0)
        liquidity_stress_penalty_bps = spread_pen + impact_pen + vol_pen

        # Total stressed cost
        total_cost_bps = (
            commission_bps
            + half_spread_bps * scenario.spread_multiplier
            + impact_bps * scenario.impact_multiplier
            + volatility_penalty_bps * scenario.volatility_multiplier
        )

        # P28-2: missing liquidity rows must always fire stress_cost_exceeds_edge=True
        # so that downstream filters on stress_cost_exceeds_edge=False cannot silently
        # include unknown-cost tickers.
        missing_liq = liq is None
        stress_cost_exceeds_edge = missing_liq or (total_cost_bps > request.alpha_edge_bps)
        if stress_cost_exceeds_edge:
            stress_cost_exceeds_count += 1

        if adv_limit_exceeded or spread_missing or missing_liq:
            constrained_count += 1

        slippage_estimates.append(SlippageEstimate(
            ticker=ticker,
            direction=intent.direction,
            commission_bps=commission_bps,
            half_spread_bps=half_spread_bps,
            impact_bps=impact_bps,
            adv_participation=adv_participation,
            volatility_penalty_bps=volatility_penalty_bps,
            liquidity_stress_penalty_bps=liquidity_stress_penalty_bps,
            total_cost_bps=total_cost_bps,
            adv_limit_exceeded=adv_limit_exceeded,
            spread_missing=spread_missing,
            liquidity_data_missing=missing_liq,
            stress_cost_exceeds_edge=stress_cost_exceeds_edge,
        ))

        # P28-3: accumulate for notional-weighted average
        notional = intent.quantity * intent.price
        total_notional += notional
        weighted_cost_sum += notional * total_cost_bps

    n = max(len(slippage_estimates), 1)
    average_trade_cost_bps = sum(s.total_cost_bps for s in slippage_estimates) / n
    weighted_portfolio_cost_bps = weighted_cost_sum / total_notional if total_notional > 0 else 0.0

    config_items: list[tuple[str, Any]] = [
        ("alpha_edge_bps", request.alpha_edge_bps),
        ("stress_scenario", request.stress_scenario),
        ("adv_participation_limit", request.adv_participation_limit),
        ("illiquidity_coefficient", request.illiquidity_coefficient),
        ("trade_intent_count", len(trade_intents)),
    ]

    return ExecutionRealismReport(
        request_config=tuple(config_items),
        slippage_estimates=tuple(slippage_estimates),
        stress_scenario=scenario,
        portfolio_liquidity_warnings=tuple(warnings),
        average_trade_cost_bps=average_trade_cost_bps,
        weighted_portfolio_cost_bps=weighted_portfolio_cost_bps,
        constrained_slippage_count=constrained_count,
        stress_cost_exceeds_edge_count=stress_cost_exceeds_count,
    )


def evaluate_ppo_execution_admission(
    evidence: dict[str, Any],
    request: PPOAdmissionRequest,
) -> PPOExecutionAdmissionDecision:
    """
    P28-5: evidence is consulted to corroborate the request.
    Any mismatch between evidence and request fields produces a rejection
    with reason 'evidence_inconsistent_with_request'.
    """
    reasons: list[str] = []
    sub_scores: list[tuple[str, float]] = []

    # Cross-check evidence vs request
    evidence_mismatch = False
    ev_obj = evidence.get("objective")
    ev_live = evidence.get("live_trading_effect")
    ev_log_count = evidence.get("execution_log_count")

    if ev_obj is not None and ev_obj != request.objective:
        evidence_mismatch = True
    if ev_live is not None and ev_live != request.live_trading_effect:
        evidence_mismatch = True
    if ev_log_count is not None and ev_log_count < request.execution_log_count:
        evidence_mismatch = True

    if evidence_mismatch:
        reasons.append("evidence_inconsistent_with_request")
        sub_scores.append(("evidence_consistent", 0.0))
    else:
        sub_scores.append(("evidence_consistent", 1.0))

    # Gate 1: objective must be execution_cost_reduction
    objective_match = request.objective == "execution_cost_reduction"
    sub_scores.append(("objective_execution_cost_reduction", float(objective_match)))
    if not objective_match:
        reasons.append("objective_not_execution_cost_reduction")

    # Gate 2: must not affect stock selection
    sub_scores.append(("stock_selection_unchanged", float(not request.affects_stock_selection)))
    if request.affects_stock_selection:
        reasons.append("affects_stock_selection_is_true")

    # Gate 3: portfolio layer must exist
    portfolio_present = bool(request.portfolio_layer_present)
    sub_scores.append(("portfolio_layer_present", float(portfolio_present)))
    if not portfolio_present:
        reasons.append("portfolio_layer_missing")

    # Gate 4: sufficient execution logs
    logs_sufficient = request.execution_log_count >= MIN_EXECUTION_LOG_COUNT
    sub_scores.append(("execution_logs_sufficient", float(logs_sufficient)))
    if not logs_sufficient:
        reasons.append("insufficient_execution_logs")

    # Gate 5: no live trading effect
    no_live_effect = not request.live_trading_effect
    sub_scores.append(("no_live_trading_effect", float(no_live_effect)))
    if request.live_trading_effect:
        reasons.append("live_trading_effect_present")

    admitted = (
        not evidence_mismatch
        and objective_match
        and not request.affects_stock_selection
        and portfolio_present
        and logs_sufficient
        and no_live_effect
    )

    if admitted:
        reasons.append("all_gates_passed")

    return PPOExecutionAdmissionDecision(
        admitted=admitted,
        objective=request.objective,
        affects_stock_selection=request.affects_stock_selection,
        portfolio_layer_present=portfolio_present,
        execution_logs_sufficient=logs_sufficient,
        no_live_trading_effect=no_live_effect,
        decision_reasons=tuple(reasons),
        sub_scores=tuple(sub_scores),
    )
