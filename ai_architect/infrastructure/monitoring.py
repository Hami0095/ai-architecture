import time
from typing import Dict, Any, List
from .persistence import PersistenceLayer
from .logging_utils import logger

class MonitoringSystem:
    """Provides monitoring and observability for ArchAI agents and infrastructure."""
    
    def __init__(self, persistence: PersistenceLayer = None):
        self.persistence = persistence or PersistenceLayer()

    def get_system_health(self) -> Dict[str, Any]:
        """Calculates high-level health metrics from stored execution history."""
        metrics = self.persistence.get_latest_reports(limit=100) # Using latest reports as a proxy for activity
        
        # In a real system, we'd query the system_metrics table specifically
        # Let's add a method to persistence to get summary metrics
        
        summary = self._get_metrics_summary()
        
        return {
            "status": "Healthy" if summary.get("overall_success_rate", 0) > 0.8 else "Degraded",
            "metrics": summary,
            "timestamp": time.time()
        }

    def _get_metrics_summary(self) -> Dict[str, Any]:
        """Aggregates raw metrics into readable summaries."""
        try:
            import sqlite3
            with sqlite3.connect(self.persistence.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Average latency per agent
                cursor.execute("""
                    SELECT agent_name, AVG(latency_ms) as avg_latency, 
                           SUM(CASE WHEN success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
                    FROM system_metrics
                    GROUP BY agent_name
                """)
                agent_stats = [dict(row) for row in cursor.fetchall()]
                
                # Overall success rate
                cursor.execute("SELECT SUM(CASE WHEN success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) FROM system_metrics")
                overall_success = cursor.fetchone()[0] or 0.0
                
                return {
                    "overall_success_rate": overall_success,
                    "agent_performance": agent_stats
                }
        except Exception as e:
            logger.error(f"Monitoring aggregation failed: {e}")
            return {}

# Singleton instance
monitor = MonitoringSystem()
