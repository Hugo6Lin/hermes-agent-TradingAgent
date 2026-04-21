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
