"""
Configuration management for the Email Summarizer Agent.
Loads settings from environment variables or .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def _parse_email_list(env_var: str, default: str = "") -> list[str]:
    """
    Parse a comma-separated list of email addresses from an environment variable.

    Args:
        env_var: Name of the environment variable.
        default: Default value if env var is not set.

    Returns:
        List of email addresses (stripped of whitespace), empty strings filtered out.
    """
    value = os.getenv(env_var, default)
    if not value:
        return []
    return [email.strip() for email in value.split(",") if email.strip()]


class Config:
    """Application configuration loaded from environment variables."""

    # Microsoft Graph / Azure AD Configuration for OAuth
    TENANT_ID: str = os.getenv("MICROSOFT_TENANT_ID", "")
    CLIENT_ID: str = os.getenv("MICROSOFT_CLIENT_ID", "")
    CLIENT_SECRET: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")

    # Sender email address (shared mailbox sender)
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "")

    # From address for sending (requires SendAs permission if different from SENDER_EMAIL)
    SEND_FROM: str = os.getenv("SEND_FROM", "")

    # Email Configuration
    SHARED_MAILBOX: str = os.getenv("SHARED_MAILBOX", "messagingai@marsh.com")

    # Legacy single recipient (for backwards compatibility)
    SUMMARY_RECIPIENT: str = os.getenv("SUMMARY_RECIPIENT", "kevin.j.taylor@mmc.com")

    # Multiple recipients support (TO, CC, BCC)
    # These take precedence over SUMMARY_RECIPIENT if set
    SUMMARY_TO: list[str] = _parse_email_list("SUMMARY_TO")
    SUMMARY_CC: list[str] = _parse_email_list("SUMMARY_CC")
    SUMMARY_BCC: list[str] = _parse_email_list("SUMMARY_BCC")

    # Major Update Digest Recipients (optional, enables major digest when TO has recipients)
    MAJOR_UPDATE_TO: list[str] = _parse_email_list("MAJOR_UPDATE_TO")
    MAJOR_UPDATE_CC: list[str] = _parse_email_list("MAJOR_UPDATE_CC")
    MAJOR_UPDATE_BCC: list[str] = _parse_email_list("MAJOR_UPDATE_BCC")

    @classmethod
    def get_recipients(cls) -> list[str]:
        """
        Get the list of TO recipients.
        Uses SUMMARY_TO if set, otherwise falls back to SUMMARY_RECIPIENT.

        Returns:
            List of TO recipient email addresses.
        """
        if cls.SUMMARY_TO:
            return cls.SUMMARY_TO
        elif cls.SUMMARY_RECIPIENT:
            return [cls.SUMMARY_RECIPIENT]
        return []

    @classmethod
    def is_major_digest_enabled(cls) -> bool:
        """
        Check if major update digest is enabled.
        Enabled when MAJOR_UPDATE_TO has at least one recipient.

        Returns:
            True if major digest is enabled, False otherwise.
        """
        return bool(cls.MAJOR_UPDATE_TO)

    @classmethod
    def get_major_recipients(cls) -> list[str]:
        """
        Get the list of major update digest TO recipients.
        No fallback - major digest recipients must be explicitly configured.

        Returns:
            List of major update TO recipient email addresses (may be empty).
        """
        return cls.MAJOR_UPDATE_TO

    @classmethod
    def get_send_from(cls) -> str:
        """
        Get the From address for sending emails.
        Uses SEND_FROM if set, otherwise falls back to SENDER_EMAIL.

        Returns:
            Email address to use as the From address.
        """
        return cls.SEND_FROM if cls.SEND_FROM else cls.SENDER_EMAIL

    # Token cache file location
    TOKEN_CACHE_FILE: Path = Path(__file__).parent.parent / ".token_cache.json"

    # Debug mode
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Azure OpenAI Configuration
    OPENAI_ENDPOINT: str = os.getenv("CHATGPT_ENDPOINT", "")
    OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    OPENAI_API_VERSION: str = os.getenv("API_VERSION", "2023-05-15")

    # LLM Summarization (set to false to use basic summarization)
    USE_LLM_SUMMARY: bool = os.getenv("USE_LLM_SUMMARY", "true").lower() == "true"

    @classmethod
    def validate(cls) -> None:
        """Validate that required configuration values are present."""
        import logging
        logger = logging.getLogger(__name__)

        missing = []

        if not cls.TENANT_ID:
            missing.append("MICROSOFT_TENANT_ID")
        if not cls.CLIENT_ID:
            missing.append("MICROSOFT_CLIENT_ID")
        if not cls.CLIENT_SECRET:
            missing.append("MICROSOFT_CLIENT_SECRET")
        if not cls.SENDER_EMAIL:
            missing.append("SENDER_EMAIL")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Please copy .env.example to .env and fill in your values."
            )

        # Validate at least one recipient is configured
        if not cls.get_recipients():
            raise ValueError(
                "No email recipients configured. "
                "Set either SUMMARY_RECIPIENT or SUMMARY_TO in your .env file."
            )

        # Validate major update digest recipients if feature is enabled
        if cls.is_major_digest_enabled():
            logger.info(f"Major digest enabled with {len(cls.MAJOR_UPDATE_TO)} TO recipient(s)")

            # Validate MAJOR_UPDATE_CC entries
            invalid_cc = [email for email in cls.MAJOR_UPDATE_CC if "@" not in email]
            if invalid_cc:
                raise ValueError(
                    f"Invalid MAJOR_UPDATE_CC addresses (missing '@'): {', '.join(invalid_cc)}"
                )

            # Validate MAJOR_UPDATE_BCC entries
            invalid_bcc = [email for email in cls.MAJOR_UPDATE_BCC if "@" not in email]
            if invalid_bcc:
                raise ValueError(
                    f"Invalid MAJOR_UPDATE_BCC addresses (missing '@'): {', '.join(invalid_bcc)}"
                )
        else:
            logger.debug("Major digest not enabled (MAJOR_UPDATE_TO empty or missing)")

    @classmethod
    def get_authority(cls) -> str:
        """Get the Azure AD authority URL with current tenant ID."""
        return f"https://login.microsoftonline.com/{cls.TENANT_ID}"
