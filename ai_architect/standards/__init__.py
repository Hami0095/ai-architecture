"""Deterministic, evidence-backed standards checking (CHECK-STANDARDS)."""
from .config import StandardsConfigError, load_config, parse_config
from .engine import deterministic_view, exit_code, public, run_check

__all__ = ["StandardsConfigError", "load_config", "parse_config", "run_check",
           "exit_code", "public", "deterministic_view"]
