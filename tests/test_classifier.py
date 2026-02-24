"""
Unit tests for email classification logic.
"""

import pytest
from datetime import datetime, timezone

from src.classifier import EmailClassifier, ClassificationResult
from src.ews_client import Email


class TestClassificationTruePositives:
    """Test cases for emails that should be classified as major updates."""

    def test_classifies_full_match_as_major_update(self, message_center_major_update):
        """Test that email with all 3 signals is classified as major update."""
        classifier = EmailClassifier()
        result = classifier.classify(message_center_major_update)

        assert result.is_major_update is True
        assert result.confidence_score >= 100
        assert "sender_domain" in result.matched_signals
        assert "subject_mc_number" in result.matched_signals
        assert "body_keywords" in result.matched_signals

    def test_classifies_sender_plus_mc_as_major_update(self, message_center_minor_update):
        """Test that sender + MC number (score=70) is classified as major update."""
        classifier = EmailClassifier()
        result = classifier.classify(message_center_minor_update)

        assert result.is_major_update is True
        assert result.confidence_score == 70
        assert "sender_domain" in result.matched_signals
        assert "subject_mc_number" in result.matched_signals
        assert "body_keywords" not in result.matched_signals

    def test_classifies_sender_plus_keywords_as_major_update(self, edge_case_sender_and_keywords):
        """Test that sender + keywords (score=70) is classified as major update."""
        classifier = EmailClassifier()
        result = classifier.classify(edge_case_sender_and_keywords)

        assert result.is_major_update is True
        assert result.confidence_score == 70
        assert "sender_domain" in result.matched_signals
        assert "body_keywords" in result.matched_signals
        assert "subject_mc_number" not in result.matched_signals


class TestClassificationTrueNegatives:
    """Test cases for emails that should NOT be classified as major updates."""

    def test_rejects_sender_only(self, regular_microsoft_email):
        """Test that sender only (score=40) is not classified as major update."""
        classifier = EmailClassifier()
        result = classifier.classify(regular_microsoft_email)

        assert result.is_major_update is False
        assert result.confidence_score == 40
        assert "sender_domain" in result.matched_signals
        assert len(result.matched_signals) == 1

    def test_rejects_keywords_only(self, edge_case_keywords_only):
        """Test that keywords only (score=30) is not classified as major update."""
        classifier = EmailClassifier()
        result = classifier.classify(edge_case_keywords_only)

        assert result.is_major_update is False
        assert result.confidence_score == 30
        assert "body_keywords" in result.matched_signals
        assert "sender_domain" not in result.matched_signals
        assert len(result.matched_signals) == 1

    def test_rejects_no_signals(self, regular_internal_email):
        """Test that email with no signals (score=0) is not classified as major update."""
        classifier = EmailClassifier()
        result = classifier.classify(regular_internal_email)

        assert result.is_major_update is False
        assert result.confidence_score == 0
        assert len(result.matched_signals) == 0

    def test_rejects_partial_mc_number(self, edge_case_partial_mc):
        """Test that partial MC number (MC123 not MC1234567) does not match."""
        classifier = EmailClassifier()
        result = classifier.classify(edge_case_partial_mc)

        assert result.is_major_update is False
        assert "subject_mc_number" not in result.matched_signals


class TestSignalTracking:
    """Test cases for signal tracking and confidence scoring."""

    def test_matched_signals_contains_all_three(self, message_center_major_update):
        """Test that all 3 signals are tracked when matched."""
        classifier = EmailClassifier()
        result = classifier.classify(message_center_major_update)

        assert "sender_domain" in result.matched_signals
        assert "subject_mc_number" in result.matched_signals
        assert "body_keywords" in result.matched_signals
        assert len(result.matched_signals) == 3

    def test_matched_signals_empty_for_no_match(self, regular_internal_email):
        """Test that matched_signals is empty when no signals match."""
        classifier = EmailClassifier()
        result = classifier.classify(regular_internal_email)

        assert result.matched_signals == []

    def test_confidence_score_reflects_weights(self, regular_microsoft_email):
        """Test that confidence score correctly reflects signal weights."""
        classifier = EmailClassifier()
        result = classifier.classify(regular_microsoft_email)

        # Only sender signal should match (40 points)
        assert result.confidence_score == 40


