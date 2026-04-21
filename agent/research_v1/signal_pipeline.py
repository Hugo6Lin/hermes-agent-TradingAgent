"""Signal persistence pipeline — repositioned around canonical output contracts."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from agent.research_v1.data.database import ResearchDatabase

if TYPE_CHECKING:
    from agent.research_v1.contracts import CanonicalSignal, CanonicalReport


@dataclass
class SignalPersistencePipeline:
    """Persist canonical signals and reports into the research database."""

    database: ResearchDatabase

    def persist_canonical_signal(
        self,
        task_id: str,
        signal: "CanonicalSignal",
    ) -> str:
        """
        Persist a CanonicalSignal to the database.

        Args:
            task_id: The research task ID.
            signal: CanonicalSignal from the final judge.

        Returns:
            The database signal_id.
        """
        return self.database.save_canonical_signal(signal, task_id)

    def persist_canonical_report(
        self,
        task_id: str,
        report: "CanonicalReport",
        ticker: str,
    ) -> str:
        """
        Persist a CanonicalReport to the database.

        Args:
            task_id: The research task ID.
            report: CanonicalReport from the final judge.
            ticker: The ticker symbol.

        Returns:
            The database report_id.
        """
        return self.database.save_canonical_report(report, task_id, ticker)

    # Backward-compatibility stub — grade_result dict form
    def persist_grade_result(self, task_id: int, grade_result: dict) -> dict:
        """Persist legacy grade result dict. Prefer persist_canonical_signal."""
        self.database.update_task_status(
            task_id=task_id,
            status="graded",
            grade=grade_result.get("grade"),
            composite_score=grade_result.get("composite_score"),
        )
        return self.database.save_signal_bundle(task_id=task_id, grade_result=grade_result)
