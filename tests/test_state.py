"""
Unit tests for StateManager with digest-type-aware state tracking.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from src.state import StateManager


@pytest.fixture
def state_file(tmp_path):
    """Provide a temporary state file path."""
    return tmp_path / ".state.json"


@pytest.fixture
def state_manager(state_file):
    """Provide a fresh StateManager instance."""
    return StateManager(state_file=state_file)


# Basic digest-type state tracking tests


def test_get_last_run_regular_default(state_manager):
    """get_last_run() with no args defaults to 'regular' digest type."""
    timestamp = datetime.now(timezone.utc)
    state_manager.set_last_run(timestamp, digest_type="regular")

    # Call without digest_type parameter - should default to "regular"
    result = state_manager.get_last_run()
    assert result is not None
    assert result == timestamp


def test_set_and_get_regular_last_run(state_manager):
    """set_last_run(digest_type='regular') then get_last_run('regular') returns the timestamp."""
    timestamp = datetime.now(timezone.utc)
    state_manager.set_last_run(timestamp, digest_type="regular")

    result = state_manager.get_last_run(digest_type="regular")
    assert result is not None
    assert result == timestamp


def test_set_and_get_major_last_run(state_manager):
    """set_last_run(digest_type='major') then get_last_run('major') returns the timestamp."""
    timestamp = datetime.now(timezone.utc)
    state_manager.set_last_run(timestamp, digest_type="major")

    result = state_manager.get_last_run(digest_type="major")
    assert result is not None
    assert result == timestamp


def test_independent_state_tracking(state_manager):
    """Setting regular last_run does NOT affect major last_run and vice versa."""
    regular_timestamp = datetime(2026, 2, 24, 10, 0, 0, tzinfo=timezone.utc)
    major_timestamp = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)

    state_manager.set_last_run(regular_timestamp, digest_type="regular")
    state_manager.set_last_run(major_timestamp, digest_type="major")

    regular_result = state_manager.get_last_run(digest_type="regular")
    major_result = state_manager.get_last_run(digest_type="major")

    assert regular_result == regular_timestamp
    assert major_result == major_timestamp
    assert regular_result != major_result


def test_get_last_run_returns_none_for_missing(state_manager):
    """get_last_run('major') returns None when only regular has been set."""
    timestamp = datetime.now(timezone.utc)
    state_manager.set_last_run(timestamp, digest_type="regular")

    # Major digest has not been set
    result = state_manager.get_last_run(digest_type="major")
    assert result is None


# State migration tests


def test_migration_old_last_run_to_regular(state_file):
    """State file with old {"last_run": "..."} format, after load, get_last_run('regular') returns the migrated timestamp."""
    # Write old format
    old_timestamp = "2026-02-24T10:00:00+00:00"
    old_state = {"last_run": old_timestamp}
    state_file.write_text(json.dumps(old_state))

    # Create StateManager (triggers _load with migration)
    sm = StateManager(state_file=state_file)

    # Should be able to read as regular
    result = sm.get_last_run("regular")
    assert result is not None
    assert result == datetime.fromisoformat(old_timestamp)


def test_migration_preserves_old_key(state_file):
    """After migration, old 'last_run' key still exists in state file (rollback safety)."""
    # Write old format
    old_timestamp = "2026-02-24T10:00:00+00:00"
    old_state = {"last_run": old_timestamp}
    state_file.write_text(json.dumps(old_state))

    # Create StateManager (triggers migration)
    sm = StateManager(state_file=state_file)

    # Read state file and verify old key is preserved
    persisted_state = json.loads(state_file.read_text())
    assert "last_run" in persisted_state
    assert persisted_state["last_run"] == old_timestamp


def test_no_migration_when_regular_exists(state_file):
    """If state file already has 'regular_last_run', migration does NOT overwrite it even if 'last_run' also exists."""
    # Write state with both keys
    old_timestamp = "2026-02-24T10:00:00+00:00"
    regular_timestamp = "2026-02-24T12:00:00+00:00"
    state = {
        "last_run": old_timestamp,
        "regular_last_run": regular_timestamp
    }
    state_file.write_text(json.dumps(state))

    # Create StateManager (should NOT migrate)
    sm = StateManager(state_file=state_file)

    # Should use the existing regular_last_run value
    result = sm.get_last_run("regular")
    assert result is not None
    assert result == datetime.fromisoformat(regular_timestamp)
    assert result != datetime.fromisoformat(old_timestamp)


# State isolation (corruption handling) tests


def test_corrupted_state_returns_none(state_file):
    """Write invalid JSON to state file, StateManager loads without error, get_last_run returns None."""
    # Write invalid JSON
    state_file.write_text("{ this is not valid json")

    # Should not crash
    sm = StateManager(state_file=state_file)

    # Should return None for missing state
    result = sm.get_last_run("regular")
    assert result is None


def test_corrupted_timestamp_returns_none(state_file):
    """Set state key to 'not-a-date', get_last_run returns None with warning logged."""
    # Write state with invalid timestamp
    state = {"regular_last_run": "not-a-date"}
    state_file.write_text(json.dumps(state))

    # Create StateManager
    sm = StateManager(state_file=state_file)

    # Should return None for corrupted timestamp
    result = sm.get_last_run("regular")
    assert result is None


def test_clear_specific_digest_type(state_manager):
    """clear(digest_type='major') removes major_last_run but preserves regular_last_run."""
    regular_timestamp = datetime(2026, 2, 24, 10, 0, 0, tzinfo=timezone.utc)
    major_timestamp = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)

    state_manager.set_last_run(regular_timestamp, digest_type="regular")
    state_manager.set_last_run(major_timestamp, digest_type="major")

    # Clear only major digest
    state_manager.clear(digest_type="major")

    # Regular should still exist
    assert state_manager.get_last_run("regular") == regular_timestamp
    # Major should be cleared
    assert state_manager.get_last_run("major") is None


def test_clear_all_state(state_file):
    """clear() with no args removes all state (existing behavior preserved)."""
    regular_timestamp = datetime(2026, 2, 24, 10, 0, 0, tzinfo=timezone.utc)
    major_timestamp = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)

    sm = StateManager(state_file=state_file)
    sm.set_last_run(regular_timestamp, digest_type="regular")
    sm.set_last_run(major_timestamp, digest_type="major")

    # Clear all state
    sm.clear()

    # Both should be cleared
    assert sm.get_last_run("regular") is None
    assert sm.get_last_run("major") is None
    # State file should be deleted
    assert not state_file.exists()
