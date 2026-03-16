"""
Email summarization module.
Generates concise summaries of emails for daily digest.
Supports both basic and LLM-powered summarization.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from .config import Config
from .graph_client import Email
from .extractor import MajorUpdateFields, UrgencyTier

if TYPE_CHECKING:
    from .action_extractor import ActionExtraction

logger = logging.getLogger(__name__)


@dataclass
class EmailSummary:
    """Summary of a single email."""
    subject: str
    sender: str
    sender_email: str
    time: str
    key_points: str
    has_attachments: bool
    category: str = ""


@dataclass
class DailySummary:
    """Complete daily email summary."""
    date: str
    total_count: int
    email_summaries: list[EmailSummary]
    categories: dict[str, list[EmailSummary]]
    executive_digest: dict = field(default_factory=dict)


class EmailSummarizer:
    """
    Summarizes emails for daily digest.
    Supports LLM-powered intelligent summaries when configured.
    """

    def __init__(self, max_body_length: int = 500, use_llm: Optional[bool] = None):
        """
        Initialize the summarizer.

        Args:
            max_body_length: Maximum characters for basic summary
            use_llm: Override LLM usage (None = use config setting)
        """
        self._max_body_length = max_body_length
        self._use_llm = use_llm if use_llm is not None else Config.USE_LLM_SUMMARY
        self._llm_summarizer = None

        if self._use_llm:
            try:
                from .llm_summarizer import LLMSummarizer
                self._llm_summarizer = LLMSummarizer()
                logger.info("LLM summarization enabled")
            except Exception as e:
                logger.warning(f"LLM summarization unavailable: {e}")
                self._use_llm = False

    def _extract_key_points(self, email: Email) -> str:
        """Extract key points from an email body (basic method)."""
        content = email.body_preview or email.body_content

        if not content:
            return "(No content)"

        if len(content) > self._max_body_length:
            content = content[:self._max_body_length].rsplit(' ', 1)[0] + "..."

        return content

    def _get_sender_domain(self, email: str) -> str:
        """Extract domain from email address."""
        if '@' in email:
            return email.split('@')[1].lower()
        return "unknown"

    def _summarize_email(self, email: Email) -> EmailSummary:
        """Create a summary for a single email."""
        if self._llm_summarizer:
            key_points = self._llm_summarizer.summarize_email(email)
        else:
            key_points = self._extract_key_points(email)

        return EmailSummary(
            subject=email.subject,
            sender=email.sender_name,
            sender_email=email.sender_email,
            time=email.received_time_local,
            key_points=key_points,
            has_attachments=email.has_attachments
        )

    def summarize_emails(self, emails: list[Email]) -> DailySummary:
        """Create a complete daily summary from a list of emails."""
        today = datetime.now().strftime("%A, %B %d, %Y")

        if not emails:
            return DailySummary(
                date=today,
                total_count=0,
                email_summaries=[],
                categories={},
                executive_digest={"summary": "No emails received today."}
            )

        # Generate executive digest first if LLM available
        executive_digest = {}
        if self._llm_summarizer:
            logger.info("Generating AI executive digest...")
            executive_digest = self._llm_summarizer.generate_daily_digest(emails)

        # Summarize each email
        logger.info(f"Summarizing {len(emails)} emails...")
        summaries = [self._summarize_email(email) for email in emails]

        # Categorize emails
        if self._llm_summarizer:
            llm_categories = self._llm_summarizer.categorize_emails(emails)
            if llm_categories:
                categories: dict[str, list[EmailSummary]] = defaultdict(list)
                for category, indices in llm_categories.items():
                    for idx in indices:
                        if 1 <= idx <= len(summaries):
                            summaries[idx - 1].category = category
                            categories[category].append(summaries[idx - 1])
            else:
                categories = self._categorize_by_domain(emails, summaries)
        else:
            categories = self._categorize_by_domain(emails, summaries)

        sorted_categories = dict(
            sorted(categories.items(), key=lambda x: len(x[1]), reverse=True)
        )

        return DailySummary(
            date=today,
            total_count=len(emails),
            email_summaries=summaries,
            categories=sorted_categories,
            executive_digest=executive_digest
        )

    def _categorize_by_domain(
        self,
        emails: list[Email],
        summaries: list[EmailSummary]
    ) -> dict[str, list[EmailSummary]]:
        """Categorize emails by sender domain."""
        categories: dict[str, list[EmailSummary]] = defaultdict(list)
        for email, summary in zip(emails, summaries):
            domain = self._get_sender_domain(email.sender_email)
            summary.category = domain
            categories[domain].append(summary)
        return categories

    def _get_color_palette(self) -> dict[str, str]:
        """
        Get the standard color palette for HTML emails.

        Returns:
            Dictionary of color names to hex values.
        """
        return {
            "primary": "#1a73e8",       # Blue
            "primary_dark": "#1557b0",
            "success": "#34a853",        # Green
            "warning": "#fbbc04",        # Yellow
            "danger": "#ea4335",         # Red
            "text_dark": "#202124",
            "text_medium": "#5f6368",
            "text_light": "#80868b",
            "bg_light": "#f8f9fa",
            "bg_card": "#ffffff",
            "border": "#e8eaed",
        }

    def format_summary_html(self, summary: DailySummary, mailbox: str) -> str:
        """Format the summary as a professional HTML email."""

        # Color palette
        colors = self._get_color_palette()

        if summary.total_count == 0:
            return self._format_no_emails_html(summary, mailbox, colors)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: {colors['bg_light']}; font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: {colors['bg_light']};">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background-color: {colors['bg_card']}; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">

                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, {colors['primary']} 0%, {colors['primary_dark']} 100%); padding: 32px 40px; border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">
                                📬 Daily Email Digest
                            </h1>
                            <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                                {summary.date}
                            </p>
                        </td>
                    </tr>

                    <!-- Stats Bar -->
                    <tr>
                        <td style="padding: 24px 40px; border-bottom: 1px solid {colors['border']};">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td width="50%">
                                        <p style="margin: 0; color: {colors['text_light']}; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Mailbox</p>
                                        <p style="margin: 4px 0 0 0; color: {colors['text_dark']}; font-size: 14px; font-weight: 500;">{mailbox}</p>
                                    </td>
                                    <td width="50%" align="right">
                                        <p style="margin: 0; color: {colors['text_light']}; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Total Emails</p>
                                        <p style="margin: 4px 0 0 0; color: {colors['primary']}; font-size: 28px; font-weight: 700;">{summary.total_count}</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
"""

        # Executive Summary Section
        if summary.executive_digest:
            digest = summary.executive_digest
            html += f"""
                    <!-- Executive Summary -->
                    <tr>
                        <td style="padding: 32px 40px; border-bottom: 1px solid {colors['border']};">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td>
                                        <h2 style="margin: 0 0 16px 0; color: {colors['text_dark']}; font-size: 18px; font-weight: 600;">
                                            🤖 AI Executive Summary
                                        </h2>
                                        <p style="margin: 0 0 20px 0; color: {colors['text_medium']}; font-size: 14px; line-height: 1.6;">
                                            {digest.get('summary', '')}
                                        </p>
"""

            # Urgent Items
            urgent_items = digest.get('urgent_items', [])
            if urgent_items:
                html += f"""
                                        <div style="background-color: #fef7f7; border-left: 4px solid {colors['danger']}; padding: 16px; border-radius: 0 8px 8px 0; margin-bottom: 16px;">
                                            <p style="margin: 0 0 8px 0; color: {colors['danger']}; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                                ⚠️ Urgent Items
                                            </p>
"""
                for item in urgent_items:
                    html += f"""
                                            <p style="margin: 6px 0; color: {colors['text_dark']}; font-size: 13px; padding-left: 16px;">• {item}</p>
"""
                html += """
                                        </div>
"""

            # Action Items
            action_items = digest.get('action_items', [])
            if action_items:
                html += f"""
                                        <div style="background-color: #f0f7ff; border-left: 4px solid {colors['primary']}; padding: 16px; border-radius: 0 8px 8px 0; margin-bottom: 16px;">
                                            <p style="margin: 0 0 8px 0; color: {colors['primary']}; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                                ✓ Action Items
                                            </p>
"""
                for item in action_items:
                    html += f"""
                                            <p style="margin: 6px 0; color: {colors['text_dark']}; font-size: 13px; padding-left: 16px;">• {item}</p>
"""
                html += """
                                        </div>
"""

            # Themes
            themes = digest.get('themes', [])
            if themes:
                html += f"""
                                        <div style="margin-top: 12px;">
                                            <p style="margin: 0 0 8px 0; color: {colors['text_light']}; font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">
                                                Topics
                                            </p>
                                            <p style="margin: 0;">
"""
                for theme in themes:
                    html += f"""
                                                <span style="display: inline-block; background-color: {colors['bg_light']}; color: {colors['text_medium']}; font-size: 12px; padding: 4px 12px; border-radius: 16px; margin: 2px 4px 2px 0;">{theme}</span>
"""
                html += """
                                            </p>
                                        </div>
"""

            html += """
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
"""

        # Email Details Section
        html += f"""
                    <!-- Email Details -->
                    <tr>
                        <td style="padding: 32px 40px;">
                            <h2 style="margin: 0 0 20px 0; color: {colors['text_dark']}; font-size: 18px; font-weight: 600;">
                                📋 Email Details
                            </h2>
"""

        # Category-based display
        category_icons = {
            "Action Required": "🎯",
            "Urgent": "🔴",
            "Meetings": "📅",
            "FYI/Informational": "ℹ️",
            "Other": "📧"
        }

        for category, category_emails in summary.categories.items():
            icon = category_icons.get(category, "📁")
            html += f"""
                            <div style="margin-bottom: 24px;">
                                <p style="margin: 0 0 12px 0; color: {colors['text_medium']}; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                    {icon} {category} ({len(category_emails)})
                                </p>
"""

            for email_summary in category_emails:
                attachment_icon = ' 📎' if email_summary.has_attachments else ''
                html += f"""
                                <div style="background-color: {colors['bg_light']}; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
                                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                        <tr>
                                            <td>
                                                <p style="margin: 0; color: {colors['text_dark']}; font-size: 14px; font-weight: 600;">
                                                    {email_summary.subject}{attachment_icon}
                                                </p>
                                                <p style="margin: 4px 0 0 0; color: {colors['text_light']}; font-size: 12px;">
                                                    {email_summary.sender} &lt;{email_summary.sender_email}&gt; • {email_summary.time}
                                                </p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding-top: 12px;">
                                                <p style="margin: 0; color: {colors['text_medium']}; font-size: 13px; line-height: 1.5;">
                                                    {email_summary.key_points}
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                </div>
"""
            html += """
                            </div>
"""

        # Footer
        html += f"""
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: {colors['bg_light']}; padding: 24px 40px; border-radius: 0 0 12px 12px; border-top: 1px solid {colors['border']};">
                            <p style="margin: 0; color: {colors['text_light']}; font-size: 12px; text-align: center;">
                                Generated automatically by Email Summarizer Agent with AI assistance
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

        return html

    def _format_no_emails_html(self, summary: DailySummary, mailbox: str, colors: dict) -> str:
        """Format the HTML for when there are no emails."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: {colors['bg_light']}; font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: {colors['bg_light']};">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background-color: {colors['bg_card']}; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">

                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, {colors['primary']} 0%, {colors['primary_dark']} 100%); padding: 32px 40px; border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">
                                📬 Daily Email Digest
                            </h1>
                            <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                                {summary.date}
                            </p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 48px 40px; text-align: center;">
                            <div style="font-size: 64px; margin-bottom: 16px;">✅</div>
                            <h2 style="margin: 0 0 8px 0; color: {colors['success']}; font-size: 20px; font-weight: 600;">
                                All Clear!
                            </h2>
                            <p style="margin: 0; color: {colors['text_medium']}; font-size: 14px;">
                                No emails received today in <strong>{mailbox}</strong>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: {colors['bg_light']}; padding: 24px 40px; border-radius: 0 0 12px 12px; border-top: 1px solid {colors['border']};">
                            <p style="margin: 0; color: {colors['text_light']}; font-size: 12px; text-align: center;">
                                Generated automatically by Email Summarizer Agent
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    def get_subject_line(self, summary: DailySummary, mailbox: str) -> str:
        """Generate the subject line for the summary email."""
        date_short = datetime.now().strftime("%m/%d/%Y")
        if summary.total_count == 0:
            return f"📬 Daily Digest ({date_short}): No emails in {mailbox}"
        else:
            ai_tag = "🤖 " if self._use_llm else ""
            return f"{ai_tag}📬 Daily Digest ({date_short}): {summary.total_count} email(s)"

    def format_major_updates_html(self, updates: list[MajorUpdateFields], actions: Optional[dict[str, "ActionExtraction"]] = None) -> str:
        """
        Format major updates as a professional HTML email digest.

        Args:
            updates: List of extracted major update fields.
            actions: Optional dict mapping mc_id to ActionExtraction (or None for failed extractions).

        Returns:
            Complete HTML email string, or empty string if no updates.
        """
        if not updates:
            return ""

        colors = self._get_color_palette()
        today = datetime.now()
        date_str = today.strftime("%A, %B %d, %Y")

        # Count updates by urgency tier
        tier_counts = {
            UrgencyTier.CRITICAL: 0,
            UrgencyTier.HIGH: 0,
            UrgencyTier.NORMAL: 0
        }
        for update in updates:
            tier_counts[update.urgency] += 1

        # Urgency tier colors
        tier_colors = {
            UrgencyTier.CRITICAL: colors["danger"],
            UrgencyTier.HIGH: colors["warning"],
            UrgencyTier.NORMAL: colors["success"]
        }

        # Urgency tier labels
        tier_labels = {
            UrgencyTier.CRITICAL: "CRITICAL - Immediate Action Required",
            UrgencyTier.HIGH: "HIGH PRIORITY - Action Required Within 30 Days",
            UrgencyTier.NORMAL: "NORMAL - Informational Updates"
        }

        # Build urgency breakdown text
        breakdown_parts = []
        if tier_counts[UrgencyTier.CRITICAL] > 0:
            breakdown_parts.append(f"{tier_counts[UrgencyTier.CRITICAL]} Critical")
        if tier_counts[UrgencyTier.HIGH] > 0:
            breakdown_parts.append(f"{tier_counts[UrgencyTier.HIGH]} High")
        if tier_counts[UrgencyTier.NORMAL] > 0:
            breakdown_parts.append(f"{tier_counts[UrgencyTier.NORMAL]} Normal")
        urgency_breakdown = ", ".join(breakdown_parts)

        # Start HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: {colors['bg_light']}; font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: {colors['bg_light']};">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background-color: {colors['bg_card']}; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">

                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, {colors['danger']} 0%, {colors['primary']} 100%); padding: 32px 40px; border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">
                                🛡️ Major Updates Digest
                            </h1>
                            <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                                {date_str}
                            </p>
                        </td>
                    </tr>

                    <!-- Stats Bar -->
                    <tr>
                        <td style="padding: 24px 40px; border-bottom: 1px solid {colors['border']};">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td width="50%">
                                        <p style="margin: 0; color: {colors['text_light']}; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Major Updates</p>
                                        <p style="margin: 4px 0 0 0; color: {colors['text_dark']}; font-size: 14px; font-weight: 500;">{urgency_breakdown}</p>
                                    </td>
                                    <td width="50%" align="right">
                                        <p style="margin: 0; color: {colors['text_light']}; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Total Updates</p>
                                        <p style="margin: 4px 0 0 0; color: {colors['primary']}; font-size: 28px; font-weight: 700;">{len(updates)}</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Main Content -->
                    <tr>
                        <td style="padding: 32px 40px;">
