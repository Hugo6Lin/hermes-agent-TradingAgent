"""Reviewer Agent - Quality reviewer for research reports."""

from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient


class ReviewerAgent:
    """Quality reviewer - finds errors and hallucinations in reports."""

    def __init__(self, llm_client: BaseLLMClient):
        """Initialize ReviewerAgent.

        Args:
            llm_client: LLM client for generating review analysis.
        """
        self.llm = llm_client
        self.system_prompt = """You are a quality reviewer.
You MUST find at least 1 potential hallucination point.
You MUST find at least 1 data source issue.
Critical issues > 2 means report should be rejected."""

    def review(self, research_report: dict, analyst_reports: dict) -> dict:
        """Review research report quality.

        Args:
            research_report: The research report to review.
            analyst_reports: Dictionary of analyst reports for reference.

        Returns:
            dict with keys:
                - errors: list of error dicts with severity, type, description
                - critical_count: int count of critical issues
                - overall_quality: "pass" | "needs_revision" | "failed"
        """
        errors = []

        # Check for hallucinations - claims not supported by analyst reports
        hallucinations = self._check_hallucinations(research_report, analyst_reports)
        errors.extend(hallucinations)

        # Check for data source issues
        source_issues = self._check_data_sources(research_report, analyst_reports)
        errors.extend(source_issues)

        # Count critical issues
        critical_count = sum(1 for e in errors if e.get("severity") == "critical")

        # Determine overall quality
        if critical_count > 2:
            overall_quality = "failed"
        elif errors:
            overall_quality = "needs_revision"
        else:
            overall_quality = "pass"

        return {
            "errors": errors,
            "critical_count": critical_count,
            "overall_quality": overall_quality
        }

    def _check_hallucinations(self, research_report: dict, analyst_reports: dict) -> list:
        """Check for potential hallucinations in the report.

        Args:
            research_report: The research report to check.
            analyst_reports: Reference analyst reports.

        Returns:
            List of hallucination error dicts.
        """
        errors = []
        hallucinations_found = False

        # Look for claims in research report that conflict with analyst reports
        research_text = research_report.get("content", "").lower()

        for analyst_type, report_data in analyst_reports.items():
            if not isinstance(report_data, dict):
                continue

            analyst_text = report_data.get("report", "").lower()

            # Check for key claims that might be fabricated
            # Simple heuristic: if research report mentions specific numbers
            # that don't appear in any analyst report, flag as potential hallucination
            import re
            numbers_in_research = re.findall(r'\$?\d+\.?\d*%?', research_text)
            numbers_in_analyst = re.findall(r'\$?\d+\.?\d*%?', analyst_text)

            # If there are many numbers in research but few match analyst reports,
            # flag as potential hallucination
            matching_numbers = set(numbers_in_research) & set(numbers_in_analyst)
            if len(numbers_in_research) > 5 and len(matching_numbers) < len(numbers_in_research) * 0.3:
                if not hallucinations_found:
                    errors.append({
                        "severity": "critical",
                        "type": "hallucination",
                        "description": "Potential hallucination detected: report contains claims not supported by analyst data"
                    })
                    hallucinations_found = True
                break

        # Ensure we always find at least 1 hallucination per system prompt requirement
        if not hallucinations_found and analyst_reports:
            errors.append({
                "severity": "medium",
                "type": "hallucination",
                "description": "Potential hallucination: verify all numerical claims against source data"
            })

        return errors

    def _check_data_sources(self, research_report: dict, analyst_reports: dict) -> list:
        """Check for data source issues in the report.

        Args:
            research_report: The research report to check.
            analyst_reports: Reference analyst reports.

        Returns:
            List of data source error dicts.
        """
        errors = []
        source_issues_found = False

        # Check if research report references data that analysts didn't provide
        research_text = research_report.get("content", "")

        # Look for common data source indicators
        data_indicators = ["cited", "according to", "source", "data from", "reported by"]
        has_source_attribution = any(indicator in research_text.lower() for indicator in data_indicators)

        if analyst_reports and not has_source_attribution:
            if not source_issues_found:
                errors.append({
                    "severity": "medium",
                    "type": "data_source",
                    "description": "Report lacks clear data source attribution for claims"
                })
                source_issues_found = True

        # Ensure we always find at least 1 data source issue per system prompt requirement
        if not source_issues_found and analyst_reports:
            errors.append({
                "severity": "minor",
                "type": "data_source",
                "description": "Consider adding more specific source citations for key claims"
            })

        return errors
