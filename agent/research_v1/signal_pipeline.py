"""Minimal signal persistence pipeline for grading results."""

from dataclasses import dataclass

from agent.research_v1.data.database import ResearchDatabase


@dataclass
class SignalPersistencePipeline:
    """Persist structured grading results into the research database."""

    database: ResearchDatabase

    def persist_grade_result(self, task_id: int, grade_result: dict) -> dict:
        """Persist task grade metadata and the structured signal bundle."""
        self.database.update_task_status(
            task_id=task_id,
            status="graded",
            grade=grade_result["grade"],
            composite_score=grade_result["composite_score"],
        )
        return self.database.save_signal_bundle(task_id=task_id, grade_result=grade_result)
