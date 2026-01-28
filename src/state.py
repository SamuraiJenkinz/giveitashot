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

    def get_last_run(self) -> datetime | None:
        """
        Get the timestamp of the last successful run.

        Returns:
            datetime in UTC if available, None if no previous run.
        """
        timestamp = self._state.get("last_run")
        if timestamp:
            return datetime.fromisoformat(timestamp)
        return None

    def set_last_run(self, timestamp: datetime | None = None) -> None:
        """
        Set the last run timestamp.

        Args:
            timestamp: The timestamp to save. Defaults to current UTC time.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Ensure timezone-aware and convert to ISO format
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        self._state["last_run"] = timestamp.isoformat()
        self._save()
        logger.info(f"Updated last run time: {timestamp.isoformat()}")

    def clear(self) -> None:
        """Clear all state (forces full fetch on next run)."""
        self._state = {}
        if self._state_file.exists():
            self._state_file.unlink()
            logger.info("State cleared")
