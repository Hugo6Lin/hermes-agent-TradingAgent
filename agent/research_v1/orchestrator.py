"""
Orchestrator - Workflow controller for research tasks.

The orchestrator owns workflow control:
- decomposes work into subtasks
- enforces required workflow steps
- validates completeness
- assembles evidence packets
- prepares final-judge inputs

The orchestrator MUST NOT:
- produce final rating
- produce final report conclusion
- collapse all evidence into a final investment judgment

Phase 4 implementation: full workflow audit, conflict detection, missing-step
signaling, and orchestrator notes generation.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from agent.research_v1.contracts import (
    ResearchTask,
    SubagentTask,
    EvidenceBundle,
    EvidenceItem,
    JudgeInputPacket,
    AgentRole,
    TaskStatus,
    TaskType,
)
from agent.research_v1.evidence_store import EvidenceStore

if TYPE_CHECKING:
    from agent.research_v1.contracts import CanonicalSignal, CanonicalReport, CanonicalReview, ReviewInputPacket


# Required agent roles by task type
REQUIRED_ROLES_BY_TASK_TYPE: dict[str, list[AgentRole]] = {
    "single_ticker_research": [
        AgentRole.FUNDAMENTALS,
        AgentRole.TECHNICAL,
        AgentRole.NEWS,
    ],
    "multi_ticker_compare": [
        AgentRole.FUNDAMENTALS,
        AgentRole.TECHNICAL,
        AgentRole.INDUSTRY,
    ],
    "option_idea": [
        AgentRole.TECHNICAL,
        AgentRole.OPTIONS,
        AgentRole.RISK,
    ],
    "portfolio_review": [
        AgentRole.FUNDAMENTALS,
        AgentRole.RISK,
        AgentRole.TECHNICAL,
    ],
    "position_management": [
        AgentRole.RISK,
        AgentRole.TECHNICAL,
        AgentRole.FUNDAMENTALS,
    ],
}


class Orchestrator:
    """
    Workflow controller for research tasks.

    Coordinates subtask creation, evidence collection, and judge packet assembly.
    Responsible for workflow control only - does NOT produce final judgment.
    """

    def __init__(self):
        """Initialize the orchestrator."""
        self._evidence_store = EvidenceStore()

    def decompose(self, task: ResearchTask) -> list[SubagentTask]:
        """
        Decompose a ResearchTask into SubagentTasks.

        Args:
            task: The research task to decompose.

        Returns:
            List of SubagentTask objects, one per required agent role per ticker.
        """
        task_type_str = task.task_type.value
        required_roles = REQUIRED_ROLES_BY_TASK_TYPE.get(
            task_type_str,
            REQUIRED_ROLES_BY_TASK_TYPE["single_ticker_research"]
        )

        subtasks = []
        for i, role in enumerate(required_roles):
            for ticker in task.tickers:
                subtask = SubagentTask(
                    task_id=task.task_id,
                    agent_role=role,
                    ticker=ticker,
                    objective=f"Analyze {ticker} from {role.value} perspective",
                    priority=i + 1,
                )
                subtasks.append(subtask)

        return subtasks

    def audit(
        self,
        task: ResearchTask,
        evidence_items: list[EvidenceItem],
        bundle_ticker: str | None = None,
    ) -> dict[str, Any]:
        """
        Audit evidence against required roles for the task.

        Performs workflow checks:
        - required roles present
        - missing steps / roles
        - direction conflicts

        Does NOT produce a final judgment. Returns only audit metadata.

        Args:
            task: The original research task.
            evidence_items: List of EvidenceItem from subagent execution.
            bundle_ticker: Ticker for this evidence bundle. Required for
                multi-ticker tasks to avoid mis-labeling. If None, defaults
                to task.tickers[0] for backward compatibility.

        Returns:
            Dict with keys:
            - is_ready: bool
            - missing_roles: list[str]
            - conflict_pairs: list of (claim_a, claim_b) string descriptions
            - orchestrator_notes: str (workflow commentary, not judgment)
        """
        ticker = bundle_ticker if bundle_ticker is not None else (task.tickers[0] if task.tickers else "")
        bundle = self.assemble_bundle(task.task_id, ticker, evidence_items)
        is_ready, missing_roles = self.check_readiness(
            bundle, task.task_type.value
        )

        # Detect direction conflicts
        conflict_pairs = self._describe_conflicts(evidence_items)

        # Build workflow notes (never a final rating or conclusion)
        notes = self._build_orchestrator_notes(
            task, is_ready, missing_roles, conflict_pairs
        )

        return {
            "is_ready": is_ready,
            "missing_roles": missing_roles,
            "conflict_pairs": conflict_pairs,
            "orchestrator_notes": notes,
        }

    def assemble_bundle(
        self,
        task_id: str,
        ticker: str,
        evidence_items: list[EvidenceItem],
    ) -> EvidenceBundle:
        """
        Assemble evidence items into an EvidenceBundle.

        Args:
            task_id: The parent task ID.
            ticker: The ticker symbol.
            evidence_items: List of EvidenceItem objects.

        Returns:
            EvidenceBundle with coverage summary, conflict flags, and missing steps.
        """
        # Build coverage summary
        coverage_summary: dict[str, int] = {}
        for item in evidence_items:
            role = item.agent_role.value
            coverage_summary[role] = coverage_summary.get(role, 0) + 1

        # Detect direction conflicts
        conflicts = self._evidence_store.detect_conflicts(evidence_items)
        conflict_flags = [
            f"{a.claim[:50]} vs {b.claim[:50]}"
            for a, b in conflicts
        ]

        bundle = EvidenceBundle(
            task_id=task_id,
            ticker=ticker,
            evidence_items=evidence_items,
            coverage_summary=coverage_summary,
            conflict_flags=conflict_flags,
        )
        return bundle

    def assemble_judge_packet(
        self,
        task: ResearchTask,
        bundle: EvidenceBundle,
        audit_result: dict[str, Any] | None = None,
    ) -> JudgeInputPacket:
        """
        Assemble a JudgeInputPacket from task and evidence bundle.

        Args:
            task: The original research task.
            bundle: The evidence bundle.
            audit_result: Optional audit result from self.audit().

        Returns:
            JudgeInputPacket ready for final judge consumption.
        """
        required_outputs = []
        output_mode = task.output_mode.value
        if output_mode in ("signal_and_report", "signal_only", "signal_report_pdf_viewer"):
            required_outputs.append("signal")
        if output_mode in ("signal_and_report", "report_only", "signal_report_pdf_viewer"):
            required_outputs.append("report")

        orchestrator_notes = ""
        if audit_result:
            orchestrator_notes = audit_result.get("orchestrator_notes", "")

        packet = JudgeInputPacket(
            task_id=task.task_id,
            ticker=bundle.ticker,
            task_summary=task.request_text,
            evidence_bundle=bundle,
            required_outputs=required_outputs,
            conflict_flags=bundle.conflict_flags,
            missing_steps=audit_result.get("missing_roles", []) if audit_result else [],
            orchestrator_notes=orchestrator_notes,
        )
        return packet

    def check_readiness(
        self,
        bundle: EvidenceBundle,
        task_type: str,
    ) -> tuple[bool, list[str]]:
        """
        Check if the evidence bundle is ready for judging.

        Args:
            bundle: The evidence bundle to check.
            task_type: The task type string (e.g., "single_ticker_research").

        Returns:
            Tuple of (is_ready, list of missing role strings).
        """
        required_roles = REQUIRED_ROLES_BY_TASK_TYPE.get(
            task_type,
            REQUIRED_ROLES_BY_TASK_TYPE["single_ticker_research"]
        )
        required_role_set = set(required_roles)

        present_roles = set(bundle.coverage_summary.keys())
        missing = list(required_role_set - present_roles)

        return len(missing) == 0, missing

    def _describe_conflicts(
        self,
        evidence_items: list[EvidenceItem],
    ) -> list[str]:
        """Describe direction conflicts as human-readable strings."""
        conflicts = self._evidence_store.detect_conflicts(evidence_items)
        return [
            f"[{c1.agent_role.value}] {c1.claim[:40]} ... [{c2.agent_role.value}] {c2.claim[:40]}"
            for c1, c2 in conflicts
        ]

    def _build_orchestrator_notes(
        self,
        task: ResearchTask,
        is_ready: bool,
        missing_roles: list[str],
        conflict_pairs: list[str],
    ) -> str:
        """
        Build orchestrator workflow notes.

        These are workflow observations, NOT a final investment judgment.
        The final judge will form the judgment; orchestrator only comments
        on process state.
        """
        notes_parts: list[str] = []

        if is_ready:
            notes_parts.append("All required evidence roles present.")
        else:
            notes_parts.append(f"Missing roles: {', '.join(missing_roles)}.")

        if conflict_pairs:
            notes_parts.append(
                f"Detected {len(conflict_pairs)} direction conflict(s) "
                "between evidence items. Final judge should resolve."
            )
        else:
            notes_parts.append("No direction conflicts detected.")

        # Note on evidence coverage
        notes_parts.append(
            f"Task type: {task.task_type.value}. "
            f"Research mode: {task.research_mode.value}. "
            f"Output mode: {task.output_mode.value}."
        )

        return " ".join(notes_parts)

    def assemble_review_packet(
        self,
        task: ResearchTask,
        bundle: EvidenceBundle,
        signal: "CanonicalSignal | None",
        report: "CanonicalReport | None",
        audit_result: dict[str, Any] | None = None,
    ) -> "ReviewInputPacket":
        """
        Assemble a ReviewInputPacket for the reviewer extension point.

        The reviewer receives only this bounded packet — it does NOT read
        arbitrary upstream state. The packet contains the task summary,
        final judge outputs (signal/report), orchestrator flags, and
        evidence bundle for cross-reference.

        Args:
            task: The original research task.
            bundle: The evidence bundle assembled by orchestrator.
            signal: The CanonicalSignal from final judge (may be None if
                output_mode did not request a signal).
            report: The CanonicalReport from final judge (may be None if
                output_mode did not request a report).
            audit_result: Optional audit result from self.audit().

        Returns:
            ReviewInputPacket ready for reviewer consumption.
        """
        from agent.research_v1.contracts import ReviewInputPacket

        orchestrator_flags = []
        if audit_result:
            orchestrator_flags.extend(audit_result.get("conflict_pairs", []))
            orchestrator_flags.extend(audit_result.get("missing_roles", []))

        return ReviewInputPacket(
            task_id=task.task_id,
            ticker=bundle.ticker,
            task_summary=task.request_text,
            signal=signal,
            report=report,
            evidence_bundle=bundle,
            orchestrator_flags=orchestrator_flags,
            reviewer_configured=True,
        )

    def review(
        self,
        packet: "ReviewInputPacket",
    ) -> "CanonicalReview":
        """
        Invoke the reviewer extension point.

        The reviewer is an OPTIONAL quality gate. It annotates the final
        judge's output with quality flags and a verdict. It NEVER overrides
        the final judge's decision.

        Args:
            packet: Bounded ReviewInputPacket from assemble_review_packet().

        Returns:
            CanonicalReview annotation (verdict + flags + quality score).
        """
        from agent.research_v1.reviewer import Reviewer

        reviewer = Reviewer()
        return reviewer.review(packet)
