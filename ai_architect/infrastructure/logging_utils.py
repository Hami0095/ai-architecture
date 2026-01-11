import logging
import sys
from pathlib import Path
from typing import Optional

class ArchAIError(Exception):
    """Base exception for all ArchAI errors."""
    pass

class AgentFailureError(ArchAIError):
    """Raised when an AI agent fails to complete its task."""
    pass

class ConfigurationError(ArchAIError):
    """Raised when there is an issue with the system configuration."""
    pass

def setup_logger(name: str, log_file: Optional[str] = "archai.log", level: int = logging.INFO):
    """Sets up a centralized logger with console and file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    if log_file:
        log_path = Path(log_file)
        # Ensure log directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

# Pre-defined logger for general use
logger = setup_logger("ArchAI")
