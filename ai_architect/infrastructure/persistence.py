import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from .logging_utils import logger

class PersistenceLayer:
    """Handles data persistence using SQLite."""
    
    def __init__(self, db_path: str = "archai_data.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initializes the database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS audit_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        repo_path TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        report_json TEXT
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_name TEXT,
                        latency_ms REAL,
                        success BOOLEAN,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def save_report(self, repo_path: str, report: Dict[str, Any]):
        """Saves an audit report to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO audit_reports (repo_path, report_json) VALUES (?, ?)",
                    (repo_path, json.dumps(report))
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save report: {e}")

    def save_metric(self, agent_name: str, latency: float, success: bool):
        """Saves agent execution metrics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO system_metrics (agent_name, latency_ms, success) VALUES (?, ?, ?)",
                    (agent_name, latency, success)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save metric: {e}")

    def get_latest_reports(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieves the latest audit reports."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM audit_reports ORDER BY timestamp DESC LIMIT ?", (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to retrieve reports: {e}")
            return []
