"""
Tests for major updates HTML formatting and subject line generation.
"""

from datetime import datetime, timedelta

import pytest

from src.action_extractor import ActionExtraction, AdminAction
from src.extractor import MajorUpdateFields, UrgencyTier
from src.summarizer import EmailSummarizer


def _make_update(mc_id="MC123456", urgency=UrgencyTier.NORMAL, **kwargs):
    """Helper to create MajorUpdateFields with defaults."""
    defaults = {
        "mc_id": mc_id,
        "action_required_date": None,
        "affected_services": ["Exchange Online"],
        "categories": ["MAJOR UPDATE"],
        "published_date": datetime.now(),
        "last_updated_date": datetime.now(),
        "body_preview": "Test body preview text...",
        "urgency": urgency,
        "is_updated": False,
        "subject": f"Test subject for {mc_id}",
    }
    defaults.update(kwargs)
    return MajorUpdateFields(**defaults)


class TestFormatMajorUpdatesHtml:
    """Test HTML formatting for major updates digest."""

    def test_returns_empty_string_for_empty_list(self):
        """Empty update list returns empty string."""
        summarizer = EmailSummarizer(use_llm=False)
        html = summarizer.format_major_updates_html([])
        assert html == ""

    def test_contains_mc_id(self):
        """HTML output contains the MC ID string."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(mc_id="MC234567")
        html = summarizer.format_major_updates_html([update])
        assert "MC234567" in html

    def test_contains_action_date(self):
        """HTML output contains formatted action date."""
        summarizer = EmailSummarizer(use_llm=False)
        action_date = datetime.now() + timedelta(days=15)
        update = _make_update(action_required_date=action_date)
        html = summarizer.format_major_updates_html([update])
        # Check for formatted date (e.g., "March 15, 2026")
        date_formatted = action_date.strftime("%B %d, %Y")
        assert date_formatted in html
        assert "Action Required:" in html

    def test_contains_affected_services(self):
        """HTML output contains service names."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(affected_services=["Microsoft Teams", "SharePoint Online"])
        html = summarizer.format_major_updates_html([update])
        assert "Microsoft Teams" in html
        assert "SharePoint Online" in html

    def test_contains_category_tags(self):
        """HTML output contains category text."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(categories=["MAJOR UPDATE", "ADMIN IMPACT"])
        html = summarizer.format_major_updates_html([update])
        assert "MAJOR UPDATE" in html
        assert "ADMIN IMPACT" in html

    def test_contains_urgency_section_headers(self):
        """HTML has urgency section headers for each tier present."""
        summarizer = EmailSummarizer(use_llm=False)
        critical_update = _make_update(mc_id="MC111111", urgency=UrgencyTier.CRITICAL)
        high_update = _make_update(mc_id="MC222222", urgency=UrgencyTier.HIGH)
        html = summarizer.format_major_updates_html([critical_update, high_update])
        assert "CRITICAL" in html
        assert "HIGH PRIORITY" in html

    def test_critical_color_border(self):
        """HTML contains the red border color for critical updates."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(urgency=UrgencyTier.CRITICAL)
        html = summarizer.format_major_updates_html([update])
        # Check for danger color (#ea4335)
        assert "#ea4335" in html

    def test_high_color_border(self):
        """HTML contains amber border color for high priority."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(urgency=UrgencyTier.HIGH)
        html = summarizer.format_major_updates_html([update])
        # Check for warning color (#fbbc04)
        assert "#fbbc04" in html

    def test_normal_color_border(self):
        """HTML contains green border color for normal updates."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(urgency=UrgencyTier.NORMAL)
        html = summarizer.format_major_updates_html([update])
        # Check for success color (#34a853)
        assert "#34a853" in html

    def test_updated_badge_shown(self):
        """Update with is_updated=True shows UPDATED badge."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(is_updated=True)
        html = summarizer.format_major_updates_html([update])
        assert "UPDATED" in html

    def test_stats_header_urgency_counts(self):
        """Stats section shows correct tier counts."""
        summarizer = EmailSummarizer(use_llm=False)
        updates = [
            _make_update(mc_id="MC111111", urgency=UrgencyTier.CRITICAL),
            _make_update(mc_id="MC222222", urgency=UrgencyTier.CRITICAL),
            _make_update(mc_id="MC333333", urgency=UrgencyTier.HIGH),
            _make_update(mc_id="MC444444", urgency=UrgencyTier.NORMAL),
        ]
        html = summarizer.format_major_updates_html(updates)
        # Check for urgency breakdown text
        assert "2 Critical" in html
        assert "1 High" in html
        assert "1 Normal" in html

    def test_no_deadline_display(self):
        """Update with no action date shows 'No deadline specified'."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(action_required_date=None)
        html = summarizer.format_major_updates_html([update])
        assert "No deadline specified" in html

    def test_overdue_display(self):
        """Past action date shows OVERDUE text."""
        summarizer = EmailSummarizer(use_llm=False)
        past_date = datetime.now() - timedelta(days=5)
        update = _make_update(
            action_required_date=past_date,
            urgency=UrgencyTier.CRITICAL  # Past dates are critical
        )
        html = summarizer.format_major_updates_html([update])
        assert "OVERDUE" in html

    def test_table_based_layout(self):
        """HTML contains table role=presentation for email client compatibility."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update()
        html = summarizer.format_major_updates_html([update])
        assert 'role="presentation"' in html
        assert "<table" in html

    def test_inline_css(self):
        """HTML does not contain style blocks or link tags."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update()
        html = summarizer.format_major_updates_html([update])
        # Should not have <style> blocks or <link> tags
        assert "<style" not in html
        assert "<link" not in html
        # Should have inline styles
        assert 'style="' in html


