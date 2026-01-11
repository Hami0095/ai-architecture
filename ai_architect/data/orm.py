from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class DBSystemMetric(Base):
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True)
    agent_name = Column(String(100), index=True)
    latency_ms = Column(Float)
    success = Column(Boolean)
    error_type = Column(String(100), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class DBAuditReport(Base):
    __tablename__ = 'audit_reports'
    
    id = Column(Integer, primary_key=True)
    repo_path = Column(String(500), index=True)
    report_json = Column(JSON) # Stores the full report structure
    goal = Column(String(200), nullable=True)
    success_score = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class DBErrorLog(Base):
    __tablename__ = 'error_logs'
    
    id = Column(Integer, primary_key=True)
    module = Column(String(100))
    severity = Column(String(20))
    message = Column(Text)
    stack_trace = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
