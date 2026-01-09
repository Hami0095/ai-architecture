import sqlite3
import json
from datetime import datetime
from .models import EvaluationMetric, ReconciliationResult

class DBClient:
    def __init__(self, db_path="system_metrics.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Metrics table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            valid_syntax BOOLEAN,
            tests_passed BOOLEAN,
            coverage_percent REAL,
            total_score REAL,
            details JSON,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Reconciliation decisions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            selected_strategy TEXT,
            rationale TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()

    def log_metrics(self, metrics: EvaluationMetric):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO metrics (run_id, valid_syntax, tests_passed, coverage_percent, total_score, details, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            metrics.run_id,
            metrics.valid_syntax,
            metrics.tests_passed,
            metrics.coverage_percent,
            metrics.total_score,
            json.dumps(metrics.details, default=str),
            datetime.now()
        ))
        conn.commit()
        conn.close()

    def log_decision(self, result: ReconciliationResult):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO decisions (selected_strategy, rationale, timestamp)
        VALUES (?, ?, ?)
        ''', (
            result.selected_strategy,
            result.rationale,
            result.timestamp
        ))
        conn.commit()
        conn.close()

    def get_latest_metrics(self, limit=5):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM metrics ORDER BY id DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
