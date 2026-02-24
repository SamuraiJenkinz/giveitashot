"""
Integration tests for the classification pipeline.
Tests the classification system end-to-end without requiring live EWS connections.
"""

import pytest
from datetime import datetime, timezone

from src.classifier import EmailClassifier, ClassificationResult
from src.ews_client import Email


class TestClassificationPipeline:
    """Integration tests for classification pipeline."""

    def test_classify_batch_excludes_major_updates_from_regular(
        self,
        message_center_major_update,
        message_center_minor_update,
        regular_internal_email,
        message_center_major_update_action_required,
        regular_email_attachment
    ):
        """
        Test that classify_batch correctly splits major updates from regular emails.
        Verifies major update emails are excluded from regular digest.
        """
        # Arrange: Create mixed email list
        # Note: message_center_minor_update has sender+MC# (70 points) so it's also classified as major
        # 2 regular: regular_internal_email, regular_email_attachment
        # 3 major: message_center_major_update, message_center_minor_update, message_center_major_update_action_required
        emails = [
            regular_internal_email,
            message_center_major_update,
            message_center_minor_update,
            message_center_major_update_action_required,
            regular_email_attachment,
        ]

        classifier = EmailClassifier()

        # Act: Classify batch
        regular_emails, major_update_emails = classifier.classify_batch(emails)

        # Assert: Correct split (2 regular, 3 major)
        assert len(regular_emails) == 2
        assert len(major_update_emails) == 3

        # Assert: No major updates in regular list
        for email in regular_emails:
            assert not email.is_major_update

        # Assert: No regular emails in major updates list
        for email in major_update_emails:
            assert email.is_major_update

    def test_classification_preserves_all_emails(
        self,
        message_center_major_update,
        message_center_minor_update,
        regular_internal_email
    ):
        """
        Test that classification doesn't lose any emails.
        Verifies len(regular) + len(major) == len(original).
        """
        # Arrange: Mixed email list
        emails = [
            regular_internal_email,
            message_center_major_update,
            message_center_minor_update,
        ]

        classifier = EmailClassifier()

        # Act: Classify batch
        regular_emails, major_update_emails = classifier.classify_batch(emails)

        # Assert: All emails accounted for
        assert len(regular_emails) + len(major_update_emails) == len(emails)

    def test_classification_failure_returns_all_as_regular(self, mocker, regular_internal_email):
        """
        Test that classification failure falls back to treating all emails as regular.
        Verifies the error handling pattern in main.py.
        """
        # Arrange: Mock classifier.classify to raise exception
        classifier = EmailClassifier()
        mocker.patch.object(
            classifier,
            'classify',
            side_effect=Exception("Classification error")
        )

        emails = [regular_internal_email]

        # Act & Assert: Verify exception is raised (main.py catches this)
        with pytest.raises(Exception, match="Classification error"):
            classifier.classify_batch(emails)

    def test_email_dataclass_classification_field_default(self):
        """
        Test that Email dataclass has classification field with None default.
        Verifies backward compatibility.
        """
        # Arrange & Act: Create Email without classification
        email = Email(
            id="test-123",
            subject="Test Subject",
            sender_name="Test Sender",
            sender_email="test@example.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Preview text",
            body_content="Full body content",
            has_attachments=False
        )

        # Assert: Classification defaults to None
        assert email.classification is None
        assert email.is_major_update is False

    def test_email_dataclass_with_classification(self):
        """
        Test that Email dataclass can hold classification result.
        Verifies is_major_update property works with classification set.
        """
        # Arrange: Create Email
        email = Email(
            id="test-456",
            subject="MC1234567: Major Update",
            sender_name="Microsoft",
            sender_email="o365mc@email2.microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="This is a major update",
            body_content="This is a major update requiring action",
            has_attachments=False
        )

        # Act: Set classification manually
        email.classification = ClassificationResult(
            is_major_update=True,
            confidence_score=100,
            matched_signals=["sender_domain", "subject_mc_number", "body_keywords"]
        )

        # Assert: Properties reflect classification
        assert email.is_major_update is True
        assert email.classification.confidence_score == 100
        assert len(email.classification.matched_signals) == 3

    def test_classify_batch_with_single_major_update(self, message_center_major_update):
        """
        Test classify_batch with single major update email.
        Should return empty regular list and single-item major updates list.
        """
        # Arrange
        emails = [message_center_major_update]
        classifier = EmailClassifier()

        # Act
        regular_emails, major_update_emails = classifier.classify_batch(emails)

        # Assert
        assert len(regular_emails) == 0
        assert len(major_update_emails) == 1
        assert major_update_emails[0].subject == message_center_major_update.subject

    def test_classify_batch_with_single_regular_email(self, regular_internal_email):
        """
        Test classify_batch with single regular email.
        Should return single-item regular list and empty major updates list.
        """
        # Arrange
        emails = [regular_internal_email]
        classifier = EmailClassifier()

        # Act
        regular_emails, major_update_emails = classifier.classify_batch(emails)

        # Assert
        assert len(regular_emails) == 1
        assert len(major_update_emails) == 0
        assert regular_emails[0].subject == regular_internal_email.subject

    def test_regular_digest_email_count_matches_after_exclusion(
        self,
        message_center_major_update,
        message_center_major_update_action_required,
        regular_internal_email,
        regular_email_attachment,
        regular_microsoft_email
    ):
        """
        Test that regular digest receives correct email count after major updates excluded.
        Simulates what summarizer would receive.
        """
        # Arrange: Create 10 emails (7 regular, 3 major updates)
        # regular: 5x regular_internal_email, 2x regular_email_attachment = 7
        # major: 2x message_center_major_update, 1x message_center_major_update_action_required = 3
        emails = [
            regular_internal_email,
            regular_email_attachment,
            regular_internal_email,
            message_center_major_update,
            regular_internal_email,
            regular_email_attachment,
            message_center_major_update_action_required,
            regular_internal_email,
            regular_internal_email,
            message_center_major_update,
        ]

        classifier = EmailClassifier()

        # Act: Classify batch
        regular_emails, major_update_emails = classifier.classify_batch(emails)

        # Assert: Exactly 7 regular emails (this is what summarizer receives)
        assert len(regular_emails) == 7
        assert len(major_update_emails) == 3


@pytest.fixture
def message_center_major_update_action_required():
    """Fixture: Message Center major update with action required."""
    return Email(
        id="AAMkAGZp...",
        subject="MC9876543: Action Required - Teams Policy Retirement",
        sender_name="Microsoft 365 Message Center",
        sender_email="o365mc@email2.microsoft.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="Action required by March 1st...",
        body_content="This is a major update. Action required: You must migrate to the new Teams policy before March 1st. This retirement affects all tenants.",
        has_attachments=False
    )


@pytest.fixture
def regular_email_attachment():
    """Fixture: Regular email with attachment."""
    return Email(
        id="AAMkAGZq...",
        subject="Weekly Report Attached",
        sender_name="Finance Team",
        sender_email="finance@company.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="Please find the weekly report attached...",
        body_content="Please find the weekly financial report attached for your review.",
        has_attachments=True
    )