"""

        # Render updates grouped by urgency tier
        for tier in [UrgencyTier.CRITICAL, UrgencyTier.HIGH, UrgencyTier.NORMAL]:
            tier_updates = [u for u in updates if u.urgency == tier]
            if not tier_updates:
                continue

            # Sort by action date (soonest first, None last)
            def sort_key(u):
                if u.action_required_date is None:
                    return (1, datetime.max)
                return (0, u.action_required_date)
            tier_updates.sort(key=sort_key)

            tier_color = tier_colors[tier]
            tier_label = tier_labels[tier]

            html += f"""
                            <!-- {tier.value} Section -->
                            <div style="margin-bottom: 32px;">
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                    <tr>
                                        <td>
                                            <p style="margin: 0 0 16px 0; color: {colors['text_dark']}; font-size: 15px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                                <span style="display: inline-block; width: 8px; height: 8px; background-color: {tier_color}; border-radius: 50%; margin-right: 8px;"></span>
                                                {tier_label}
                                            </p>
                                        </td>
                                    </tr>
                </table>
"""

            for update in tier_updates:
                # MC ID with optional UPDATED badge
                mc_id_display = update.mc_id if update.mc_id else "MC######"
                updated_badge = ""
                if update.is_updated:
                    updated_badge = f' <span style="display: inline-block; background-color: {colors["warning"]}; color: #ffffff; font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; margin-left: 4px;">UPDATED</span>'

                # Action date and days remaining
                action_date_html = ""
                if update.action_required_date:
                    date_formatted = update.action_required_date.strftime("%B %d, %Y")
                    days_diff = (update.action_required_date.date() - today.date()).days

                    if days_diff < 0:
                        # Overdue
                        days_text = f'<span style="color: {colors["danger"]}; font-weight: 600;">(OVERDUE - {abs(days_diff)} days past deadline)</span>'
                    else:
                        days_text = f"({days_diff} days remaining)"

                    action_date_html = f"""
                                                <p style="margin: 8px 0 0 0; color: {colors['text_dark']}; font-size: 13px;">
                                                    <strong>Action Required:</strong> {date_formatted} {days_text}
                                                </p>
