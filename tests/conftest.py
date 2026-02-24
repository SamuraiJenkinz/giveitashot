"""
Shared pytest fixtures for email classification tests.
"""

import pytest
from datetime import datetime, timezone

from src.ews_client import Email


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
