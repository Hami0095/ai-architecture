import os
import json
import logging
from typing import Optional, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io
from ..infrastructure.config_manager import config

logger = logging.getLogger("ArchAI.GoogleDrive")

class GoogleDriveConnector:
    """Handles encrypted ArchAI backups in the user's Google Drive (appDataFolder)."""

    def __init__(self, credentials_json: Optional[str] = None):
        if credentials_json:
            self.creds = Credentials.from_authorized_user_info(json.loads(credentials_json))
        else:
            # Fallback to config/env for headless or initial setup
            token = config.get_secret("google_drive_token")
            if token:
                self.creds = Credentials.from_authorized_user_info(json.loads(token))
            else:
                self.creds = None
                logger.warning("No Google Drive credentials found.")

        self.service = build('drive', 'v3', credentials=self.creds) if self.creds else None

    def upload_backup(self, filename: str, content: bytes, mime_type: str = 'application/octet-stream'):
        """Uploads an encrypted file to the hidden appDataFolder."""
        if not self.service:
            return None

        file_metadata = {
            'name': filename,
            'parents': ['appDataFolder']
        }
        
        media = MediaFileUpload(
            io.BytesIO(content),
            mimetype=mime_type,
            resumable=True
        )

        try:
            # Check if file exists to update or create
            query = f"name = '{filename}' and 'appDataFolder' in parents"
            results = self.service.files().list(q=query, spaces='appDataFolder').execute()
            files = results.get('files', [])

            if files:
                file_id = files[0]['id']
                updated_file = self.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                logger.info(f"Updated backup: {filename} (ID: {file_id})")
                return file_id
            else:
                created_file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                logger.info(f"Created new backup: {filename} (ID: {created_file.get('id')})")
                return created_file.get('id')
        except Exception as e:
            logger.error(f"Google Drive Upload Error: {e}")
            return None

    def download_backup(self, filename: str) -> Optional[bytes]:
        """Downloads a backup from the appDataFolder."""
        if not self.service:
            return None

        try:
            query = f"name = '{filename}' and 'appDataFolder' in parents"
            results = self.service.files().list(q=query, spaces='appDataFolder').execute()
            files = results.get('files', [])

            if not files:
                return None

            file_id = files[0]['id']
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            return fh.getvalue()
        except Exception as e:
            logger.error(f"Google Drive Download Error: {e}")
            return None
