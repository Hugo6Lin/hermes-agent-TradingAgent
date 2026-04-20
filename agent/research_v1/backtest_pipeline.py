"""P1 backtest pipeline from persisted signals to persisted outcomes."""

from dataclasses import dataclass

from agent.research_v1.backtest import (
    compute_signal_outcomes,
    summarize_signal_outcomes,
    summarize_signal_outcomes_by_grade,
)
from agent.research_v1.data.database import ResearchDatabase


@dataclass
class BacktestPipeline:
    """Run historical backtests for persisted signals."""

    database: ResearchDatabase
    historical_data_source: object

    def backtest_signal(self, signal_id: int, start_date: str, end_date: str) -> dict:
        """Backtest one persisted signal and store computed outcomes."""
        signal = self.database.get_signal(signal_id)
        if signal is None:
            raise ValueError(f"Unknown signal_id: {signal_id}")

        price_points = self.historical_data_source.fetch_history(
            signal["symbol"],
            start_date=start_date,
            end_date=end_date,
        )
        computed_outcomes = compute_signal_outcomes(signal=signal, price_points=price_points)

        persisted_outcomes = []
        summary_by_horizon = {}
        for horizon, outcome in computed_outcomes.items():
            outcome_id = self.database.save_signal_outcome(
                signal_id=signal_id,
                horizon_days=horizon,
                exit_price=outcome["exit_price"],
                return_pct=outcome["return_pct"],
                max_drawdown_pct=outcome["max_drawdown_pct"],
                win=outcome["win"],
                gap_handled=outcome["gap_handled"],
            )
            persisted = dict(outcome)
            persisted["outcome_id"] = outcome_id
            persisted["horizon_days"] = horizon
            persisted_outcomes.append(persisted)
            summary_by_horizon[horizon] = summarize_signal_outcomes([outcome])

        return {
            "signal": signal,
            "persisted_outcomes": persisted_outcomes,
            "summary_by_horizon": summary_by_horizon,
        }

    def summarize_edge_by_grade(self, horizon_days: int | None = None) -> dict[str, dict]:
        """Summarize persisted outcomes by signal grade."""
        joined = self.database.get_signal_outcomes_with_grade(horizon_days=horizon_days)
        return summarize_signal_outcomes_by_grade(joined)
