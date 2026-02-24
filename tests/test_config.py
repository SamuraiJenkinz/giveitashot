"""
Unit tests for Configuration management.

Tests the major update digest configuration features including:
- Feature toggle activation based on MAJOR_UPDATE_TO presence
- Email address parsing for MAJOR_UPDATE_TO/CC/BCC
- Validation behavior when major digest is enabled/disabled
- No fallback from MAJOR_UPDATE_TO to SUMMARY_TO
"""

import pytest
from src.config import Config


@pytest.fixture
def backup_config():
    """
    Fixture to backup and restore Config class attributes.

    Since Config uses class-level attributes loaded from environment at import time,
    we need to save and restore them for test isolation.
    """
    # Backup original values
    backup = {
        "MAJOR_UPDATE_TO": Config.MAJOR_UPDATE_TO.copy(),
        "MAJOR_UPDATE_CC": Config.MAJOR_UPDATE_CC.copy(),
        "MAJOR_UPDATE_BCC": Config.MAJOR_UPDATE_BCC.copy(),
    }

    yield

    # Restore original values
    Config.MAJOR_UPDATE_TO = backup["MAJOR_UPDATE_TO"]
    Config.MAJOR_UPDATE_CC = backup["MAJOR_UPDATE_CC"]
    Config.MAJOR_UPDATE_BCC = backup["MAJOR_UPDATE_BCC"]


def test_major_digest_disabled_when_no_recipients(backup_config):
    """Test that is_major_digest_enabled() returns False when MAJOR_UPDATE_TO is empty."""
    Config.MAJOR_UPDATE_TO = []

    assert Config.is_major_digest_enabled() is False


def test_major_digest_enabled_when_recipients_set(backup_config):
    """Test that is_major_digest_enabled() returns True when MAJOR_UPDATE_TO has recipients."""
    Config.MAJOR_UPDATE_TO = ["admin@co.com"]

    assert Config.is_major_digest_enabled() is True


def test_major_recipients_parsed_correctly(backup_config):
    """Test that MAJOR_UPDATE_TO parses comma-separated addresses correctly."""
    Config.MAJOR_UPDATE_TO = ["a@b.com", "c@d.com"]

    assert Config.MAJOR_UPDATE_TO == ["a@b.com", "c@d.com"]


def test_major_cc_bcc_parsed(backup_config):
    """Test that MAJOR_UPDATE_CC and MAJOR_UPDATE_BCC parse correctly."""
    Config.MAJOR_UPDATE_CC = ["cc1@test.com", "cc2@test.com"]
    Config.MAJOR_UPDATE_BCC = ["bcc1@test.com"]

    assert Config.MAJOR_UPDATE_CC == ["cc1@test.com", "cc2@test.com"]
    assert Config.MAJOR_UPDATE_BCC == ["bcc1@test.com"]


def test_get_major_recipients_returns_to_list(backup_config):
    """Test that get_major_recipients() returns the MAJOR_UPDATE_TO list."""
    Config.MAJOR_UPDATE_TO = ["admin@co.com", "lead@co.com"]

    result = Config.get_major_recipients()

    assert result == ["admin@co.com", "lead@co.com"]


def test_get_major_recipients_no_fallback(backup_config):
    """Test that get_major_recipients() returns empty list with no fallback to SUMMARY_TO."""
    Config.MAJOR_UPDATE_TO = []
    Config.SUMMARY_TO = ["summary@co.com"]  # Should NOT be used as fallback

    result = Config.get_major_recipients()

    assert result == []
    assert result != Config.SUMMARY_TO  # Explicit check: no fallback


def test_validate_passes_when_major_disabled(backup_config):
    """Test that validate() does not raise when major digest is disabled."""
    # Set up valid basic config
    Config.TENANT_ID = "test-tenant"
    Config.CLIENT_ID = "test-client"
    Config.CLIENT_SECRET = "test-secret"
    Config.USER_EMAIL = "user@test.com"
    Config.SUMMARY_TO = ["summary@test.com"]

    # Major digest disabled
    Config.MAJOR_UPDATE_TO = []
    Config.MAJOR_UPDATE_CC = ["invalid-no-at-sign"]  # Invalid, but should be ignored
    Config.MAJOR_UPDATE_BCC = []

    # Should not raise even with invalid CC when major digest is disabled
    Config.validate()


def test_validate_passes_when_major_enabled_valid(backup_config):
    """Test that validate() passes with valid major digest configuration."""
    # Set up valid basic config
    Config.TENANT_ID = "test-tenant"
    Config.CLIENT_ID = "test-client"
    Config.CLIENT_SECRET = "test-secret"
    Config.USER_EMAIL = "user@test.com"
    Config.SUMMARY_TO = ["summary@test.com"]

    # Valid major digest config
    Config.MAJOR_UPDATE_TO = ["admin@test.com"]
    Config.MAJOR_UPDATE_CC = ["cc@test.com"]
    Config.MAJOR_UPDATE_BCC = ["bcc@test.com"]

    # Should not raise
    Config.validate()


def test_validate_fails_invalid_major_cc(backup_config):
    """Test that validate() raises ValueError when MAJOR_UPDATE_CC has invalid addresses."""
    # Set up valid basic config
    Config.TENANT_ID = "test-tenant"
    Config.CLIENT_ID = "test-client"
    Config.CLIENT_SECRET = "test-secret"
    Config.USER_EMAIL = "user@test.com"
    Config.SUMMARY_TO = ["summary@test.com"]

    # Major digest enabled with invalid CC
    Config.MAJOR_UPDATE_TO = ["admin@test.com"]
    Config.MAJOR_UPDATE_CC = ["valid@test.com", "invalid-no-at"]
    Config.MAJOR_UPDATE_BCC = []

    with pytest.raises(ValueError) as exc_info:
        Config.validate()

    assert "MAJOR_UPDATE_CC" in str(exc_info.value)
    assert "invalid-no-at" in str(exc_info.value)


def test_validate_fails_invalid_major_bcc(backup_config):
    """Test that validate() raises ValueError when MAJOR_UPDATE_BCC has invalid addresses."""
    # Set up valid basic config
    Config.TENANT_ID = "test-tenant"
    Config.CLIENT_ID = "test-client"
    Config.CLIENT_SECRET = "test-secret"
    Config.USER_EMAIL = "user@test.com"
    Config.SUMMARY_TO = ["summary@test.com"]

    # Major digest enabled with invalid BCC
    Config.MAJOR_UPDATE_TO = ["admin@test.com"]
    Config.MAJOR_UPDATE_CC = []
    Config.MAJOR_UPDATE_BCC = ["bcc-missing-at-sign"]

    with pytest.raises(ValueError) as exc_info:
        Config.validate()

    assert "MAJOR_UPDATE_BCC" in str(exc_info.value)
    assert "bcc-missing-at-sign" in str(exc_info.value)
