import os
import sys
import time
from typing import List, Dict, Any

class ConsoleUI:
    """Handles professional, authoritative terminal output for ArchAI."""

    @staticmethod
    def banner():
        banner_text = r"""
        ___            _       ___         
       / _ \          | |     / _ \ ( )
      / /_\ \_ __ ___ | |__  / /_\ \| |
      |  _  | '__/ __|| '_ \ |  _  || |
      | | | | | | (__ | | | || | | || |
      \_| |_/_|  \___||_| |_|\_| |_/|_| 
                                        
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
            print("A", end="", flush=True)
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

    @staticmethod
    def spinner(message: str = "Thinking"):
        """Context manager for a professional console spinner."""
        import threading
        import itertools
        
        class Spinner:
            def __init__(self, msg):
                self.msg = msg
                self.spinner_cycle = itertools.cycle(['[/a\\]', '[|a|]', '[\\a/]', '[-a-]'])
                self.stop_event = threading.Event()
                self.thread = threading.Thread(target=self._animate)

            def _animate(self):
                while not self.stop_event.is_set():
                    sys.stdout.write(f"\r  {next(self.spinner_cycle)} {self.msg}...")
                    sys.stdout.flush()
                    time.sleep(0.1)
                # Clear the line on stop
                sys.stdout.write("\r" + " " * (len(self.msg) + 10) + "\r")
                sys.stdout.flush()

            def __enter__(self):
                self.thread.start()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.stop_event.set()
                self.thread.join()

        return Spinner(message)
