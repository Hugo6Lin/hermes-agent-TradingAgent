"""Tests for progressive reporting mechanism."""

import pytest
from agent.research_v1.progressive_reporting import (
    ProgressiveReport,
    ProgressiveReportBuilder,
    ReportSection
)


def test_progressive_report_initialization():
    report = ProgressiveReport(symbol="AAPL", trading_date="2026-04-17")
    assert report.symbol == "AAPL"
    assert report.trading_date == "2026-04-17"
    assert report.is_complete is False
    assert report.is_degraded is False
    assert report.version == 1


def test_add_section():
    report = ProgressiveReport(symbol="AAPL", trading_date="2026-04-17")
    report.add_section(
        name="test",
        title="Test Section",
        content="Test content",
        completeness=0.8,
        source="test"
    )
    section = report.get_section("test")
    assert section is not None
    assert section.title == "Test Section"
    assert section.content == "Test content"
    assert section.completeness == 0.8


def test_get_completeness():
    report = ProgressiveReport(symbol="AAPL", trading_date="2026-04-17")
    assert report.get_completeness() == 0.0
    report.add_section("s1", "Section 1", "Content 1", completeness=0.5)
    assert report.get_completeness() == 0.5
    report.add_section("s2", "Section 2", "Content 2", completeness=1.0)
    assert report.get_completeness() == 0.75


def test_mark_complete():
    report = ProgressiveReport(symbol="AAPL", trading_date="2026-04-17")
    report.mark_complete()
    assert report.is_complete is True


def test_mark_degraded():
    report = ProgressiveReport(symbol="AAPL", trading_date="2026-04-17")
    report.mark_degraded()
    assert report.is_degraded is True


def test_to_markdown():
    report = ProgressiveReport(symbol="AAPL", trading_date="2026-04-17")
    report.add_section("test", "Test Section", "Test content", completeness=1.0, source="unit_test")
    markdown = report.to_markdown()
    assert "# AAPL 研究报告" in markdown
    assert "Test Section" in markdown
    assert "Test content" in markdown
    assert "[完整版]" in markdown


def test_to_markdown_degraded():
    report = ProgressiveReport(symbol="AAPL", trading_date="2026-04-17")
    report.mark_degraded()
    report.add_section("test", "Test Section", "Test content")
    markdown = report.to_markdown()
    assert "[初步版本]" in markdown


def test_progressive_report_builder():
    builder = ProgressiveReportBuilder(symbol="AAPL", trading_date="2026-04-17")
    assert builder.report.symbol == "AAPL"
    assert builder.has_analysts() is False


def test_add_analyst_results():
    builder = ProgressiveReportBuilder(symbol="AAPL", trading_date="2026-04-17")
    results = {
        "fundamentals": {"report": "Fundamental analysis content", "completeness": 1.0},
        "technical": {"report": "Technical analysis content", "completeness": 0.9}
    }
    builder.add_analyst_results(results)
    assert builder.has_analysts() is True
    assert builder.report.get_section("analyst_fundamentals") is not None
    assert builder.report.version == 2


def test_add_debate_results():
    builder = ProgressiveReportBuilder(symbol="AAPL", trading_date="2026-04-17")
    builder.add_debate_results(
        bull_points=["Bull point 1", "Bull point 2"],
        bear_points=["Bear point 1"],
        decision="BUY",
        confidence="high"
    )
    assert builder.has_debate() is True
    section = builder.report.get_section("debate")
    assert "Bull Case" in section.content
    assert "Bear Case" in section.content
    assert "BUY" in section.content


def test_add_manager_decision():
    builder = ProgressiveReportBuilder(symbol="AAPL", trading_date="2026-04-17")
    builder.add_manager_decision(
        decision="HOLD",
        confidence="medium",
        key_reasons=["Reason 1", "Reason 2"],
        remaining_concerns=["Concern 1"]
    )
    assert builder.has_decision() is True
    section = builder.report.get_section("decision")
    assert "HOLD" in section.content
    assert "Reason 1" in section.content


def test_mark_degraded_on_builder():
    builder = ProgressiveReportBuilder(symbol="AAPL", trading_date="2026-04-17")
    builder.add_analyst_results({"fundamentals": {"report": "Test", "completeness": 1.0}})
    builder.mark_degraded("timeout_phase2")
    assert builder.report.is_degraded is True


def test_get_current_output():
    builder = ProgressiveReportBuilder(symbol="AAPL", trading_date="2026-04-17")
    builder.add_analyst_results({"fundamentals": {"report": "Fundamental report", "completeness": 1.0}})
    output = builder.get_current_output()
    assert "Fundamental report" in output
    assert "Fundamentals Analyst" in output
