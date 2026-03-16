"""
Unit tests for GraphAuthenticator.

Tests cover:
- GRAPH_SCOPE constant correctness
- get_access_token() returns plain str bearer token
- get_access_token() raises AuthenticationError on failure
- get_access_token() uses Graph scope (not Exchange scope)
- acquire_token_silent is NOT called (redundant per MSAL 1.23+)
- clear_cache() resets _app to None
"""

import pytest
from unittest.mock import MagicMock, patch, call

from src.auth import GraphAuthenticator, AuthenticationError, GRAPH_SCOPE
from src.config import Config


@pytest.fixture
def mock_config(monkeypatch):
    """
    Fixture that patches Config.validate to a no-op and sets test values
    for all Config attributes used by GraphAuthenticator.
    """
    monkeypatch.setattr(Config, "validate", lambda: None)
    monkeypatch.setattr(Config, "TENANT_ID", "test-tenant-id")
    monkeypatch.setattr(Config, "CLIENT_ID", "test-client-id")
    monkeypatch.setattr(Config, "CLIENT_SECRET", "test-client-secret")


def test_graph_scope_is_correct():
    """GRAPH_SCOPE must be the Graph API client-credentials scope."""
    assert GRAPH_SCOPE == ["https://graph.microsoft.com/.default"]


def test_get_access_token_returns_string(mock_config):
    """get_access_token() must return a plain str bearer token."""
    with patch("msal.ConfidentialClientApplication") as mock_msal:
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token-123"}
        mock_msal.return_value = mock_app

        auth = GraphAuthenticator()
        token = auth.get_access_token()

    assert token == "test-token-123"
    assert isinstance(token, str)


def test_get_access_token_raises_on_error(mock_config):
    """get_access_token() raises AuthenticationError when MSAL returns an error dict."""
    with patch("msal.ConfidentialClientApplication") as mock_msal:
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Bad secret"
        }
        mock_msal.return_value = mock_app

        auth = GraphAuthenticator()

        with pytest.raises(AuthenticationError) as exc_info:
            auth.get_access_token()

    assert "invalid_client" in str(exc_info.value)


def test_get_access_token_raises_on_exception(mock_config):
    """get_access_token() raises AuthenticationError when MSAL raises an exception."""
    with patch("msal.ConfidentialClientApplication") as mock_msal:
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.side_effect = Exception("network error")
        mock_msal.return_value = mock_app

        auth = GraphAuthenticator()

        with pytest.raises(AuthenticationError) as exc_info:
            auth.get_access_token()

    assert "network error" in str(exc_info.value)


def test_get_access_token_uses_graph_scope(mock_config):
    """get_access_token() must call acquire_token_for_client with GRAPH_SCOPE."""
    with patch("msal.ConfidentialClientApplication") as mock_msal:
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "token-xyz"}
        mock_msal.return_value = mock_app

        auth = GraphAuthenticator()
        auth.get_access_token()

        mock_app.acquire_token_for_client.assert_called_once_with(scopes=GRAPH_SCOPE)


def test_acquire_token_silent_not_called(mock_config):
    """acquire_token_silent must NOT be called — redundant for client credentials (MSAL 1.23+)."""
    with patch("msal.ConfidentialClientApplication") as mock_msal:
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "token"}
        mock_msal.return_value = mock_app

        auth = GraphAuthenticator()
        auth.get_access_token()

        mock_app.acquire_token_silent.assert_not_called()


def test_clear_cache_resets_app(mock_config):
    """clear_cache() must reset _app to None."""
    with patch("msal.ConfidentialClientApplication") as mock_msal:
        mock_msal.return_value = MagicMock()

        auth = GraphAuthenticator()
        _ = auth.app  # Force lazy initialisation

        assert auth._app is not None

        auth.clear_cache()

        assert auth._app is None
