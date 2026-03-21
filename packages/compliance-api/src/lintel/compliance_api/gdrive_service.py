"""Google Drive document import service.

Encapsulates URL parsing, authentication, and content fetching from Google Drive.
Supports Google Docs (exported to plain text) and other file types (downloaded as-is).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from google.auth.credentials import Credentials
    from googleapiclient.discovery import Resource

logger = logging.getLogger(__name__)

# Patterns to extract Google Drive file IDs from various URL formats.
_FILE_ID_PATTERNS = [
    re.compile(r"/d/([a-zA-Z0-9_-]+)"),  # /d/{fileId}/
    re.compile(r"id=([a-zA-Z0-9_-]+)"),  # ?id={fileId} or &id={fileId}
]

# Google Docs MIME type — these are exported rather than downloaded.
_GOOGLE_DOCS_MIME = "application/vnd.google-apps.document"


class GDriveError(Exception):
    """Base exception for Google Drive operations."""


class GDriveAuthError(GDriveError):
    """Raised when authentication with Google APIs fails."""


class GDrivePermissionError(GDriveError):
    """Raised when the service account lacks permission to access the file."""


class GDriveInvalidURLError(GDriveError):
    """Raised when the provided URL cannot be parsed into a file ID."""


def extract_file_id(url: str) -> str:
    """Extract the Google Drive file ID from a sharing URL.

    Supports formats like:
    - https://docs.google.com/document/d/{fileId}/edit
    - https://drive.google.com/file/d/{fileId}/view
    - https://drive.google.com/open?id={fileId}

    Raises:
        GDriveInvalidURLError: If no file ID can be extracted.
    """
    for pattern in _FILE_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    msg = f"Cannot extract Google Drive file ID from URL: {url}"
    raise GDriveInvalidURLError(msg)


def _build_credentials(service_account_json: str | None = None) -> Credentials:
    """Build Google API credentials.

    Args:
        service_account_json: JSON string of service account credentials.
            If None, falls back to Application Default Credentials.

    Returns:
        google.auth.credentials.Credentials instance.
    """
    if service_account_json:
        from google.oauth2 import service_account

        info = json.loads(service_account_json)
        return service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )

    # Fallback: Application Default Credentials (ADC)
    import google.auth

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return credentials


class GDriveService:
    """Service for fetching document content from Google Drive.

    Uses a service account (preferred) or Application Default Credentials
    to authenticate with the Google Drive API.
    """

    def __init__(self, service_account_json: str | None = None) -> None:
        self._service_account_json = service_account_json

    def _get_drive_service(self) -> Resource:
        """Build and return a Google Drive API service client."""
        try:
            credentials = _build_credentials(self._service_account_json)
        except Exception as exc:
            msg = f"Failed to authenticate with Google Drive API: {exc}"
            raise GDriveAuthError(msg) from exc

        from googleapiclient.discovery import build

        return build("drive", "v3", credentials=credentials)

    def get_file_metadata(self, file_id: str) -> dict[str, str]:
        """Retrieve file metadata (name, mimeType) from Google Drive.

        Returns:
            Dict with 'name' and 'mimeType' keys.
        """
        from googleapiclient.errors import HttpError

        service = self._get_drive_service()
        try:
            meta: dict[str, str] = (
                service.files().get(fileId=file_id, fields="name,mimeType").execute()
            )
            return meta
        except HttpError as exc:
            if exc.resp.status in (403, 404):
                msg = f"Cannot access file {file_id}: {exc}"
                raise GDrivePermissionError(msg) from exc
            raise

    def fetch_content(self, file_id: str) -> tuple[str, str]:
        """Fetch document content from Google Drive.

        For Google Docs, exports to plain text.
        For other files, downloads the raw content.

        Returns:
            Tuple of (content_text, title).
        """
        from googleapiclient.errors import HttpError

        service = self._get_drive_service()
        try:
            meta = self.get_file_metadata(file_id)
            title = meta.get("name", "Untitled")
            mime_type = meta.get("mimeType", "")

            if mime_type == _GOOGLE_DOCS_MIME:
                # Export Google Doc to plain text
                content: str = (
                    service.files()
                    .export(fileId=file_id, mimeType="text/plain")
                    .execute()
                    .decode("utf-8")
                )
            else:
                # Download raw file content
                content = service.files().get_media(fileId=file_id).execute().decode("utf-8")

            return content, title

        except HttpError as exc:
            if exc.resp.status in (403, 404):
                msg = f"Cannot access file {file_id}: {exc}"
                raise GDrivePermissionError(msg) from exc
            raise

    def fetch_from_url(self, url: str) -> dict[str, str]:
        """Fetch document content given a Google Drive sharing URL.

        Returns:
            Dict with 'content', 'file_id', and 'title' keys.
        """
        file_id = extract_file_id(url)
        content, title = self.fetch_content(file_id)
        return {"content": content, "file_id": file_id, "title": title}


def create_gdrive_service(settings_getter: Callable[[], str | None] | None = None) -> GDriveService:
    """Factory to create a GDriveService with credentials from settings or env.

    Args:
        settings_getter: Callable that returns the Google service account JSON
            from the settings store, or None.

    Returns:
        Configured GDriveService instance.
    """
    sa_json: str | None = None

    # Try settings store first
    if settings_getter is not None:
        try:
            sa_json = settings_getter()
        except Exception:
            logger.debug("Could not fetch service account JSON from settings store")

    # Fallback to environment variable
    if not sa_json:
        sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    return GDriveService(service_account_json=sa_json)
