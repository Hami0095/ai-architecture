import os
import hmac
import hashlib
from .logging_utils import logger
from .config_manager import config

class SecurityManager:
    """Provides basic security utilities for authentication and authorization."""
    
    @staticmethod
    def verify_api_key(api_key: str) -> bool:
        """Verifies if the provided API key matches the configured one."""
        valid_key = config.get("security.api_key")
        if not valid_key:
            # If no key is configured, allow all (default local behavior)
            return True
        return hmac.compare_digest(api_key, valid_key)

    @staticmethod
    def encrypt_data(data: str, secret: str) -> str:
        """Dummy encryption for placeholder."""
        # This is a placeholder for actual encryption logic
        return hashlib.sha256((data + secret).encode()).hexdigest()

    @staticmethod
    def check_permissions(user_role: str, required_role: str) -> bool:
        """Basic role-based access control logic."""
        roles = ["guest", "user", "admin"]
        try:
            return roles.index(user_role) >= roles.index(required_role)
        except ValueError:
            return False

security = SecurityManager()
