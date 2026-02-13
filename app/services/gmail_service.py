"""Gmail service for fetching invoice emails."""
import base64
import logging
from datetime import datetime
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.cloud import secretmanager, storage

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# GCP project - read from centralized config
from app.config import get_settings

_settings = get_settings()
PROJECT_ID = _settings.GCP_PROJECT_ID
BUCKET_NAME = _settings.GCS_BUCKET_NAME


class GmailService:
    """Service for fetching and processing invoice emails from Gmail."""

    def __init__(self):
        self._service = None
        self._storage_client = None
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
        """Get Gmail API service (lazy initialization)."""
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build('gmail', 'v1', credentials=credentials)
        return self._service

    @property
    def storage_client(self):
        """Get Cloud Storage client (lazy initialization)."""
        if self._storage_client is None:
            self._storage_client = storage.Client(project=PROJECT_ID)
        return self._storage_client

    def search_invoice_emails(
        self,
        sender_addresses: list[str] | None = None,
        after_date: datetime | None = None,
        max_results: int = 100
    ) -> list[dict]:
        """
        Search for potential invoice emails.

        Args:
            sender_addresses: List of email addresses to filter by
            after_date: Only get emails after this date
            max_results: Maximum number of results to return

        Returns:
            List of message metadata dicts with keys: id, threadId
        """
        # Build search query
        query_parts = []

        # Filter by senders if provided
        if sender_addresses:
            sender_query = " OR ".join(f"from:{addr}" for addr in sender_addresses)
            query_parts.append(f"({sender_query})")

        # Subject patterns that suggest invoices
        # Note: multi-word patterns need quotes
        subject_patterns = ["invoice", "statement", '"order confirmation"', "billing"]
        subject_query = " OR ".join(f"subject:{pattern}" for pattern in subject_patterns)
        query_parts.append(f"({subject_query})")

        # Has attachment
        query_parts.append("has:attachment")

        # Date filter
        if after_date:
            date_str = after_date.strftime("%Y/%m/%d")
            query_parts.append(f"after:{date_str}")

        query = " ".join(query_parts)
        logger.info(f"Gmail search query: {query}")

        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} potential invoice emails")
            return messages

        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            raise

    def get_message_details(self, message_id: str) -> dict:
        """
        Get full details of an email message.

        Returns dict with:
            - id: Gmail message ID
            - threadId: Gmail thread ID
            - from_address: Sender email
            - subject: Email subject
            - date: When received (datetime)
            - attachments: List of attachment info
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            # Extract headers
            headers = {h['name'].lower(): h['value'] for h in message['payload'].get('headers', [])}

            # Parse date
            date_str = headers.get('date', '')
            received_at = self._parse_email_date(date_str)

            # Extract from address (just the email part)
            from_header = headers.get('from', '')
            from_address = self._extract_email_address(from_header)

            # Find attachments
            attachments = self._find_attachments(message['payload'], message_id)

            return {
                'id': message['id'],
                'threadId': message['threadId'],
                'from_address': from_address,
                'subject': headers.get('subject', ''),
                'date': received_at,
                'attachments': attachments,
                'snippet': message.get('snippet', '')
            }

        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            raise

    def _parse_email_date(self, date_str: str) -> datetime:
        """Parse email date header into datetime."""
        from email.utils import parsedate_to_datetime
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return datetime.utcnow()

    def _extract_email_address(self, from_header: str) -> str:
        """Extract email address from From header like 'Name <email@example.com>'."""
        import re
        match = re.search(r'<([^>]+)>', from_header)
        if match:
            return match.group(1).lower()
        return from_header.strip().lower()

    def _find_attachments(self, payload: dict, message_id: str) -> list[dict]:
        """Recursively find all attachments in message payload."""
        attachments = []

        if 'parts' in payload:
            for part in payload['parts']:
                attachments.extend(self._find_attachments(part, message_id))
        else:
            filename = payload.get('filename', '')
            if filename and payload.get('body', {}).get('attachmentId'):
                mime_type = payload.get('mimeType', '')
                attachments.append({
                    'filename': filename,
                    'mimeType': mime_type,
                    'attachmentId': payload['body']['attachmentId'],
                    'size': payload['body'].get('size', 0)
                })

        return attachments

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download an attachment and return its content."""
        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()

            data = attachment['data']
            # Gmail uses URL-safe base64
            return base64.urlsafe_b64decode(data)

        except Exception as e:
            logger.error(f"Error downloading attachment: {e}")
            raise

    def upload_to_storage(
        self,
        content: bytes,
        destination_path: str,
        content_type: str = "application/pdf"
    ) -> str:
        """
        Upload content to Cloud Storage.

        Args:
            content: File content as bytes
            destination_path: Path within bucket (e.g., "invoices/2024/12/invoice.pdf")
            content_type: MIME type

        Returns:
            Full GCS path (gs://bucket/path)
        """
        try:
            bucket = self.storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(destination_path)
            blob.upload_from_string(content, content_type=content_type)

            gcs_path = f"gs://{BUCKET_NAME}/{destination_path}"
            logger.info(f"Uploaded to {gcs_path}")
            return gcs_path

        except Exception as e:
            logger.error(f"Error uploading to storage: {e}")
            raise


# Singleton instance
_gmail_service: Optional[GmailService] = None


def get_gmail_service() -> GmailService:
    """Get or create the Gmail service singleton."""
    global _gmail_service
    if _gmail_service is None:
        _gmail_service = GmailService()
    return _gmail_service
