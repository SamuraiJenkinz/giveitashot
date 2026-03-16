"""
Comprehensive tests for MessageCenterExtractor field extraction and urgency calculation.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.extractor import MessageCenterExtractor, MajorUpdateFields, UrgencyTier
from src.graph_client import Email


def _date_from_now(days: int) -> datetime:
    """Helper to create a datetime relative to now."""
    return datetime.now() + timedelta(days=days)


class TestMCIDExtraction:
    """Tests for MC ID extraction from subject and body."""

    def test_extracts_mc_id_from_subject(self, major_update_with_deadline):
        """MC ID in subject line extracted correctly."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(major_update_with_deadline)
        assert result.mc_id == "MC1234567"

    def test_extracts_mc_id_from_body_fallback(self):
        """MC ID not in subject, found in body."""
        email = Email(
            id="test001",
            subject="Important update notification",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="See MC7654321 for details",
            body_content="This update is tracked as MC7654321 in the Message Center.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.mc_id == "MC7654321"

    def test_extracts_5_digit_mc_id(self):
        """MC ID with minimum 5 digits extracted correctly."""
        email = Email(
            id="test002",
            subject="MC12345: Short MC ID test",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Test",
            body_content="Test content",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.mc_id == "MC12345"

    def test_extracts_7_digit_mc_id(self):
        """MC ID with maximum 7 digits extracted correctly."""
        email = Email(
            id="test003",
            subject="MC1234567: Long MC ID test",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Test",
            body_content="Test content",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.mc_id == "MC1234567"

    def test_returns_none_for_no_mc_id(self, regular_internal_email):
        """No MC pattern returns None."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(regular_internal_email)
        assert result.mc_id is None

    def test_returns_none_for_short_mc(self, edge_case_partial_mc):
        """MC ID with only 3 digits does NOT match."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(edge_case_partial_mc)
        assert result.mc_id is None

    def test_case_insensitive_mc_match(self):
        """Lowercase 'mc' matches the pattern."""
        email = Email(
            id="test004",
            subject="mc1234567: lowercase test",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Test",
            body_content="Test content",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.mc_id == "MC1234567"


class TestActionDateExtraction:
    """Tests for action-required date parsing."""

    def test_extracts_date_mm_dd_yyyy(self, major_update_with_deadline):
        """Date in format 'MM/DD/YYYY' parsed correctly."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(major_update_with_deadline)
        assert result.action_required_date is not None
        assert result.action_required_date.month == 3
        assert result.action_required_date.day == 15
        assert result.action_required_date.year == 2026

    def test_extracts_date_word_format(self, major_update_word_date):
        """Date in format 'Month DD, YYYY' parsed correctly."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(major_update_word_date)
        assert result.action_required_date is not None
        assert result.action_required_date.month == 3
        assert result.action_required_date.day == 15
        assert result.action_required_date.year == 2026

    def test_extracts_deadline_format(self):
        """Date with 'deadline:' prefix parsed correctly."""
        email = Email(
            id="test005",
            subject="MC1111111: Deadline test",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Deadline: 06/30/2026",
            body_content="Important: deadline: 06/30/2026 for this update.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.action_required_date is not None
        assert result.action_required_date.month == 6
        assert result.action_required_date.day == 30
        assert result.action_required_date.year == 2026

    def test_returns_none_no_date(self, major_update_no_deadline):
        """Email without action date returns None."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(major_update_no_deadline)
        assert result.action_required_date is None

    def test_returns_none_invalid_date(self):
        """Invalid date format returns None without crash."""
        email = Email(
            id="test006",
            subject="MC2222222: Invalid date test",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Action required by 99/99/9999",
            body_content="Action required by 99/99/9999 - this is invalid",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.action_required_date is None


class TestServiceExtraction:
    """Tests for affected service extraction."""

    def test_extracts_single_service(self):
        """Single service name found correctly."""
        email = Email(
            id="test007",
            subject="Update for Exchange Online",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Exchange Online update",
            body_content="This update affects Exchange Online only.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert "Exchange Online" in result.affected_services

    def test_extracts_multiple_services(self, major_update_with_deadline):
        """Multiple services extracted and deduplicated."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(major_update_with_deadline)
        assert len(result.affected_services) >= 2
        assert "Exchange Online" in result.affected_services
        assert "Teams" in result.affected_services

    def test_extracts_from_subject_and_body(self):
        """Services found in both subject and body are combined."""
        email = Email(
            id="test008",
            subject="Teams update notification",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="SharePoint changes",
            body_content="This update affects SharePoint Online and related services.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert "Teams" in result.affected_services
        assert "Sharepoint Online" in result.affected_services

    def test_returns_empty_no_services(self):
        """No known services returns empty list."""
        email = Email(
            id="test009",
            subject="Generic notification",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="No services mentioned",
            body_content="This is a generic notification without specific service names.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.affected_services == []

    def test_deduplicates_services(self):
        """Same service mentioned twice returns once."""
        email = Email(
            id="test010",
            subject="Teams and Teams update",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Teams Teams Teams",
            body_content="Teams will be updated. This affects all Teams users and Teams admins.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        # Count occurrences of Teams
        teams_count = sum(1 for s in result.affected_services if 'teams' in s.lower())
        assert teams_count == 1


class TestCategoryExtraction:
    """Tests for category tag extraction."""

    def test_extracts_major_update(self, major_update_with_deadline):
        """MAJOR UPDATE category found."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(major_update_with_deadline)
        assert "MAJOR UPDATE" in result.categories

    def test_extracts_multiple_categories(self, major_update_with_deadline):
        """Multiple categories extracted correctly."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(major_update_with_deadline)
        assert len(result.categories) >= 2
        assert "MAJOR UPDATE" in result.categories
        assert "ADMIN IMPACT" in result.categories

    def test_case_insensitive(self):
        """Lowercase category keywords match."""
        email = Email(
            id="test011",
            subject="Update notification",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="major update coming",
            body_content="This is a major update with admin impact required.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert "MAJOR UPDATE" in result.categories
        assert "ADMIN IMPACT" in result.categories

    def test_returns_empty_no_categories(self):
        """No categories returns empty list."""
        email = Email(
            id="test012",
            subject="General information",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="General content",
            body_content="This is general information without specific category keywords.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.categories == []


class TestUrgencyCalculation:
    """Tests for urgency tier calculation based on deadline proximity."""

    def test_no_date_returns_normal(self, major_update_no_deadline):
        """None action date results in Normal urgency."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(major_update_no_deadline)
        assert result.urgency == UrgencyTier.NORMAL

    def test_critical_within_7_days(self):
        """Date 5 days out returns Critical."""
        action_date = _date_from_now(5)
        email = Email(
            id="test013",
            subject="MC3333333: Urgent update",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview=f"Action required by {action_date.strftime('%m/%d/%Y')}",
            body_content=f"Action required by {action_date.strftime('%m/%d/%Y')}. Please act soon.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.urgency == UrgencyTier.CRITICAL

    def test_high_within_30_days(self):
        """Date 15 days out returns High."""
        action_date = _date_from_now(15)
        email = Email(
            id="test014",
            subject="MC4444444: Important update",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview=f"Action required by {action_date.strftime('%m/%d/%Y')}",
            body_content=f"Action required by {action_date.strftime('%m/%d/%Y')}.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.urgency == UrgencyTier.HIGH

    def test_normal_beyond_30_days(self):
        """Date 60 days out returns Normal."""
        action_date = _date_from_now(60)
        email = Email(
            id="test015",
            subject="MC5555555: Future update",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview=f"Action required by {action_date.strftime('%m/%d/%Y')}",
            body_content=f"Action required by {action_date.strftime('%m/%d/%Y')}.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.urgency == UrgencyTier.NORMAL

    def test_past_date_is_critical(self):
        """Date 3 days ago returns Critical."""
        action_date = _date_from_now(-3)
        email = Email(
            id="test016",
            subject="MC6666666: Overdue update",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview=f"Action required by {action_date.strftime('%m/%d/%Y')}",
            body_content=f"Action required by {action_date.strftime('%m/%d/%Y')}.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.urgency == UrgencyTier.CRITICAL

    def test_boundary_7_days_is_critical(self):
        """Exactly 7 days out returns Critical."""
        action_date = _date_from_now(7)
        email = Email(
            id="test017",
            subject="MC7777777: Boundary test 7d",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview=f"Action required by {action_date.strftime('%m/%d/%Y')}",
            body_content=f"Action required by {action_date.strftime('%m/%d/%Y')}.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.urgency == UrgencyTier.CRITICAL

    def test_boundary_30_days_is_high(self):
        """Exactly 30 days out returns High."""
        action_date = _date_from_now(30)
        email = Email(
            id="test018",
            subject="MC8888888: Boundary test 30d",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview=f"Action required by {action_date.strftime('%m/%d/%Y')}",
            body_content=f"Action required by {action_date.strftime('%m/%d/%Y')}.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.urgency == UrgencyTier.HIGH

    def test_boundary_31_days_is_normal(self):
        """31 days out returns Normal."""
        action_date = _date_from_now(31)
        email = Email(
            id="test019",
            subject="MC9999999: Boundary test 31d",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview=f"Action required by {action_date.strftime('%m/%d/%Y')}",
            body_content=f"Action required by {action_date.strftime('%m/%d/%Y')}.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)
        assert result.urgency == UrgencyTier.NORMAL


class TestExtractFull:
    """Tests for full field extraction."""

    def test_extract_returns_all_fields(self, major_update_with_deadline):
        """Full extraction populates all MajorUpdateFields."""
        extractor = MessageCenterExtractor()
        result = extractor.extract(major_update_with_deadline)

        assert result.mc_id == "MC1234567"
        assert result.action_required_date is not None
        assert len(result.affected_services) > 0
        assert len(result.categories) > 0
        assert result.published_date == major_update_with_deadline.received_datetime
        assert result.last_updated_date == major_update_with_deadline.received_datetime
        assert len(result.body_preview) > 0
        assert result.urgency in [UrgencyTier.CRITICAL, UrgencyTier.HIGH, UrgencyTier.NORMAL]
        assert result.is_updated is False
        assert result.subject == major_update_with_deadline.subject

    def test_extract_with_missing_fields(self):
        """Email with no MC ID, no date, no services still returns fields."""
        email = Email(
            id="test020",
            subject="Generic notification",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Generic content",
            body_content="This is generic content without specific fields.",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)

        assert result.mc_id is None
        assert result.action_required_date is None
        assert result.affected_services == []
        assert result.categories == []
        assert result.urgency == UrgencyTier.NORMAL

    def test_body_preview_truncation(self):
        """Long body truncated at 200 chars at word boundary."""
        long_body = "This is a very long body content that will be truncated. " * 20
        email = Email(
            id="test021",
            subject="MC1010101: Long content test",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview=long_body[:200],
            body_content=long_body,
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)

        assert len(result.body_preview) <= 203  # 200 + "..."
        assert result.body_preview.endswith("...")

    def test_body_preview_short(self):
        """Short body not truncated."""
        short_body = "This is short content."
        email = Email(
            id="test022",
            subject="MC1111111: Short content test",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview=short_body,
            body_content=short_body,
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        result = extractor.extract(email)

        assert result.body_preview == short_body
        assert not result.body_preview.endswith("...")


class TestDeduplication:
    """Tests for MC ID deduplication."""

    def test_keeps_latest_by_received_datetime(self, duplicate_mc_emails):
        """Two emails same MC ID, keeps the newer one."""
        extractor = MessageCenterExtractor()
        fields_list = extractor.extract_batch(duplicate_mc_emails)
        deduplicated = extractor.deduplicate(fields_list)

        assert len(deduplicated) == 1
        assert deduplicated[0].mc_id == "MC1234567"
        # Should keep the newer version
        assert deduplicated[0].published_date == duplicate_mc_emails[1].received_datetime

    def test_marks_kept_as_updated(self, duplicate_mc_emails):
        """Deduplicated entry has is_updated=True."""
        extractor = MessageCenterExtractor()
        fields_list = extractor.extract_batch(duplicate_mc_emails)
        deduplicated = extractor.deduplicate(fields_list)

        assert deduplicated[0].is_updated is True

    def test_no_duplicates_unchanged(self, major_update_with_deadline):
        """Single entries kept as-is with is_updated=False."""
        extractor = MessageCenterExtractor()
        fields_list = [extractor.extract(major_update_with_deadline)]
        deduplicated = extractor.deduplicate(fields_list)

        assert len(deduplicated) == 1
        assert deduplicated[0].is_updated is False

    def test_none_mc_id_always_kept(self):
        """Emails without MC ID not deduplicated."""
        email1 = Email(
            id="test023",
            subject="No MC ID 1",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Content 1",
            body_content="Content 1",
            has_attachments=False
        )
        email2 = Email(
            id="test024",
            subject="No MC ID 2",
            sender_name="Microsoft",
            sender_email="test@microsoft.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Content 2",
            body_content="Content 2",
            has_attachments=False
        )
        extractor = MessageCenterExtractor()
        fields_list = extractor.extract_batch([email1, email2])
        deduplicated = extractor.deduplicate(fields_list)

        assert len(deduplicated) == 2

    def test_mixed_duplicates_and_uniques(self, duplicate_mc_emails, major_update_no_deadline):
        """Mix of duplicates and unique MC IDs handled correctly."""
        all_emails = duplicate_mc_emails + [major_update_no_deadline]
        extractor = MessageCenterExtractor()
        fields_list = extractor.extract_batch(all_emails)
        deduplicated = extractor.deduplicate(fields_list)

        # Should have 2 unique MC IDs: MC1234567 (deduplicated) and MC9876543 (unique)
        assert len(deduplicated) == 2
        mc_ids = [f.mc_id for f in deduplicated]
        assert "MC1234567" in mc_ids
        assert "MC9876543" in mc_ids


class TestExtractBatch:
    """Tests for batch extraction."""

    def test_extracts_multiple_emails(
        self,
        major_update_with_deadline,
        major_update_no_deadline,
        major_update_word_date
    ):
        """Batch of 3 emails returns 3 MajorUpdateFields."""
        emails = [
            major_update_with_deadline,
            major_update_no_deadline,
            major_update_word_date
        ]
        extractor = MessageCenterExtractor()
        results = extractor.extract_batch(emails)

        assert len(results) == 3
        assert all(isinstance(r, MajorUpdateFields) for r in results)
        # Verify each has different MC ID
        mc_ids = [r.mc_id for r in results]
        assert len(set(mc_ids)) == 3  # All unique