class TestGetMajorSubjectLine:
    """Test subject line generation for major updates digest."""

    def test_critical_subject(self):
        """Updates with critical urgency produce CRITICAL prefix."""
        summarizer = EmailSummarizer(use_llm=False)
        updates = [
            _make_update(mc_id="MC111111", urgency=UrgencyTier.CRITICAL),
            _make_update(mc_id="MC222222", urgency=UrgencyTier.NORMAL),
        ]
        subject = summarizer.get_major_subject_line(updates)
        assert subject.startswith("CRITICAL:")
        assert "2 Major Update(s)" in subject

    def test_high_priority_subject(self):
        """No critical but high urgency produces ACTION REQUIRED prefix."""
        summarizer = EmailSummarizer(use_llm=False)
        updates = [
            _make_update(mc_id="MC111111", urgency=UrgencyTier.HIGH),
            _make_update(mc_id="MC222222", urgency=UrgencyTier.NORMAL),
        ]
        subject = summarizer.get_major_subject_line(updates)
        assert subject.startswith("ACTION REQUIRED:")
        assert "2 Major Update(s)" in subject

    def test_normal_subject(self):
        """All normal urgency produces standard prefix."""
        summarizer = EmailSummarizer(use_llm=False)
        updates = [
            _make_update(mc_id="MC111111", urgency=UrgencyTier.NORMAL),
            _make_update(mc_id="MC222222", urgency=UrgencyTier.NORMAL),
        ]
        subject = summarizer.get_major_subject_line(updates)
        assert subject.startswith("Major Updates Digest")
        assert "2 Update(s)" in subject

    def test_includes_date(self):
        """Subject contains today's date in MM/DD/YYYY format."""
        summarizer = EmailSummarizer(use_llm=False)
        updates = [_make_update()]
        subject = summarizer.get_major_subject_line(updates)
        # Check for date pattern
        date_str = datetime.now().strftime("%m/%d/%Y")
        assert date_str in subject

    def test_includes_count(self):
        """Subject contains total update count."""
        summarizer = EmailSummarizer(use_llm=False)
        updates = [
            _make_update(mc_id="MC111111"),
            _make_update(mc_id="MC222222"),
            _make_update(mc_id="MC333333"),
        ]
        subject = summarizer.get_major_subject_line(updates)
        assert "3" in subject


