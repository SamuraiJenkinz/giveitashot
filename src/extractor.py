"""
Message Center email field extraction and urgency calculation.
Extracts structured fields from major update emails for digest rendering.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from .ews_client import Email

logger = logging.getLogger(__name__)


class UrgencyTier(str, Enum):
    """Urgency classification based on action-required date proximity."""
    CRITICAL = "Critical"  # <= 7 days
    HIGH = "High"         # <= 30 days
    NORMAL = "Normal"     # > 30 days or no date


@dataclass
class MajorUpdateFields:
    """Structured fields extracted from a major update email."""
    mc_id: Optional[str]
    action_required_date: Optional[datetime]
    affected_services: list[str]
    categories: list[str]
    published_date: datetime
    last_updated_date: datetime
    body_preview: str
    urgency: UrgencyTier
    is_updated: bool
    subject: str


class MessageCenterExtractor:
    """
    Extracts structured fields from Message Center major update emails.

    Provides extraction of:
    - MC ID (MC###### format with 5-7 digits)
    - Action-required dates (multiple format support)
    - Affected services (Exchange, Teams, SharePoint, etc.)
    - Category tags (MAJOR UPDATE, ADMIN IMPACT, etc.)
    - Urgency tiers (Critical/High/Normal based on deadline proximity)
    - Deduplication (by MC ID, keeping latest version)
    """

    # Compiled regex patterns for performance
    MC_ID_PATTERN = re.compile(r'\bMC(\d{5,7})\b', re.IGNORECASE)
    ACTION_DATE_PATTERN = re.compile(
        r'(?:action required by|act by|deadline[:\s]|by)\s*'
        r'(\w+ \d{1,2},?\s*\d{4}|\d{1,2}/\d{1,2}/\d{4})',
        re.IGNORECASE
    )
    SERVICE_PATTERN = re.compile(
        r'\b(Exchange Online|Microsoft 365 Apps|Microsoft Teams|Teams|'
        r'SharePoint Online|SharePoint|OneDrive for Business|OneDrive|'
        r'Power Platform|Power BI|Power Automate|Power Apps|'
        r'Microsoft Viva|Viva|Microsoft Intune|Intune|'
        r'Microsoft Entra|Entra|Windows|Outlook|'
        r'Microsoft Purview|Purview|Microsoft Copilot|Copilot)\b',
        re.IGNORECASE
    )
    CATEGORY_PATTERN = re.compile(
        r'\b(MAJOR UPDATE|ADMIN IMPACT|USER IMPACT|RETIREMENT|'
        r'BREAKING CHANGE|ACTION REQUIRED)\b',
        re.IGNORECASE
    )

    def extract(self, email: Email) -> MajorUpdateFields:
        """
        Extract all structured fields from a single email.

        Args:
            email: Email object to extract fields from.

        Returns:
            MajorUpdateFields with all extracted data and calculated urgency.
        """
        mc_id = self._extract_mc_id(email)
        action_date = self._extract_action_date(email)
        services = self._extract_services(email)
        categories = self._extract_categories(email)
        urgency = self._calculate_urgency(action_date)
        body_preview = self._make_body_preview(email.body_content)

        return MajorUpdateFields(
            mc_id=mc_id,
            action_required_date=action_date,
            affected_services=services,
            categories=categories,
            published_date=email.received_datetime,
            last_updated_date=email.received_datetime,
            body_preview=body_preview,
            urgency=urgency,
            is_updated=False,
            subject=email.subject
        )

    def extract_batch(self, emails: list[Email]) -> list[MajorUpdateFields]:
        """
        Extract fields from multiple emails.

        Args:
            emails: List of Email objects.

        Returns:
            List of MajorUpdateFields, one per email.
        """
        return [self.extract(email) for email in emails]

    def deduplicate(self, fields_list: list[MajorUpdateFields]) -> list[MajorUpdateFields]:
        """
        Deduplicate major updates by MC ID, keeping the latest version.

        Groups by mc_id and keeps the entry with the latest published_date.
        Sets is_updated=True on kept entries that had duplicates.
        Entries with mc_id=None are never deduplicated.

        Args:
            fields_list: List of MajorUpdateFields to deduplicate.

        Returns:
            Deduplicated list with is_updated flags set appropriately.
        """
        # Separate entries with and without MC IDs
        without_mc = [f for f in fields_list if f.mc_id is None]
        with_mc = [f for f in fields_list if f.mc_id is not None]

        # Group by MC ID
        mc_groups: dict[str, list[MajorUpdateFields]] = {}
        for field in with_mc:
            if field.mc_id not in mc_groups:
                mc_groups[field.mc_id] = []
            mc_groups[field.mc_id].append(field)

        # Keep latest from each group and mark if updated
        deduplicated = []
        for mc_id, group in mc_groups.items():
            if len(group) == 1:
                # No duplicates, keep as-is
                deduplicated.append(group[0])
            else:
                # Multiple versions, keep latest and mark as updated
                latest = max(group, key=lambda f: f.published_date)
                latest.is_updated = True
                latest.last_updated_date = latest.published_date
                deduplicated.append(latest)
                logger.info(
                    f"Deduplicated {mc_id}: kept version from "
                    f"{latest.published_date.isoformat()}"
                )

        # Add back entries without MC IDs
        result = deduplicated + without_mc
        logger.info(
            f"Deduplication complete: {len(fields_list)} → {len(result)} "
            f"({len(fields_list) - len(result)} duplicates removed)"
        )
        return result

    def _calculate_urgency(self, action_date: Optional[datetime]) -> UrgencyTier:
        """
        Calculate urgency tier based on action-required date proximity.

        Args:
            action_date: Action-required date or None.

        Returns:
            UrgencyTier: CRITICAL (<=7 days), HIGH (<=30 days), or NORMAL.
        """
        if action_date is None:
            return UrgencyTier.NORMAL

        days_remaining = (action_date.date() - datetime.now().date()).days

        if days_remaining <= 7:
            return UrgencyTier.CRITICAL
        elif days_remaining <= 30:
            return UrgencyTier.HIGH
        else:
            return UrgencyTier.NORMAL

    def _extract_mc_id(self, email: Email) -> Optional[str]:
        """
        Extract MC ID from email subject or body.

        Searches subject first, then falls back to body.

        Args:
            email: Email to search.

        Returns:
            MC ID in format "MC######" or None if not found.
        """
        # Search subject first
        match = self.MC_ID_PATTERN.search(email.subject)
        if match:
            return f"MC{match.group(1)}"

        # Fall back to body
        match = self.MC_ID_PATTERN.search(email.body_content)
        if match:
            return f"MC{match.group(1)}"

        return None

    def _extract_action_date(self, email: Email) -> Optional[datetime]:
        """
        Extract action-required date from email body.

        Supports multiple date formats:
        - MM/DD/YYYY (e.g., "03/15/2026")
        - Month DD, YYYY (e.g., "March 15, 2026")
        - Month DD YYYY (e.g., "March 15 2026")

        Args:
            email: Email to search.

        Returns:
            Parsed datetime or None if not found or unparseable.
        """
        match = self.ACTION_DATE_PATTERN.search(email.body_content)
        if not match:
            return None

        date_str = match.group(1).strip()

        # Try multiple date formats
        date_formats = [
            "%m/%d/%Y",           # 03/15/2026
            "%B %d, %Y",          # March 15, 2026
            "%B %d %Y",           # March 15 2026
            "%b %d, %Y",          # Mar 15, 2026
            "%b %d %Y",           # Mar 15 2026
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # All formats failed
        logger.warning(f"Could not parse action date: {date_str}")
        return None

    def _extract_services(self, email: Email) -> list[str]:
        """
        Extract affected services from email subject and body.

        Args:
            email: Email to search.

        Returns:
            Deduplicated list of service names in title case.
        """
        # Search both subject and body
        search_text = f"{email.subject} {email.body_content}"
        matches = self.SERVICE_PATTERN.findall(search_text)

        # Deduplicate while preserving order
        seen = set()
        services = []
        for service in matches:
            service_lower = service.lower()
            if service_lower not in seen:
                seen.add(service_lower)
                # Normalize capitalization for display
                services.append(service.title())

        return services

    def _extract_categories(self, email: Email) -> list[str]:
        """
        Extract category tags from email subject and body.

        Args:
            email: Email to search.

        Returns:
            Deduplicated list of category names in uppercase.
        """
        # Search both subject and body
        search_text = f"{email.subject} {email.body_content}"
        matches = self.CATEGORY_PATTERN.findall(search_text)

        # Deduplicate while preserving order
        seen = set()
        categories = []
        for category in matches:
            category_upper = category.upper()
            if category_upper not in seen:
                seen.add(category_upper)
                categories.append(category_upper)

        return categories

    def _make_body_preview(self, body_content: str, max_length: int = 200) -> str:
        """
        Create a truncated body preview.

        Truncates at word boundary and adds "..." if truncated.

        Args:
            body_content: Full body content.
            max_length: Maximum preview length in characters.

        Returns:
            Body preview string.
        """
        if len(body_content) <= max_length:
            return body_content

        # Truncate at word boundary
        truncated = body_content[:max_length]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]

        return truncated + "..."
