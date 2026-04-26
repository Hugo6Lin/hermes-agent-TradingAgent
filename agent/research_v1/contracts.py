"""
Canonical object model for Hermes model-agnostic research core.

Defines the stable contracts that all research roles (orchestrator, subagents,
final judge) operate through. These objects are the system's primary language.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    """Supported research task types."""
    SINGLE_TICKER_RESEARCH = "single_ticker_research"
    MULTI_TICKER_COMPARE = "multi_ticker_compare"
    OPTION_IDEA = "option_idea"
    PORTFOLIO_REVIEW = "portfolio_review"
    POSITION_MANAGEMENT = "position_management"


class OutputMode(str, Enum):
    """Supported output modes."""
    SIGNAL_ONLY = "signal_only"
    REPORT_ONLY = "report_only"
    SIGNAL_AND_REPORT = "signal_and_report"
    SIGNAL_REPORT_PDF_VIEWER = "signal_report_pdf_viewer"


class ResearchMode(str, Enum):
    """Research depth modes."""
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"


class AgentRole(str, Enum):
    """Subagent role types."""
    FUNDAMENTALS = "fundamentals"
    TECHNICAL = "technical"
    NEWS = "news"
    SENTIMENT = "sentiment"
    INDUSTRY = "industry"
    OPTIONS = "options"
    RISK = "risk"
    VALUATION = "valuation"


class ClaimType(str, Enum):
    """Types of evidence claims."""
    FACTUAL = "factual"
    DIRECTIONAL = "directional"
    QUANTITATIVE = "quantitative"
    QUALITATIVE = "qualitative"
    CONDITIONAL = "conditional"


class Direction(str, Enum):
    """Direction of a claim or signal."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class TaskStatus(str, Enum):
    """Status of a research task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvidenceImportance(str, Enum):
    """Importance level of an evidence item."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


