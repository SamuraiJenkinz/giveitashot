"""
OAuth 2.0 Authentication module for EWS using client credentials flow.
Uses app-only authentication with client secret for Exchange Web Services.
"""

import logging
from typing import Optional

import msal
from exchangelib import OAuth2Credentials, Identity

from .config import Config

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class EWSAuthenticator:
    """
    Handles OAuth 2.0 authentication for Exchange Web Services.
    Uses MSAL client credentials flow (app-only, no user interaction).
    """

    def __init__(self):
        """Initialize the authenticator with configuration."""
        Config.validate()
        self._app: Optional[msal.ConfidentialClientApplication] = None
        self._access_token: Optional[str] = None

    @property
    def app(self) -> msal.ConfidentialClientApplication:
        """Get or create the MSAL application instance."""
        if self._app is None:
            self._app = msal.ConfidentialClientApplication(
                client_id=Config.CLIENT_ID,
                client_credential=Config.CLIENT_SECRET,
                authority=Config.get_authority()
            )
        return self._app

    def get_access_token(self) -> str:
        """
        Acquire an access token for EWS using client credentials flow.

        Returns:
            str: A valid access token for EWS.

        Raises:
            AuthenticationError: If authentication fails.
        """
        # EWS scope for client credentials (app-only)
        scopes = ["https://outlook.office365.com/.default"]

        logger.info("Acquiring token using client credentials flow...")

        try:
            # Try to get token from cache first
            result = self.app.acquire_token_silent(scopes=scopes, account=None)

            if not result:
                # No cached token, acquire new one
                logger.debug("No cached token, acquiring new token...")
                result = self.app.acquire_token_for_client(scopes=scopes)

            if "access_token" in result:
                logger.info("Token acquired successfully")
                self._access_token = result["access_token"]
                return result["access_token"]

            # Authentication failed
            error = result.get("error", "Unknown error")
            error_description = result.get("error_description", "No description available")
            raise AuthenticationError(f"Authentication failed: {error} - {error_description}")

        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise AuthenticationError(f"Authentication failed: {e}")

    def get_ews_credentials(self) -> OAuth2Credentials:
        """
        Get EWS credentials for use with exchangelib.

        Returns:
            OAuth2Credentials: Credentials object for exchangelib.
        """
        access_token = self.get_access_token()

        # Create OAuth2 credentials for exchangelib (app-only / client credentials)
        credentials = OAuth2Credentials(
            client_id=Config.CLIENT_ID,
            client_secret=Config.CLIENT_SECRET,
            tenant_id=Config.TENANT_ID,
            identity=Identity(primary_smtp_address=Config.USER_EMAIL)
        )

        return credentials

    def clear_cache(self) -> None:
        """Clear the cached token (useful for troubleshooting)."""
        self._app = None
        self._access_token = None
        logger.info("Token cache cleared")
