import os
import sys
import time
from typing import List, Dict, Any

class ConsoleUI:
    """Handles professional, authoritative terminal output for ArchAI."""

    @staticmethod
    def banner():
        banner_text = """
    ┌───────────────────────────────────────────────────────────────────────────┐
    │  ARCHAI: COMMAND-CENTER CONSOLE                                           │
    │  [PROFESSIONAL-GRADE ARCHITECTURAL INTELLIGENCE]                          │
    └───────────────────────────────────────────────────────────────────────────┘
        """
        print(banner_text)

    @staticmethod
    def system_info(data: Dict[str, Any]):
        print(f"  [SYSTEM STATE]")
        for k, v in data.items():
            print(f"  > {k:20}: {v}")
        print("-" * 77)

    @staticmethod
    def status_line(label: str, status: str, color: str = None):
        """Prints a professional status line."""
        # Simple status labels for now
        print(f"  [ {status:^10} ] {label}")

    @staticmethod
    def step_header(title: str, subtitle: str = None):
        print(f"\n  ## {title.upper()}")
        if subtitle:
            print(f"     {subtitle}")
        print("-" * 77)

    @staticmethod
    def progress_bar(label: str, duration: float = 1.0):
        """Simulates architectural analysis progress."""
        print(f"  {label:30} [", end="", flush=True)
        steps = 20
        for i in range(steps):
            time.sleep(duration / steps)
            print("■", end="", flush=True)
        print("] COMPLETE")

    @staticmethod
    def negotiate_contract() -> str:
        """Explicitly negotiates the Execution Authority Contract."""
        print("\n  [EXECUTION AUTHORITY CONTRACT]")
        print("  1. DIRECTED MODE  - Step-by-step approval for every architectural shift.")
        print("  2. DELEGATED MODE - ArchAI-controlled orchestration and execution.")
        
        while True:
            choice = input("\n  Select Operational Authority (1 or 2): ").strip()
            if choice == "1":
                return "directed"
            if choice == "2":
                return "delegated"
            print("  [ERROR] Sequential failure: Invalid selection. Operational authority must be explicitly granted.")

    @staticmethod
    def report_risk(issue: str, severity: str, confidence: float):
        colors = {"HIGH": "!", "MEDIUM": "*", "LOW": "-"}
        print(f"  [{colors.get(severity, '?')}] {severity:6} | {issue} (Conf: {confidence:.2f})")
