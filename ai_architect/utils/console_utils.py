import os
import sys
import time
from typing import List, Dict, Any, Tuple

# ArchAI orange, plus the shades used for the logo gradient (light to deep).
ORANGE = (255, 122, 26)
_GRADIENT = [(255, 167, 77), (255, 146, 51), (255, 122, 26), (247, 103, 7), (232, 89, 12), (204, 74, 8)]

# "ARCHAI" in an ANSI Shadow style block font.
_LOGO = [
    " █████╗ ██████╗  ██████╗██╗  ██╗ █████╗ ██╗",
    "██╔══██╗██╔══██╗██╔════╝██║  ██║██╔══██╗██║",
    "███████║██████╔╝██║     ███████║███████║██║",
    "██╔══██║██╔══██╗██║     ██╔══██║██╔══██║██║",
    "██║  ██║██║  ██║╚██████╗██║  ██║██║  ██║██║",
    "╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝",
]
# Fallback for consoles whose code page has no block characters.
_LOGO_ASCII = [
    r"    ___              __    ___    ____",
    r"   /   |  __________/ /_  /   |  /  _/",
    r"  / /| | / ___/ ___/ __ \/ /| |  / /  ",
    r" / ___ |/ /  / /__/ / / / ___ |_/ /   ",
    r"/_/  |_/_/   \___/_/ /_/_/  |_/___/   ",
]
TAGLINE = "Understand the code. Check the rules. Prove the findings."

_vt_enabled = None


def _enable_windows_vt() -> bool:
    """Turns on ANSI escape processing for the Windows console (once)."""
    global _vt_enabled
    if _vt_enabled is not None:
        return _vt_enabled
    _vt_enabled = True
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            _vt_enabled = False
    return _vt_enabled


def color_enabled(stream=None) -> bool:
    """Color only for a real terminal; NO_COLOR disables, FORCE_COLOR enables."""
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not getattr(stream, "isatty", lambda: False)():
        return False
    return _enable_windows_vt()


def unicode_enabled(stream=None) -> bool:
    encoding = getattr(stream or sys.stdout, "encoding", None) or "ascii"
    try:
        "█╗⠋▌".encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def _truecolor() -> bool:
    return (os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
            or "WT_SESSION" in os.environ
            or os.environ.get("TERM_PROGRAM", "") in ("vscode", "iTerm.app", "WezTerm", "Hyper"))


def _fg(rgb: Tuple[int, int, int]) -> str:
    if _truecolor():
        return "\x1b[38;2;{};{};{}m".format(*rgb)
    return "\x1b[38;5;208m"  # closest 256-color orange


def _bg(rgb: Tuple[int, int, int]) -> str:
    if _truecolor():
        return "\x1b[48;2;{};{};{}m".format(*rgb)
    return "\x1b[48;5;208m"


def paint(text: str, rgb: Tuple[int, int, int] = ORANGE, bold: bool = False) -> str:
    if not color_enabled():
        return text
    return ("\x1b[1m" if bold else "") + _fg(rgb) + text + "\x1b[0m"


class ConsoleUI:
    """Terminal output for ArchAI: orange brand, real animations, plain text when piped."""

    @staticmethod
    def accent(text: str, bold: bool = True) -> str:
        return paint(text, ORANGE, bold)

    @staticmethod
    def dim(text: str) -> str:
        return f"\x1b[2m{text}\x1b[0m" if color_enabled() else text

    @staticmethod
    def label(text: str) -> str:
        """Inverted orange tab, like a window title bar."""
        if not color_enabled():
            return f"[{text}]"
        return "\x1b[1m\x1b[30m" + _bg(ORANGE) + f" {text} \x1b[0m"

    @staticmethod
    def banner():
        logo = _LOGO if unicode_enabled() else _LOGO_ASCII
        print()
        for i, line in enumerate(logo):
            print("  " + paint(line, _GRADIENT[min(i, len(_GRADIENT) - 1)], bold=True))
        bar = "▌" if unicode_enabled() else "|"
        print(f"\n  {ConsoleUI.accent(bar)} {TAGLINE}")
        print(f"  {ConsoleUI.accent(bar)} " + ConsoleUI.dim("Command-center console. Type HELP for commands, EXIT to leave.") + "\n")

    @staticmethod
    def system_info(data: Dict[str, Any]):
        print(f"  {ConsoleUI.label('SYSTEM STATE')}")
        for k, v in data.items():
            print(f"  > {k:20}: {v}")
        print("-" * 77)

    @staticmethod
    def status_line(label: str, status: str, color: str = None):
        """Prints a professional status line."""
        print(f"  [ {status:^10} ] {label}")

    @staticmethod
    def step_header(title: str, subtitle: str = None):
        print(f"\n  {ConsoleUI.accent('##')} {ConsoleUI.accent(title.upper())}")
        if subtitle:
            print(f"     {ConsoleUI.dim(subtitle)}")
        print(ConsoleUI.dim("-" * 77))

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
        """Context manager for a "thinking" animation with elapsed time.

        Animates only on a terminal; when output is piped or captured it prints
        the message once instead of filling logs with animation frames.
        """
        import threading

        class Spinner:
            FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            ASCII_FRAMES = "|/-\\"

            def __init__(self, msg):
                self.msg = msg
                self.stop_event = threading.Event()
                self.thread = threading.Thread(target=self._animate, daemon=True)
                self.animate = sys.stdout.isatty()
                self.frames = self.FRAMES if unicode_enabled() else self.ASCII_FRAMES

            def _line(self, frame: str, elapsed: float) -> str:
                return f"\r  {ConsoleUI.accent(frame)} {self.msg}" + ConsoleUI.dim(f"  {elapsed:4.1f}s")

            def _animate(self):
                start, i = time.monotonic(), 0
                width = 0
                while not self.stop_event.is_set():
                    line = self._line(self.frames[i % len(self.frames)], time.monotonic() - start)
                    width = max(width, len(line))
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    i += 1
                    self.stop_event.wait(0.08)
                sys.stdout.write("\r" + " " * width + "\r")
                sys.stdout.flush()

            def __enter__(self):
                if self.animate:
                    self.thread.start()
                else:
                    print(f"  {self.msg}...")
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.animate:
                    self.stop_event.set()
                    self.thread.join()

        return Spinner(message)
