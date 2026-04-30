"""Phase 27 factor expansion pack: shadow-only macro, event-surprise, and sector-relation candidate factors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from types import MappingProxyType
import json
from typing import Any


class FactorExpansionError(ValueError):
    """Raised for unsafe Phase 27 expansion requests."""


# ─── Constants ───────────────────────────────────────────────────────────────

RELATION_BASELINE_VERSION = "phase27.0"

# Forbidden production-tainted fields (P27-5)
FORBIDDEN_FIELDS = frozenset({
    "live_trade_signal",
    "order_id",
    "broker_instruction",
    "production_config_update",
})


# ─── Request ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FactorExpansionRequest:
    candidate_namespace: str
    macro_regime_column: str = "value"
    macro_momentum_column: str = "value"
    event_surprise_column: str = "observed_direction"
    relation_strength_column: str = "sector_return_proxy"
    notes: str = ""

    def __post_init__(self) -> None:
        # P27-6: require non-empty suffix after "shadow_candidate_factor."
        prefix = "shadow_candidate_factor."
        if not (
            self.candidate_namespace.startswith(prefix)
            and len(self.candidate_namespace) > len(prefix)
        ):
            raise FactorExpansionError(
                "candidate_namespace must start with shadow_candidate_factor. "
                "and have a non-empty suffix"
            )


# ─── Diagnostics row ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CandidateFactorObservation:
    schema_version: str
    candidate_factor_name: str
    candidate_family: str       # "macro" | "event_surprise" | "sector_relation"
    trading_day: str
    ticker: str | None          # None for macro (no ticker dimension)
    score_value: float          # composite; see sub_scores for components
    point_in_time_confirmed: bool
    source_audit_complete: bool
    candidate_namespace: str    # P27-7: spec §4 required field
    sub_scores: tuple[tuple[str, float], ...]  # P27-1: (key, value) pairs per family
    metadata: tuple[tuple[str, str], ...]     # P27-RR1: string-valued audit fields
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_factor_name": self.candidate_factor_name,
            "candidate_family": self.candidate_family,
            "trading_day": self.trading_day,
            "ticker": self.ticker,
            "score_value": self.score_value,
            "point_in_time_confirmed": self.point_in_time_confirmed,
            "source_audit_complete": self.source_audit_complete,
            "candidate_namespace": self.candidate_namespace,
            "sub_scores": dict(self.sub_scores),
            "metadata": dict(self.metadata),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class CandidateFactorSet:
    family: str
    candidate_namespace: str
    observation_count: int
    blocked_count: int
    observations: tuple[CandidateFactorObservation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "candidate_namespace": self.candidate_namespace,
            "observation_count": self.observation_count,
            "blocked_count": self.blocked_count,
            "observations": [o.to_dict() for o in self.observations],
        }


# ─── Report ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FactorExpansionReport:
    schema_version: str
    candidate_namespace: str
    macro_candidates: CandidateFactorSet
    event_candidates: CandidateFactorSet
    sector_relation_candidates: CandidateFactorSet
    total_observations: int
    total_blocked: int
    blocked_by_reason: tuple[tuple[str, str, int], ...]   # (family, reason, count)
    warnings: tuple[str, ...]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_namespace": self.candidate_namespace,
            "macro_candidates": self.macro_candidates.to_dict(),
            "event_candidates": self.event_candidates.to_dict(),
            "sector_relation_candidates": self.sector_relation_candidates.to_dict(),
            "total_observations": self.total_observations,
            "total_blocked": self.total_blocked,
            "blocked_by_reason": [list(r) for r in self.blocked_by_reason],
            "warnings": list(self.warnings),
            "created_at": self.created_at,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Shared helpers ─────────────────────────────────────────────────────────────

def _extract_date_from_timestamp(ts: str) -> str:
    """Extract YYYY-MM-DD date portion from an ISO timestamp string."""
    if not ts:
        return ""
    return ts[:10]


def _check_pit_and_source(row: dict[str, Any], trading_day: str) -> tuple[bool, bool, str | None]:
    """
    Check point-in-time and source audit for a row.
    P27-3: also receives trading_day to pass to per-family timestamp checks.
    Returns (pit_confirmed, source_audit_complete, block_reason_or_None).
    """
    source_as_of = row.get("source_as_of_date", "")

    # P27-4: missing source_as_of_date is a PIT violation — block
    if not source_as_of:
        return False, False, "source_as_of_date_missing"

    if source_as_of > trading_day:
        return False, False, "source_as_of_after_trading_day"

    # Source audit is complete when source_as_of_date <= trading_day
    source_audit_complete = True
    pit_confirmed = True
    return pit_confirmed, source_audit_complete, None


def _check_macro_timestamp_pit(row: dict[str, Any], trading_day: str) -> str | None:
    """
    P27-3: macro release_timestamp must not be after trading_day.
    Returns block reason or None.
    """
    release_ts = row.get("release_timestamp", "")
    if not release_ts:
        return None  # already blocked elsewhere by missing_release_timestamp
    release_date = _extract_date_from_timestamp(release_ts)
    if release_date and release_date > trading_day:
        return "release_timestamp_after_trading_day"
    return None


def _check_event_timestamp_pit(row: dict[str, Any], trading_day: str) -> str | None:
    """
    P27-3: event event_timestamp must not be after trading_day.
    Returns block reason or None.
    """
    event_ts = row.get("event_timestamp", "")
    if not event_ts:
        return None  # already blocked elsewhere
    event_date = _extract_date_from_timestamp(event_ts)
    if event_date and event_date > trading_day:
        return "event_timestamp_after_trading_day"
    return None


def _check_forbidden_fields(row: dict[str, Any]) -> list[str]:
    """P27-5: return list of forbidden field names present in row."""
    return [f for f in FORBIDDEN_FIELDS if f in row]


def _emit_observation(
    schema_version: str,
    candidate_namespace: str,
    candidate_factor_name: str,
    candidate_family: str,
    trading_day: str,
    ticker: str | None,
    score_value: float,
    point_in_time_confirmed: bool,
    source_audit_complete: bool,
    sub_scores: tuple[tuple[str, float], ...],
    metadata: tuple[tuple[str, str], ...],
    warnings: tuple[str, ...],
) -> CandidateFactorObservation:
    """P27-8: shared observation factory used by all three builders."""
    return CandidateFactorObservation(
        schema_version=schema_version,
        candidate_factor_name=candidate_factor_name,
        candidate_family=candidate_family,
        trading_day=trading_day,
        ticker=ticker,
        score_value=score_value,
        point_in_time_confirmed=point_in_time_confirmed,
        source_audit_complete=source_audit_complete,
        candidate_namespace=candidate_namespace,
        sub_scores=sub_scores,
        metadata=metadata,
        warnings=warnings,
    )


# ─── Macro candidate builder ─────────────────────────────────────────────────

def _build_macro_candidates(
    macro_inputs: list[dict[str, Any]],
    request: FactorExpansionRequest,
) -> tuple[CandidateFactorSet, list[tuple[str, str, int]]]:
    """
    Build macro candidate factor observations.

    Block conditions:
    - missing trading_day
    - missing release_timestamp
    - release_timestamp > trading_day  (P27-3)
    - source_as_of_date missing       (P27-4)
    - source_as_of_date > trading_day
    - forbidden production fields present  (P27-5)

    Scoring (P27-2 fix):
    - macro_regime_score: z-score of value; normalized via min-max over z-scores
    - macro_momentum_score: pct_change from prior observation for same series
    - composite = (normalized_regime + normalized_momentum) / 2
    """
    observations: list[CandidateFactorObservation] = []
    blocked_count = 0
    blocked_reasons: dict[str, int] = {}
    schema = "phase27_factor_expansion.0"

    if not macro_inputs:
        return CandidateFactorSet(
            family="macro",
            candidate_namespace=request.candidate_namespace,
            observation_count=0,
            blocked_count=0,
            observations=(),
        ), []

    # Group by macro_series_id
    series_rows: dict[str, list[dict[str, Any]]] = {}
    for row in macro_inputs:
        series_id = str(row.get("macro_series_id", ""))
        if series_id not in series_rows:
            series_rows[series_id] = []
        series_rows[series_id].append(row)

    # Pre-compute z-score statistics per series
    series_stats: dict[str, tuple[float, float, list[float]]] = {}
    for series_id, rows in series_rows.items():
        vals = [float(r.get(request.macro_regime_column, 0)) for r in rows]
        mean_v = sum(vals) / len(vals) if vals else 0.0
        if len(vals) > 1:
            variance = sum((v - mean_v) ** 2 for v in vals) / len(vals)
            std_v = variance ** 0.5
        else:
            std_v = 0.0
        series_stats[series_id] = (mean_v, std_v, vals)

    for series_id, rows in series_rows.items():
        mean_v, std_v, vals = series_stats[series_id]
        sorted_rows = sorted(rows, key=lambda r: str(r.get("trading_day", "")))

        # Compute z-scores for all rows in this series
        z_scores: list[float] = []
        for val in vals:
            if std_v > 0:
                z_scores.append((val - mean_v) / std_v)
            else:
                z_scores.append(0.0)

        # P27-2 fix: normalize z-scores via their own min-max
        z_min = min(z_scores) if z_scores else 0.0
        z_range = max(z_scores) - z_min if len(z_scores) > 1 else 0.0

        for i, row in enumerate(sorted_rows):
            trading_day = str(row.get("trading_day", ""))
            warnings: list[str] = []

            # P27-5: forbidden fields check; P27-RR3: count blocked rows, not fields
            forbidden = _check_forbidden_fields(row)
            if forbidden:
                blocked_count += 1
                for f in forbidden:
                    blocked_reasons[f"forbidden_field_{f}"] = (
                        blocked_reasons.get(f"forbidden_field_{f}", 0) + 1
                    )
                continue

            # Block: missing trading_day
            if not trading_day:
                blocked_count += 1
                blocked_reasons["missing_trading_day"] = (
                    blocked_reasons.get("missing_trading_day", 0) + 1
                )
                continue

            # Block: missing release_timestamp
            release_ts = row.get("release_timestamp")
            if not release_ts:
                blocked_count += 1
                blocked_reasons["missing_release_timestamp"] = (
                    blocked_reasons.get("missing_release_timestamp", 0) + 1
                )
                continue

            # P27-3: release_timestamp > trading_day
            ts_block = _check_macro_timestamp_pit(row, trading_day)
            if ts_block:
                blocked_count += 1
                blocked_reasons[ts_block] = blocked_reasons.get(ts_block, 0) + 1
                continue

            # PIT / source audit
            pit_confirmed, source_audit_complete, pit_block = _check_pit_and_source(row, trading_day)
            if pit_block:
                blocked_count += 1
                blocked_reasons[pit_block] = blocked_reasons.get(pit_block, 0) + 1
                continue

            val = float(row.get(request.macro_regime_column, 0))

            # Regime score: z-score
            if std_v > 0:
                regime_score = (val - mean_v) / std_v
            else:
                regime_score = 0.0

            # P27-2 fix: normalize regime via z-score min-max
            if z_range > 1e-9:
                normalized_regime = (regime_score - z_min) / z_range
            else:
                normalized_regime = 0.0

            # Momentum score: pct_change from prior observation in same series
            if i == 0:
                momentum_score = 0.0
            else:
                prev_val = float(sorted_rows[i - 1].get(request.macro_momentum_column, 0))
                if prev_val != 0:
                    momentum_score = (val - prev_val) / abs(prev_val)
                else:
                    momentum_score = 0.0

            normalized_momentum = max(-1.0, min(1.0, momentum_score))
            composite = (normalized_regime + normalized_momentum) / 2.0

            sub_scores = (
                ("macro_regime_score", regime_score),
                ("macro_momentum_score", momentum_score),
            )

            observations.append(_emit_observation(
                schema_version=schema,
                candidate_namespace=request.candidate_namespace,
                candidate_factor_name=f"{request.candidate_namespace}.macro_regime",
                candidate_family="macro",
                trading_day=trading_day,
                ticker=None,
                score_value=composite,
                point_in_time_confirmed=pit_confirmed,
                source_audit_complete=source_audit_complete,
                sub_scores=sub_scores,
                metadata=(),  # macro has no string metadata fields
                warnings=tuple(warnings),
            ))

    return CandidateFactorSet(
        family="macro",
        candidate_namespace=request.candidate_namespace,
        observation_count=len(observations),
        blocked_count=blocked_count,
        observations=tuple(observations),
    ), [("macro", k, v) for k, v in blocked_reasons.items()]


# ─── Event surprise builder ─────────────────────────────────────────────────

def _build_event_candidates(
    event_inputs: list[dict[str, Any]],
    request: FactorExpansionRequest,
) -> tuple[CandidateFactorSet, list[tuple[str, str, int]]]:
    """
    Build event-surprise candidate factor observations.

    Block conditions:
    - missing event_timestamp
    - event_timestamp > trading_day     (P27-3)
    - missing source_refs
    - missing taxonomy_version
    - source_as_of_date missing          (P27-4)
    - source_as_of_date > trading_day
    - forbidden production fields present  (P27-5)
    """
    observations: list[CandidateFactorObservation] = []
    blocked_count = 0
    blocked_reasons: dict[str, int] = {}
    schema = "phase27_factor_expansion.0"

    for row in event_inputs:
        trading_day = str(row.get("trading_day", ""))
        warnings: list[str] = []

        # P27-5: forbidden fields check; P27-RR3: count blocked rows, not fields
        forbidden = _check_forbidden_fields(row)
        if forbidden:
            blocked_count += 1
            for f in forbidden:
                blocked_reasons[f"forbidden_field_{f}"] = (
                    blocked_reasons.get(f"forbidden_field_{f}", 0) + 1
                )
            continue

        # Block: missing event_timestamp
        if not row.get("event_timestamp"):
            blocked_count += 1
            blocked_reasons["missing_event_timestamp"] = (
                blocked_reasons.get("missing_event_timestamp", 0) + 1
            )
            continue

        # P27-3: event_timestamp > trading_day
        if not trading_day:
            blocked_count += 1
            blocked_reasons["missing_trading_day"] = (
                blocked_reasons.get("missing_trading_day", 0) + 1
            )
            continue

        ts_block = _check_event_timestamp_pit(row, trading_day)
        if ts_block:
            blocked_count += 1
            blocked_reasons[ts_block] = blocked_reasons.get(ts_block, 0) + 1
            continue

        # Block: missing source_refs
        if not row.get("source_refs"):
            blocked_count += 1
            blocked_reasons["missing_source_refs"] = (
                blocked_reasons.get("missing_source_refs", 0) + 1
            )
            continue

        # Block: missing taxonomy_version
        if not row.get("taxonomy_version"):
            blocked_count += 1
            blocked_reasons["missing_taxonomy_version"] = (
                blocked_reasons.get("missing_taxonomy_version", 0) + 1
            )
            continue

        # PIT / source audit
        pit_confirmed, source_audit_complete, pit_block = _check_pit_and_source(row, trading_day)
        if pit_block:
            blocked_count += 1
            blocked_reasons[pit_block] = blocked_reasons.get(pit_block, 0) + 1
            continue

        observed = str(row.get("observed_direction", ""))
        expected = str(row.get("expected_direction", ""))
        confidence = float(row.get("confidence_score", 0.5))
        taxonomy_label = str(row.get("taxonomy_label", ""))
        taxonomy_version = str(row.get("taxonomy_version", ""))

        # event_surprise_score
        surprise_score = 1.0 if observed != expected else 0.0

        # event_sentiment_score
        obs_upper = observed.upper()
        if obs_upper in ("POSITIVE", "UP", "BUY", "HIGH", "POS", "+"):
            sentiment_score = 1.0
        elif obs_upper in ("NEGATIVE", "DOWN", "SELL", "LOW", "NEG", "-"):
            sentiment_score = -1.0
        else:
            sentiment_score = 0.0

        # event_novelty_score = confidence_score
        novelty_score = confidence

        # label_consistency_score
        if taxonomy_label and obs_upper == taxonomy_label.upper():
            consistency_score = 1.0
        elif taxonomy_label:
            consistency_score = 0.5
        else:
            consistency_score = 0.5

        composite = (
            0.4 * surprise_score
            + 0.3 * (sentiment_score + 1) / 2
            + 0.2 * novelty_score
            + 0.1 * consistency_score
        )

        ticker = str(row.get("ticker", "")) or None

        # P27-1: store all sub-scores; P27-RR1: taxonomy_version goes to metadata (string)
        sub_scores = (
            ("event_surprise_score", surprise_score),
            ("event_sentiment_score", sentiment_score),
            ("event_novelty_score", novelty_score),
            ("label_consistency_score", consistency_score),
        )
        metadata = (("taxonomy_version", taxonomy_version),)

        observations.append(_emit_observation(
            schema_version=schema,
            candidate_namespace=request.candidate_namespace,
            candidate_factor_name=f"{request.candidate_namespace}.event_surprise",
            candidate_family="event_surprise",
            trading_day=trading_day,
            ticker=ticker,
            score_value=composite,
            point_in_time_confirmed=pit_confirmed,
            source_audit_complete=source_audit_complete,
            sub_scores=sub_scores,
            metadata=metadata,
            warnings=tuple(warnings),
        ))

    return CandidateFactorSet(
        family="event_surprise",
        candidate_namespace=request.candidate_namespace,
        observation_count=len(observations),
        blocked_count=blocked_count,
        observations=tuple(observations),
    ), [("event_surprise", k, v) for k, v in blocked_reasons.items()]


# ─── Sector relation builder ─────────────────────────────────────────────────

def _build_sector_relation_candidates(
    relation_inputs: list[dict[str, Any]],
    request: FactorExpansionRequest,
) -> tuple[CandidateFactorSet, list[tuple[str, str, int]]]:
    """
    Build sector-relation candidate factor observations.

    Block conditions:
    - missing ticker
    - missing sector
    - missing peer_group_id
    - missing trading_day
    - source_as_of_date missing       (P27-4)
    - source_as_of_date > trading_day
    - forbidden production fields present (P27-5)
    """
    observations: list[CandidateFactorObservation] = []
    blocked_count = 0
    blocked_reasons: dict[str, int] = {}
    schema = "phase27_factor_expansion.0"
    EPS = 1e-9

    for row in relation_inputs:
        trading_day = str(row.get("trading_day", ""))
        ticker = str(row.get("ticker", ""))
        warnings: list[str] = []

        # P27-5: forbidden fields check; P27-RR3: count blocked rows, not fields
        forbidden = _check_forbidden_fields(row)
        if forbidden:
            blocked_count += 1
            for f in forbidden:
                blocked_reasons[f"forbidden_field_{f}"] = (
                    blocked_reasons.get(f"forbidden_field_{f}", 0) + 1
                )
            continue

        # Block: missing ticker
        if not ticker:
            blocked_count += 1
            blocked_reasons["missing_ticker"] = (
                blocked_reasons.get("missing_ticker", 0) + 1
            )
            continue

        # Block: missing sector
        if not row.get("sector"):
            blocked_count += 1
            blocked_reasons["missing_sector"] = (
                blocked_reasons.get("missing_sector", 0) + 1
            )
            continue

        # Block: missing peer_group_id
        if not row.get("peer_group_id"):
            blocked_count += 1
            blocked_reasons["missing_peer_group_id"] = (
                blocked_reasons.get("missing_peer_group_id", 0) + 1
            )
            continue

        # Block: missing trading_day
        if not trading_day:
            blocked_count += 1
            blocked_reasons["missing_trading_day"] = (
                blocked_reasons.get("missing_trading_day", 0) + 1
            )
            continue

        # PIT / source audit
        pit_confirmed, source_audit_complete, pit_block = _check_pit_and_source(row, trading_day)
        if pit_block:
            blocked_count += 1
            blocked_reasons[pit_block] = blocked_reasons.get(pit_block, 0) + 1
            continue

        sector_ret = float(row.get("sector_return_proxy", 0))
        peer_ret = float(row.get("peer_return_proxy", 0))

        # sector_relative_strength_score
        denom = abs(peer_ret) + EPS
        sector_rel_strength = (sector_ret - peer_ret) / denom

        # peer_relation_score: sign agreement
        if sector_ret * peer_ret > 0:
            peer_relation = 1.0
        elif sector_ret * peer_ret < 0:
            peer_relation = -1.0
        else:
            peer_relation = 0.0

        # sector_dispersion_score
        sum_abs = abs(sector_ret) + abs(peer_ret) + EPS
        sector_dispersion = abs(sector_ret - peer_ret) / sum_abs

        composite = (
            0.5 * ((sector_rel_strength + 1) / 2)
            + 0.3 * ((peer_relation + 1) / 2)
            + 0.2 * (1 - sector_dispersion)
        )

        # P27-1: store all sub-scores; P27-RR2: relation_baseline_version goes to metadata (string)
        sub_scores = (
            ("sector_relative_strength_score", sector_rel_strength),
            ("peer_relation_score", peer_relation),
            ("sector_dispersion_score", sector_dispersion),
        )
        metadata = (("relation_baseline_version", RELATION_BASELINE_VERSION),)

        observations.append(_emit_observation(
            schema_version=schema,
            candidate_namespace=request.candidate_namespace,
            candidate_factor_name=f"{request.candidate_namespace}.sector_relation",
            candidate_family="sector_relation",
            trading_day=trading_day,
            ticker=ticker,
            score_value=composite,
            point_in_time_confirmed=pit_confirmed,
            source_audit_complete=source_audit_complete,
            sub_scores=sub_scores,
            metadata=metadata,
            warnings=tuple(warnings),
        ))

    return CandidateFactorSet(
        family="sector_relation",
        candidate_namespace=request.candidate_namespace,
        observation_count=len(observations),
        blocked_count=blocked_count,
        observations=tuple(observations),
    ), [("sector_relation", k, v) for k, v in blocked_reasons.items()]


# ─── Public API ─────────────────────────────────────────────────────────────

def build_factor_expansion_candidates(
    macro_inputs: list[dict[str, Any]],
    event_inputs: list[dict[str, Any]],
    relation_inputs: list[dict[str, Any]],
    request: FactorExpansionRequest,
) -> FactorExpansionReport:
    """
    Build shadow-only candidate factor observations from macro, event, and sector-relation inputs.

    All outputs are diagnostics-ready rows intended for P22-style IC/ICIR diagnostics and
    P23-style shadow observation. No canonical FactorSnapshot writes, no production config
    changes, no live trade signals.
    """
    macro_set, macro_blocked = _build_macro_candidates(macro_inputs, request)
    event_set, event_blocked = _build_event_candidates(event_inputs, request)
    relation_set, relation_blocked = _build_sector_relation_candidates(relation_inputs, request)

    total_obs = (
        macro_set.observation_count
        + event_set.observation_count
        + relation_set.observation_count
    )
    total_blocked = (
        macro_set.blocked_count
        + event_set.blocked_count
        + relation_set.blocked_count
    )

    blocked_by_reason = tuple(
        (family, reason, count)
        for family, reason, count in macro_blocked + event_blocked + relation_blocked
    )

    report_warnings: list[str] = []
    if not macro_inputs and not event_inputs and not relation_inputs:
        report_warnings.append("all_inputs_empty")

    return FactorExpansionReport(
        schema_version="phase27_factor_expansion.0",
        candidate_namespace=request.candidate_namespace,
        macro_candidates=macro_set,
        event_candidates=event_set,
        sector_relation_candidates=relation_set,
        total_observations=total_obs,
        total_blocked=total_blocked,
        blocked_by_reason=blocked_by_reason,
        warnings=tuple(report_warnings),
        created_at=_utc_now(),
    )