"""
Shared pytest fixtures for email classification tests.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from email import message_from_file
from email.message import Message

from src.ews_client import Email
from src.state import StateManager


@pytest.fixture
def message_center_major_update():
    """Fixture: Typical Message Center major update email with all 3 signals."""
    return Email(
        id="AAMkAGZmMajorUpdate123",
        subject="MC1234567: Major update - Teams meeting policy changes",
        sender_name="Microsoft 365 Message Center",
        sender_email="o365mc@email2.microsoft.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="Action required: This major update requires admin action...",
        body_content="This is a major update to Microsoft Teams. Admin impact: You must update your tenant settings by the deadline.",
        has_attachments=False
    )


@pytest.fixture
def message_center_minor_update():
    """Fixture: Message Center email without major update keywords (sender + MC# only)."""
    return Email(
        id="AAMkAGZmMinorUpdate456",
        subject="MC9876543: New feature - Teams background effects",
        sender_name="Microsoft 365 Message Center",
        sender_email="o365mc@email2.microsoft.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="New Teams feature available...",
        body_content="A new Teams feature is now available. Users can customize their background effects with additional options.",
        has_attachments=False
    )


@pytest.fixture
def regular_microsoft_email():
    """Fixture: Non-Message-Center email from Microsoft domain (sender only)."""
    return Email(
        id="AAMkAGZmRegularMSFT789",
        subject="Your monthly invoice is ready",
        sender_name="Microsoft Billing",
        sender_email="billing@email2.microsoft.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="Your invoice for this month is now available...",
        body_content="Please review your monthly billing statement. Your payment is due by the end of the month.",
        has_attachments=True
    )


@pytest.fixture
def regular_internal_email():
    """Fixture: Regular internal email with no signals."""
    return Email(
        id="AAMkAGZmInternal000",
        subject="Team meeting notes",
        sender_name="John Doe",
        sender_email="john.doe@company.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="Here are the notes from today's meeting...",
        body_content="Project status: On track. Next milestone is scheduled for next week. Please review the attached documents.",
        has_attachments=False
    )


@pytest.fixture
def edge_case_partial_mc():
    """Fixture: Email with partial MC number (MC123 - only 3 digits, should NOT match)."""
    return Email(
        id="AAMkAGZmPartialMC111",
        subject="Schedule MC123 for review",
        sender_name="Project Manager",
        sender_email="pm@company.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="Please schedule MC123 project for review...",
        body_content="The MC123 project needs scheduling for the next sprint review meeting.",
        has_attachments=False
    )


@pytest.fixture
def edge_case_keywords_only():
    """Fixture: Email with major update keywords but no other signals."""
    return Email(
        id="AAMkAGZmKeywordsOnly222",
        subject="Action required: update your profile",
        sender_name="HR Department",
        sender_email="hr@company.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="Action required: Please update your employee profile...",
        body_content="Action required: All employees must update their profiles in the HR system by Friday.",
        has_attachments=False
    )


@pytest.fixture
def edge_case_sender_and_keywords():
    """Fixture: Email with sender + keywords signals (score=70, at threshold)."""
    return Email(
        id="AAMkAGZmSenderKeywords333",
        subject="Security alert",
        sender_name="Microsoft Security",
        sender_email="notifications@email2.microsoft.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="Action required for security compliance...",
        body_content="Action required: Admin impact detected. You must review and update your security settings immediately.",
        has_attachments=False
    )


# Extractor fixtures

@pytest.fixture
def major_update_with_deadline():
    """Fixture: Major update email with MC ID, action date, services, and categories."""
    return Email(
        id="AAMkAGZmExtractorTest001",
        subject="MC1234567: Major update - Exchange Online policy changes",
        sender_name="Microsoft 365 Message Center",
        sender_email="o365mc@email2.microsoft.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="Action required by 03/15/2026: Update your tenant settings...",
        body_content="MAJOR UPDATE - Action required by 03/15/2026. This update affects Exchange Online and Teams. Admin impact: You must update your tenant settings before the deadline.",
        has_attachments=False
    )


@pytest.fixture
def major_update_no_deadline():
    """Fixture: Major update email with MC ID but no action date."""
    return Email(
        id="AAMkAGZmExtractorTest002",
        subject="MC9876543: Service retirement notification",
        sender_name="Microsoft 365 Message Center",
        sender_email="o365mc@email2.microsoft.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="RETIREMENT notice: Legacy feature being retired...",
        body_content="RETIREMENT: The legacy authentication feature is being retired. This affects Exchange Online. No immediate action required.",
        has_attachments=False
    )


@pytest.fixture
def major_update_word_date():
    """Fixture: Major update email with date in word format (Month DD, YYYY)."""
    return Email(
        id="AAMkAGZmExtractorTest003",
        subject="MC5555555: Breaking change notification",
        sender_name="Microsoft 365 Message Center",
        sender_email="o365mc@email2.microsoft.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="Action required by March 15, 2026...",
        body_content="BREAKING CHANGE - Action required by March 15, 2026. This update affects SharePoint Online and OneDrive. Admin impact: Configuration changes needed.",
        has_attachments=False
    )


@pytest.fixture
def duplicate_mc_emails():
    """Fixture: List of 2 emails with same MC ID but different received dates."""
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    older_date = now - timedelta(hours=2)

    older_email = Email(
        id="AAMkAGZmDuplicate001",
        subject="MC1234567: Major update - First version",
        sender_name="Microsoft 365 Message Center",
        sender_email="o365mc@email2.microsoft.com",
        received_datetime=older_date,
        body_preview="First version of this update...",
        body_content="MAJOR UPDATE: This is the first version of this update.",
        has_attachments=False
    )

    newer_email = Email(
        id="AAMkAGZmDuplicate002",
        subject="MC1234567: Major update - Updated version",
        sender_name="Microsoft 365 Message Center",
        sender_email="o365mc@email2.microsoft.com",
        received_datetime=now,
        body_preview="Updated version with more details...",
        body_content="MAJOR UPDATE: This is the updated version with additional information.",
        has_attachments=False
    )

    return [older_email, newer_email]


# Integration test fixtures for .eml files and state isolation

@pytest.fixture
def eml_fixtures_dir():
    """Fixture: Returns path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def load_eml(eml_fixtures_dir):
    """
    Fixture: Factory to load .eml files from fixtures directory.

    Usage:
        message = load_eml("synthetic", "mc_major_update_action_required.eml")

    Args:
        category: Subdirectory name (e.g., "synthetic", "real")
        filename: .eml filename

    Returns:
        Parsed email.message.Message object
    """
    def _load(category: str, filename: str) -> Message:
        file_path = eml_fixtures_dir / category / filename
        if not file_path.exists():
            pytest.skip(f"Fixture file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return message_from_file(f)

    return _load


@pytest.fixture
def isolated_state(tmp_path):
    """
    Fixture: Provides isolated StateManager for tests.

    Creates a StateManager with tmp_path state file to prevent
    pollution of real .state.json during tests.

    Returns:
        StateManager instance with temporary state file
    """
    state_file = tmp_path / "state.json"
    return StateManager(state_file=str(state_file))


@pytest.fixture
def mock_emails_from_eml():
    """
    Fixture: Factory to convert parsed .eml messages to Email dataclass instances.

    Usage:
        msg1 = load_eml("synthetic", "mc_major_update.eml")
        msg2 = load_eml("synthetic", "regular_internal.eml")
        emails = mock_emails_from_eml([msg1, msg2])

    Args:
        messages: List of email.message.Message objects

    Returns:
        List of Email dataclass instances
    """
    def _convert(messages: list[Message]) -> list[Email]:
        emails = []
        for idx, msg in enumerate(messages):
            # Extract headers
            sender_email = msg.get('From', '').split('<')[-1].rstrip('>')
            sender_name = msg.get('From', '').split('<')[0].strip().strip('"')
            subject = msg.get('Subject', '')
            date_str = msg.get('Date', '')

            # Parse date - use current time if parsing fails
            try:
                from email.utils import parsedate_to_datetime
                received_datetime = parsedate_to_datetime(date_str)
                # Ensure timezone-aware
                if received_datetime.tzinfo is None:
                    received_datetime = received_datetime.replace(tzinfo=timezone.utc)
            except Exception:
                received_datetime = datetime.now(timezone.utc)

            # Extract body content
            body_content = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
            else:
                body_content = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

            # Create body preview (first 200 chars)
            body_preview = body_content[:200].strip()
            if len(body_content) > 200:
                body_preview += "..."

            # Generate synthetic ID
            email_id = f"AAMkAGZmSynthetic{idx:03d}"

            emails.append(Email(
                id=email_id,
                subject=subject,
                sender_name=sender_name,
                sender_email=sender_email,
                received_datetime=received_datetime,
                body_preview=body_preview,
                body_content=body_content,
                has_attachments=False
            ))

        return emails

    return _convert
