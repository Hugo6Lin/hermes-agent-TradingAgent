"""Paper-trading helpers for Hermes signals."""

from agent.research_v1.data.database import ResearchDatabase


class PaperTradeEngine:
    """Create simulated trades from generated plans."""

    def __init__(self, database: ResearchDatabase):
        self.database = database

    def simulate_from_plan(self, signal_id: int, plan: dict) -> dict:
        """Persist a paper trade from a generated trade plan."""
        paper_trade_id = self.database.save_paper_trade(
            signal_id=signal_id,
            symbol=plan["symbol"],
            entry_price=plan["entry_zone"]["mid"],
            quantity=plan["suggested_position_size"],
            status="open",
        )
        return self.database.get_paper_trade(paper_trade_id)