class TestBatchClassification:
    """Test cases for batch classification functionality."""

    def test_classify_batch_splits_correctly(
        self,
        message_center_major_update,
        regular_internal_email,
        regular_microsoft_email
    ):
        """Test that batch classification correctly splits regular vs major updates."""
        classifier = EmailClassifier()
        emails = [message_center_major_update, regular_internal_email, regular_microsoft_email]

        regular, major_updates = classifier.classify_batch(emails)

        assert len(regular) == 2
        assert len(major_updates) == 1
        assert regular_internal_email in regular
        assert regular_microsoft_email in regular
        assert message_center_major_update in major_updates

    def test_classify_batch_empty_list(self):
        """Test that batch classification handles empty list."""
        classifier = EmailClassifier()
        emails = []

        regular, major_updates = classifier.classify_batch(emails)

        assert regular == []
        assert major_updates == []

    def test_classify_batch_all_regular(self, regular_internal_email, regular_microsoft_email):
        """Test that batch with all regular emails returns empty major updates list."""
        classifier = EmailClassifier()
        emails = [regular_internal_email, regular_microsoft_email]

        regular, major_updates = classifier.classify_batch(emails)

        assert len(regular) == 2
        assert len(major_updates) == 0

    def test_classify_batch_all_major(self, message_center_major_update, message_center_minor_update):
        """Test that batch with all major updates returns empty regular list."""
        classifier = EmailClassifier()
        emails = [message_center_major_update, message_center_minor_update]

        regular, major_updates = classifier.classify_batch(emails)

        assert len(regular) == 0
        assert len(major_updates) == 2


class TestEdgeCases:
    """Test cases for edge cases and error conditions."""

    def test_case_insensitive_sender(self):
        """Test that sender pattern matching is case-insensitive."""
        classifier = EmailClassifier()
        email = Email(
            id="test_upper_sender",
            subject="MC1234567: Test",
            sender_name="Microsoft",
            sender_email="O365MC@EMAIL2.MICROSOFT.COM",
            received_datetime=datetime.now(timezone.utc),
            body_preview="",
            body_content="major update",
            has_attachments=False
        )

        result = classifier.classify(email)

        assert "sender_domain" in result.matched_signals

    def test_case_insensitive_keywords(self):
        """Test that keyword matching is case-insensitive."""
        classifier = EmailClassifier()
        email = Email(
            id="test_upper_keywords",
            subject="Test",
            sender_name="Test",
            sender_email="test@example.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="",
            body_content="This is a MAJOR UPDATE announcement",
            has_attachments=False
        )

        result = classifier.classify(email)

        assert "body_keywords" in result.matched_signals

    def test_empty_body_no_crash(self):
        """Test that empty body content does not cause errors."""
        classifier = EmailClassifier()
        email = Email(
            id="test_empty_body",
            subject="MC1234567: Test",
            sender_name="Microsoft",
            sender_email="o365mc@email2.microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="",
            body_content="",
            has_attachments=False
        )

        result = classifier.classify(email)

        # Should have sender and MC signals, no body keywords
        assert result.is_major_update is True
        assert "sender_domain" in result.matched_signals
        assert "subject_mc_number" in result.matched_signals
        assert "body_keywords" not in result.matched_signals

    def test_empty_subject_no_crash(self):
        """Test that empty subject does not cause errors."""
        classifier = EmailClassifier()
        email = Email(
            id="test_empty_subject",
            subject="",
            sender_name="Microsoft",
            sender_email="o365mc@email2.microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="",
            body_content="major update admin impact",
            has_attachments=False
        )

        result = classifier.classify(email)

        # Should have sender and body keywords, no MC number
        assert result.is_major_update is True
        assert "sender_domain" in result.matched_signals
        assert "body_keywords" in result.matched_signals
        assert "subject_mc_number" not in result.matched_signals
