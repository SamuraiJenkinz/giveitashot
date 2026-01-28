"""
Exchange Web Services client for email operations.
Handles reading emails from shared mailboxes and sending emails via EWS.
Uses app-only authentication with impersonation.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from html import unescape
import re

from exchangelib import (
    Account,
    Configuration,
    IMPERSONATION,
    Message,
    Mailbox,
    HTMLBody,
    EWSTimeZone,
    OAuth2Credentials,
)

from .config import Config

logger = logging.getLogger(__name__)


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

    @property
    def received_time_local(self) -> str:
        """Get the received time in local timezone as a formatted string."""
        local_time = self.received_datetime.astimezone()
        return local_time.strftime("%I:%M %p")


class EWSClientError(Exception):
    """Raised when an EWS operation fails."""
    pass


class EWSClient:
    """
    Exchange Web Services client for email operations.
    Uses app-only authentication with impersonation to access mailboxes.
    """

    def __init__(self, credentials: OAuth2Credentials):
        """
        Initialize the EWS client with OAuth credentials.

        Args:
            credentials: OAuth2 credentials for EWS authentication.
        """
        self._credentials = credentials
        self._config: Optional[Configuration] = None
        self._shared_account: Optional[Account] = None
        self._sender_account: Optional[Account] = None

    def _get_config(self) -> Configuration:
        """Get or create the EWS configuration."""
        if self._config is None:
            self._config = Configuration(
                server=Config.EWS_SERVER,
                credentials=self._credentials
            )
        return self._config

    def _get_account(self, email_address: str) -> Account:
        """
        Get an account connection using impersonation.

        Args:
            email_address: Email address of the mailbox to access.

        Returns:
            Account: Connected account for the mailbox.
        """
        logger.info(f"Connecting to mailbox: {email_address}")

        account = Account(
            primary_smtp_address=email_address,
            config=self._get_config(),
            autodiscover=False,
            access_type=IMPERSONATION
        )

        logger.info(f"Mailbox connection established: {email_address}")
        return account

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

    def get_shared_mailbox_emails_today(
        self,
        shared_mailbox: str,
        max_emails: int = 100
    ) -> list[Email]:
        """
        Get today's emails from a shared mailbox.

        Args:
            shared_mailbox: Email address of the shared mailbox.
            max_emails: Maximum number of emails to retrieve.

        Returns:
            list[Email]: List of emails received today.
        """
        try:
            if self._shared_account is None:
                self._shared_account = self._get_account(shared_mailbox)

            account = self._shared_account

            # Calculate today's date at midnight in local timezone
            tz = EWSTimeZone.localzone()
            now = datetime.now(tz)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            logger.info(f"Fetching emails received since {today_start.isoformat()}")

            # Query inbox for today's emails
            inbox = account.inbox

            # Filter emails received today, ordered by newest first
            emails_query = inbox.filter(
                datetime_received__gte=today_start
            ).order_by('-datetime_received')[:max_emails]

            all_emails = []

            for item in emails_query:
                try:
                    # Extract sender info
                    sender_name = "Unknown"
                    sender_email = "unknown@unknown.com"

                    if item.sender:
                        sender_name = item.sender.name or "Unknown"
                        sender_email = item.sender.email_address or "unknown@unknown.com"

                    # Extract body content
                    body_content = ""
                    if item.body:
                        body_content = self._strip_html(str(item.body))

                    # Create body preview (first 200 chars)
                    body_preview = body_content[:200] if body_content else ""

                    # Convert EWS datetime to Python datetime
                    received_dt = datetime.now(timezone.utc)
                    if item.datetime_received:
                        received_dt = datetime(
                            item.datetime_received.year,
                            item.datetime_received.month,
                            item.datetime_received.day,
                            item.datetime_received.hour,
                            item.datetime_received.minute,
                            item.datetime_received.second,
                            tzinfo=timezone.utc
                        )

                    email = Email(
                        id=item.id or "",
                        subject=item.subject or "(No Subject)",
                        sender_name=sender_name,
                        sender_email=sender_email,
                        received_datetime=received_dt,
                        body_preview=body_preview,
                        body_content=body_content,
                        has_attachments=bool(item.has_attachments)
                    )
                    all_emails.append(email)

                except Exception as e:
                    logger.warning(f"Failed to parse email: {e}")
                    continue

            logger.info(f"Total emails retrieved: {len(all_emails)}")
            return all_emails

        except Exception as e:
            raise EWSClientError(f"Failed to retrieve emails: {e}")

    def send_email(
        self,
        to_recipients: list[str] | str,
        subject: str,
        body_html: str,
        cc_recipients: list[str] | None = None,
        bcc_recipients: list[str] | None = None
    ) -> None:
        """
        Send an email using impersonation.

        Args:
            to_recipients: Recipient email address(es). Can be a single string or list.
            subject: Email subject.
            body_html: HTML body content.
            cc_recipients: Optional list of CC recipient email addresses.
            bcc_recipients: Optional list of BCC recipient email addresses.
        """
        try:
            # Use the configured user email to send
            if self._sender_account is None:
                self._sender_account = self._get_account(Config.USER_EMAIL)

            account = self._sender_account

            # Normalize to_recipients to a list
            if isinstance(to_recipients, str):
                to_recipients = [to_recipients]

            # Filter out empty strings
            to_recipients = [r for r in to_recipients if r]
            cc_recipients = [r for r in (cc_recipients or []) if r]
            bcc_recipients = [r for r in (bcc_recipients or []) if r]

            if not to_recipients:
                raise EWSClientError("At least one TO recipient is required")

            # Log recipient info
            logger.info(f"Sending email from {Config.USER_EMAIL}")
            logger.info(f"  TO: {', '.join(to_recipients)}")
            if cc_recipients:
                logger.info(f"  CC: {', '.join(cc_recipients)}")
            if bcc_recipients:
                logger.info(f"  BCC: {', '.join(bcc_recipients)}")

            # Build recipient lists
            to_mailboxes = [Mailbox(email_address=email) for email in to_recipients]
            cc_mailboxes = [Mailbox(email_address=email) for email in cc_recipients] if cc_recipients else None
            bcc_mailboxes = [Mailbox(email_address=email) for email in bcc_recipients] if bcc_recipients else None

            message = Message(
                account=account,
                subject=subject,
                body=HTMLBody(body_html),
                to_recipients=to_mailboxes,
                cc_recipients=cc_mailboxes,
                bcc_recipients=bcc_mailboxes
            )

            message.send_and_save()
            logger.info("Email sent successfully")

        except Exception as e:
            raise EWSClientError(f"Failed to send email: {e}")
