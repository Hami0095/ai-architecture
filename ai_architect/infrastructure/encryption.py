import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from ..infrastructure.config_manager import config

class ArchEncryption:
    """Handles encryption for ArchAI backups using a user-specific secret."""

    def __init__(self, user_id: str):
        # We derive a key from the user's ID and a system salt/passphrase
        self.salt = config.get("security.salt", "archai-default-salt").encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(user_id.encode()))
        self.fernet = Fernet(key)

    def encrypt(self, data: bytes) -> bytes:
        return self.fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        return self.fernet.decrypt(token)

    def encrypt_json(self, data_dict: dict) -> bytes:
        import json
        return self.encrypt(json.dumps(data_dict).encode())

    def decrypt_json(self, token: bytes) -> dict:
        import json
        return json.loads(self.decrypt(token).decode())
