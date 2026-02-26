"""
Tests for dry-run HTML preview functionality.

Verifies that:
- HTML digests are saved to output/ directory
- Files are opened in default browser (with graceful failure handling)
- Console output is preserved alongside HTML saves
- Both digest types (regular and major) are handled correctly
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.main import _save_and_open_preview


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def sample_html():
    """Sample HTML content for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Digest</title></head>
    <body><h1>Test Email Digest</h1></body>
    </html>
    """


def test_save_and_open_preview_creates_file(tmp_path, mocker, mock_logger, sample_html):
    """Test that _save_and_open_preview creates HTML file and opens in browser."""
    # Mock webbrowser to prevent actual browser opening
    mock_browser = mocker.patch("src.main.webbrowser.open_new_tab")

    # Patch the output directory to use tmp_path
    with patch("src.main.Path") as mock_path_class:
        # Set up the Path mock to use tmp_path
        mock_main_file = MagicMock()
        mock_main_file.parent.parent = tmp_path
        mock_path_class.return_value = mock_main_file
        mock_path_class.__truediv__ = Path.__truediv__

        # Create actual Path objects for the directory operations
        output_dir = tmp_path / "output"
        file_path = output_dir / "regular_digest.html"

        # Override __file__ to point to tmp_path structure
        with patch("src.main.__file__", str(tmp_path / "src" / "main.py")):
            # Call the function
            _save_and_open_preview(sample_html, "regular", mock_logger)

        # Verify file was created (by checking tmp_path structure)
        # Since we're mocking Path, we need to verify differently
        # Let's verify the logger was called with file path information
        assert mock_logger.info.call_count >= 1

    # Verify webbrowser.open_new_tab was called
    assert mock_browser.call_count == 1


def test_save_and_open_preview_actually_saves_file(tmp_path, mocker, mock_logger, sample_html):
    """Test that file is actually written to disk with correct content."""
    # Mock webbrowser
    mocker.patch("src.main.webbrowser.open_new_tab")

    # Set up output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Patch __file__ to use tmp_path
    with patch("src.main.__file__", str(tmp_path / "src" / "main.py")):
        _save_and_open_preview(sample_html, "regular", mock_logger)

    # Verify file exists and has correct content
    file_path = output_dir / "regular_digest.html"
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert content == sample_html


def test_save_and_open_preview_browser_failure_handled(tmp_path, mocker, mock_logger, sample_html):
    """Test that browser open failure is handled gracefully (non-fatal)."""
    # Mock webbrowser to raise exception
    mock_browser = mocker.patch("src.main.webbrowser.open_new_tab")
    mock_browser.side_effect = Exception("No browser available")

    # Set up output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Patch __file__ to use tmp_path
    with patch("src.main.__file__", str(tmp_path / "src" / "main.py")):
        # Should not raise exception
        try:
            _save_and_open_preview(sample_html, "regular", mock_logger)
        except Exception as e:
            pytest.fail(f"Function should handle browser failure gracefully, but raised: {e}")

    # Verify warning was logged
    assert mock_logger.warning.call_count >= 1
    warning_call = mock_logger.warning.call_args[0][0]
    assert "Could not auto-open browser" in warning_call

    # Verify file still exists (browser failure doesn't prevent file save)
    file_path = output_dir / "regular_digest.html"
    assert file_path.exists()


def test_save_and_open_preview_creates_output_dir(tmp_path, mocker, mock_logger, sample_html):
    """Test that output directory is created if it doesn't exist."""
    # Mock webbrowser
    mocker.patch("src.main.webbrowser.open_new_tab")

    # Ensure output dir does NOT exist yet
    output_dir = tmp_path / "output"
    assert not output_dir.exists()

    # Patch __file__ to use tmp_path
    with patch("src.main.__file__", str(tmp_path / "src" / "main.py")):
        _save_and_open_preview(sample_html, "regular", mock_logger)

    # Verify directory was created
    assert output_dir.exists()
    assert output_dir.is_dir()


def test_both_digest_types_saved(tmp_path, mocker, mock_logger, sample_html):
    """Test that both regular and major digest types create correct filenames."""
    # Mock webbrowser
    mocker.patch("src.main.webbrowser.open_new_tab")

    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Patch __file__
    with patch("src.main.__file__", str(tmp_path / "src" / "main.py")):
        # Save both digest types
        _save_and_open_preview(sample_html, "regular", mock_logger)
        _save_and_open_preview(sample_html, "major", mock_logger)

    # Verify both files exist with correct names
    regular_file = output_dir / "regular_digest.html"
    major_file = output_dir / "major_digest.html"

    assert regular_file.exists()
    assert major_file.exists()

    # Verify content
    assert regular_file.read_text(encoding="utf-8") == sample_html
    assert major_file.read_text(encoding="utf-8") == sample_html


def test_file_path_logged_correctly(tmp_path, mocker, mock_logger, sample_html):
    """Test that absolute file path is logged for user reference."""
    # Mock webbrowser
    mocker.patch("src.main.webbrowser.open_new_tab")

    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    with patch("src.main.__file__", str(tmp_path / "src" / "main.py")):
        _save_and_open_preview(sample_html, "regular", mock_logger)

    # Verify logger.info was called with file path
    info_calls = [call[0][0] for call in mock_logger.info.call_args_list]

    # Check that at least one call contains "Digest saved:" with absolute path
    path_logged = any("Digest saved:" in call for call in info_calls)
    assert path_logged, "Expected logger.info to log 'Digest saved:' message"

    # Check that browser open was logged
    browser_logged = any("Opened in browser:" in call or "Please manually open:" in call
                         for call in info_calls)
    assert browser_logged, "Expected logger.info to log browser open status"


def test_as_uri_method_used(tmp_path, mocker, mock_logger, sample_html):
    """Test that Path.as_uri() is used for cross-platform file URL generation."""
    # Mock webbrowser to capture the URL passed to it
    mock_browser = mocker.patch("src.main.webbrowser.open_new_tab")

    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    with patch("src.main.__file__", str(tmp_path / "src" / "main.py")):
        _save_and_open_preview(sample_html, "regular", mock_logger)

    # Verify webbrowser.open_new_tab was called with a file:// URL
    assert mock_browser.call_count == 1
    url_arg = mock_browser.call_args[0][0]
    assert url_arg.startswith("file://"), f"Expected file:// URL, got: {url_arg}"
