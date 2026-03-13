"""
Microsoft Graph REST API client for email operations.
Handles reading emails from shared mailboxes via Microsoft Graph v1.0.
Uses app-only authentication via GraphAuthenticator (MSAL client credentials).
"""

import logging
import time
import re
import requests
from html import unescape
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Any

from .config import Config

logger = logging.getLogger(__name__)

# Graph API base URL (v1.0 stable endpoint)
BASE_GRAPH_URL = "https://graph.microsoft.com/v1.0"

# HTTP status codes that warrant a retry (throttling + transient server errors)
RETRY_STATUS_CODES = {429, 502, 503, 504}

# Maximum number of retry attempts per request
MAX_RETRIES = 3

# Fields to project in $select — only what we need for the Email dataclass
# bodyPreview is NOT selected — we compute body_preview from body_content[:200]
SELECT_FIELDS = "id,internetMessageId,subject,sender,from,body,receivedDateTime,hasAttachments"


@dataclass
class Email:
    """Represents an email message."""
    id: str
    subject: str
    sender_name: str
    sender_email: str
    received_datetime: datetime
    body_preview: str
    body_content: str
    has_attachments: bool
    classification: Optional[Any] = None  # Set by EmailClassifier post-fetch

    @property
    def received_time_local(self) -> str:
        """Get the received time in local timezone as a formatted string."""
        local_time = self.received_datetime.astimezone()
        return local_time.strftime("%I:%M %p")

    @property
    def is_major_update(self) -> bool:
        """Check if email is classified as a major update."""
        if self.classification is None:
            return False
        return self.classification.is_major_update


class GraphClientError(Exception):
    """Raised when a Graph API operation fails."""
    pass


