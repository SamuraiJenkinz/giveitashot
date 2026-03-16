"""
OAuth 2.0 Authentication module for Microsoft Graph API using client credentials flow.
Uses app-only authentication with client secret for Microsoft Graph.
"""

import logging
from typing import Optional

import msal

from .config import Config

logger = logging.getLogger(__name__)

# Graph API scope for client credentials (app-only)
# Tokens acquired with this scope will have aud: https://graph.microsoft.com/
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

# NOTE: Client secret expires per Azure AD app registration (typically 24 months). Monitor expiry.


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class GraphAuthenticator:
    """
    Handles OAuth 2.0 authentication for Microsoft Graph API.
    Uses MSAL client credentials flow (app-only, no user interaction).
    """

    def __init__(self):
        """Initialize the authenticator with configuration."""
        Config.validate()
        self._app: Optional[msal.ConfidentialClientApplication] = None

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
        Acquire an access token for Microsoft Graph using client credentials flow.

        Returns:
            str: A valid bearer token string for use as Authorization header value.

        Raises:
            AuthenticationError: If authentication fails.
        """
        logger.info("Acquiring token using client credentials flow...")

        try:
            # acquire_token_for_client handles its own internal cache (MSAL 1.23+)
            # acquire_token_silent is redundant for client credentials flow
            result = self.app.acquire_token_for_client(scopes=GRAPH_SCOPE)

            if "access_token" in result:
                logger.info("Token acquired successfully")
                return result["access_token"]

            # Authentication failed
            error = result.get("error", "Unknown error")
            error_description = result.get("error_description", "No description available")
            raise AuthenticationError(f"Authentication failed: {error} - {error_description}")

        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise AuthenticationError(f"Authentication failed: {e}")

    def clear_cache(self) -> None:
        """Clear the cached MSAL application instance (useful for troubleshooting)."""
        self._app = None
        logger.info("Token cache cleared")