class TestActionItemsDisplay:
    """Test AI-extracted action items rendering in major digest HTML."""

    def test_actions_displayed_inline(self):
        """Pass actions dict with 2 actions for an update. Verify HTML contains ACTION ITEMS header and both action texts."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(mc_id="MC123456")

        action1 = AdminAction(action="Update auth settings")
        action2 = AdminAction(action="Review tenant config")
        extraction = ActionExtraction(actions=[action1, action2], confidence="HIGH")
        actions = {"MC123456": extraction}

        html = summarizer.format_major_updates_html([update], actions=actions)

        assert "ACTION ITEMS" in html
        assert "Update auth settings" in html
        assert "Review tenant config" in html

    def test_actions_with_role_badge(self):
        """Pass action with role='Global Admin'. Verify HTML contains role badge span with 'Global Admin' text."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(mc_id="MC123456")

        action = AdminAction(action="Enable new feature", role="Global Admin")
        extraction = ActionExtraction(actions=[action], confidence="HIGH")
        actions = {"MC123456": extraction}

        html = summarizer.format_major_updates_html([update], actions=actions)

        assert "ACTION ITEMS" in html
        assert "Enable new feature" in html
        assert "Global Admin" in html

    def test_actions_with_details(self):
        """Pass action with details='Check tenant config page'. Verify details text appears in HTML."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(mc_id="MC123456")

        action = AdminAction(
            action="Review settings",
            details="Check tenant config page"
        )
        extraction = ActionExtraction(actions=[action], confidence="HIGH")
        actions = {"MC123456": extraction}

        html = summarizer.format_major_updates_html([update], actions=actions)

        assert "ACTION ITEMS" in html
        assert "Review settings" in html
        assert "Check tenant config page" in html

    def test_actions_limit_to_three(self):
        """Pass actions dict with 5 actions. Verify only first 3 appear in HTML."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(mc_id="MC123456")

        actions_list = [
            AdminAction(action="Action 1"),
            AdminAction(action="Action 2"),
            AdminAction(action="Action 3"),
            AdminAction(action="Action 4"),
            AdminAction(action="Action 5"),
        ]
        extraction = ActionExtraction(actions=actions_list, confidence="HIGH")
        actions = {"MC123456": extraction}

        html = summarizer.format_major_updates_html([update], actions=actions)

        assert "Action 1" in html
        assert "Action 2" in html
        assert "Action 3" in html
        assert "Action 4" not in html
        assert "Action 5" not in html

    def test_no_actions_shows_body_preview(self):
        """Pass actions=None. Verify body_preview still appears, no ACTION ITEMS section."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(mc_id="MC123456", body_preview="Test body preview text")

        html = summarizer.format_major_updates_html([update], actions=None)

        assert "Test body preview text" in html
        assert "ACTION ITEMS" not in html

    def test_failed_extraction_no_action_section(self):
        """Pass actions dict with mc_id mapped to None. Verify no ACTION ITEMS section for that update."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(mc_id="MC123456", body_preview="Test body preview")

        actions = {"MC123456": None}  # Extraction failed

        html = summarizer.format_major_updates_html([update], actions=actions)

        assert "Test body preview" in html
        assert "ACTION ITEMS" not in html

    def test_actions_mixed_success_failure(self):
        """Pass actions dict with one mc_id=ActionExtraction and another mc_id=None. Verify first update has actions, second does not."""
        summarizer = EmailSummarizer(use_llm=False)
        update1 = _make_update(mc_id="MC111111")
        update2 = _make_update(mc_id="MC222222")

        action = AdminAction(action="Test action")
        extraction = ActionExtraction(actions=[action], confidence="HIGH")
        actions = {
            "MC111111": extraction,  # Success
            "MC222222": None  # Failed
        }

        html = summarizer.format_major_updates_html([update1, update2], actions=actions)

        # First update has actions
        mc111_pos = html.find("MC111111")
        mc222_pos = html.find("MC222222")
        action_pos = html.find("ACTION ITEMS")

        # ACTION ITEMS should appear between MC111111 and MC222222
        assert mc111_pos < action_pos < mc222_pos

    def test_no_actions_param_backward_compatible(self):
        """Call format_major_updates_html WITHOUT the actions param (old call signature). Verify it works without error."""
        summarizer = EmailSummarizer(use_llm=False)
        update = _make_update(mc_id="MC123456")

        # Call without actions parameter (backward compatible)
        html = summarizer.format_major_updates_html([update])

        assert "MC123456" in html
        assert "ACTION ITEMS" not in html