class GraphClient:
    """
    Microsoft Graph REST API client for email operations.
    Uses app-only authentication with client credentials flow.

    The authenticator parameter must expose:
        get_access_token() -> str
    which returns a valid Bearer token string. GraphAuthenticator (from auth.py)
    satisfies this contract.
    """

    def __init__(self, authenticator) -> None:
        """
        Initialize the Graph client.

        Args:
            authenticator: An object with a get_access_token() -> str method.
                           Typically a GraphAuthenticator instance.
        """
        self._authenticator = authenticator
        # Session enables connection pooling and clean mock patching in tests
        self._session = requests.Session()

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make a Graph API request with automatic retry on throttling / transient errors.

        Retry behaviour:
          - 401 Unauthorized: re-authenticate silently via MSAL and retry
          - 429 / 502 / 503 / 504: honour Retry-After header, then retry
          - All other statuses: return response immediately (caller decides success)

        After MAX_RETRIES exhausted, raises GraphClientError.

        Args:
            method: HTTP method string (e.g. "GET", "POST").
            url:    Full URL to request.
            **kwargs: Additional arguments forwarded to requests.Session.request().

        Returns:
            requests.Response from the final attempt.

        Raises:
            GraphClientError: If all retry attempts are exhausted.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            token = self._authenticator.get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            # Allow callers to merge additional headers without losing auth header
            if "headers" in kwargs:
                headers.update(kwargs.pop("headers"))

            response = self._session.request(method, url, headers=headers, **kwargs)

            if response.status_code == 401 and attempt < MAX_RETRIES:
                # Token may have expired mid-pagination — re-auth is silent via MSAL
                logger.warning(
                    "Token may have expired, re-authenticating "
                    f"(attempt {attempt}/{MAX_RETRIES})"
                )
                continue

            if response.status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES:
                # Respect Graph's Retry-After header (integer seconds); exponential fallback
                retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                logger.info(
                    f"Throttled by Graph API, retrying in {retry_after}s "
                    f"(attempt {attempt}/{MAX_RETRIES})"
                )
                time.sleep(retry_after)
                continue

            return response

        raise GraphClientError(
            f"Request failed after {MAX_RETRIES} attempts: {url}"
        )

    def _raise_graph_error(self, operation: str, response: requests.Response) -> None:
        """
        Raise a GraphClientError with production-useful details from a failed response.

        Extracts the Graph error code and message from the JSON body. Falls back to
        raw response text if JSON parsing fails.

        Args:
            operation: Human-readable description of what was attempted (e.g. "retrieve emails").
            response:  The failed requests.Response object.

        Raises:
            GraphClientError: Always raised with HTTP status + Graph error detail.
        """
        try:
            err = response.json().get("error", {})
            graph_msg = err.get("message", response.text)
            graph_code = err.get("code", "")
            detail = f"{graph_code} - {graph_msg}" if graph_code else graph_msg
        except Exception:
            detail = response.text
        raise GraphClientError(
            f"Failed to {operation}: {response.status_code} {response.reason} - {detail}"
        )

    def _strip_html(self, html_content: str) -> str:
        """Strip HTML tags and decode entities from content."""
        if not html_content:
            return ""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html_content)
        # Decode HTML entities
        text = unescape(text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _parse_datetime(self, dt_str: str) -> datetime:
        """
        Parse a Graph ISO 8601 UTC datetime string to a timezone-aware datetime.

        Graph always returns UTC strings ending in 'Z' (e.g. "2026-03-13T10:30:00Z").
        Python 3.9/3.10 fromisoformat() does not support 'Z' — replace with '+00:00'.

        Args:
            dt_str: ISO 8601 datetime string from Graph response.

        Returns:
            Timezone-aware UTC datetime. Falls back to datetime.now(timezone.utc) on failure.
        """
        if not dt_str:
            return datetime.now(timezone.utc)
        try:
            # Python 3.11+ supports 'Z'; replace for 3.9/3.10 compatibility
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Could not parse datetime: {dt_str!r}")
            return datetime.now(timezone.utc)

    def _parse_message(self, msg: dict) -> Email:
        """
        Map a Graph message resource dict to an Email dataclass instance.

        Field mapping rationale:
          - id: internetMessageId (RFC2822 stable ID) preferred over Graph id (changes on folder move)
          - body_content: HTML body stripped locally (preserves exact classifier/summarizer input)
          - body_preview: first 200 chars of body_content (NOT Graph's bodyPreview which is 255 chars)
          - received_datetime: parsed from Graph's UTC ISO 8601 string

        Args:
            msg: Graph message resource dict from the API response.

        Returns:
            Email dataclass populated from the message.
        """
        # Use internetMessageId (stable RFC2822 Message-ID) as primary;
        # fall back to Graph's internal id only if absent
        email_id = msg.get("internetMessageId") or msg.get("id", "")

        subject = msg.get("subject") or "(No Subject)"

        # sender and from both have the same structure:
        # {"emailAddress": {"name": "...", "address": "..."}}
        sender = msg.get("sender") or msg.get("from") or {}
        sender_addr = sender.get("emailAddress", {})
        sender_name = sender_addr.get("name") or "Unknown"
        sender_email = sender_addr.get("address") or "unknown@unknown.com"

        # Graph returns HTML by default; strip to plain text so classifier/summarizer
        # continue receiving the same format they receive from the EWS path
        body_obj = msg.get("body") or {}
        raw_body = body_obj.get("content", "")
        body_content = self._strip_html(raw_body)

        # Compute body_preview from stripped content (matches EWS behaviour)
        body_preview = body_content[:200]

        received_str = msg.get("receivedDateTime", "")
        received_datetime = self._parse_datetime(received_str)

        has_attachments = bool(msg.get("hasAttachments", False))

        return Email(
            id=email_id,
            subject=subject,
            sender_name=sender_name,
            sender_email=sender_email,
            received_datetime=received_datetime,
            body_preview=body_preview,
            body_content=body_content,
            has_attachments=has_attachments,
        )

    def get_shared_mailbox_emails(
        self,
        shared_mailbox: str,
        since: datetime | None = None,
        max_emails: int = 100,
    ) -> list[Email]:
        """
        Retrieve emails from a shared mailbox received since a given datetime.

        Uses OData $filter (receivedDateTime ge …), $select for field projection,
        $orderby for newest-first ordering, and follows @odata.nextLink for pagination
        until max_emails is reached or all matching emails are returned.

        Individual email parse failures log a warning and skip the bad email
        without aborting the entire fetch.

        Args:
            shared_mailbox: Email address of the shared mailbox to read.
            since:          Only return emails received at or after this datetime.
                            Defaults to today at midnight UTC if None.
            max_emails:     Upper bound on returned emails (also sets Graph $top).

        Returns:
            List of Email objects, up to max_emails, ordered newest-first.

        Raises:
            GraphClientError: On non-recoverable Graph API errors.
        """
        try:
            if since is None:
                now = datetime.now(timezone.utc)
                since = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Graph requires UTC ISO 8601 without quotes in OData $filter expressions
            since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

            params: dict | None = {
                "$filter": f"receivedDateTime ge {since_str}",
                "$select": SELECT_FIELDS,
                "$orderby": "receivedDateTime desc",
                "$top": min(max_emails, 100),  # Graph max $top is 1000; 100 is a safe default
            }

            url: str | None = f"{BASE_GRAPH_URL}/users/{shared_mailbox}/messages"
            all_emails: list[Email] = []

            logger.info(
                f"Fetching emails from {shared_mailbox} since {since_str} "
                f"(max={max_emails})"
            )

            while url and len(all_emails) < max_emails:
                response = self._make_request("GET", url, params=params)

                if not response.ok:
                    self._raise_graph_error("retrieve emails", response)

                data = response.json()

                for msg in data.get("value", []):
                    try:
                        email = self._parse_message(msg)
                        all_emails.append(email)
                    except Exception as exc:
                        logger.warning(
                            f"Failed to parse email {msg.get('id', '?')}: {exc}"
                        )

                # Follow @odata.nextLink — it is a complete URL with all params embedded.
                # CRITICAL: set params=None after first request so we do not duplicate
                # query parameters on subsequent pages.
                url = data.get("@odata.nextLink")
                params = None

            logger.info(f"Total emails retrieved: {len(all_emails)}")
            return all_emails[:max_emails]

        except GraphClientError:
            raise
        except Exception as exc:
            raise GraphClientError(f"Failed to retrieve emails: {exc}") from exc
