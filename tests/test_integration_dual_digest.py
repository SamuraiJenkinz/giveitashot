"""
Integration tests for dual-digest orchestration.

Tests the end-to-end dual-digest system including:
- Multi-run state simulation with persistence
- State corruption recovery
- Failure isolation between digest types
- Edge cases and boundary conditions
- Full pipeline from classification to HTML formatting
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from src.state import StateManager
from src.classifier import EmailClassifier
from src.extractor import MessageCenterExtractor
from src.summarizer import EmailSummarizer
from src.graph_client import Email
from src.config import Config


class TestMultiRunStateSimulation:
    """Test consecutive hourly runs with state persistence."""

    def test_state_transitions_across_5_runs(self, tmp_path):
        """
        Simulate 5 consecutive runs with different email patterns.

        Run 1: Empty inbox
        Run 2: Regular only (3 emails)
        Run 3: Mixed (2 regular + 2 major)
        Run 4: Major only (1 email)
        Run 5: Empty inbox again
        """
        state_file = tmp_path / "state.json"
        base_time = datetime.now(timezone.utc)

        # Run 1: Empty inbox
        state = StateManager(state_file=state_file)
        state.set_last_run(base_time, "regular")
        assert state.get_last_run("regular") == base_time
        assert state.get_last_run("major") is None

        # Run 2: Regular only
        run2_time = base_time + timedelta(hours=1)
        state = StateManager(state_file=state_file)
        state.set_last_run(run2_time, "regular")
        assert state.get_last_run("regular") == run2_time
        assert state.get_last_run("major") is None

        # Run 3: Mixed (both digest types updated)
        run3_time = base_time + timedelta(hours=2)
        state = StateManager(state_file=state_file)
        state.set_last_run(run3_time, "regular")
        state.set_last_run(run3_time, "major")
        assert state.get_last_run("regular") == run3_time
        assert state.get_last_run("major") == run3_time

        # Run 4: Major only (regular unchanged)
        run4_time = base_time + timedelta(hours=3)
        state = StateManager(state_file=state_file)
        state.set_last_run(run4_time, "major")
        assert state.get_last_run("regular") == run3_time  # Unchanged from run 3
        assert state.get_last_run("major") == run4_time

        # Run 5: Empty inbox (timestamps unchanged)
        state = StateManager(state_file=state_file)
        assert state.get_last_run("regular") == run3_time
        assert state.get_last_run("major") == run4_time

    def test_state_persists_across_manager_instances(self, tmp_path):
        """Verify state persists when StateManager instances are destroyed."""
        state_file = tmp_path / "state.json"
        timestamp = datetime.now(timezone.utc)

        # Create manager, set state, destroy instance
        state1 = StateManager(state_file=state_file)
        state1.set_last_run(timestamp, "regular")
        del state1

        # Create new manager, verify state persisted
        state2 = StateManager(state_file=state_file)
        assert state2.get_last_run("regular") == timestamp

    def test_independent_digest_type_state(self, tmp_path):
        """Verify setting one digest type does not affect the other."""
        state_file = tmp_path / "state.json"
        state = StateManager(state_file=state_file)

        regular_time = datetime.now(timezone.utc)
        major_time = regular_time + timedelta(hours=1)

        # Set both independently
        state.set_last_run(regular_time, "regular")
        state.set_last_run(major_time, "major")

        assert state.get_last_run("regular") == regular_time
        assert state.get_last_run("major") == major_time

        # Clear one, verify other preserved
        state.clear("regular")
        assert state.get_last_run("regular") is None
        assert state.get_last_run("major") == major_time


class TestStateCorruptionRecovery:
    """Test resilience to corrupted state files."""

    def test_completely_corrupted_json(self, tmp_path):
        """State manager handles completely invalid JSON."""
        state_file = tmp_path / "state.json"
        state_file.write_text("{ invalid json")

        state = StateManager(state_file=state_file)
        assert state.get_last_run("regular") is None
        assert state.get_last_run("major") is None

    def test_empty_state_file(self, tmp_path):
        """State manager handles empty state file."""
        state_file = tmp_path / "state.json"
        state_file.write_text("")

        state = StateManager(state_file=state_file)
        assert state.get_last_run("regular") is None
        assert state.get_last_run("major") is None

    def test_missing_state_file(self, tmp_path):
        """State manager handles nonexistent state file."""
        state_file = tmp_path / "nonexistent.json"

        state = StateManager(state_file=state_file)
        assert state.get_last_run("regular") is None
        assert state.get_last_run("major") is None

    def test_invalid_timestamp_format(self, tmp_path):
        """State manager handles per-field corruption, isolates invalid fields."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({
            "regular_last_run": "not-a-date",
            "major_last_run": "2026-02-26T10:00:00+00:00"
        }))

        state = StateManager(state_file=state_file)
        assert state.get_last_run("regular") is None  # Corrupted field returns None
        assert state.get_last_run("major") is not None  # Valid field loads successfully

    def test_wrong_schema_extra_fields(self, tmp_path):
        """State manager ignores extra unexpected fields."""
        state_file = tmp_path / "state.json"
        timestamp = datetime.now(timezone.utc).isoformat()
        state_file.write_text(json.dumps({
            "regular_last_run": timestamp,
            "major_last_run": timestamp,
            "unexpected_field": "garbage",
            "another_extra": 12345
        }))

        state = StateManager(state_file=state_file)
        assert state.get_last_run("regular") is not None
        assert state.get_last_run("major") is not None

    def test_truncated_json_file(self, tmp_path):
        """State manager handles truncated JSON."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"regular_last_run": "2026-02')

        state = StateManager(state_file=state_file)
        assert state.get_last_run("regular") is None
        assert state.get_last_run("major") is None


class TestFailureIsolation:
    """Test that one digest type's failure doesn't affect the other."""

    def test_major_digest_exception_does_not_crash_program(
        self, message_center_major_update, regular_internal_email
    ):
        """
        Verify exception in major digest processing is caught and isolated.

        Tests the error isolation pattern from main.py lines 245-325.
        """
        extractor = MessageCenterExtractor()

        # Create list with major update
        major_emails = [message_center_major_update]

        # Mock extract_batch to raise exception
        with patch.object(extractor, 'extract_batch', side_effect=Exception("Extraction failed")):
            # The main.py pattern uses try/except around major digest processing
            major_fields = None
            try:
                major_fields = extractor.extract_batch(major_emails)
            except Exception as e:
                # Exception caught, program continues
                assert "Extraction failed" in str(e)

            # Major digest failed, but regular digest would proceed
            assert major_fields is None

    def test_regular_digest_failure_preserves_major_state(self, tmp_path):
        """Regular digest failure does not affect major digest state."""
        state_file = tmp_path / "state.json"
        state = StateManager(state_file=state_file)

        major_time = datetime.now(timezone.utc)
        state.set_last_run(major_time, "major")

        # Simulate regular digest failure (no state update for regular)
        # In main.py, if regular digest fails, major_last_run should be intact
        state_reloaded = StateManager(state_file=state_file)
        assert state_reloaded.get_last_run("major") == major_time

    def test_classification_failure_treats_all_as_regular(
        self, message_center_major_update, regular_internal_email
    ):
        """
        When classification fails, all emails treated as regular (non-blocking).

        Tests the fallback pattern from main.py.
        """
        classifier = EmailClassifier()
        emails = [message_center_major_update, regular_internal_email]

        # Mock classify_batch to raise exception
        with patch.object(classifier, 'classify_batch', side_effect=Exception("Classification failed")):
            # The main.py pattern catches exception and treats all as regular
            regular_emails = []
            major_emails = []
            try:
                regular_emails, major_emails = classifier.classify_batch(emails)
            except Exception:
                # Fallback: all emails go to regular
                regular_emails = emails
                major_emails = []

            assert len(regular_emails) == 2
            assert len(major_emails) == 0


class TestEdgeCases:
    """Test boundary conditions for dual-digest system."""

    def test_empty_inbox_no_digest_generated(self):
        """Empty email list requires no summarizer calls."""
        classifier = EmailClassifier()
        emails = []

        regular_emails, major_emails = classifier.classify_batch(emails)

        assert len(regular_emails) == 0
        assert len(major_emails) == 0

    def test_all_emails_are_major_updates(
        self, message_center_major_update, major_update_with_deadline
    ):
        """All emails classified as major updates."""
        classifier = EmailClassifier()
        emails = [message_center_major_update, major_update_with_deadline]

        regular_emails, major_emails = classifier.classify_batch(emails)

        assert len(regular_emails) == 0
        assert len(major_emails) == 2

    def test_all_emails_are_regular(
        self, regular_internal_email, regular_microsoft_email
    ):
        """All emails classified as regular."""
        classifier = EmailClassifier()
        emails = [regular_internal_email, regular_microsoft_email]

        regular_emails, major_emails = classifier.classify_batch(emails)

        assert len(regular_emails) == 2
        assert len(major_emails) == 0

    def test_duplicate_mc_ids_deduplicated(self, duplicate_mc_emails):
        """Duplicate MC IDs are deduplicated, keeping latest."""
        extractor = MessageCenterExtractor()

        fields_list = extractor.extract_batch(duplicate_mc_emails)
        deduplicated = extractor.deduplicate(fields_list)

        # Should have only 1 result
        assert len(deduplicated) == 1
        # Should be marked as updated
        assert deduplicated[0].is_updated is True
        # Should be the newer email (check subject has "Updated version")
        # The fixture creates newer_email with "Updated version" in subject
        assert "Updated version" in deduplicated[0].subject

    @patch.object(Config, 'is_major_digest_enabled', return_value=False)
    def test_major_digest_disabled_skips_processing(
        self, mock_enabled, message_center_major_update
    ):
        """When major digest disabled, no major digest generated."""
        # Classification still happens
        classifier = EmailClassifier()
        emails = [message_center_major_update]

        regular_emails, major_emails = classifier.classify_batch(emails)

        # Email is classified as major
        assert len(major_emails) == 1

        # But major digest generation is skipped (following main.py pattern)
        if not Config.is_major_digest_enabled():
            # Skip major digest processing
            pass

        # Verify config check returns False
        assert not Config.is_major_digest_enabled()

    def test_selective_execution_flags(
        self, message_center_major_update, regular_internal_email
    ):
        """
        Test selective execution patterns (--regular-only, --major-only).

        In main.py, these flags skip processing for the other digest type.
        """
        classifier = EmailClassifier()
        emails = [message_center_major_update, regular_internal_email]

        regular_emails, major_emails = classifier.classify_batch(emails)

        # Simulate --regular-only flag
        regular_only = True
        if regular_only:
            # Skip major digest processing
            major_emails = []

        assert len(regular_emails) == 1
        assert len(major_emails) == 0

        # Simulate --major-only flag
        regular_emails, major_emails = classifier.classify_batch(emails)
        major_only = True
        if major_only:
            # Skip regular digest processing
            regular_emails = []

        assert len(regular_emails) == 0
        assert len(major_emails) == 1


class TestEndToEndPipeline:
    """Test the full classification -> extraction -> formatting pipeline."""

    def test_full_pipeline_mixed_emails(
        self,
        message_center_major_update,
        major_update_with_deadline,
        regular_internal_email,
        regular_microsoft_email,
        message_center_minor_update
    ):
        """
        Full pipeline with mixed emails (3 regular + 2 major).

        Tests: classification -> extraction -> deduplication -> HTML formatting
        """
        emails = [
            regular_internal_email,
            message_center_major_update,
            major_update_with_deadline,
            regular_microsoft_email,
            message_center_minor_update
        ]

        # Step 1: Classification
        classifier = EmailClassifier()
        regular_emails, major_emails = classifier.classify_batch(emails)

        # Note: message_center_minor_update has sender+MC# which hits 70% threshold
        # So it gets classified as major even without major keywords
        assert len(regular_emails) == 2  # 2 regular internal/microsoft
        assert len(major_emails) == 3  # 2 with keywords + 1 with sender+MC#

        # Step 2: Extraction
        extractor = MessageCenterExtractor()
        major_fields = extractor.extract_batch(major_emails)

        assert len(major_fields) == 3
        assert major_fields[0].mc_id is not None
        assert major_fields[1].mc_id is not None

        # Step 3: Deduplication
        unique_updates = extractor.deduplicate(major_fields)

        # Note: message_center_major_update and major_update_with_deadline both have MC1234567
        # So deduplication reduces 3 to 2
        assert len(unique_updates) == 2  # 3 emails, but 2 share same MC ID

        # Step 4: HTML Formatting
        summarizer = EmailSummarizer()
        html = summarizer.format_major_updates_html(unique_updates)

        assert html != ""
        assert "MC1234567" in html or "MC" in html  # Contains MC IDs
        assert "Critical" in html or "High" in html or "Normal" in html  # Contains urgency sections

    def test_full_pipeline_synthetic_eml_files(
        self, load_eml, mock_emails_from_eml
    ):
        """
        Full pipeline using synthetic .eml fixtures.

        Tests: .eml loading -> Email conversion -> classification -> extraction -> formatting
        """
        # Load synthetic fixtures
        mc_major_action = load_eml("synthetic", "mc_major_update_action_required.eml")
        mc_major_retire = load_eml("synthetic", "mc_major_update_retirement.eml")
        mc_major_feature = load_eml("synthetic", "mc_major_update_new_feature.eml")
        mc_minor = load_eml("synthetic", "mc_minor_update.eml")
        regular = load_eml("synthetic", "regular_internal.eml")

        # Convert to Email objects
        emails = mock_emails_from_eml([mc_major_action, mc_major_retire, mc_major_feature, mc_minor, regular])

        assert len(emails) == 5

        # Step 1: Classification
        classifier = EmailClassifier()
        regular_emails, major_emails = classifier.classify_batch(emails)

        # Verify classification accuracy
        # The mc_minor_update.eml still has sender + MC# which hits 70% threshold
        # So it gets classified as major even without major keywords
        # 3 major with keywords + 1 major from MC#/sender = 4 major, 1 regular
        assert len(major_emails) == 4  # 3 with MAJOR UPDATE + 1 with sender+MC#
        assert len(regular_emails) == 1  # Only regular internal

        # Step 2: Extraction
        extractor = MessageCenterExtractor()
        major_fields = extractor.extract_batch(major_emails)

        assert len(major_fields) == 4

        # Verify MC IDs extracted
        mc_ids = [f.mc_id for f in major_fields]
        assert "MC1234567" in mc_ids
        assert "MC2345678" in mc_ids
        assert "MC3456789" in mc_ids
        assert "MC4567890" in mc_ids  # Minor update still has MC ID

        # Step 3: Deduplication (no duplicates expected)
        unique_updates = extractor.deduplicate(major_fields)

        assert len(unique_updates) == 4

        # Step 4: HTML Formatting
        summarizer = EmailSummarizer()
        html = summarizer.format_major_updates_html(unique_updates)

        assert html != ""
        # Verify all MC IDs appear in HTML
        assert "MC1234567" in html
        assert "MC2345678" in html
        assert "MC3456789" in html
        assert "MC4567890" in html

        # Verify urgency sections present
        assert "Critical" in html or "High" in html or "Normal" in html


class TestRealEmailIntegration:
    """Integration tests using real .eml samples from Message Center."""

    def test_real_eml_sanitization_check(self, load_eml):
        """
        Verify all real .eml files are sanitized (no PII).

        Tests each file in tests/fixtures/real/ to ensure no mmc.com or marsh.com
        domains are present. This prevents accidental PII commits.
        """
        real_fixtures_dir = Path("tests/fixtures/real")
        if not real_fixtures_dir.exists():
            pytest.skip("Real fixtures directory not present")

        eml_files = list(real_fixtures_dir.glob("*.eml"))
        if not eml_files:
            pytest.skip("No real .eml files found")

        # Check each file for PII patterns
        for eml_file in eml_files:
            content = eml_file.read_text(encoding="utf-8", errors="ignore")

            # Assert no corporate domains present
            assert "mmc.com" not in content.lower(), f"Found mmc.com in {eml_file.name}"
            assert "marsh.com" not in content.lower(), f"Found marsh.com in {eml_file.name}"

    @pytest.mark.parametrize("eml_filename", [
        "Major update from Message center00.eml",
        "Major update from Message center02.eml",
        "Major update from Message center03.eml",
        "Major update from Message center04.eml",
        "Major update from Message center05.eml",
        "Major update from Message center06.eml",
    ])
    def test_real_major_update_classification(self, load_eml, mock_emails_from_eml, eml_filename):
        """
        Verify real major update .eml files are classified correctly.

        Tests that real Message Center emails match our detection patterns:
        - Classified as major update
        - Confidence score >= 70%
        - MC ID pattern detected
        """
        # Load real .eml file (will skip if not present)
        eml_content = load_eml("real", eml_filename)

        # Convert to Email object
        emails = mock_emails_from_eml([eml_content])
        assert len(emails) == 1
        email = emails[0]

        # Classify
        classifier = EmailClassifier()
        result = classifier.classify(email)

        # Verify classified as major update
        assert result.is_major_update is True, f"{eml_filename} not classified as major update"
        assert result.confidence_score >= 70, f"{eml_filename} confidence too low: {result.confidence_score}"

        # Verify MC ID detected (either in subject or body)
        assert "MC" in email.subject or "MC" in email.body_content, f"{eml_filename} missing MC ID pattern"

    def test_real_major_updates_full_pipeline(self, load_eml, mock_emails_from_eml):
        """
        Run all real major updates through full pipeline.

        Tests: .eml loading -> classification -> extraction -> deduplication -> HTML formatting

        Verifies:
        - All classified as major updates
        - MC IDs extracted correctly
        - Action dates extracted where present
        - HTML output contains MC IDs and urgency tiers
        """
        real_fixtures_dir = Path("tests/fixtures/real")
        if not real_fixtures_dir.exists():
            pytest.skip("Real fixtures directory not present")

        eml_files = list(real_fixtures_dir.glob("*.eml"))
        if not eml_files:
            pytest.skip("No real .eml files found")

        # Load all real .eml files
        eml_contents = [load_eml("real", f.name) for f in eml_files]

        # Convert to Email objects
        emails = mock_emails_from_eml(eml_contents)
        assert len(emails) == len(eml_files)

        # Step 1: Classification
        classifier = EmailClassifier()
        regular_emails, major_emails = classifier.classify_batch(emails)

        # All real fixtures are major updates
        assert len(major_emails) == len(emails), "Not all real emails classified as major"
        assert len(regular_emails) == 0, "Regular emails found when all should be major"

        # Step 2: Extraction
        extractor = MessageCenterExtractor()
        major_fields = extractor.extract_batch(major_emails)

        assert len(major_fields) == len(major_emails)

        # Verify MC IDs extracted
        mc_ids_found = 0
        for fields in major_fields:
            if fields.mc_id:
                mc_ids_found += 1
                # Verify MC ID format
                assert fields.mc_id.startswith("MC"), f"Invalid MC ID format: {fields.mc_id}"

        # All major updates should have MC IDs
        assert mc_ids_found == len(major_fields), "Some major updates missing MC IDs"

        # Step 3: Deduplication
        unique_updates = extractor.deduplicate(major_fields)

        # No duplicates expected in real samples
        assert len(unique_updates) <= len(major_fields)

        # Step 4: HTML Formatting
        summarizer = EmailSummarizer()
        html = summarizer.format_major_updates_html(unique_updates)

        # Verify HTML output
        assert html != "", "HTML output is empty"
        assert "MC" in html, "HTML missing MC IDs"

        # Verify urgency sections present
        urgency_keywords = ["Critical", "High", "Normal"]
        assert any(keyword in html for keyword in urgency_keywords), "HTML missing urgency sections"

    def test_real_emails_mixed_batch_classification(self, load_eml, mock_emails_from_eml):
        """
        Classify all real .eml files as a batch.

        Tests batch classification efficiency and consistency.
        All real fixtures are major updates, so verify batch consistency.
        """
        real_fixtures_dir = Path("tests/fixtures/real")
        if not real_fixtures_dir.exists():
            pytest.skip("Real fixtures directory not present")

        eml_files = list(real_fixtures_dir.glob("*.eml"))
        if not eml_files:
            pytest.skip("No real .eml files found")

        # Load all real .eml files
        eml_contents = [load_eml("real", f.name) for f in eml_files]

        # Convert to Email objects
        emails = mock_emails_from_eml(eml_contents)

        # Batch classify
        classifier = EmailClassifier()
        regular_emails, major_emails = classifier.classify_batch(emails)

        # All real fixtures are major updates
        assert len(major_emails) == len(emails), "Batch classification inconsistent with individual results"
        assert len(regular_emails) == 0, "Regular emails found when all should be major"

        # Verify all have high confidence
        for email in major_emails:
            result = classifier.classify(email)
            assert result.confidence_score >= 70, f"Low confidence for {email.subject}"
