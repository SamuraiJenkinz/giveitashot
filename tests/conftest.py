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
