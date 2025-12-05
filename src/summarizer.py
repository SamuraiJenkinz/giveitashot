"""
Email summarization module.
Generates concise summaries of emails for daily digest.
Supports both basic and LLM-powered summarization.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .config import Config
from .ews_client import Email

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

    def format_summary_html(self, summary: DailySummary, mailbox: str) -> str:
        """Format the summary as a professional HTML email."""

        # Color palette
        colors = {
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
