"""Tests for token budget monitoring."""

import pytest
from agent.research_v1.token_budget import (
    TokenBudget,
    TokenBudgetMonitor,
    BudgetExceededError
)


def test_token_budget_initialization():
    budget = TokenBudget(max_tokens=500_000)
    assert budget.max_tokens == 500_000
    assert budget.current_tokens == 0


def test_token_budget_add_usage():
    budget = TokenBudget(max_tokens=500_000)
    budget.add_usage("fundamentals", 1000, 500)
    assert budget.current_tokens == 1500
    assert budget.agent_costs["fundamentals"] == 1500


def test_token_budget_exceeded():
    budget = TokenBudget(max_tokens=100)
    budget.add_usage("fundamentals", 50, 30)  # 80 total
    with pytest.raises(BudgetExceededError):
        budget.add_usage("bull", 30, 20)  # 50 more, would be 130 > 100


def test_token_budget_check_within_budget():
    budget = TokenBudget(max_tokens=500_000)
    assert budget.check_within_budget(1000, 500) is True
    budget.add_usage("test", 499_000, 0)
    assert budget.check_within_budget(1000, 500) is False


def test_token_budget_monitor_get_budget():
    monitor = TokenBudgetMonitor(max_tokens_per_task=500_000)
    budget1 = monitor.get_budget(1)
    budget2 = monitor.get_budget(1)
    assert budget1 is budget2  # Same instance
    budget3 = monitor.get_budget(2)
    assert budget3 is not budget1  # Different task


def test_token_budget_monitor_record_usage():
    monitor = TokenBudgetMonitor(max_tokens_per_task=500_000)
    monitor.record_usage(task_id=1, agent_type="fundamentals", input_tokens=1000, output_tokens=500)
    summary = monitor.get_task_summary(1)
    assert summary["total_used"] == 1500
    assert summary["by_agent"]["fundamentals"] == 1500


def test_token_budget_monitor_budget_exceeded():
    monitor = TokenBudgetMonitor(max_tokens_per_task=100)
    monitor.record_usage(task_id=1, agent_type="fundamentals", input_tokens=50, output_tokens=30)
    with pytest.raises(BudgetExceededError):
        monitor.record_usage(task_id=1, agent_type="bull", input_tokens=30, output_tokens=20)


def test_token_budget_monitor_clear_task():
    monitor = TokenBudgetMonitor()
    monitor.record_usage(task_id=1, agent_type="fundamentals", input_tokens=100, output_tokens=50)
    monitor.clear_task(1)
    summary = monitor.get_task_summary(1)
    assert summary["total_used"] == 0


def test_token_budget_get_remaining():
    budget = TokenBudget(max_tokens=500_000)
    budget.add_usage("test", 100_000, 50_000)
    assert budget.get_remaining() == 350_000
