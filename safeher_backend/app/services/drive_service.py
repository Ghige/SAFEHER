"""
Google Drive evidence upload service.

Evidence is uploaded directly to the USER's own Google Drive — SafeHer
never stores it on its own servers.

Drive tokens are encrypted at rest using the encryption_service before
being stored in the DB, and decrypted here before use.
"""

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from app.services.encryption_service import decrypt_token
import logging
import os

logger = logging.getLogger(__name__)


def upload_evidence_to_drive(
    encrypted_drive_token: str,
    file_path: str,
    alert_id: str,
    file_name: str = None
) -> str:
    """
    Upload evidence file to the user's Google Drive.
    Returns the shareable Drive URL, or "" on failure.

    Args:
        encrypted_drive_token: the token as stored in DB (may be encrypted)
        file_path:             local path to the evidence file
        alert_id:              used to name the Drive folder
        file_name:             optional display name for the file
    """
    drive_token = decrypt_token(encrypted_drive_token)
    if not drive_token:
        logger.error("Drive token decryption failed — cannot upload evidence")
        return ""

    try:
        creds = Credentials(token=drive_token)
        service = build("drive", "v3", credentials=creds)

        folder_id = _get_or_create_folder(service, f"SafeHer_Alert_{alert_id}")

        name = file_name or os.path.basename(file_path)
        media = MediaFileUpload(file_path, resumable=True)

        file_meta = {
            "name": name,
            "parents": [folder_id]
        }

        uploaded = service.files().create(
            body=file_meta,
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        drive_url = uploaded.get("webViewLink", "")
        logger.info(f"Evidence uploaded to Drive: {drive_url}")
        return drive_url

    except Exception as e:
        logger.error(f"Drive upload failed: {e}")
        return ""


def _get_or_create_folder(service, folder_name: str) -> str:
    """Get existing folder ID or create a new one."""
    results = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)"
    ).execute()

    files = results.get("files", [])
    if files:
        return files[0]["id"]

    folder_meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder"
    }
    folder = service.files().create(body=folder_meta, fields="id").execute()
    return folder["id"]