"""
                else:
                    action_date_html = f"""
                                                <p style="margin: 8px 0 0 0; color: {colors['text_light']}; font-size: 13px;">
                                                    No deadline specified
                                                </p>
"""

                # Affected services
                services_html = ""
                if update.affected_services:
                    services_list = ", ".join(update.affected_services)
                    services_html = f"""
                                                <p style="margin: 8px 0 0 0; color: {colors['text_medium']}; font-size: 12px;">
                                                    <strong>Services:</strong> {services_list}
                                                </p>
"""
                else:
                    services_html = f"""
                                                <p style="margin: 8px 0 0 0; color: {colors['text_light']}; font-size: 12px;">
                                                    <strong>Services:</strong> Services not specified
                                                </p>
"""

                # Categories
                categories_html = ""
                if update.categories:
                    categories_pills = []
                    for i, category in enumerate(update.categories):
                        if i == 0:
                            # Primary category - use tier color
                            bg_color = tier_color
                            text_color = "#ffffff"
                        else:
                            # Secondary categories - muted
                            bg_color = colors["bg_light"]
                            text_color = colors["text_medium"]
                        categories_pills.append(
                            f'<span style="display: inline-block; background-color: {bg_color}; color: {text_color}; font-size: 10px; font-weight: 600; padding: 4px 8px; border-radius: 4px; margin: 2px 4px 2px 0;">{category}</span>'
                        )
                    categories_html = f"""
                                                <p style="margin: 8px 0 0 0;">
                                                    {"".join(categories_pills)}
                                                </p>