@dataclass
class ResearchTask:
    """
    Canonical system entry object.

    Represents a normalized research request from boss, API, or CLI.
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_text: str = ""
    task_type: TaskType = TaskType.SINGLE_TICKER_RESEARCH
    tickers: list[str] = field(default_factory=list)
    markets: list[str] = field(default_factory=list)
    research_mode: ResearchMode = ResearchMode.STANDARD
    time_horizon: str = ""  # e.g., "1week", "3months", "1year"
    output_mode: OutputMode = OutputMode.SIGNAL_AND_REPORT
    constraints: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: TaskStatus = TaskStatus.PENDING

    def __post_init__(self):
        if not self.request_text:
            raise ValueError("request_text is required")
        if not self.tickers:
            raise ValueError("at least one ticker is required")


@dataclass
class SubagentTask:
    """
    One orchestrator-issued work unit.

    Scoped to one role and one objective.
    """
    subtask_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    agent_role: AgentRole = AgentRole.FUNDAMENTALS
    ticker: str = ""
    objective: str = ""
    required_context: dict[str, Any] = field(default_factory=dict)
    expected_schema: dict[str, Any] = field(default_factory=dict)
    priority: int = 1  # 1 = highest
    deadline_hint: str = ""  # e.g., "5min", "10min"
    status: TaskStatus = TaskStatus.PENDING

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.ticker:
            raise ValueError("ticker is required")
        if not self.objective:
            raise ValueError("objective is required")


@dataclass
class EvidenceItem:
    """
    Canonical subagent output atom.

    Primary system truth unit. Subagents produce these from their research.
    """
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    subtask_id: str = ""
    ticker: str = ""
    agent_role: AgentRole = AgentRole.FUNDAMENTALS
    claim_type: ClaimType = ClaimType.FACTUAL
    claim: str = ""  # Human-readable claim summary
    value: Any = None  # Structured value (number, string, dict)
    confidence: float = 0.0  # 0.0 to 1.0
    direction: Direction = Direction.NEUTRAL
    importance: EvidenceImportance = EvidenceImportance.MEDIUM
    source_refs: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)  # Preserved original output
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.subtask_id:
            raise ValueError("subtask_id is required")
        if not self.ticker:
            raise ValueError("ticker is required")
        if not self.claim:
            raise ValueError("claim is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass
class EvidenceBundle:
    """
    Normalized collection of evidence prepared by orchestrator for final judging.
    """
    task_id: str = ""
    ticker: str = ""
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    coverage_summary: dict[str, int] = field(default_factory=dict)  # role -> count
    missing_steps: list[str] = field(default_factory=list)
    conflict_flags: list[str] = field(default_factory=list)
    context_snapshot: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.ticker:
            raise ValueError("ticker is required")


@dataclass
class JudgeInputPacket:
    """
    Exact bounded input contract for final judge.

    Final judge should consume only this bounded packet, not arbitrary upstream state.
    """
    task_id: str = ""
    ticker: str = ""
    task_summary: str = ""
    evidence_bundle: EvidenceBundle | None = None
    required_outputs: list[str] = field(default_factory=list)  # e.g., ["signal", "report"]
    conflict_flags: list[str] = field(default_factory=list)
    missing_steps: list[str] = field(default_factory=list)
    orchestrator_notes: str = ""

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.ticker:
            raise ValueError("ticker is required")
        if not self.task_summary:
            raise ValueError("task_summary is required")
        if self.evidence_bundle is None:
            raise ValueError("evidence_bundle is required")


@dataclass
class CanonicalSignal:
    """
    Unified final signal contract for all downstream product surfaces.

    Produced by final judge, consumed by viewer, trade planning, monitoring.
    """
    ticker: str = ""
    rating: str = ""  # e.g., "BUY", "SELL", "HOLD"
    confidence: float = 0.0  # 0.0 to 1.0
    priority_score: float = 0.0  # 0.0 to 100.0
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    holding_horizon: str = ""  # e.g., "1week", "3months"
    signal_valid_until: datetime | None = None
    risk_flags: list[str] = field(default_factory=list)
    decision_reason: str = ""  # Summary of why this decision

    def __post_init__(self):
        if not self.ticker:
            raise ValueError("ticker is required")
        if not self.rating:
            raise ValueError("rating is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not 0.0 <= self.priority_score <= 100.0:
            raise ValueError("priority_score must be between 0.0 and 100.0")


@dataclass
class TradePlan:
    """
    Trade plan entry within a canonical report.
    """
    action: str = ""  # e.g., "BUY", "SELL", "HOLD"
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    size_hint: str = ""  # e.g., "5% of portfolio"
    holding_period: str = ""


@dataclass
class CanonicalReport:
    """
    Unified final boss-facing report contract.

    Produced by final judge, rendered by PDF and viewer.
    """
    title: str = ""
    executive_summary: str = ""
    bottom_line: str = ""  # One-sentence investment conclusion
    why_now: str = ""  # Why this decision at this time
    bull_case: str = ""  # Bullish argument summary
    bear_case: str = ""  # Bearish argument summary
    trade_plan: TradePlan | None = None
    risk_watch: list[str] = field(default_factory=list)  # Key risks to monitor
    key_evidence: list[str] = field(default_factory=list)  # IDs of key EvidenceItems used
    appendix: dict[str, Any] = field(default_factory=dict)  # Additional supporting data
    # Phase 14-17: Decision objects (serialized as dicts for DB persistence)
    decision_card: dict | None = None  # PositionDecisionCard as dict
    instrument_rec: dict | None = None  # InstrumentRecommendation as dict
    options_structure: dict | None = None  # OptionsStructure as dict
    early_exit: dict | None = None  # EarlyExitPlan as dict

    def __post_init__(self):
        if not self.title:
            raise ValueError("title is required")
        if not self.bottom_line:
            raise ValueError("bottom_line is required")
        if not self.executive_summary:
            raise ValueError("executive_summary is required")
        if not self.why_now:
            raise ValueError("why_now is required")
        if not self.bull_case:
            raise ValueError("bull_case is required")
        if not self.bear_case:
            raise ValueError("bear_case is required")


class ReviewVerdict(str, Enum):
    """Reviewer quality verdict."""
    PASS = "pass"                        # Signal/report is sound
    NEEDS_REVISION = "needs_revision"   # Flagged issues, human review recommended
    REJECTED = "rejected"               # Signal/report should not be acted upon


@dataclass
class ReviewInputPacket:
    """
    Exact bounded input contract for the reviewer extension point.

    The reviewer consumes only this bounded packet — it does NOT read
    arbitrary upstream runtime state. The packet contains the same
    information available to the orchestrator at final-judgment time.

    The reviewer is an OPTIONAL extension. The pipeline functions correctly
    without it (final judge remains the sole decision authority).
    """
    task_id: str = ""
    ticker: str = ""
    # The original request text
    task_summary: str = ""
    # The canonical signal from the final judge
    signal: "CanonicalSignal | None" = None
    # The canonical report from the final judge
    report: "CanonicalReport | None" = None
    # Evidence bundle from orchestrator (for cross-reference)
    evidence_bundle: "EvidenceBundle | None" = None
    # Flags from orchestrator's conflict/missing-step detection
    orchestrator_flags: list[str] = field(default_factory=list)
    # Whether a reviewer was configured/requested
    reviewer_configured: bool = False

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.ticker:
            raise ValueError("ticker is required")
        if not self.task_summary:
            raise ValueError("task_summary is required")
        if self.evidence_bundle is None:
            raise ValueError("evidence_bundle is required")
        if self.signal is None and self.report is None:
            raise ValueError("at least one of signal or report is required")


@dataclass
class CanonicalReview:
    """
    Canonical review output from the reviewer extension point.

    Produced by the reviewer, consumed by the product surface (viewer, PDF).
    The reviewer NEVER overrides the final judge — it only annotates quality
    and recommends human review when warranted.

    The verdict field is the primary output:
    - PASS: signal/report is sound; product surface may proceed
    - NEEDS_REVISION: flagged issues present; human review recommended
    - REJECTED: critical issues; signal/report should not be acted upon
    """
    review_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    ticker: str = ""
    verdict: ReviewVerdict = ReviewVerdict.PASS
    quality_score: float = 1.0  # 0.0 to 1.0
    flags: list[str] = field(default_factory=list)  # e.g. "low_confidence", "conflict_unresolved"
    annotations: list[str] = field(default_factory=list)  # Human-readable notes
    recommended_action: str = ""  # e.g. "proceed", "escalate", "block"
    review_reason: str = ""  # Brief explanation of the verdict

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.ticker:
            raise ValueError("ticker is required")
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("quality_score must be between 0.0 and 1.0")


# Convenience factory functions

# Allowed bullish-only actions for Phase 14 instrument selection
VALID_BULLISH_ACTIONS = frozenset([
    "Buy Stock",
    "Buy Call",
    "Bull Call Spread",
    "Sell Cash-Secured Put",
    "Covered Call",
    "Watchlist",
    "No Trade",
])


@dataclass
class UnderlyingThesis:
    """
    Phase 14: Stock-thesis evaluation — determines whether a stock is worth owning.

    This is the first step in the bullish decision flow: evaluate the underlying
    before any derivative instrument selection.

    Classifications:
        - Investable: strong quality + credible upside + reasonable path
        - Watchlist: positive thesis but weak timing / weak current upside
        - No Trade: low quality or broken economics
    """
    task_id: str
    ticker: str
    quality_score: float          # 0.0–1.0: business quality, earnings quality, balance sheet
    valuation_score: float        # 0.0–1.0: implied upside vs current price
    catalyst_score: float          # 0.0–1.0: identified drivers, visibility and timing confidence
    thesis_risk_score: float     # 0.0–1.0: what can break the thesis
    classification: str           # "Investable" | "Watchlist" | "No Trade"
    summary: str                  # Human-readable one-line thesis summary

    def __post_init__(self):
        if self.classification not in {"Investable", "Watchlist", "No Trade"}:
            raise ValueError(
                f"classification must be Investable, Watchlist, or No Trade; got {self.classification!r}"
            )
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("quality_score must be between 0.0 and 1.0")
        if not 0.0 <= self.valuation_score <= 1.0:
            raise ValueError("valuation_score must be between 0.0 and 1.0")
        if not 0.0 <= self.catalyst_score <= 1.0:
            raise ValueError("catalyst_score must be between 0.0 and 1.0")


@dataclass
class InstrumentRecommendation:
    """
    Phase 14: Instrument selection — selects the best bullish expression of a stock thesis.

    After UnderlyingThesis classifies a stock as Investable, this recommends the
    best way to express that bullish view (stock vs. call vs. spread vs. sell put).

    The primary_action must be one of the VALID_BULLISH_ACTIONS.
    """
    task_id: str
    ticker: str
    primary_action: str           # One of VALID_BULLISH_ACTIONS
    ranked_alternatives: list[str]  # Other valid instruments, in preference order
    reason: str                   # Why this instrument was chosen

    def __post_init__(self):
        if not self.primary_action:
            raise ValueError("primary_action is required")
        if self.primary_action not in VALID_BULLISH_ACTIONS:
            raise ValueError(
                f"primary_action must be one of {sorted(VALID_BULLISH_ACTIONS)}; "
                f"got {self.primary_action!r}"
            )


@dataclass
class PositionDecisionCard:
    """
    Phase 14: Boss-facing decision artifact — the primary output of the bullish
    decision flow.

    Combines the underlying thesis evaluation and instrument selection into a
    single coherent decision card that can be rendered in the viewer and PDF.
    """
    task_id: str
    ticker: str
    primary_action: str            # Must be a VALID_BULLISH_ACTIONS
    conviction: str               # "High" | "Medium" | "Low"
    thesis_summary: str           # Why the stock is worth owning
    why_now: str                  # Why this decision at this time
    alternatives: list[str]        # Why rejected alternatives were rejected

    def __post_init__(self):
        if not self.primary_action:
            raise ValueError("primary_action is required")
        if self.primary_action not in VALID_BULLISH_ACTIONS:
            raise ValueError(
                f"primary_action must be one of {sorted(VALID_BULLISH_ACTIONS)}; "
                f"got {self.primary_action!r}"
            )
        if self.conviction not in {"High", "Medium", "Low"}:
            raise ValueError(
                f"conviction must be High, Medium, or Low; got {self.conviction!r}"
            )


# ---------------------------------------------------------------------------
# Phase 15: Options Structure
# ---------------------------------------------------------------------------

class ExitTrigger(str, Enum):
    """Trigger classes for early exit decisions."""
    TARGET_REACHED = "target_reached"
    RETURN_THRESHOLD = "return_threshold"
    EFFICIENCY_BREAKDOWN = "efficiency_breakdown"
    THESIS_BREAK = "thesis_break"
    STRUCTURE_BREAK = "structure_break"
    PRICE_RISK_DISCIPLINE = "price_risk_discipline"


@dataclass
class ExitZone:
    """
    One zone in the exit plan (first trim / main profit / full exit).
    """
    zone_name: str          # "first_trim" | "main_profit" | "full_exit"
    action: str            # "Trim" | "Take Profit" | "Consider Exit" | "No Action"
    target_return_pct: float | None  # e.g. 0.30 for 30%
    trigger_condition: str  # Human-readable trigger description


@dataclass
class EarlyExitPlan:
    """
    Phase 15: Early exit planning for an options position.

    Three-zone model from spec:
    - first_trim_zone: first opportunity to lock in partial gains
    - main_profit_zone: primary profit-taking window
    - full_exit_zone: full position exit
    """
    ticker: str
    primary_exit_trigger: ExitTrigger
    severity: str          # "Critical" | "High" | "Medium" | "Low" | "None"
    primary_reason: str
    first_trim: ExitZone
    main_profit: ExitZone
    full_exit: ExitZone

    def __post_init__(self):
        if self.severity not in {"Critical", "High", "Medium", "Low", "None"}:
            raise ValueError(f"severity must be one of Critical/High/Medium/Low/None; got {self.severity!r}")


@dataclass
class OptionContract:
    """
    Phase 15: A single option contract specification.
    """
    expiry_months: int
    strike: float
    option_type: str   # "call" or "put"
    delta_estimate: float | None = None
    position_type: str = "long"  # "long" or "short"
    # Multi-leg support: short leg for spreads, CSP assignment, covered call
    short_contract: "OptionContract | None" = None  # the paired short leg (spread/CSP/covered)
    net_debit: float | None = None   # net cost to open (for spreads)
    net_credit: float | None = None  # net premium received (for spreads/CSP/covered call)
    assignment_strike: float | None = None  # CSP/covered call assignment price
    covered_by_shares: bool = False  # True for covered call (already holding shares)

    def __post_init__(self):
        if self.option_type not in {"call", "put"}:
            raise ValueError(f"option_type must be 'call' or 'put'; got {self.option_type!r}")
        if self.short_contract is not None:
            if not isinstance(self.short_contract, OptionContract):
                raise ValueError("short_contract must be an OptionContract instance")


@dataclass
class OptionsStructure:
    """
    Phase 15: Structured options details for the selected instrument.

    Produced by OptionsDecisionEngine after InstrumentSelectionEngine has
    chosen an options-based expression (Buy Call, Bull Call Spread, CSP).
    For spreads/CSP/covered call, primary_contract.short_contract holds the paired leg.
    """
    ticker: str
    instrument_action: str          # e.g. "Buy Call", "Bull Call Spread"
    primary_contract: OptionContract  # The recommended contract; short_contract holds paired leg for spreads
    conservative_alternative: str | None  # Label e.g. "Buy Stock", "Buy ATM Call"
    higher_upside_alternative: str | None  # Label e.g. "Buy OTM Call"
    target_path_summary: str         # Human-readable target/return mapping
    early_exit_summary: str          # Summary of exit zones
    # Strategy-specific structured fields (eliminate parsing from text)
    strategy_net_debit: float | None = None   # Net cost to open position (spread/buy call)
    strategy_net_credit: float | None = None  # Net premium received (CSP/covered call)
    assignment_strike: float | None = None   # Strike at which underlying would be assigned (CSP/covered)
    covered_by_shares: bool = False           # True if covered call (shares already held)
    break_even_price: float | None = None
    max_profit_pct: float | None = None
    max_loss_pct: float | None = None

    def __post_init__(self):
        if not self.instrument_action:
            raise ValueError("instrument_action is required")
        if self.primary_contract.option_type not in {"call", "put"}:
            raise ValueError(f"option_type must be call or put; got {self.primary_contract.option_type!r}")


# ---------------------------------------------------------------------------
# Phase 16: Watchlist & Alert Center
# ---------------------------------------------------------------------------

@dataclass
class WatchlistEntry:
    """
    Phase 16: Monitored ticker state for the boss-facing watchlist.

    Status drives monitoring cadence:
      - Held / High Priority Watch / Research In Progress → business_day
      - Passive Watch → weekly

    Thesis state drives alert level:
      - Broken → Critical
      - Weakening → High
      - Strengthening → Medium
      - Stable → None
    """
    ticker: str
    status: str       # "Held" | "High Priority Watch" | "Research In Progress" | "Passive Watch"
    thesis_state: str  # "Strengthening" | "Stable" | "Weakening" | "Broken"
    alert_level: str   # "Critical" | "High" | "Medium" | "Low" | "None"
    current_action_bias: str  # "Buy Stock" | "Buy Call" | "Watchlist" | etc.
    last_user_interest_at: str | None = None
    last_research_at: str | None = None
    next_review_date: str | None = None

    def __post_init__(self):
        if self.status not in {
            "Held", "High Priority Watch", "Research In Progress", "Passive Watch",
        }:
            raise ValueError(
                f"status must be one of Held/High Priority Watch/"
                f"Research In Progress/Passive Watch; got {self.status!r}"
            )
        if self.thesis_state not in {
            "Strengthening", "Stable", "Weakening", "Broken",
        }:
            raise ValueError(
                f"thesis_state must be one of Strengthening/Stable/"
                f"Weakening/Broken; got {self.thesis_state!r}"
            )
        if self.alert_level not in {"Critical", "High", "Medium", "Low", "None"}:
            raise ValueError(
                f"alert_level must be one of Critical/High/Medium/Low/None; "
                f"got {self.alert_level!r}"
            )


@dataclass
class WatchlistAlert:
    """
    Phase 16: An alert generated by the WatchlistAlertCenter.
    Alert-only: advisory message, never an execution instruction.
    """
    ticker: str
    alert_level: str      # "Critical" | "High" | "Medium" | "Low" | "None"
    message: str          # Human-readable alert text
    thesis_state: str      # Thesis state at time of alert
    triggered_at: str | None = None  # ISO timestamp

    def __post_init__(self):
        if self.alert_level not in {"Critical", "High", "Medium", "Low", "None"}:
            raise ValueError(f"alert_level must be Critical/High/Medium/Low/None; got {self.alert_level!r}")


def new_research_task(
    request_text: str,
    tickers: list[str],
    task_type: TaskType = TaskType.SINGLE_TICKER_RESEARCH,
    **kwargs
) -> ResearchTask:
    """Create a new ResearchTask with validation."""
    return ResearchTask(
        request_text=request_text,
        tickers=tickers,
        task_type=task_type,
        **kwargs
    )


# ---------------------------------------------------------------------------
# Phase 17: Validation Engine
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """
    Phase 17: Lightweight validation annotation for the bullish decision system.

    Provides historical support, environment fit, failure mode, and confidence
    assessment WITHOUT overriding the thesis or instrument recommendation.

    This is an annotation layer — it does not change decision authority.
    """
    ticker: str
    regime: str           # "trend_up" | "range_bound" | "high_volatility" | "risk_off" | "unknown"
    historical_support: str  # "strong" | "moderate" | "weak"
    environment_fit: str     # "good" | "mixed" | "poor"
    main_failure_mode: str   # "direction" | "timing" | "iv" | "liquidity" | "none"
    validation_confidence: float  # 0.0 – 1.0
    notes: str | None = None

    def __post_init__(self):
        if self.regime not in {
            "trend_up", "range_bound", "high_volatility", "risk_off", "unknown"
        }:
            raise ValueError(f"regime must be trend_up/range_bound/high_volatility/risk_off/unknown; got {self.regime!r}")
        if self.historical_support not in {"strong", "moderate", "weak"}:
            raise ValueError(f"historical_support must be strong/moderate/weak; got {self.historical_support!r}")
        if self.environment_fit not in {"good", "mixed", "poor"}:
            raise ValueError(f"environment_fit must be good/mixed/poor; got {self.environment_fit!r}")
        if self.main_failure_mode not in {"direction", "timing", "iv", "liquidity", "none"}:
            raise ValueError(f"main_failure_mode must be direction/timing/iv/liquidity/none; got {self.main_failure_mode!r}")
        if not (0.0 <= self.validation_confidence <= 1.0):
            raise ValueError(f"validation_confidence must be 0.0-1.0; got {self.validation_confidence!r}")


# ---------------------------------------------------------------------------
# P20: Factor Calibration Contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LLMAdjustment:
    """
    P20: A bounded, signed, auditable adjustment applied by LLM analysis.

    LLM adjustments are overlays on top of hard-data base scores.
    They must not replace the base score directly and must be logged with reason.
    """
    affected_category: str          # "quality" | "valuation" | "timing" | "regime"
    delta: float                   # signed adjustment amount
    max_abs_delta: float           # upper bound on |delta|
    reason: str
    source_refs: list[str]
    model_provider: str
    model_name: str
    prompt_version: str

    def __post_init__(self):
        if abs(self.delta) > self.max_abs_delta:
            raise ValueError(f"|delta| {abs(self.delta)} exceeds max_abs_delta {self.max_abs_delta}")


@dataclass(frozen=True)
class ThesisGateResult:
    """
    P20: Result of a single gate evaluation in the classification logic.
    """
    gate: str                        # "coverage" | "regime" | "quality" | "valuation" | "timing"
    status: str                     # "passed" | "failed" | "stubbed" | "insufficient_definition"
    score: float
    threshold: float
    failing_dimension: str | None   # which sub-dimension failed, if any
    reason_code: str                 # machine-readable reason
    recommended_action: str          # what to do to resolve the failure


@dataclass(frozen=True)
class ClassificationReason:
    """
    P20: Structured classification reason replacing free-text summaries.
    """
    classification: str                      # "Investable" | "Watchlist" | "Inconclusive" | "No Trade"
    primary_gate: str                       # which gate drove the decision
    primary_reason_code: str                # machine-readable primary reason
    supporting_gates: list[str]            # list of gates that contributed positively
    blocking_gates: list[str]              # list of gates that blocked stronger classification
    recommended_next_action: str
    human_summary: str                      # free-text summary for human readers


@dataclass(frozen=True)
class SourceValueRef:
    """
    P20: Structured reference to the source of a factor value.

    Enables later audit and traceability of factor scores to raw data.
    """
    field_name: str
    value: float | None
    source: str                            # e.g. "yahoo_finance", "futu_opend", "analyst_report"
    fetched_at: str                        # ISO timestamp
    as_of_date: str                       # trading day or data date
    provider: str                          # e.g. "Futu", "YahooFinance"
    quality_flags: list[str]              # e.g. "stale", "missing", "estimated"


@dataclass
class FactorSnapshot:
    """
    P20: Core factor logging object. Persisted for future IC, ICIR, decay,
    autocorrelation, and orthogonality diagnostics.

    The canonical key for deduplication is:
    (ticker, trading_day, universe_membership_snapshot_id)
    """
    snapshot_id: str
    schema_version: str
    task_id: str
    ticker: str
    as_of_timestamp: str
    trading_day: str
    data_as_of_date: str
    universe_id: str | None
    universe_label: str | None
    universe_membership_snapshot_id: str
    company_quality_score: float
    valuation_attractiveness_score: float
    timing_market_fit_score: float
    quality_coverage: float
    valuation_coverage: float
    timing_coverage: float
    regime_coverage: float
    llm_overlay_coverage: float
    llm_adjustment_total: float
    llm_adjustments: list[LLMAdjustment]
    gate_results: list[ThesisGateResult]
    classification: str
    classification_reason: ClassificationReason
    negative_signal_strength_decile: int | None  # 1-10, or None if not computed
    thresholds_used: dict
    model_routes_used: dict
    source_refs: list[SourceValueRef]
    created_at: str
    # Optional fields
    raw_factor_values: dict | None = None
    normalized_factor_values: dict | None = None
    missing_dimensions: list[str] | None = None
    stale_dimensions: list[str] | None = None
    fallback_reasons: list[str] | None = None
    provider_versions: dict | None = None
    prompt_versions: dict | None = None
    sector_id: str | None = None
    size_decile: int | None = None


@dataclass
class ForwardReturnObservation:
    """
    P20: Persisted forward return for a factor snapshot.

    P22 IC/ICIR/decay jobs consume this table rather than reading price history.
    Supported horizons: 1, 5, 21, 63 trading days.

    gross_return_pct / net_return_pct / transaction_cost_pct / cost_source allow
    P22 to audit gross IC vs net IC without re-running a cost model.
    """
    observation_id: str
    snapshot_id: str                     # links to FactorSnapshot.snapshot_id
    ticker: str
    trading_day: str
    horizon_days: int                   # 1 | 5 | 21 | 63
    return_value: float                 # alias for gross_return_pct for backward compat
    return_source: str                  # "close_to_close" | "vwap" | etc.
    price_start: float
    price_end: float
    start_price_date: str
    end_price_date: str
    gap_handled: bool
    computed_at: str
    # P22-required cost awareness fields
    gross_return_pct: float              # return before transaction costs
    net_return_pct: float               # return after transaction costs
    transaction_cost_pct: float         # cost component (gross - net)
    cost_source: str | None             # "CostModel" | "fixed" | "none"; None when status != "computed"
    # If horizon could not be computed, observation may still be persisted with:
    observation_status: str | None = None  # "computed" | "missing_horizon" | "gap_unresolvable"
    missing_reason: str | None = None


@dataclass
class UniverseMembershipSnapshot:
    """
    P20: Point-in-time universe membership to avoid look-ahead bias.

    Diagnostics must use the point-in-time membership linked from FactorSnapshot,
    not today's index membership.
    """
    universe_membership_snapshot_id: str
    universe_id: str
    universe_label: str
    as_of_timestamp: str
    members: list[str]                   # list of ticker symbols
    source: str                          # e.g. "sp500_constituents", "custom_universe"
    created_at: str


def new_subagent_task(
    task_id: str,
    agent_role: AgentRole,
    ticker: str,
    objective: str,
    **kwargs
) -> SubagentTask:
    """Create a new SubagentTask with validation."""
    return SubagentTask(
        task_id=task_id,
        agent_role=agent_role,
        ticker=ticker,
        objective=objective,
        **kwargs
    )


def new_evidence_item(
    task_id: str,
    ticker: str,
    agent_role: AgentRole,
    claim: str,
    **kwargs
) -> EvidenceItem:
    """Create a new EvidenceItem with validation."""
    return EvidenceItem(
        task_id=task_id,
        agent_role=agent_role,
        ticker=ticker,
        claim=claim,
        **kwargs
    )
