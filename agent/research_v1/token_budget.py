"""Token budget monitoring for research pipeline."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TokenBudget:
    """Token budget for a research task."""
    max_tokens: int = 500_000  # 500K per task limit
    current_tokens: int = 0
    agent_costs: dict[str, int] = field(default_factory=dict)

    def add_usage(self, agent_type: str, input_tokens: int, output_tokens: int) -> None:
        """Add token usage for an agent.

        Args:
            agent_type: Name of the agent (e.g., "fundamentals", "bull").
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens used.

        Raises:
            BudgetExceededError: If adding these tokens would exceed budget.
        """
        total = input_tokens + output_tokens
        new_total = self.current_tokens + total

        if new_total > self.max_tokens:
            raise BudgetExceededError(
                f"Token budget exceeded: {self.current_tokens} + {total} = {new_total} > {self.max_tokens}"
            )

        self.current_tokens = new_total
        self.agent_costs[agent_type] = self.agent_costs.get(agent_type, 0) + total

    def check_within_budget(self, input_tokens: int, output_tokens: int) -> bool:
        """Check if adding these tokens would be within budget.

        Args:
            input_tokens: Input tokens to add.
            output_tokens: Output tokens to add.

        Returns:
            True if within budget, False otherwise.
        """
        return (self.current_tokens + input_tokens + output_tokens) <= self.max_tokens

    def get_remaining(self) -> int:
        """Get remaining token budget.

        Returns:
            Number of tokens remaining.
        """
        return max(0, self.max_tokens - self.current_tokens)

    def get_usage_by_agent(self) -> dict[str, int]:
        """Get token usage breakdown by agent.

        Returns:
            Dict mapping agent_type to total tokens used.
        """
        return dict(self.agent_costs)


class BudgetExceededError(Exception):
    """Raised when token budget is exceeded."""
    pass


class TokenBudgetMonitor:
    """Monitor and enforce token budgets across research pipeline."""

    def __init__(self, max_tokens_per_task: int = 500_000):
        """Initialize TokenBudgetMonitor.

        Args:
            max_tokens_per_task: Maximum tokens allowed per task.
        """
        self.max_tokens_per_task = max_tokens_per_task
        self._task_budgets: dict[int, TokenBudget] = {}

    def get_budget(self, task_id: int) -> TokenBudget:
        """Get or create budget for a task.

        Args:
            task_id: The task ID.

        Returns:
            TokenBudget for the task.
        """
        if task_id not in self._task_budgets:
            self._task_budgets[task_id] = TokenBudget(max_tokens=self.max_tokens_per_task)
        return self._task_budgets[task_id]

    def record_usage(
        self,
        task_id: int,
        agent_type: str,
        input_tokens: int,
        output_tokens: int
    ) -> None:
        """Record token usage for a task.

        Args:
            task_id: The task ID.
            agent_type: The agent type.
            input_tokens: Input tokens used.
            output_tokens: Output tokens used.

        Raises:
            BudgetExceededError: If budget is exceeded.
        """
        budget = self.get_budget(task_id)
        budget.add_usage(agent_type, input_tokens, output_tokens)

    def check_budget(self, task_id: int, input_tokens: int, output_tokens: int) -> bool:
        """Check if tokens would be within budget.

        Args:
            task_id: The task ID.
            input_tokens: Input tokens to check.
            output_tokens: Output tokens to check.

        Returns:
            True if within budget, False otherwise.
        """
        budget = self.get_budget(task_id)
        return budget.check_within_budget(input_tokens, output_tokens)

    def get_task_summary(self, task_id: int) -> dict:
        """Get summary of token usage for a task.

        Args:
            task_id: The task ID.

        Returns:
            Dict with usage summary.
        """
        if task_id not in self._task_budgets:
            return {
                "task_id": task_id,
                "total_used": 0,
                "remaining": self.max_tokens_per_task,
                "by_agent": {},
                "within_budget": True
            }

        budget = self._task_budgets[task_id]
        return {
            "task_id": task_id,
            "total_used": budget.current_tokens,
            "remaining": budget.get_remaining(),
            "by_agent": budget.get_usage_by_agent(),
            "within_budget": budget.current_tokens <= budget.max_tokens,
            "max_budget": budget.max_tokens
        }

    def clear_task(self, task_id: int) -> None:
        """Clear budget tracking for a task.

        Args:
            task_id: The task ID to clear.
        """
        self._task_budgets.pop(task_id, None)
