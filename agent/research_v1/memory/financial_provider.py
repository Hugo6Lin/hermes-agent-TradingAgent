"""Financial memory provider for Hermes Agent.

Integrates with Hermes Agent's MemoryManager system.
Stores stock profiles, industry memory, and debate learnings.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider


class FinancialMemoryProvider(MemoryProvider):
    """External memory provider for financial research.

    Integrates with Hermes Agent's MemoryManager system.
    Stores stock profiles, industry memory, and debate learnings.
    """

    name = "financial"

    def __init__(self, db_path: str):
        """Initialize the financial memory provider.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = _ResearchDatabaseWrapper(db_path)
        self.db.initialize_memory()

    def is_available(self) -> bool:
        """Return True if this provider is configured and ready."""
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize for a session.

        Called once at agent startup by MemoryManager.
        """
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return tool schemas for Hermes Agent memory system."""
        return [
            {
                "name": "get_stock_profile",
                "description": "Get stock profile and analysis history for a symbol",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"}
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "update_stock_profile",
                "description": "Update stock profile after analysis completes",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "grade": {"type": "string"},
                        "summary": {"type": "string"},
                        "concerns": {"type": "array", "items": {"type": "string"}},
                        "highlights": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "get_industry_memory",
                "description": "Get industry memory for a sector",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "industry": {"type": "string"},
                        "quarter": {"type": "string"}
                    },
                    "required": ["industry"]
                }
            },
            {
                "name": "get_debate_learnings",
                "description": "Get debate learnings for a symbol",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"}
                    },
                    "required": ["symbol"]
                }
            }
        ]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        """Route tool calls to appropriate methods."""
        handlers = {
            "get_stock_profile": self.get_stock_profile,
            "update_stock_profile": self.update_stock_profile,
            "get_industry_memory": self.get_industry_memory,
            "get_debate_learnings": self.get_debate_learnings
        }
        handler = handlers.get(tool_name)
        if handler:
            return json.dumps(handler(**args))
        return "{}"

    def get_stock_profile(self, symbol: str) -> Dict[str, Any]:
        """Get stock profile from memory.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            Dictionary with stock profile data.
        """
        return self.db.get_stock_profile(symbol)

    def update_stock_profile(self, symbol: str, grade: str = None, summary: str = None,
                           concerns: List[str] = None, highlights: List[str] = None) -> Dict[str, Any]:
        """Update stock profile in memory.

        Args:
            symbol: Stock ticker symbol.
            grade: Letter grade (A, B, C, D, F).
            summary: Text summary of the analysis.
            concerns: List of concerns.
            highlights: List of highlights.

        Returns:
            Dictionary with the updated profile.
        """
        return self.db.update_stock_profile(symbol, grade, summary, concerns, highlights)

    def get_industry_memory(self, industry: str, quarter: str = None) -> Dict[str, Any]:
        """Get industry memory.

        Args:
            industry: Industry/sector name.
            quarter: Optional quarter (e.g., "Q1-2024").

        Returns:
            Dictionary with industry memory data.
        """
        return self.db.get_industry_memory(industry, quarter)

    def get_debate_learnings(self, symbol: str) -> Dict[str, Any]:
        """Get debate learnings for symbol.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            Dictionary with debate learnings.
        """
        return self.db.get_debate_learnings(symbol)

    def prefetch(self, query: str, session_id: str = "") -> str:
        """Called by MemoryManager to prefetch relevant memories.

        Returns empty string as no prefetch implementation is needed.
        """
        return ""

    def sync_turn(self, user_content: str, assistant_content: str, session_id: str = "") -> None:
        """Called by MemoryManager after each turn.

        No-op for this provider.
        """
        pass

    def system_prompt_block(self) -> str:
        """Return system prompt addition for memory context.

        Returns empty string as no additional prompt is needed.
        """
        return ""