"""

                # Published and updated dates
                published_str = update.published_date.strftime("%b %d, %Y")
                dates_html = f"""
                                                <p style="margin: 8px 0 0 0; color: {colors['text_light']}; font-size: 11px;">
                                                    <strong>Published:</strong> {published_str}
"""
                if update.is_updated:
                    updated_str = update.last_updated_date.strftime("%b %d, %Y")
                    dates_html += f"""                                                    <span style="margin-left: 12px;"><strong>Updated:</strong> {updated_str}</span>
"""
                dates_html += """                                                </p>
"""

                # Body preview
                body_preview_html = ""
                if update.body_preview:
                    body_preview_html = f"""
                                                <p style="margin: 12px 0 0 0; color: {colors['text_medium']}; font-size: 13px; line-height: 1.5;">
                                                    {update.body_preview}
                                                </p>
"""

                # Action items (AI-extracted)
                actions_html = ""
                if actions and update.mc_id:
                    update_actions = actions.get(update.mc_id)
                    if update_actions and update_actions.actions:
                        # Limit to first 3 actions for layout safety
                        actions_to_display = update_actions.actions[:3]
                        actions_bullets = []
                        for action in actions_to_display:
                            # Build action text with optional role badge
                            role_badge = ""
                            if action.role:
                                role_badge = f'<span style="display: inline-block; background-color: {colors["primary"]}; color: #ffffff; font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-left: 4px;">{action.role}</span>'

                            action_text = f'<p style="margin: 6px 0; color: {colors["text_dark"]}; font-size: 13px;">• {action.action}{role_badge}</p>'

                            # Add details if present
                            if action.details:
                                action_text += f'<p style="margin: 2px 0 6px 16px; color: {colors["text_medium"]}; font-size: 12px; font-style: italic;">{action.details}</p>'

                            actions_bullets.append(action_text)

                        actions_html = f"""
                                                <div style="margin-top: 12px; padding: 12px; background-color: {colors['bg_card']}; border: 1px solid {colors['border']}; border-radius: 6px;">
                                                    <p style="margin: 0 0 8px 0; color: {colors['text_dark']}; font-size: 12px; font-weight: 600;">
                                                        ⚡ ACTION ITEMS
                                                    </p>
                                                    {"".join(actions_bullets)}
                                                </div>
