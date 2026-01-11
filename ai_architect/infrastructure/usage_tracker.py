import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from .encryption import ArchEncryption
from ..connectors.google_drive import GoogleDriveConnector
from ..infrastructure.config_manager import config

logger = logging.getLogger("ArchAI.BackupService")

class BackupManager:
    """Orchestrates encrypted state backups to user's Google Drive."""

    def __init__(self, user_id: str, google_creds_json: str = None):
        self.user_id = user_id
        self.encryption = ArchEncryption(user_id)
        self.drive = GoogleDriveConnector(google_creds_json)

    def backup_state(self, state_data: Dict[str, Any], filename: str = "archai_state.enc"):
        """Encrypts and uploads current project/usage state."""
        try:
            encrypted_data = self.encryption.encrypt_json(state_data)
            file_id = self.drive.upload_backup(filename, encrypted_data)
            if file_id:
                logger.info(f"Encrypted state backup successful. FileID: {file_id}")
                return True
        except Exception as e:
            logger.error(f"Backup failed: {e}")
        return False

    def restore_state(self, filename: str = "archai_state.enc") -> Dict[str, Any]:
        """Downloads and decrypts project/usage state."""
        try:
            encrypted_data = self.drive.download_backup(filename)
            if encrypted_data:
                return self.encryption.decrypt_json(encrypted_data)
        except Exception as e:
            logger.error(f"Restore failed: {e}")
        return {}

class UsageTracker:
    """Tracks user activity, metrics, and plan usage."""
    
    def __init__(self):
        self.stats = {
            "total_audits": 0,
            "total_tokens_estimated": 0,
            "reports_generated": [],
            "last_active": None
        }

    def log_event(self, event_type: str, metadata: Dict[str, Any] = None):
        self.stats["total_audits"] += 1 if event_type == "audit" else 0
        self.stats["last_active"] = datetime.now().isoformat()
        if metadata:
            self.stats["reports_generated"].append({
                "type": event_type,
                "timestamp": self.stats["last_active"],
                "meta": metadata
            })
        logger.info(f"Usage logged: {event_type}")

    def get_summary(self) -> Dict[str, Any]:
        return self.stats
