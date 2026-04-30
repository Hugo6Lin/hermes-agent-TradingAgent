"""Phase 26 shadow portfolio simulation and advisory governance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from types import MappingProxyType
import json
from typing import Any


PORTFOLIO_MODES = {"long_only_top_rank", "long_short_rank_shadow"}
REBALANCE_FREQUENCIES = {"window", "weekly", "monthly"}
COST_BASIS_OPTIONS = {"net_target", "explicit_cost_field"}
FORBIDDEN_FIELDS = {
    "live_trade_signal",
    "order_id",
    "broker_instruction",
    "production_config_update",
}

# Governance gate thresholds (spec §8)
HIT_RATE_READY_THRESHOLD = 0.60
AVG_TURNOVER_WATCH_THRESHOLD = 0.80


class PortfolioSimulationError(ValueError):
    """Raised for unsafe Phase 26 simulation requests."""


@dataclass(frozen=True)
class PortfolioSimulationRequest:
    simulation_id: str
    training_run_id: str
    experiment_id: str
    candidate_namespace: str
    portfolio_mode: str
    initial_capital: float
    max_positions: int
    max_single_name_weight: float
    max_sector_weight: float
    gross_exposure_limit: float
    turnover_limit: float
    min_prediction_value: float
    rebalance_frequency: str
    cost_basis: str
    governance_review_enabled: bool
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_namespace.startswith("shadow_meta_model."):
            raise PortfolioSimulationError("candidate_namespace must start with shadow_meta_model")
        if self.portfolio_mode not in PORTFOLIO_MODES:
            raise PortfolioSimulationError(f"portfolio_mode not allowed: {self.portfolio_mode}")
        if self.initial_capital <= 0:
            raise PortfolioSimulationError("initial_capital must be > 0")
        if self.max_positions < 1:
            raise PortfolioSimulationError("max_positions must be >= 1")
        if not (0 < self.max_single_name_weight <= 1):
            raise PortfolioSimulationError("max_single_name_weight must be in (0, 1]")
        if not (0 < self.max_sector_weight <= 1):
            raise PortfolioSimulationError("max_sector_weight must be in (0, 1]")
        if not (0 < self.gross_exposure_limit <= 2):
            raise PortfolioSimulationError("gross_exposure_limit must be in (0, 2]")
        if not (0 <= self.turnover_limit <= 2):
            raise PortfolioSimulationError("turnover_limit must be in [0, 2]")
        if self.rebalance_frequency not in REBALANCE_FREQUENCIES:
            raise PortfolioSimulationError(f"rebalance_frequency not allowed: {self.rebalance_frequency}")
        if self.cost_basis not in COST_BASIS_OPTIONS:
            raise PortfolioSimulationError(f"cost_basis not allowed: {self.cost_basis}")
        if self.governance_review_enabled is not True:
            raise PortfolioSimulationError("governance_review_enabled must be true")


@dataclass(frozen=True)
class PortfolioHolding:
    window_id: str
    snapshot_id: str
    ticker: str
    sector: str
    target_weight: float
    capped_weight: float
    prediction_value: float
    actual_target_value: float
    constraint_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "snapshot_id": self.snapshot_id,
            "ticker": self.ticker,
            "sector": self.sector,
            "target_weight": self.target_weight,
            "capped_weight": self.capped_weight,
            "prediction_value": self.prediction_value,
            "actual_target_value": self.actual_target_value,
            "constraint_flags": list(self.constraint_flags),
        }


@dataclass(frozen=True)
class PortfolioWindowResult:
    simulation_id: str
    window_id: str
    candidate_namespace: str
    holding_count: int
    gross_exposure: float
    net_exposure: float
    turnover: float
    portfolio_gross_return: float
    portfolio_net_return: float
    max_single_name_weight: float
    max_sector_weight: float
    constraint_violations: tuple[str, ...]
    holdings: tuple[PortfolioHolding, ...]
    status: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "window_id": self.window_id,
            "candidate_namespace": self.candidate_namespace,
            "holding_count": self.holding_count,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "turnover": self.turnover,
            "portfolio_gross_return": self.portfolio_gross_return,
            "portfolio_net_return": self.portfolio_net_return,
            "max_single_name_weight": self.max_single_name_weight,
            "max_sector_weight": self.max_sector_weight,
            "constraint_violations": list(self.constraint_violations),
            "holdings": [h.to_dict() for h in self.holdings],
            "status": self.status,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PortfolioRiskSummary:
    total_windows: int
    evaluated_windows: int
    cumulative_net_return: float
    average_window_net_return: float
    volatility_proxy: float
    max_drawdown: float
    hit_rate: float
    average_turnover: float
    max_observed_single_name_weight: float
    max_observed_sector_weight: float
    constraint_violation_count: int
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_windows": self.total_windows,
            "evaluated_windows": self.evaluated_windows,
            "cumulative_net_return": self.cumulative_net_return,
            "average_window_net_return": self.average_window_net_return,
            "volatility_proxy": self.volatility_proxy,
            "max_drawdown": self.max_drawdown,
            "hit_rate": self.hit_rate,
            "average_turnover": self.average_turnover,
            "max_observed_single_name_weight": self.max_observed_single_name_weight,
            "max_observed_sector_weight": self.max_observed_sector_weight,
            "constraint_violation_count": self.constraint_violation_count,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class Phase26GovernanceDecision:
    schema_version: str
    simulation_id: str
    training_run_id: str
    experiment_id: str
    candidate_namespace: str
    decision: str
    decision_reasons: tuple[str, ...]
    production_config_changes: dict[str, Any]
    apply_to_production: bool
    next_phase_recommendation: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        # Enforce invariants: these are always empty/False per spec
        return {
            "schema_version": self.schema_version,
            "simulation_id": self.simulation_id,
            "training_run_id": self.training_run_id,
            "experiment_id": self.experiment_id,
            "candidate_namespace": self.candidate_namespace,
            "decision": self.decision,
            "decision_reasons": list(self.decision_reasons),
            "production_config_changes": {},
            "apply_to_production": False,
            "next_phase_recommendation": self.next_phase_recommendation,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ShadowPortfolioSimulationReport:
    schema_version: str
    simulation_id: str
    training_run_id: str
    experiment_id: str
    candidate_namespace: str
    portfolio_mode: str
    request_config: dict[str, Any]
    window_results: tuple[PortfolioWindowResult, ...]
    risk_summary: PortfolioRiskSummary
    governance_decision: Phase26GovernanceDecision
    safety_flags: dict[str, bool]
    warnings: tuple[str, ...]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "simulation_id": self.simulation_id,
            "training_run_id": self.training_run_id,
            "experiment_id": self.experiment_id,
            "candidate_namespace": self.candidate_namespace,
            "portfolio_mode": self.portfolio_mode,
            "request_config": dict(self.request_config),
            "window_results": [w.to_dict() for w in self.window_results],
            "risk_summary": self.risk_summary.to_dict(),
            "governance_decision": self.governance_decision.to_dict(),
            # Defensive copies prevent post-construction mutation from flowing into audit surface
            "safety_flags": dict(self.safety_flags),
            "warnings": list(self.warnings),
            "created_at": self.created_at,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise PortfolioSimulationError("input must be dict-like")


def _get_phase25_decision(phase25_result: Any) -> dict[str, Any]:
    if hasattr(phase25_result, "readiness_decision"):
        return _as_dict(phase25_result.readiness_decision)
    return _as_dict(phase25_result.get("readiness_decision", {}))


def _get_phase25_report(phase25_result: Any) -> dict[str, Any]:
    if hasattr(phase25_result, "evaluation_report"):
        return _as_dict(phase25_result.evaluation_report)
    return _as_dict(phase25_result.get("evaluation_report", {}))


# ─── Safety validation ────────────────────────────────────────────────────────

def _validate_prediction_rows(rows: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    """Check for forbidden fields. Returns (safety_warnings, sanitized_rows)."""
    safety_warnings: list[str] = []
    clean_rows: list[dict[str, Any]] = []
    for row in rows:
        row_warnings = []
        for field in FORBIDDEN_FIELDS:
            if field in row:
                row_warnings.append(f"forbidden_field_{field}")
        if row.get("candidate_namespace", "").startswith("production."):
            row_warnings.append("production_namespace_in_predictions")
        if row_warnings:
            safety_warnings.extend(row_warnings)
        else:
            clean_rows.append(row)
    return sorted(set(safety_warnings)), clean_rows


# ─── Portfolio construction ──────────────────────────────────────────────────

def _build_long_only_portfolio(
    rows: list[dict[str, Any]],
    request: PortfolioSimulationRequest,
) -> tuple[list[PortfolioHolding], float, float, float, float]:
    """
    Build long-only top-rank portfolio applying single-name and sector caps.
    Returns (holdings, gross_exposure, net_exposure, max_single_weight, max_sector_weight).
    """
    if not rows:
        return [], 0.0, 0.0, 0.0, 0.0

    sorted_rows = sorted(rows, key=lambda r: float(r.get("prediction_value", 0)), reverse=True)
    filtered = [r for r in sorted_rows if float(r.get("prediction_value", 0)) >= request.min_prediction_value]
    top = filtered[: request.max_positions]

    n = len(top)
    equal_weight = 1.0 / n if n > 0 else 0.0

    # Compute raw (equal) weights per snapshot
    raw_weights: dict[str, float] = {str(r.get("snapshot_id", "")): equal_weight for r in top}

    # Apply single-name cap
    capped_weights: dict[str, float] = {}
    for r in top:
        sid = str(r.get("snapshot_id", ""))
        w = raw_weights[sid]
        capped_weights[sid] = min(w, request.max_single_name_weight)

    # Apply sector cap via pro-rata scaling (P26-2 fix)
    sector_weights: dict[str, float] = {}
    for r in top:
        sid = str(r.get("snapshot_id", ""))
        sector = str(r.get("sector", "UNKNOWN"))
        sector_weights[sector] = sector_weights.get(sector, 0.0) + capped_weights[sid]

    for sector, total in sector_weights.items():
        if total > request.max_sector_weight + 1e-9:
            scale = request.max_sector_weight / total
            for r in top:
                sid = str(r.get("snapshot_id", ""))
                if str(r.get("sector", "UNKNOWN")) == sector:
                    capped_weights[sid] *= scale

    # Re-normalize so weights sum to 1 if caps not binding
    # P26-RR1: can_scale must also verify sector caps are not reintroduced by the scale
    total = sum(capped_weights.values())
    if total > 0 and abs(total - 1.0) > 1e-9:
        scale = 1.0 / total
        # Check single-name cap
        if all(capped_weights[sid] * scale <= request.max_single_name_weight + 1e-9 for sid in capped_weights):
            # Check sector cap is not reintroduced
            sector_totals_after_scale: dict[str, float] = {}
            for r in top:
                sid = str(r.get("snapshot_id", ""))
                sec = str(r.get("sector", "UNKNOWN"))
                sector_totals_after_scale[sec] = sector_totals_after_scale.get(sec, 0.0) + capped_weights[sid] * scale
            if all(v <= request.max_sector_weight + 1e-9 for v in sector_totals_after_scale.values()):
                for sid in capped_weights:
                    capped_weights[sid] *= scale

    # Build holdings with per-holding constraint flags
    holdings: list[PortfolioHolding] = []
    max_single_weight = 0.0
    sector_agg: dict[str, float] = {}

    for r in top:
        sid = str(r.get("snapshot_id", ""))
        ticker = str(r.get("ticker", ""))
        sector = str(r.get("sector", "UNKNOWN"))
        capped = capped_weights.get(sid, 0.0)
        raw = equal_weight

        flags: list[str] = []
        if capped < raw - 1e-9:
            flags.append("single_name_cap_applied")

        holdings.append(PortfolioHolding(
            window_id=str(r.get("window_id", "")),
            snapshot_id=sid,
            ticker=ticker,
            sector=sector,
            target_weight=raw,
            capped_weight=capped,
            prediction_value=float(r.get("prediction_value", 0)),
            actual_target_value=float(r.get("actual_target_value", 0)),
            constraint_flags=tuple(flags),
        ))

        max_single_weight = max(max_single_weight, capped)
        sector_agg[sector] = sector_agg.get(sector, 0.0) + capped

    max_sector_weight_val = max(sector_agg.values()) if sector_agg else 0.0
    gross_exposure = sum(capped_weights.values())
    net_exposure = gross_exposure  # long-only

    return holdings, gross_exposure, net_exposure, max_single_weight, max_sector_weight_val


def _build_long_short_shadow_portfolio(
    rows: list[dict[str, Any]],
    request: PortfolioSimulationRequest,
) -> tuple[list[PortfolioHolding], float, float, float, float]:
    """
    Long-short shadow: top half long, bottom half short, each leg capped at max_positions.
    Returns (holdings, gross_exposure, net_exposure, max_single_weight, max_sector_weight).
    Emits shadow_only_short_analysis warning only; never a constraint violation.
    """
    if not rows:
        return [], 0.0, 0.0, 0.0, 0.0

    sorted_rows = sorted(rows, key=lambda r: float(r.get("prediction_value", 0)), reverse=True)
    half = len(sorted_rows) // 2
    if half == 0:
        return [], 0.0, 0.0, 0.0, 0.0

    max_per_leg = max(1, request.max_positions // 2)

    long_rows = sorted_rows[:max_per_leg]
    short_rows = sorted_rows[-max_per_leg:] if max_per_leg < len(sorted_rows) else []

    n_long = len(long_rows)
    n_short = len(short_rows)
    long_weight = 0.5 / n_long if n_long > 0 else 0.0
    short_weight = 0.5 / n_short if n_short > 0 else 0.0

    holdings: list[PortfolioHolding] = []
    gross = 0.0
    max_single = 0.0
    sector_agg: dict[str, float] = {}

    for r in long_rows:
        w = long_weight
        sid = str(r.get("snapshot_id", ""))
        sector = str(r.get("sector", "UNKNOWN"))
        holdings.append(PortfolioHolding(
            window_id=str(r.get("window_id", "")),
            snapshot_id=sid,
            ticker=str(r.get("ticker", "")),
            sector=sector,
            target_weight=w,
            capped_weight=w,
            prediction_value=float(r.get("prediction_value", 0)),
            actual_target_value=float(r.get("actual_target_value", 0)),
            constraint_flags=(),
        ))
        gross += w
        max_single = max(max_single, w)
        sector_agg[sector] = sector_agg.get(sector, 0.0) + w

    for r in short_rows:
        w = short_weight
        sid = str(r.get("snapshot_id", ""))
        sector = str(r.get("sector", "UNKNOWN"))
        holdings.append(PortfolioHolding(
            window_id=str(r.get("window_id", "")),
            snapshot_id=sid,
            ticker=str(r.get("ticker", "")),
            sector=sector,
            target_weight=-w,
            capped_weight=-w,
            prediction_value=float(r.get("prediction_value", 0)),
            actual_target_value=float(r.get("actual_target_value", 0)),
            constraint_flags=("shadow_short_position",),
        ))
        gross += w
        max_single = max(max_single, w)
        sector_agg[sector] = sector_agg.get(sector, 0.0) + w

    max_sector_val = max(sector_agg.values()) if sector_agg else 0.0
    net_exposure = sum(h.capped_weight for h in holdings)

    return holdings, gross, net_exposure, max_single, max_sector_val


# ─── Turnover ────────────────────────────────────────────────────────────────

def _compute_turnover(
    current_holdings: list[PortfolioHolding],
    prior_holdings: list[PortfolioHolding] | None,
) -> float:
    if prior_holdings is None:
        return 0.0
    current_weights = {h.ticker: h.capped_weight for h in current_holdings}
    prior_weights = {h.ticker: h.capped_weight for h in prior_holdings}
    all_tickers = set(current_weights) | set(prior_weights)
    return sum(abs(current_weights.get(t, 0.0) - prior_weights.get(t, 0.0)) for t in all_tickers)


# ─── Risk helpers ───────────────────────────────────────────────────────────

def _max_drawdown(window_returns: list[float]) -> float:
    """Peak-to-trough drawdown. Peak is initialized to 1.0 (initial capital)."""
    if not window_returns:
        return 0.0
    peak = 1.0
    cumulative = 1.0
    max_dd = 0.0
    for r in window_returns:
        cumulative *= (1.0 + r)
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return -max_dd


def _build_window_results(
    rows_by_window: dict[str, list[dict[str, Any]]],
    request: PortfolioSimulationRequest,
    prior_holdings_by_window: dict[str, list[PortfolioHolding]] | None,
) -> tuple[list[PortfolioWindowResult], list[str], int, float, float, float, float, list[str]]:
    """
    Build per-window results threading prior holdings for turnover computation.
    Returns (window_results, all_constraint_violations, cumulative_net,
            avg_net, avg_turnover, max_single, max_sector, all_safety_warnings).
    """
    window_results: list[PortfolioWindowResult] = []
    all_constraint_violations: list[str] = []
    all_safety_warnings: list[str] = []
    total_gross_return = 0.0
    total_net_return = 0.0
    total_turnover = 0.0
    max_single = 0.0
    max_sector = 0.0
    window_returns: list[float] = []

    sorted_windows = sorted(rows_by_window.keys())
    prior_holdings = dict(prior_holdings_by_window) if prior_holdings_by_window else {}

    for window_id in sorted_windows:
        rows = rows_by_window[window_id]

        if request.portfolio_mode == "long_short_rank_shadow":
            holdings, gross_exp, net_exp, ms, mss = _build_long_short_shadow_portfolio(rows, request)
        else:
            holdings, gross_exp, net_exp, ms, mss = _build_long_only_portfolio(rows, request)

        max_single = max(max_single, ms)
        max_sector = max(max_sector, mss)

        # Turnover vs prior window
        prior = prior_holdings.get(window_id)
        turnover = _compute_turnover(holdings, prior)

        # Compute return (P26-4: explicit cost field)
        cost_warnings: list[str] = []
        if holdings:
            if request.cost_basis == "explicit_cost_field":
                # P26-RR3: build snapshot->cost map once to avoid O(N²) repeated .index() calls
                snapshot_to_cost: dict[str, float] = {
                    str(r.get("snapshot_id", "")): float(r.get("estimated_cost_pct", 0.0))
                    for r in rows
                }
                gross_ret = sum(h.capped_weight * h.actual_target_value for h in holdings)
                net_ret = 0.0
                for h in holdings:
                    cost = snapshot_to_cost.get(h.snapshot_id, 0.0)
                    net_ret += h.capped_weight * (h.actual_target_value - cost)
                    if cost == 0.0:
                        cost_warnings.append("cost_field_missing")
            else:
                gross_ret = sum(h.capped_weight * h.actual_target_value for h in holdings)
                net_ret = gross_ret
        else:
            gross_ret = 0.0
            net_ret = 0.0

        window_returns.append(net_ret)
        all_safety_warnings.extend(cost_warnings)

        # Build violations list from POST-MITIGATION checks only
        violations: list[str] = []
        if turnover > request.turnover_limit + 1e-9:
            violations.append("turnover_limit_exceeded")
        if gross_exp > request.gross_exposure_limit + 1e-9:
            violations.append("gross_exposure_exceeded")
        if len(holdings) > request.max_positions:
            violations.append("max_positions_exceeded")
        if ms > request.max_single_name_weight + 1e-9:
            violations.append("single_name_cap_exceeded")
        if mss > request.max_sector_weight + 1e-9:
            violations.append("sector_cap_exceeded")

        all_constraint_violations.extend(violations)

        total_gross_return += gross_ret
        total_net_return += net_ret
        total_turnover += turnover

        status = "evaluated" if not violations else "constrained"

        window_results.append(PortfolioWindowResult(
            simulation_id=request.simulation_id,
            window_id=window_id,
            candidate_namespace=request.candidate_namespace,
            holding_count=len(holdings),
            gross_exposure=gross_exp,
            net_exposure=net_exp,
            turnover=turnover,
            portfolio_gross_return=gross_ret,
            portfolio_net_return=net_ret,
            max_single_name_weight=ms,
            max_sector_weight=mss,
            constraint_violations=tuple(sorted(set(violations))),
            holdings=tuple(holdings),
            status=status,
            warnings=tuple(cost_warnings),
        ))

        # Thread current holdings as prior for next window's turnover
        prior_holdings[window_id] = holdings

    n = len(window_results)
    avg_gross = total_gross_return / n if n else 0.0
    avg_net = total_net_return / n if n else 0.0
    avg_turnover = total_turnover / n if n else 0.0

    return (
        window_results, all_constraint_violations,
        total_net_return, avg_net, avg_turnover,
        max_single, max_sector, all_safety_warnings,
    )


def _build_risk_summary(
    window_results: list[PortfolioWindowResult],
    constraint_violations: list[str],
    cumulative_net: float,
    avg_net: float,
    avg_turnover: float,
    max_single: float,
    max_sector: float,
) -> PortfolioRiskSummary:
    n = len(window_results)
    window_returns = [wr.portfolio_net_return for wr in window_results]

    positive_windows = sum(1 for r in window_returns if r > 0)
    hit_rate = positive_windows / n if n else 0.0

    if n >= 2 and window_returns:
        mean = sum(window_returns) / n
        variance = sum((r - mean) ** 2 for r in window_returns) / n
        vol_proxy = variance ** 0.5
    else:
        vol_proxy = 0.0

    max_dd = _max_drawdown(window_returns)

    return PortfolioRiskSummary(
        total_windows=n,
        evaluated_windows=n,
        cumulative_net_return=cumulative_net,
        average_window_net_return=avg_net,
        volatility_proxy=vol_proxy,
        max_drawdown=max_dd,
        hit_rate=hit_rate,
        average_turnover=avg_turnover,
        max_observed_single_name_weight=max_single,
        max_observed_sector_weight=max_sector,
        constraint_violation_count=len(constraint_violations),
        warnings=(),
    )


# ─── Governance decision ─────────────────────────────────────────────────────

def _make_decision(
    request: PortfolioSimulationRequest,
    phase25_decision: dict[str, Any],
    phase25_report: dict[str, Any],
    constraint_violations: list[str],
    safety_warnings: list[str],
    safety_flags: dict[str, bool],
    cumulative_net_return: float,
    window_results: list[PortfolioWindowResult],
) -> Phase26GovernanceDecision:
    p25_decision = str(phase25_decision.get("decision", ""))

    if p25_decision != "ready_for_phase26_shadow_portfolio":
        return Phase26GovernanceDecision(
            schema_version="phase26_portfolio_governance.0",
            simulation_id=request.simulation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="blocked_by_phase25",
            decision_reasons=(f"Phase 25 decision is: {p25_decision}",),
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="resolve_phase25_block",
            created_at=_utc_now(),
        )

    # P26-7: Phase 25 invariants must hold
    # Block if phase25 erroneously set apply_to_production=True (unsafe)
    if safety_flags.get("phase25_apply_to_production", False):
        return Phase26GovernanceDecision(
            schema_version="phase26_portfolio_governance.0",
            simulation_id=request.simulation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="blocked_by_safety",
            decision_reasons=("phase25_apply_to_production is True",),
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="resolve_safety_violations",
            created_at=_utc_now(),
        )

    # Block if phase25 erroneously set non-empty production_config_changes (unsafe)
    if not safety_flags.get("phase25_production_config_changes_empty", True):
        return Phase26GovernanceDecision(
            schema_version="phase26_portfolio_governance.0",
            simulation_id=request.simulation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="blocked_by_safety",
            decision_reasons=("phase25_production_config_changes is non-empty",),
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="resolve_safety_violations",
            created_at=_utc_now(),
        )

    if phase25_report.get("safety_violations") or safety_warnings:
        all_safety = list(phase25_report.get("safety_violations", [])) + safety_warnings
        return Phase26GovernanceDecision(
            schema_version="phase26_portfolio_governance.0",
            simulation_id=request.simulation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="blocked_by_safety",
            decision_reasons=tuple(all_safety),
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="resolve_safety_violations",
            created_at=_utc_now(),
        )

    if constraint_violations:
        return Phase26GovernanceDecision(
            schema_version="phase26_portfolio_governance.0",
            simulation_id=request.simulation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="blocked_by_constraints",
            decision_reasons=tuple(sorted(set(constraint_violations))),
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="relax_constraints",
            created_at=_utc_now(),
        )

    if cumulative_net_return <= 0:
        return Phase26GovernanceDecision(
            schema_version="phase26_portfolio_governance.0",
            simulation_id=request.simulation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="rejected_portfolio_underperforms",
            decision_reasons=(f"cumulative_net_return={cumulative_net_return:.6f} <= 0",),
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="do_not_promote",
            created_at=_utc_now(),
        )

    hit_rate = (
        sum(1 for wr in window_results if wr.portfolio_net_return > 0) / len(window_results)
        if window_results else 0.0
    )
    avg_turnover = (
        sum(wr.turnover for wr in window_results) / len(window_results)
        if window_results else 0.0
    )

    if hit_rate < HIT_RATE_READY_THRESHOLD or avg_turnover > AVG_TURNOVER_WATCH_THRESHOLD:
        return Phase26GovernanceDecision(
            schema_version="phase26_portfolio_governance.0",
            simulation_id=request.simulation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="watch_more_shadow_windows",
            decision_reasons=(
                f"hit_rate={hit_rate:.2f} < {HIT_RATE_READY_THRESHOLD:.2f}",
                f"avg_turnover={avg_turnover:.2f} > {AVG_TURNOVER_WATCH_THRESHOLD:.2f}",
            ),
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="continue_shadow_observation",
            created_at=_utc_now(),
        )

    return Phase26GovernanceDecision(
        schema_version="phase26_portfolio_governance.0",
        simulation_id=request.simulation_id,
        training_run_id=request.training_run_id,
        experiment_id=request.experiment_id,
        candidate_namespace=request.candidate_namespace,
        decision="ready_for_manual_production_review",
        decision_reasons=(
            f"cumulative_net_return={cumulative_net_return:.6f} > 0, "
            f"hit_rate={hit_rate:.2f}, avg_turnover={avg_turnover:.2f}",
        ),
        production_config_changes={},
        apply_to_production=False,
        next_phase_recommendation="proceed_to_manual_production_review",
        created_at=_utc_now(),
    )


# ─── Public API ─────────────────────────────────────────────────────────────

def run_shadow_portfolio_simulation(
    phase25_result: Any,
    prediction_rows: list[dict[str, Any]],
    request: PortfolioSimulationRequest,
) -> ShadowPortfolioSimulationReport:
    phase25_decision = _get_phase25_decision(phase25_result)
    phase25_report = _get_phase25_report(phase25_result)

    # P26-7: Extract Phase 25 invariants as safety flags
    safety_flags = {
        "phase25_ready": phase25_decision.get("decision") == "ready_for_phase26_shadow_portfolio",
        "phase25_apply_to_production": bool(phase25_decision.get("apply_to_production", False)),
        "phase25_production_config_changes_empty": phase25_decision.get("production_config_changes", {}) == {},
    }

    # P26-9: Drop forbidden-field rows before simulation
    row_safety_warnings, clean_rows = _validate_prediction_rows(prediction_rows)

    # Group clean rows by window
    rows_by_window: dict[str, list[dict[str, Any]]] = {}
    for row in clean_rows:
        wid = str(row.get("window_id", ""))
        if wid not in rows_by_window:
            rows_by_window[wid] = []
        rows_by_window[wid].append(_as_dict(row))

    # P26-3: Thread prior holdings through windows for turnover
    # Process windows in order, threading prior_holdings from the previous window
    sorted_windows = sorted(rows_by_window.keys())
    window_results: list[PortfolioWindowResult] = []
    all_violations: list[str] = []
    all_safety_warnings: list[str] = []
    total_gross_return = 0.0
    total_net_return = 0.0
    total_turnover = 0.0
    max_single = 0.0
    max_sector = 0.0
    # prior_holdings tracks the previous window's holdings for turnover computation
    prior_holdings: list[PortfolioHolding] = []

    for window_id in sorted_windows:
        window_rows = {window_id: rows_by_window[window_id]}
        # P26-RR4 / P26-3 threading: prior_holdings holds window N-1's holdings.
        # We pass {window_id: prior_holdings} so that inside _build_window_results,
        # prior_holdings.get(window_id) returns exactly the prior window's holdings list.
        (
            wr_list, violations,
            net_ret, avg_net_win, turnover,
            ms, mss, safety_warns,
        ) = _build_window_results(window_rows, request, {window_id: prior_holdings} if prior_holdings else None)
        wr = wr_list[0]
        window_results.append(wr)
        all_violations.extend(violations)
        all_safety_warnings.extend(safety_warns)
        total_gross_return += wr.portfolio_gross_return
        total_net_return += wr.portfolio_net_return
        total_turnover += turnover
        max_single = max(max_single, ms)
        max_sector = max(max_sector, mss)
        # Thread current holdings as prior for next window
        prior_holdings = list(wr.holdings)

    n = len(window_results)
    cumulative_net = total_net_return
    avg_net = total_net_return / n if n else 0.0
    avg_turnover = total_turnover / n if n else 0.0

    # Combine safety warnings (P26-9 rows + P26-4 cost field)
    combined_safety_warnings = list(row_safety_warnings) + all_safety_warnings
    all_violations = sorted(set(all_violations))

    # Build risk summary
    risk_summary = _build_risk_summary(
        window_results, all_violations,
        cumulative_net, avg_net, avg_turnover,
        max_single, max_sector,
    )

    # Governance decision (P26-7: safety_flags passed)
    governance_decision = _make_decision(
        request, phase25_decision, phase25_report,
        all_violations, combined_safety_warnings, safety_flags,
        cumulative_net, window_results,
    )

    # Assemble report warnings
    report_warnings = list(combined_safety_warnings)
    if request.portfolio_mode == "long_short_rank_shadow":
        # P26-6: shadow_only_short_analysis is a warning, never a violation
        report_warnings.append("shadow_only_short_analysis")
    if governance_decision.decision == "ready_for_manual_production_review":
        report_warnings.append("advisory_only_not_production_approval")

    # Request config snapshot
    request_config = {
        "initial_capital": request.initial_capital,
        "max_positions": request.max_positions,
        "max_single_name_weight": request.max_single_name_weight,
        "max_sector_weight": request.max_sector_weight,
        "gross_exposure_limit": request.gross_exposure_limit,
        "turnover_limit": request.turnover_limit,
        "min_prediction_value": request.min_prediction_value,
        "rebalance_frequency": request.rebalance_frequency,
        "cost_basis": request.cost_basis,
    }

    report = ShadowPortfolioSimulationReport(
        schema_version="phase26_shadow_portfolio.0",
        simulation_id=request.simulation_id,
        training_run_id=request.training_run_id,
        experiment_id=request.experiment_id,
        candidate_namespace=request.candidate_namespace,
        portfolio_mode=request.portfolio_mode,
        request_config=MappingProxyType(request_config),
        window_results=tuple(window_results),
        risk_summary=risk_summary,
        governance_decision=governance_decision,
        safety_flags=MappingProxyType(safety_flags),
        warnings=tuple(report_warnings),
        created_at=_utc_now(),
    )

    return report