"""Structured ingest helpers for boss-facing research batches."""

from typing import Any

from agent.research_v1.data.database import ResearchDatabase


def save_batch_research(database: ResearchDatabase, payload: dict[str, Any]) -> dict[str, Any]:
    """Persist a structured batch payload into batch, item, and report tables."""
    # Ensure batch tables exist even if validation fails (test expects tables to exist after error)
    database.initialize_batch_research()
    tickers = payload.get("tickers")
    if not isinstance(tickers, list) or not tickers:
        raise ValueError("tickers must be a non-empty list")

    return database.save_research_batch_payload(payload)