"""

                # Update card
                html += f"""
                                <div style="background-color: {colors['bg_light']}; border-left: 4px solid {tier_color}; border-radius: 0 8px 8px 0; padding: 16px; margin-bottom: 16px;">
                                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                        <tr>
                                            <td>
                                                <p style="margin: 0; color: {colors['primary']}; font-size: 14px; font-weight: 700;">
                                                    {mc_id_display}{updated_badge}
                                                </p>
{action_date_html}{services_html}{categories_html}{dates_html}{body_preview_html}{actions_html}
                                            </td>
                                        </tr>
                                    </table>
                                </div>
"""

            html += """
                            </div>
"""

        # Footer
        html += f"""
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: {colors['bg_light']}; padding: 24px 40px; border-radius: 0 0 12px 12px; border-top: 1px solid {colors['border']};">
                            <p style="margin: 0; color: {colors['text_light']}; font-size: 12px; text-align: center;">
                                Generated automatically by InboxIQ Major Updates Digest
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

        return html

    def get_major_subject_line(self, updates: list[MajorUpdateFields]) -> str:
        """
        Generate subject line for major updates digest.

        Args:
            updates: List of extracted major update fields.

        Returns:
            Subject line with urgency-based prefix and counts.
        """
        date_str = datetime.now().strftime("%m/%d/%Y")
        total = len(updates)

        # Count by urgency
        critical_count = sum(1 for u in updates if u.urgency == UrgencyTier.CRITICAL)
        high_count = sum(1 for u in updates if u.urgency == UrgencyTier.HIGH)

        if critical_count > 0:
            return f"CRITICAL: {total} Major Update(s) Require Immediate Action ({date_str})"
        elif high_count > 0:
            return f"ACTION REQUIRED: {total} Major Update(s) ({date_str})"
        else:
            return f"Major Updates Digest ({date_str}) - {total} Update(s)"