class _ResearchDatabaseWrapper:
    """Wrapper around ResearchDatabase providing stock profile methods.

    Uses raw SQL queries to access the memory tables since ResearchDatabase
    doesn't have methods for all memory table operations.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_memory(self) -> None:
        """Initialize memory tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # stock_profiles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                company_name TEXT,
                industry TEXT,
                market_cap REAL,
                profile_data_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # industry_memory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS industry_memory (
                memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                industry TEXT NOT NULL,
                key_insights_json TEXT NOT NULL,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # debate_learnings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS debate_learnings (
                learning_id INTEGER PRIMARY KEY AUTOINCREMENT,
                debate_topic TEXT NOT NULL,
                winning_argument TEXT NOT NULL,
                key_points_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # memory_access_log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_access_log (
                access_id INTEGER PRIMARY KEY AUTOINCREMENT,
                access_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def get_stock_profile(self, symbol: str) -> Dict[str, Any]:
        """Get stock profile from memory.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            Dictionary with stock profile data, or empty dict if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM stock_profiles WHERE symbol = ?",
            (symbol,)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return {}

        profile = dict(row)
        # Parse profile_data_json if present
        if profile.get("profile_data_json"):
            try:
                profile["profile_data"] = json.loads(profile["profile_data_json"])
            except json.JSONDecodeError:
                pass

        return profile

    def update_stock_profile(self, symbol: str, grade: str = None, summary: str = None,
                            concerns: List[str] = None, highlights: List[str] = None) -> Dict[str, Any]:
        """Update or create stock profile in memory.

        Args:
            symbol: Stock ticker symbol.
            grade: Letter grade.
            summary: Text summary.
            concerns: List of concerns.
            highlights: List of highlights.

        Returns:
            Dictionary with the updated profile.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Build profile_data structure
        profile_data = {}
        if grade:
            profile_data["grade"] = grade
        if summary:
            profile_data["summary"] = summary
        if concerns:
            profile_data["concerns"] = concerns
        if highlights:
            profile_data["highlights"] = highlights

        profile_data_json = json.dumps(profile_data) if profile_data else None

        # Check if profile exists
        cursor.execute(
            "SELECT profile_id FROM stock_profiles WHERE symbol = ?",
            (symbol,)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing profile
            cursor.execute("""
                UPDATE stock_profiles
                SET profile_data_json = COALESCE(?, profile_data_json),
                    updated_at = CURRENT_TIMESTAMP
                WHERE symbol = ?
            """, (profile_data_json, symbol))
        else:
            # Insert new profile
            cursor.execute("""
                INSERT INTO stock_profiles (symbol, profile_data_json)
                VALUES (?, ?)
            """, (symbol, profile_data_json))

        conn.commit()
        conn.close()

        return self.get_stock_profile(symbol)

    def get_industry_memory(self, industry: str, quarter: str = None) -> Dict[str, Any]:
        """Get industry memory.

        Args:
            industry: Industry/sector name.
            quarter: Optional quarter filter.

        Returns:
            Dictionary with industry memory data, or empty dict if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM industry_memory WHERE industry = ? ORDER BY created_at DESC LIMIT 1",
            (industry,)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return {}

        memory = dict(row)
        # Parse key_insights_json if present
        if memory.get("key_insights_json"):
            try:
                memory["key_insights"] = json.loads(memory["key_insights_json"])
            except json.JSONDecodeError:
                pass

        return memory

    def get_debate_learnings(self, symbol: str) -> Dict[str, Any]:
        """Get debate learnings for a symbol.

        Note: The debate_learnings table uses debate_topic, not symbol.
        We search for debates where the topic contains the symbol.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            Dictionary with debate learnings, or empty dict if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM debate_learnings WHERE debate_topic LIKE ? ORDER BY created_at DESC",
            (f"%{symbol}%",)
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {}

        # Return a list of learnings
        learnings = []
        for row in rows:
            learning = dict(row)
            if learning.get("key_points_json"):
                try:
                    learning["key_points"] = json.loads(learning["key_points_json"])
                except json.JSONDecodeError:
                    pass
            learnings.append(learning)

        return {"learnings": learnings, "symbol": symbol}