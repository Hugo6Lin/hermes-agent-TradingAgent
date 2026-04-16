"""SQLite database schemas for research system."""
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

@dataclass
class ResearchDatabase:
    """Manages all research system SQLite databases."""

    db_path: str

    def __post_init__(self):
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Initialize research.db schema with tables: analysis_tasks, analyst_reports, debate_records, research_decisions, review_records, token_usage."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # analysis_tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                report_date TEXT NOT NULL,
                session TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                grade TEXT,
                composite_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # analyst_reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analyst_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                analyst_type TEXT NOT NULL,
                content TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                model_used TEXT NOT NULL,
                tokens_used INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES analysis_tasks(task_id)
            )
        """)

        # debate_records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS debate_records (
                debate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                debate_type TEXT NOT NULL,
                initial_position TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                final_consensus TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES analysis_tasks(task_id)
            )
        """)

        # research_decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_decisions (
                decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                decision_type TEXT NOT NULL,
                rationale TEXT NOT NULL,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES analysis_tasks(task_id)
            )
        """)

        # review_records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_records (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                reviewer_type TEXT NOT NULL,
                grade TEXT NOT NULL,
                comments TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES analysis_tasks(task_id)
            )
        """)

        # token_usage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                agent_type TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES analysis_tasks(task_id)
            )
        """)

        conn.commit()
        conn.close()

    def initialize_watchlist(self) -> None:
        """Initialize watchlist tables: watchlists, watchlist_items, alert_history."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # watchlists table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlists (
                list_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id TEXT DEFAULT 'default',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # watchlist_items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (list_id) REFERENCES watchlists(list_id),
                UNIQUE(list_id, symbol)
            )
        """)

        # alert_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (list_id) REFERENCES watchlists(list_id)
            )
        """)

        conn.commit()
        conn.close()

    def initialize_memory(self) -> None:
        """Initialize memory tables: stock_profiles, industry_memory, debate_learnings, memory_access_log."""
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

    def create_task(self, symbol: str, report_date: str, session: str) -> int:
        """Create new analysis task. Returns task_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO analysis_tasks (symbol, report_date, session) VALUES (?, ?, ?)",
            (symbol, report_date, session)
        )
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id

    def get_task(self, task_id: int) -> Optional[dict]:
        """Get task by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM analysis_tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return dict(row)

    def update_task_status(self, task_id: int, status: str, grade: str = None, composite_score: float = None) -> None:
        """Update task status, grade, and composite score."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if grade is not None and composite_score is not None:
            cursor.execute(
                "UPDATE analysis_tasks SET status = ?, grade = ?, composite_score = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                (status, grade, composite_score, task_id)
            )
        elif grade is not None:
            cursor.execute(
                "UPDATE analysis_tasks SET status = ?, grade = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                (status, grade, task_id)
            )
        elif composite_score is not None:
            cursor.execute(
                "UPDATE analysis_tasks SET status = ?, composite_score = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                (status, composite_score, task_id)
            )
        else:
            cursor.execute(
                "UPDATE analysis_tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                (status, task_id)
            )

        conn.commit()
        conn.close()

    def save_analyst_report(self, task_id: int, analyst_type: str, content: str, summary_json: str, model_used: str, tokens_used: int) -> int:
        """Save analyst report. Returns report_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO analyst_reports (task_id, analyst_type, content, summary_json, model_used, tokens_used) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, analyst_type, content, summary_json, model_used, tokens_used)
        )
        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return report_id

    def create_watchlist(self, name: str, user_id: str = "default") -> int:
        """Create a new watchlist. Returns list_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO watchlists (name, user_id) VALUES (?, ?)",
            (name, user_id)
        )
        list_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return list_id

    def add_to_watchlist(self, list_id: int, symbol: str, notes: str = None) -> int:
        """Add symbol to watchlist. Returns item_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO watchlist_items (list_id, symbol, notes) VALUES (?, ?, ?)",
            (list_id, symbol, notes)
        )
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return item_id

    def get_watchlist_items(self, list_id: int) -> list:
        """Get all items in a watchlist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM watchlist_items WHERE list_id = ? ORDER BY created_at",
            (list_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def record_token_usage(self, task_id: int, agent_type: str, model: str, input_tokens: int, output_tokens: int, cost: float) -> None:
        """Record token usage for a task."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO token_usage (task_id, agent_type, model, input_tokens, output_tokens, cost) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, agent_type, model, input_tokens, output_tokens, cost)
        )
        conn.commit()
        conn.close()

    def get_token_usage_summary(self, days: int = 30) -> dict:
        """Get token usage summary for the specified number of days."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=days)

        cursor.execute(
            """
            SELECT
                COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                COALESCE(SUM(cost), 0) as total_cost
            FROM token_usage
            WHERE created_at >= ?
            """,
            (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return {
                "total_tokens": 0,
                "total_cost": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0
            }

        return dict(row)
