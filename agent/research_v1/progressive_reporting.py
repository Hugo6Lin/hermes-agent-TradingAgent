"""Progressive reporting mechanism for research pipeline.

Provides partial results ("初步版本") when pipeline degrades or times out,
ensuring users always get something useful.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ReportSection:
    """A section of a research report."""
    title: str
    content: str
    completeness: float  # 0.0 to 1.0, how complete this section is
    source: str  # e.g., "analysts", "debate", "manager", "degraded"


@dataclass
class ProgressiveReport:
    """A progressively built research report."""
    symbol: str
    trading_date: str
    sections: dict[str, ReportSection] = field(default_factory=dict)
    version: int = 1  # Version number, increments with each update
    is_complete: bool = False
    is_degraded: bool = False
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    def add_section(self, name: str, title: str, content: str, completeness: float = 1.0, source: str = "unknown") -> None:
        """Add or update a section in the report.

        Args:
            name: Internal section name.
            title: Display title.
            content: Section content.
            completeness: How complete this section is (0.0-1.0).
            source: Source of this section data.
        """
        self.sections[name] = ReportSection(
            title=title,
            content=content,
            completeness=completeness,
            source=source
        )
        self.updated_at = _utc_now_iso()

    def get_section(self, name: str) -> Optional[ReportSection]:
        """Get a section by name.

        Args:
            name: Section name.

        Returns:
            ReportSection or None if not found.
        """
        return self.sections.get(name)

    def get_completeness(self) -> float:
        """Calculate overall report completeness.

        Returns:
            Completeness score from 0.0 to 1.0.
        """
        if not self.sections:
            return 0.0
        return sum(s.completeness for s in self.sections.values()) / len(self.sections)

    def mark_complete(self) -> None:
        """Mark the report as fully complete."""
        self.is_complete = True
        self.updated_at = _utc_now_iso()

    def mark_degraded(self) -> None:
        """Mark the report as degraded (partial results)."""
        self.is_degraded = True
        self.updated_at = _utc_now_iso()

    def to_markdown(self) -> str:
        """Convert report to Markdown format.

        Returns:
            Markdown string representation.
        """
        version_tag = "[初步版本]" if self.is_degraded else "[完整版]"
        lines = [
            f"# {self.symbol} 研究报告 {version_tag}",
            f"",
            f"**日期:** {self.trading_date}",
            f"**版本:** {self.version}",
            f"**完整度:** {self.get_completeness() * 100:.0f}%",
            f"**生成时间:** {self.created_at}",
            f"",
        ]

        # Add each section
        for name, section in self.sections.items():
            lines.append(f"## {section.title}")
            lines.append(f"<sup>来源: {section.source} | 完整度: {section.completeness * 100:.0f}%</sup>")
            lines.append("")
            lines.append(section.content)
            lines.append("")

        return "\n".join(lines)

    def to_summary_dict(self) -> dict:
        """Convert report to summary dictionary.

        Returns:
            Dict with report summary.
        """
        return {
            "symbol": self.symbol,
            "trading_date": self.trading_date,
            "version": self.version,
            "is_complete": self.is_complete,
            "is_degraded": self.is_degraded,
            "completeness": self.get_completeness(),
            "sections": {
                name: {
                    "title": s.title,
                    "completeness": s.completeness,
                    "source": s.source
                }
                for name, s in self.sections.items()
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class ProgressiveReportBuilder:
    """Builds progressive reports as pipeline executes.

    Accumulates results from each pipeline phase and provides
    a usable report at any point, even if pipeline degrades.
    """

    def __init__(self, symbol: str, trading_date: str):
        """Initialize ProgressiveReportBuilder.

        Args:
            symbol: Stock ticker symbol.
            trading_date: Trading date string.
        """
        self.report = ProgressiveReport(symbol=symbol, trading_date=trading_date)
        self._degradation_sources: set[str] = set()

    def add_analyst_results(self, results: dict[str, dict]) -> None:
        """Add analyst results to the report.

        Args:
            results: Dict mapping analyst type to their report data.
        """
        for analyst_type, data in results.items():
            content = data.get("report", "")
            completeness = data.get("completeness", 1.0)
            self.report.add_section(
                name=f"analyst_{analyst_type}",
                title=f"{analyst_type.title()} Analyst",
                content=content,
                completeness=completeness,
                source="analysts"
            )
        self.report.version += 1

    def add_debate_results(self, bull_points: list, bear_points: list, decision: str, confidence: str) -> None:
        """Add debate results to the report.

        Args:
            bull_points: List of bull case points.
            bear_points: List of bear case points.
            decision: Debate decision (BUY/SELL/HOLD).
            confidence: Confidence level.
        """
        debate_content = f"""**多空辩论结果:**

