import logging
import sys
import time
import functools
from pathlib import Path
from typing import Optional, Callable, Any

class ArchAIError(Exception):
    """Base exception for all ArchAI errors."""
    pass

class AgentFailureError(ArchAIError):
    """Raised when an AI agent fails to complete its task."""
    pass

class ConfigurationError(ArchAIError):
    """Raised when there is an issue with the system configuration."""
    pass

class InfrastructureError(ArchAIError):
    """Raised when an infrastructure component (DB, Network) fails."""
    pass

class LLMProviderError(AgentFailureError):
    """Raised when the LLM provider (Ollama, OpenAI, etc.) returns an error."""
    pass

def setup_logger(name: str, log_file: Optional[str] = "archai.log", level: int = logging.INFO):
    """Sets up a centralized logger with console and file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        return logger

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

# Singleton logger
logger = setup_logger("ArchAI")

def retry(retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """
    Retry decorator for functions that may fail due to transient issues.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            m_retries, m_delay = retries, delay
            while m_retries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    m_retries -= 1
                    if m_retries == 0:
                        logger.error(f"Function {func.__name__} failed after all retries. Final error: {e}")
                        raise
                    logger.warning(f"Function {func.__name__} failed with '{e}'. Retrying in {m_delay}s... ({m_retries} left)")
                    time.sleep(m_delay)
                    m_delay *= backoff
            return func(*args, **kwargs)
        return wrapper
    return decorator

def async_retry(retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """
    Async version of the retry decorator.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            m_retries, m_delay = retries, delay
            while m_retries > 0:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    m_retries -= 1
                    if m_retries == 0:
                        logger.error(f"Async Function {func.__name__} failed after all retries. Final error: {e}")
                        raise
                    logger.warning(f"Async Function {func.__name__} failed with '{e}'. Retrying in {m_delay}s... ({m_retries} left)")
                    import asyncio
                    await asyncio.sleep(m_delay)
                    m_delay *= backoff
        return wrapper
    return decorator
