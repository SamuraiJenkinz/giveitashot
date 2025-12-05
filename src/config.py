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


class Config:
    """Application configuration loaded from environment variables."""

    # Azure AD Configuration for OAuth
    TENANT_ID: str = os.getenv("AZURE_TENANT_ID", "")
    CLIENT_ID: str = os.getenv("AZURE_CLIENT_ID", "")
    CLIENT_SECRET: str = os.getenv("AZURE_CLIENT_SECRET", "")

    # EWS Configuration
    EWS_SERVER: str = os.getenv("EWS_SERVER", "outlook.office365.com")

    # User email for sending (the account to send from)
    USER_EMAIL: str = os.getenv("USER_EMAIL", "kevin.j.taylor@mmc.com")

    # Email Configuration
    SHARED_MAILBOX: str = os.getenv("SHARED_MAILBOX", "messagingai@marsh.com")
    SUMMARY_RECIPIENT: str = os.getenv("SUMMARY_RECIPIENT", "kevin.j.taylor@mmc.com")

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
        missing = []

        if not cls.TENANT_ID:
            missing.append("AZURE_TENANT_ID")
        if not cls.CLIENT_ID:
            missing.append("AZURE_CLIENT_ID")
        if not cls.CLIENT_SECRET:
            missing.append("AZURE_CLIENT_SECRET")
        if not cls.USER_EMAIL:
            missing.append("USER_EMAIL")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Please copy .env.example to .env and fill in your values."
            )

    @classmethod
    def get_authority(cls) -> str:
        """Get the Azure AD authority URL with current tenant ID."""
        return f"https://login.microsoftonline.com/{cls.TENANT_ID}"