**Bull Case ({len(bull_points)} points):**
{chr(10).join(f"- {p}" for p in bull_points)}

**Bear Case ({len(bear_points)} points):**
{chr(10).join(f"- {p}" for p in bear_points)}

**Decision:** {decision} (Confidence: {confidence})
"""
        self.report.add_section(
            name="debate",
            title="多空辩论 (Bull/Bear Debate)",
            content=debate_content,
            completeness=1.0,
            source="debate"
        )
        self.report.version += 1

    def add_manager_decision(
        self,
        decision: str,
        confidence: str,
        key_reasons: list,
        remaining_concerns: list
    ) -> None:
        """Add Research Manager decision to the report.

        Args:
            decision: BUY/SELL/HOLD.
            confidence: high/medium/low.
            key_reasons: List of key reasons.
            remaining_concerns: List of remaining concerns.
        """
        decision_content = f"""**最终决策:** {decision}
**置信度:** {confidence}

**核心理由:**
{chr(10).join(f"- {r}" for r in key_reasons)}

**剩余顾虑:**
{chr(10).join(f"- {c}" for c in remaining_concerns)}
"""
        self.report.add_section(
            name="decision",
            title="研究经理决策 (Research Manager Decision)",
            content=decision_content,
            completeness=1.0,
            source="manager"
        )
        self.report.version += 1

    def add_final_grade(self, grade: str, fundamental_score: float, technical_score: float, macro_score: float) -> None:
        """Add final grading to the report.

        Args:
            grade: S/A/B/C grade.
            fundamental_score: Fundamental analysis score.
            technical_score: Technical analysis score.
            macro_score: Macro analysis score.
        """
        grade_content = f"""**最终评级:** {grade}

**评分细分:**
- 基本面 (40%): {fundamental_score:.1f}/100
- 技术面 (30%): {technical_score:.1f}/100
- 宏观 (30%): {macro_score:.1f}/100
"""
        self.report.add_section(
            name="grade",
            title="综合评级 (Composite Grade)",
            content=grade_content,
            completeness=1.0,
            source="grading"
        )
        self.report.version += 1

    def mark_degraded(self, reason: str) -> None:
        """Mark the report as degraded with a reason.

        Args:
            reason: Description of why degradation occurred.
        """
        self.report.mark_degraded()
        self._degradation_sources.add(reason)

    def mark_complete(self) -> None:
        """Mark the report as complete."""
        self.report.mark_complete()

    def get_report(self) -> ProgressiveReport:
        """Get the current state of the report.

        Returns:
            ProgressiveReport with current sections and status.
        """
        return self.report

    def has_analysts(self) -> bool:
        """Check if analyst results have been added.

        Returns:
            True if analyst sections exist.
        """
        return any(name.startswith("analyst_") for name in self.report.sections)

    def has_debate(self) -> bool:
        """Check if debate results have been added.

        Returns:
            True if debate section exists.
        """
        return self.report.get_section("debate") is not None

    def has_decision(self) -> bool:
        """Check if manager decision has been added.

        Returns:
            True if decision section exists.
        """
        return self.report.get_section("decision") is not None

    def get_current_output(self) -> str:
        """Get the best available output based on current state.

        Returns the most complete report possible given what
        has been collected so far.

        Returns:
            Markdown string of current report state.
        """
        return self.report.to_markdown()
