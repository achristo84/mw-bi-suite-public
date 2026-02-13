"""Google Sheets service for reading recipe spreadsheets."""
import logging
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.cloud import secretmanager

logger = logging.getLogger(__name__)

# Google Sheets API scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# GCP project - read from centralized config
from app.config import get_settings

PROJECT_ID = get_settings().GCP_PROJECT_ID


class SheetsService:
    """Service for reading recipe data from Google Sheets."""

    def __init__(self):
        self._service = None
        self._credentials = None

    def _get_secret(self, secret_id: str) -> str:
        """Fetch a secret from Secret Manager."""
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")

    def _get_credentials(self) -> Credentials:
        """Get OAuth2 credentials from Secret Manager."""
        if self._credentials and self._credentials.valid:
            return self._credentials

        # Reuse the same OAuth credentials as Gmail (just different scope)
        client_id = self._get_secret("gmail-client-id")
        client_secret = self._get_secret("gmail-client-secret")
        refresh_token = self._get_secret("gmail-refresh-token")

        self._credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES
        )

        # Refresh to get an access token
        self._credentials.refresh(Request())
        return self._credentials

    @property
    def service(self):
        """Get Sheets API service (lazy initialization)."""
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build('sheets', 'v4', credentials=credentials)
        return self._service

    def get_spreadsheet_metadata(self, spreadsheet_id: str) -> dict:
        """Get spreadsheet metadata including sheet names."""
        try:
            result = self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()

            return {
                'title': result.get('properties', {}).get('title', ''),
                'sheets': [
                    {
                        'title': sheet['properties']['title'],
                        'sheetId': sheet['properties']['sheetId'],
                        'index': sheet['properties']['index'],
                    }
                    for sheet in result.get('sheets', [])
                ]
            }
        except Exception as e:
            logger.error(f"Error getting spreadsheet metadata: {e}")
            raise

    def get_sheet_data(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        range_notation: str = ""
    ) -> list[list]:
        """
        Get data from a specific sheet.

        Args:
            spreadsheet_id: The Google Sheets ID from the URL
            sheet_name: Name of the sheet/tab
            range_notation: Optional A1 notation range (e.g., "A1:F30")

        Returns:
            2D list of cell values
        """
        try:
            # Build the range string
            if range_notation:
                full_range = f"'{sheet_name}'!{range_notation}"
            else:
                full_range = f"'{sheet_name}'"

            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=full_range,
                valueRenderOption='UNFORMATTED_VALUE'
            ).execute()

            values = result.get('values', [])
            logger.info(f"Got {len(values)} rows from {sheet_name}")
            return values

        except Exception as e:
            logger.error(f"Error getting sheet data: {e}")
            raise

    def list_sheets_in_folder(self, folder_id: str) -> list[dict]:
        """
        List all spreadsheets in a Google Drive folder.

        Note: Requires Drive API access. For now, we'll just work with
        direct spreadsheet IDs.
        """
        # Not implemented - use direct spreadsheet IDs instead
        raise NotImplementedError("Use direct spreadsheet IDs for now")


# Singleton instance
_sheets_service: Optional[SheetsService] = None


def get_sheets_service() -> SheetsService:
    """Get or create the Sheets service singleton."""
    global _sheets_service
    if _sheets_service is None:
        _sheets_service = SheetsService()
    return _sheets_service
