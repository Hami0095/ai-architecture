from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Generator
import json
import logging
from ..data.orm import Base, DBSystemMetric, DBAuditReport, DBErrorLog
from .logging_utils import logger, retry, InfrastructureError
from .config_manager import config

class PersistenceLayer:
    """
    Handles data persistence using SQLAlchemy ORM with connection pooling.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(PersistenceLayer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_url: Optional[str] = None):
        if self._initialized:
            return
            
        self.db_url = db_url or config.get("database.url", "sqlite:///archai_data.db")
        self._init_engine()
        self._initialized = True

    def _init_engine(self):
        """Initializes the SQLAlchemy engine with connection pooling."""
        try:
            connect_args = {"check_same_thread": False} if "sqlite" in self.db_url else {}
            
            self.engine = create_engine(
                self.db_url,
                poolclass=QueuePool,
                pool_size=config.get("database.pool_size", 5),
                max_overflow=config.get("database.max_overflow", 10),
                connect_args=connect_args
            )
            
            # Create tables
            Base.metadata.create_all(self.engine)
            
            self.SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=self.engine))
            logger.info(f"Database engine initialized at {self.db_url}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise InfrastructureError(f"Database initialization failed: {e}")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    @retry(retries=3, delay=0.5, exceptions=(Exception,))
    def save_report(self, repo_path: str, report: Dict[str, Any]):
        """Saves an audit report using ORM."""
        with self.get_session() as session:
            db_report = DBAuditReport(
                repo_path=repo_path,
                report_json=report,
                goal=report.get("goal")
            )
            session.add(db_report)
            logger.info(f"Report saved for {repo_path}")

    @retry(retries=3, delay=0.1, exceptions=(Exception,))
    def save_metric(self, agent_name: str, latency: float, success: bool, error_type: str = None):
        """Saves agent execution metrics."""
        with self.get_session() as session:
            metric = DBSystemMetric(
                agent_name=agent_name,
                latency_ms=latency,
                success=success,
                error_type=error_type
            )
            session.add(metric)

    def log_error(self, module: str, severity: str, message: str, stack_trace: str = None):
        """Structured error logging to DB."""
        try:
            with self.get_session() as session:
                log_entry = DBErrorLog(
                    module=module,
                    severity=severity,
                    message=message,
                    stack_trace=stack_trace
                )
                session.add(log_entry)
        except Exception as e:
            # Fallback to file logging if DB fails
            logger.error(f"Failed to write error to DB: {e}")

    def get_latest_reports(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieves the latest audit reports."""
        with self.get_session() as session:
            reports = session.query(DBAuditReport).order_by(DBAuditReport.timestamp.desc()).limit(limit).all()
            return [
                {
                    "id": r.id, 
                    "repo_path": r.repo_path, 
                    "timestamp": r.timestamp.isoformat(), 
                    "report": r.report_json
                } 
                for r in reports
            ]
