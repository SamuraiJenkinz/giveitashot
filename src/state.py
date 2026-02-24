"""
State management for tracking last run time.
Enables incremental email fetching (only new emails since last run).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Default state file location (in project root)
DEFAULT_STATE_FILE = Path(__file__).parent.parent / ".state.json"


class StateManager:
    """Manages persistent state between runs."""

    def __init__(self, state_file: Path | None = None):
        """
        Initialize state manager.

        Args:
            state_file: Path to state file. Defaults to .state.json in project root.
        """
        self._state_file = state_file or DEFAULT_STATE_FILE
        self._state: dict = {}
        self._load()

    def _load(self) -> None:
        """Load state from file."""
        if self._state_file.exists():
            try:
                with open(self._state_file, "r") as f:
                    self._state = json.load(f)
                logger.debug(f"Loaded state from {self._state_file}")

                # Backwards-compatible migration: last_run -> regular_last_run
                if "last_run" in self._state and "regular_last_run" not in self._state:
                    self._state["regular_last_run"] = self._state["last_run"]
                    logger.info("Migrated state: last_run -> regular_last_run")
                    self._save()  # Persist migration

            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load state file: {e}")
                self._state = {}
        else:
            self._state = {}

    def _save(self) -> None:
        """Save state to file."""
        try:
            with open(self._state_file, "w") as f:
                json.dump(self._state, f, indent=2)
            logger.debug(f"Saved state to {self._state_file}")
        except IOError as e:
            logger.error(f"Failed to save state file: {e}")

    def get_last_run(self, digest_type: str = "regular") -> datetime | None:
        """
        Get the timestamp of the last successful run for a specific digest type.

        Args:
            digest_type: Type of digest ("regular" or "major"). Defaults to "regular".

        Returns:
            datetime in UTC if available, None if no previous run.
        """
        key = f"{digest_type}_last_run"
        timestamp = self._state.get(key)
        if timestamp:
            try:
                return datetime.fromisoformat(timestamp)
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse {key} timestamp: {e}")
                return None
        return None

    def set_last_run(self, timestamp: datetime | None = None, digest_type: str = "regular") -> None:
        """
        Set the last run timestamp for a specific digest type.

        Args:
            timestamp: The timestamp to save. Defaults to current UTC time.
            digest_type: Type of digest ("regular" or "major"). Defaults to "regular".
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Ensure timezone-aware and convert to ISO format
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        key = f"{digest_type}_last_run"
        self._state[key] = timestamp.isoformat()
        self._save()
        logger.info(f"Updated {digest_type} last run time: {timestamp.isoformat()}")

    def clear(self, digest_type: str | None = None) -> None:
        """
        Clear state.

        Args:
            digest_type: If specified, clear only that digest type's state.
                        If None (default), clear all state.
        """
        if digest_type is None:
            # Clear all state
            self._state = {}
            if self._state_file.exists():
                self._state_file.unlink()
                logger.info("State cleared")
        else:
            # Clear specific digest type
            key = f"{digest_type}_last_run"
            if key in self._state:
                del self._state[key]
                self._save()
                logger.info(f"Cleared {digest_type} state")
