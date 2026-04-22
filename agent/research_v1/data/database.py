"""SQLite database schemas for research system."""
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

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
        conn.execute("PRAGMA foreign_keys = ON")
        # Always store as UTF-8 and read as UTF-8 to avoid Windows cp1252/mbcs mis-decoding
        conn.execute("PRAGMA encoding = 'UTF-8'")
        conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
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

        # signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                symbol TEXT NOT NULL,
                grade TEXT NOT NULL,
                confidence REAL NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                holding_horizon TEXT NOT NULL,
                signal_valid_until TEXT NOT NULL,
                priority_score REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES analysis_tasks(task_id)
            )
        """)

        # price_snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                snapshot_type TEXT NOT NULL,
                captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
            )
        """)

        # signal_revisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_revisions (
                revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                previous_grade TEXT,
                new_grade TEXT NOT NULL,
                revision_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
            )
        """)

        # signal_outcomes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_outcomes (
                outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                horizon_days INTEGER NOT NULL,
                exit_price REAL NOT NULL,
                return_pct REAL NOT NULL,
                max_drawdown_pct REAL NOT NULL,
                win BOOLEAN NOT NULL,
                gap_handled BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
            )
        """)

        # positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                position_id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
            )
        """)

        # paper_trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_trades (
                paper_trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
            )
        """)

        conn.commit()
        conn.close()

    def initialize_batch_research(self) -> None:
        """Initialize batch research tables: research_batches, research_batch_items, company_reports."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_batches (
                batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                requested_tickers_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                boss_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_batch_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                display_rank INTEGER NOT NULL,
                overall_rating TEXT NOT NULL,
                confidence REAL NOT NULL,
                priority_score REAL NOT NULL,
                action TEXT NOT NULL,
                top_thesis TEXT NOT NULL,
                top_risk TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                holding_horizon TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (batch_id) REFERENCES research_batches(batch_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_item_id INTEGER NOT NULL,
                bottom_line TEXT NOT NULL,
                why_it_matters TEXT NOT NULL,
                action_plan TEXT NOT NULL,
                bull_case TEXT NOT NULL,
                risk_watch TEXT NOT NULL,
                research_summary TEXT NOT NULL,
                signal_snapshot_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (batch_item_id) REFERENCES research_batch_items(item_id)
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

        # Phase 16: structured watchlist_entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_entries (
                ticker TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                thesis_state TEXT NOT NULL,
                alert_level TEXT NOT NULL,
                current_action_bias TEXT NOT NULL,
                last_user_interest_at TEXT,
                last_research_at TEXT,
                next_review_date TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    def get_signal(self, signal_id: int) -> Optional[dict]:
        """Get signal by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signals WHERE signal_id = ?", (signal_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row is not None else None

    def list_recent_signals(self, limit: int = 20) -> list[dict]:
        """List recent signals ordered by newest first, then priority."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM signals
            ORDER BY created_at DESC, priority_score DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_signal_outcomes(self, signal_id: int) -> list[dict]:
        """Get all persisted outcomes for a signal ordered by horizon."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM signal_outcomes WHERE signal_id = ? ORDER BY horizon_days",
            (signal_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_signal_outcomes_with_grade(self, horizon_days: int | None = None) -> list[dict]:
        """Get persisted outcomes joined with signal grade."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if horizon_days is None:
            cursor.execute(
                """
                SELECT o.*, s.grade
                FROM signal_outcomes o
                JOIN signals s ON s.signal_id = o.signal_id
                ORDER BY o.horizon_days, o.outcome_id
                """
            )
        else:
            cursor.execute(
                """
                SELECT o.*, s.grade
                FROM signal_outcomes o
                JOIN signals s ON s.signal_id = o.signal_id
                WHERE o.horizon_days = ?
                ORDER BY o.outcome_id
                """,
                (horizon_days,),
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_position(self, position_id: int) -> Optional[dict]:
        """Get a tracked position by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions WHERE position_id = ?", (position_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row is not None else None

    def list_positions(self, status: str | None = None, limit: int = 50) -> list[dict]:
        """List tracked positions, optionally filtered by status."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if status is None:
            cursor.execute(
                "SELECT * FROM positions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM positions
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status, limit),
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_paper_trade(self, paper_trade_id: int) -> Optional[dict]:
        """Get a paper trade by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM paper_trades WHERE paper_trade_id = ?",
            (paper_trade_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row is not None else None

    def list_paper_trades(self, status: str | None = None, limit: int = 50) -> list[dict]:
        """List paper trades, optionally filtered by status."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if status is None:
            cursor.execute(
                "SELECT * FROM paper_trades ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM paper_trades
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status, limit),
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

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

    def save_signal(self, task_id: int, signal: dict) -> int:
        """Save a structured signal. Returns signal_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO signals (
                task_id, symbol, grade, confidence, entry_price, stop_loss,
                take_profit, holding_horizon, signal_valid_until, priority_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                signal["symbol"],
                signal["grade"],
                signal["confidence"],
                signal["entry_price"],
                signal["stop_loss"],
                signal["take_profit"],
                signal["holding_horizon"],
                signal["signal_valid_until"],
                signal["priority_score"],
            )
        )
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return signal_id

    def save_price_snapshot(
        self,
        signal_id: int,
        symbol: str,
        price: float,
        snapshot_type: str
    ) -> int:
        """Save a price snapshot linked to a signal. Returns snapshot_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO price_snapshots (signal_id, symbol, price, snapshot_type)
            VALUES (?, ?, ?, ?)
            """,
            (signal_id, symbol, price, snapshot_type)
        )
        snapshot_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return snapshot_id

    def save_signal_revision(
        self,
        signal_id: int,
        previous_grade: str | None,
        new_grade: str,
        revision_reason: str | None = None
    ) -> int:
        """Save a signal grade revision. Returns revision_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO signal_revisions (
                signal_id, previous_grade, new_grade, revision_reason
            ) VALUES (?, ?, ?, ?)
            """,
            (signal_id, previous_grade, new_grade, revision_reason)
        )
        revision_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return revision_id

    def save_signal_bundle(self, task_id: int, grade_result: dict) -> dict:
        """Persist a grade result's signal and its entry price snapshot."""
        signal_payload = dict(grade_result["signal"])
        signal_payload["grade"] = grade_result["grade"]

        signal_id = self.save_signal(task_id=task_id, signal=signal_payload)
        snapshot_id = self.save_price_snapshot(
            signal_id=signal_id,
            symbol=signal_payload["symbol"],
            price=signal_payload["entry_price"],
            snapshot_type="signal_entry",
        )

        return {
            "signal_id": signal_id,
            "snapshot_id": snapshot_id,
        }

    def save_signal_outcome(
        self,
        signal_id: int,
        horizon_days: int,
        exit_price: float,
        return_pct: float,
        max_drawdown_pct: float,
        win: bool,
        gap_handled: bool
    ) -> int:
        """Persist a computed signal outcome. Returns outcome_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO signal_outcomes (
                signal_id, horizon_days, exit_price, return_pct,
                max_drawdown_pct, win, gap_handled
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                horizon_days,
                exit_price,
                return_pct,
                max_drawdown_pct,
                int(win),
                int(gap_handled),
            )
        )
        outcome_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return outcome_id

    def open_position(
        self,
        signal_id: int,
        symbol: str,
        entry_price: float,
        quantity: float,
        stop_loss: float,
        take_profit: float,
        status: str,
    ) -> int:
        """Persist an opened position generated from a trade plan."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO positions (
                signal_id, symbol, entry_price, quantity,
                stop_loss, take_profit, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (signal_id, symbol, entry_price, quantity, stop_loss, take_profit, status),
        )
        position_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return position_id

    def save_paper_trade(
        self,
        signal_id: int,
        symbol: str,
        entry_price: float,
        quantity: float,
        status: str,
    ) -> int:
        """Persist a simulated trade for paper-trading validation."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO paper_trades (
                signal_id, symbol, entry_price, quantity, status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (signal_id, symbol, entry_price, quantity, status),
        )
        paper_trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return paper_trade_id

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

    def save_watchlist_entry(self, entry: Any) -> None:
        """
        Save or update a structured WatchlistEntry (Phase 16).

        Uses INSERT OR REPLACE so updates work as upserts.
        """
        from agent.research_v1.contracts import WatchlistEntry

        if not isinstance(entry, WatchlistEntry):
            raise TypeError(f"entry must be a WatchlistEntry; got {type(entry).__name__}")

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO watchlist_entries
            (ticker, status, thesis_state, alert_level, current_action_bias,
             last_user_interest_at, last_research_at, next_review_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            entry.ticker,
            entry.status,
            entry.thesis_state,
            entry.alert_level,
            entry.current_action_bias,
            entry.last_user_interest_at,
            entry.last_research_at,
            entry.next_review_date,
        ))
        conn.commit()
        conn.close()

    def list_watchlist_entries(self) -> list[dict]:
        """List all structured watchlist entries (Phase 16)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM watchlist_entries ORDER BY updated_at DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def list_recent_alerts(self, unread_only: bool = False, limit: int = 50) -> list[dict]:
        """List recent alerts across watchlists."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            if unread_only:
                cursor.execute(
                    """
                    SELECT * FROM alert_history
                    WHERE is_read = 0
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM alert_history
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):
                return []
            raise
        finally:
            conn.close()

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

    # --- Canonical research core ---

    def initialize_research_core(self) -> None:
        """Initialize canonical object tables: research_tasks, subagent_tasks, evidence_items, judge_packets, canonical_signals, canonical_reports."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_tasks (
                task_id TEXT PRIMARY KEY,
                request_text TEXT NOT NULL,
                task_type TEXT NOT NULL,
                tickers_json TEXT NOT NULL,
                markets_json TEXT NOT NULL DEFAULT '[]',
                research_mode TEXT NOT NULL DEFAULT 'standard',
                time_horizon TEXT NOT NULL DEFAULT '',
                output_mode TEXT NOT NULL DEFAULT 'signal_and_report',
                constraints_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subagent_tasks (
                subtask_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                ticker TEXT NOT NULL,
                objective TEXT NOT NULL,
                required_context_json TEXT NOT NULL DEFAULT '{}',
                expected_schema_json TEXT NOT NULL DEFAULT '{}',
                priority INTEGER NOT NULL DEFAULT 1,
                deadline_hint TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES research_tasks(task_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_items (
                evidence_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                subtask_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                claim_type TEXT NOT NULL DEFAULT 'factual',
                claim TEXT NOT NULL,
                value_json TEXT NOT NULL DEFAULT 'null',
                confidence REAL NOT NULL DEFAULT 0.0,
                direction TEXT NOT NULL DEFAULT 'neutral',
                importance TEXT NOT NULL DEFAULT 'medium',
                source_refs_json TEXT NOT NULL DEFAULT '[]',
                raw_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES research_tasks(task_id),
                FOREIGN KEY (subtask_id) REFERENCES subagent_tasks(subtask_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS judge_packets (
                packet_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                task_summary TEXT NOT NULL,
                evidence_bundle_json TEXT NOT NULL,
                required_outputs_json TEXT NOT NULL DEFAULT '[]',
                conflict_flags_json TEXT NOT NULL DEFAULT '[]',
                missing_steps_json TEXT NOT NULL DEFAULT '[]',
                orchestrator_notes TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES research_tasks(task_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canonical_signals (
                signal_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                rating TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.0,
                priority_score REAL NOT NULL DEFAULT 0.0,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                holding_horizon TEXT NOT NULL DEFAULT '',
                signal_valid_until TIMESTAMP,
                risk_flags_json TEXT NOT NULL DEFAULT '[]',
                decision_reason TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES research_tasks(task_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canonical_reports (
                report_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                title TEXT NOT NULL,
                executive_summary TEXT NOT NULL DEFAULT '',
                bottom_line TEXT NOT NULL DEFAULT '',
                why_now TEXT NOT NULL DEFAULT '',
                bull_case TEXT NOT NULL DEFAULT '',
                bear_case TEXT NOT NULL DEFAULT '',
                trade_plan_json TEXT NOT NULL DEFAULT 'null',
                risk_watch_json TEXT NOT NULL DEFAULT '[]',
                key_evidence_json TEXT NOT NULL DEFAULT '[]',
                appendix_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES research_tasks(task_id)
            )
        """)

        conn.commit()
        conn.close()

    def save_research_task(self, task: "ResearchTask") -> None:
        """Persist a ResearchTask record so child tables (canonical_signals, etc.) satisfy FK constraints."""
        import json
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO research_tasks (
                    task_id, request_text, task_type, tickers_json, markets_json,
                    research_mode, time_horizon, output_mode, constraints_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.request_text,
                    task.task_type.value,
                    json.dumps(task.tickers),
                    json.dumps(task.markets),
                    task.research_mode.value,
                    task.time_horizon,
                    task.output_mode.value,
                    json.dumps(task.constraints),
                    task.status.value,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def save_canonical_signal(self, signal: "CanonicalSignal", task_id: str) -> str:
        """Persist a CanonicalSignal. Returns signal_id."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            signal_id = f"signal_{task_id}_{signal.ticker}"
            cursor.execute(
                """
                INSERT INTO canonical_signals (
                    signal_id, task_id, ticker, rating, confidence, priority_score,
                    entry_price, stop_loss, take_profit, holding_horizon,
                    signal_valid_until, risk_flags_json, decision_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal_id,
                    task_id,
                    signal.ticker,
                    signal.rating,
                    signal.confidence,
                    signal.priority_score,
                    signal.entry_price,
                    signal.stop_loss,
                    signal.take_profit,
                    signal.holding_horizon,
                    signal.signal_valid_until.isoformat() if signal.signal_valid_until else None,
                    json.dumps(signal.risk_flags),
                    signal.decision_reason,
                )
            )
            conn.commit()
            return signal_id
        finally:
            conn.close()

    def save_canonical_report(self, report: "CanonicalReport", task_id: str, ticker: str) -> str:
        """Persist a CanonicalReport. Returns report_id."""
        from dataclasses import asdict
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Migrate schema if decision object columns don't exist
            try:
                cursor.execute(
                    "SELECT decision_card_json FROM canonical_reports WHERE 1=0"
                )
            except sqlite3.OperationalError:
                # Columns missing — add them
                cursor.execute(
                    "ALTER TABLE canonical_reports ADD COLUMN decision_card_json TEXT NOT NULL DEFAULT 'null'"
                )
                cursor.execute(
                    "ALTER TABLE canonical_reports ADD COLUMN instrument_rec_json TEXT NOT NULL DEFAULT 'null'"
                )
                cursor.execute(
                    "ALTER TABLE canonical_reports ADD COLUMN options_structure_json TEXT NOT NULL DEFAULT 'null'"
                )
                cursor.execute(
                    "ALTER TABLE canonical_reports ADD COLUMN early_exit_json TEXT NOT NULL DEFAULT 'null'"
                )
                conn.commit()

            report_id = f"report_{task_id}_{report.title[:20].replace(' ', '_')}"
            trade_plan_dict = None
            if report.trade_plan is not None:
                tp = report.trade_plan
                trade_plan_dict = {
                    "action": tp.action,
                    "entry_price": tp.entry_price,
                    "stop_loss": tp.stop_loss,
                    "take_profit": tp.take_profit,
                    "size_hint": tp.size_hint,
                    "holding_period": tp.holding_period,
                }

            # Serialize decision objects (Phase 14-17)
            def to_dict(obj):
                if obj is None:
                    return None
                if isinstance(obj, dict):
                    return obj
                if hasattr(obj, "__dataclass_fields__"):
                    return asdict(obj)
                return str(obj)

            decision_card_dict = to_dict(report.decision_card)
            instrument_rec_dict = to_dict(report.instrument_rec)
            options_structure_dict = to_dict(report.options_structure)
            early_exit_dict = to_dict(report.early_exit)

            cursor.execute(
                """
                INSERT INTO canonical_reports (
                    report_id, task_id, ticker, title, executive_summary,
                    bottom_line, why_now, bull_case, bear_case,
                    trade_plan_json, risk_watch_json, key_evidence_json, appendix_json,
                    decision_card_json, instrument_rec_json, options_structure_json, early_exit_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    task_id,
                    ticker,
                    report.title,
                    report.executive_summary,
                    report.bottom_line,
                    report.why_now,
                    report.bull_case,
                    report.bear_case,
                    json.dumps(trade_plan_dict),
                    json.dumps(report.risk_watch),
                    json.dumps(report.key_evidence),
                    json.dumps(report.appendix),
                    json.dumps(decision_card_dict),
                    json.dumps(instrument_rec_dict),
                    json.dumps(options_structure_dict),
                    json.dumps(early_exit_dict),
                )
            )
            conn.commit()
            return report_id
        finally:
            conn.close()

    def list_canonical_signals(self, limit: int = 20) -> list[dict]:
        """List canonical signals ordered by newest first."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM canonical_signals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        results = []
        for row in rows:
            d = dict(row)
            d['risk_flags'] = json.loads(d.pop('risk_flags_json', '[]'))
            results.append(d)
        return results

    # -------------------------------------------------------------------------
    # Phase 17: Validation results
    # -------------------------------------------------------------------------

    def save_validation_result(self, result: Any) -> None:
        """
        Persist a ValidationResult to the validation_results table.

        Uses INSERT OR REPLACE so re-running research on the same ticker
        updates the validation entry.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation_results (
                ticker TEXT PRIMARY KEY,
                regime TEXT NOT NULL,
                historical_support TEXT NOT NULL,
                environment_fit TEXT NOT NULL,
                main_failure_mode TEXT NOT NULL,
                validation_confidence REAL NOT NULL,
                notes TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT OR REPLACE INTO validation_results
            (ticker, regime, historical_support, environment_fit, main_failure_mode, validation_confidence, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            result.ticker,
            result.regime,
            result.historical_support,
            result.environment_fit,
            result.main_failure_mode,
            result.validation_confidence,
            result.notes,
        ))
        conn.commit()
        conn.close()

    def list_validation_results(self, limit: int = 20) -> list[dict]:
        """List validation results ordered by newest first."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM validation_results ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def list_canonical_reports(self, limit: int = 20) -> list[dict]:
        """List canonical reports ordered by newest first."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM canonical_reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        results = []
        for row in rows:
            d = dict(row)
            d['trade_plan'] = json.loads(d.pop('trade_plan_json', 'null'))
            d['risk_watch'] = json.loads(d.pop('risk_watch_json', '[]'))
            d['key_evidence'] = json.loads(d.pop('key_evidence_json', '[]'))
            d['appendix'] = json.loads(d.pop('appendix_json', '{}'))
            results.append(d)
        return results

    def get_canonical_reports_by_task(self, task_id: str) -> list[dict]:
        """Get all canonical reports for a research task."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM canonical_reports WHERE task_id = ? ORDER BY created_at DESC",
            (task_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        results = []
        for row in rows:
            d = dict(row)
            d['trade_plan'] = json.loads(d.pop('trade_plan_json', 'null'))
            d['risk_watch'] = json.loads(d.pop('risk_watch_json', '[]'))
            d['key_evidence'] = json.loads(d.pop('key_evidence_json', '[]'))
            d['appendix'] = json.loads(d.pop('appendix_json', '{}'))
            # Phase 14-17: deserialize decision objects
            d['decision_card'] = json.loads(d.pop('decision_card_json', 'null') or 'null')
            d['instrument_rec'] = json.loads(d.pop('instrument_rec_json', 'null') or 'null')
            d['options_structure'] = json.loads(d.pop('options_structure_json', 'null') or 'null')
            d['early_exit'] = json.loads(d.pop('early_exit_json', 'null') or 'null')
            results.append(d)
        return results

    # --- Batch research persistence ---

    def save_research_batch_payload(self, payload: dict) -> dict:
        """Persist a structured batch payload. Returns dict with batch_id, item_ids, report_ids."""
        import json
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Ensure batch tables exist
            self.initialize_batch_research()

            title = payload["title"]
            tickers = payload["tickers"]
            status = payload.get("status", "completed")
            boss_summary = payload.get("boss_summary", "")

            cursor.execute(
                """
                INSERT INTO research_batches (title, requested_tickers_json, status, boss_summary)
                VALUES (?, ?, ?, ?)
                """,
                (title, json.dumps([t["symbol"] for t in tickers]), status, boss_summary),
            )
            batch_id = cursor.lastrowid

            item_ids = []
            report_ids = []

            for ticker_data in tickers:
                cursor.execute(
                    """
                    INSERT INTO research_batch_items (
                        batch_id, symbol, display_rank, overall_rating, confidence,
                        priority_score, action, top_thesis, top_risk,
                        entry_price, stop_loss, take_profit, holding_horizon
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        ticker_data["symbol"],
                        ticker_data["display_rank"],
                        ticker_data["overall_rating"],
                        ticker_data["confidence"],
                        ticker_data["priority_score"],
                        ticker_data["action"],
                        ticker_data["top_thesis"],
                        ticker_data["top_risk"],
                        ticker_data["entry_price"],
                        ticker_data["stop_loss"],
                        ticker_data["take_profit"],
                        ticker_data["holding_horizon"],
                    ),
                )
                item_id = cursor.lastrowid
                item_ids.append(item_id)

                report_data = ticker_data["report"]
                cursor.execute(
                    """
                    INSERT INTO company_reports (
                        batch_item_id, bottom_line, why_it_matters, action_plan,
                        bull_case, risk_watch, research_summary, signal_snapshot_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        report_data["bottom_line"],
                        report_data["why_it_matters"],
                        report_data["action_plan"],
                        report_data["bull_case"],
                        json.dumps(report_data["risk_watch"]) if isinstance(report_data["risk_watch"], list) else report_data["risk_watch"],
                        report_data["research_summary"],
                        json.dumps(report_data["signal_snapshot_json"]) if isinstance(report_data["signal_snapshot_json"], dict) else report_data["signal_snapshot_json"],
                    ),
                )
                report_ids.append(cursor.lastrowid)

            conn.commit()
            return {
                "batch_id": batch_id,
                "item_ids": item_ids,
                "report_ids": report_ids,
            }
        finally:
            conn.close()

    def create_research_batch(
        self,
        title: str,
        requested_tickers: list[str],
        boss_summary: str = "",
        status: str = "completed",
    ) -> int:
        """Create a new research batch. Returns the new batch_id."""
        import json
        self.initialize_batch_research()
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO research_batches (title, requested_tickers_json, status, boss_summary)
                VALUES (?, ?, ?, ?)
                """,
                (title, json.dumps(requested_tickers), status, boss_summary),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_research_batch_item(
        self,
        batch_id: int,
        symbol: str,
        display_rank: int,
        overall_rating: str,
        confidence: float,
        priority_score: float,
        action: str,
        top_thesis: str,
        top_risk: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        holding_horizon: str,
    ) -> int:
        """Add a ticker item to an existing research batch. Returns the new item_id."""
        self.initialize_batch_research()
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO research_batch_items (
                    batch_id, symbol, display_rank, overall_rating, confidence,
                    priority_score, action, top_thesis, top_risk,
                    entry_price, stop_loss, take_profit, holding_horizon
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id, symbol, display_rank, overall_rating, confidence,
                    priority_score, action, top_thesis, top_risk,
                    entry_price, stop_loss, take_profit, holding_horizon,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def save_company_report(
        self,
        batch_item_id: int,
        bottom_line: str,
        why_it_matters: str,
        action_plan: str,
        bull_case: str,
        risk_watch: str,
        research_summary: str,
        signal_snapshot_json: str,
    ) -> int:
        """Save a company report for a batch item. Returns the new report_id."""
        self.initialize_batch_research()
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO company_reports (
                    batch_item_id, bottom_line, why_it_matters, action_plan,
                    bull_case, risk_watch, research_summary, signal_snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_item_id, bottom_line, why_it_matters, action_plan,
                    bull_case, risk_watch, research_summary, signal_snapshot_json,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_research_batch(self, batch_id: int) -> Optional[dict]:
        """Get a research batch by ID."""
        import json
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM research_batches WHERE batch_id = ?", (batch_id,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        d = dict(row)
        d["requested_tickers"] = json.loads(d.pop("requested_tickers_json", "[]"))
        return d

    def get_research_batch_with_items_and_reports(self, batch_id: int) -> Optional[dict]:
        """Get a research batch with its items and reports."""
        import json
        batch = self.get_research_batch(batch_id)
        if batch is None:
            return None
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM research_batch_items WHERE batch_id = ? ORDER BY display_rank ASC",
                (batch_id,),
            )
            items = []
            for item_row in cursor.fetchall():
                item = dict(item_row)
                cursor.execute(
                    "SELECT * FROM company_reports WHERE batch_item_id = ? ORDER BY report_id DESC LIMIT 1",
                    (item["item_id"],),
                )
                report_row = cursor.fetchone()
                item["report"] = dict(report_row) if report_row else None
                items.append(item)
            batch = dict(batch)
            batch["items"] = items
            return batch
        finally:
            conn.close()

    def list_research_batch_items(self, batch_id: int) -> list[dict]:
        """List all items for a research batch."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM research_batch_items WHERE batch_id = ? ORDER BY display_rank ASC",
            (batch_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_company_report(self, report_id: int) -> Optional[dict]:
        """Get a company report by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM company_reports WHERE report_id = ?", (report_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
