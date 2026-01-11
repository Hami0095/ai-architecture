import time
from typing import Dict, Any, List
from sqlalchemy.sql import func
from .persistence import PersistenceLayer
from ..data.orm import DBSystemMetric
from .logging_utils import logger

class MonitoringSystem:
    """Provides monitoring and observability for ArchAI agents and infrastructure."""
    
    def __init__(self, persistence: PersistenceLayer = None):
        self.persistence = persistence or PersistenceLayer()

    def get_system_health(self) -> Dict[str, Any]:
        """Calculates high-level health metrics from stored execution history."""
        summary = self._get_metrics_summary()
        
        return {
            "status": "Healthy" if summary.get("overall_success_rate", 0) > 0.8 else "Degraded",
            "metrics": summary,
            "timestamp": time.time()
        }

    def _get_metrics_summary(self) -> Dict[str, Any]:
        """Aggregates raw metrics into readable summaries using ORM."""
        try:
            with self.persistence.get_session() as session:
                # Average latency and success rate per agent
                stats_query = session.query(
                    DBSystemMetric.agent_name,
                    func.avg(DBSystemMetric.latency_ms).label('avg_latency'),
                    (func.sum(func.case((DBSystemMetric.success.is_(True), 1), else_=0)) * 100.0 / func.count()).label('success_rate')
                ).group_by(DBSystemMetric.agent_name).all()
                
                agent_stats = [
                    {
                        "agent_name": row.agent_name,
                        "avg_latency": row.avg_latency,
                        "success_rate": row.success_rate
                    }
                    for row in stats_query
                ]

                # Overall success rate
                overall_query = session.query(
                    (func.sum(func.case((DBSystemMetric.success.is_(True), 1), else_=0)) * 100.0 / func.count())
                ).scalar()
                
                overall_success = overall_query or 0.0

                return {
                    "overall_success_rate": overall_success,
                    "agent_performance": agent_stats
                }
        except Exception as e:
            logger.error(f"Monitoring aggregation failed: {e}")
            return {}

# Singleton instance
monitor = MonitoringSystem()
