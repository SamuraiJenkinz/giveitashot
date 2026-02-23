# Testing Patterns

**Analysis Date:** 2026-02-23

## Test Framework

**Status:** No test infrastructure detected

**Current State:**
- No test files found in codebase (no `*test*.py` or `*spec*.py` files)
- No pytest, unittest, or other test framework configuration
- No `pytest.ini`, `setup.cfg`, `tox.ini`, or test-related pyproject.toml entries
- No dedicated `tests/` directory

**Implication:** Application is currently untested. Any new testing should follow Python standard practices with clear patterns established first.

## Recommended Testing Approach

Given the nature of this application (email processing with external API dependencies), the following testing strategy is recommended:

### Unit Test Organization

**Test file location:** `tests/` directory parallel to `src/`
```
giveitashot/
├── src/
│   ├── __init__.py
│   ├── auth.py
│   ├── config.py
│   ├── ews_client.py
│   ├── llm_summarizer.py
│   ├── main.py
│   ├── state.py
│   └── summarizer.py
├── tests/
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_config.py
│   ├── test_ews_client.py
│   ├── test_llm_summarizer.py
│   ├── test_state.py
│   ├── test_summarizer.py
│   └── conftest.py
```

**Test naming convention:** `test_*.py` for test modules (standard pytest convention)

### Recommended Framework

**Primary:** pytest - Recommended for this Python project
- Modern assertion syntax
- Excellent fixture support (needed for mocking external APIs)
- Clear output and debugging
- Works well with dependency injection

**Configuration:**
```ini
# pytest.ini or pyproject.toml [tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

## Test File Organization

**Pattern:** Co-located mirrors of source modules

**Structure example for `src/auth.py` → `tests/test_auth.py`:**
```python
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.auth import EWSAuthenticator, AuthenticationError
from src.config import Config


class TestEWSAuthenticator:
    """Test suite for EWSAuthenticator."""

    @pytest.fixture
    def authenticator(self):
        """Provide an authenticator instance."""
        return EWSAuthenticator()

    def test_initialization(self, authenticator):
        """Test authenticator initializes without error."""
        assert authenticator is not None

    @patch('src.auth.msal.ConfidentialClientApplication')
    def test_get_access_token_success(self, mock_msal, authenticator):
        """Test successful token acquisition."""
        # Setup
        mock_app = MagicMock()
        mock_app.acquire_token_silent.return_value = None
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "test_token_12345"
        }
        mock_msal.return_value = mock_app

        # Execute
        token = authenticator.get_access_token()

        # Assert
        assert token == "test_token_12345"

    def test_get_access_token_failure(self, authenticator):
        """Test token acquisition failure handling."""
        with patch('src.auth.msal.ConfidentialClientApplication') as mock_msal:
            mock_app = MagicMock()
            mock_app.acquire_token_silent.return_value = {
                "error": "invalid_client",
                "error_description": "The client is invalid"
            }
            mock_msal.return_value = mock_app

            with pytest.raises(AuthenticationError) as exc_info:
                authenticator.get_access_token()

            assert "invalid_client" in str(exc_info.value)
```

## Mocking

**Framework:** `unittest.mock` (Python standard library)

**Patterns:**

### External API Mocking
```python
# Mock Exchange Web Services
@patch('src.ews_client.Account')
def test_get_shared_mailbox_emails(self, mock_account_class):
    """Test email retrieval from shared mailbox."""
    # Setup mock account
    mock_account = MagicMock()
    mock_account.inbox.filter().order_by.return_value = [
        MagicMock(
            id="msg-001",
            subject="Test Email",
            sender=MagicMock(name="John Doe", email_address="john@example.com"),
            body="Test content",
            datetime_received=datetime.now(timezone.utc),
            has_attachments=False
        )
    ]
    mock_account_class.return_value = mock_account

    # Execute & Assert
```

### LLM API Mocking
```python
@patch('src.llm_summarizer.httpx.Client')
def test_summarize_email_with_llm(self, mock_http_client):
    """Test LLM-powered email summarization."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": "Email is about quarterly reviews scheduled for next month."
            }
        }]
    }
    mock_response.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_http_client.return_value.__enter__.return_value = mock_client

    # Execute & Assert
```

### Configuration Mocking
```python
@patch.dict('os.environ', {
    'AZURE_TENANT_ID': 'test-tenant',
    'AZURE_CLIENT_ID': 'test-client',
    'AZURE_CLIENT_SECRET': 'test-secret',
    'USER_EMAIL': 'test@example.com',
    'SHARED_MAILBOX': 'shared@example.com',
    'SUMMARY_RECIPIENT': 'recipient@example.com'
})
def test_config_validation_success():
    """Test configuration validates with all required vars."""
    Config.validate()  # Should not raise
```

**What to Mock:**
- External API calls (Exchange, OpenAI, Azure AD)
- File I/O operations for state management
- HTTP requests via httpx
- MSAL authentication flows
- System time for date-dependent logic

**What NOT to Mock:**
- Config reading from environment variables (test with actual env vars when possible)
- Data model creation (Email, EmailSummary, DailySummary)
- Pure business logic (summarization algorithms without API calls)
- Error handling and exception raising logic

## Fixtures and Factories

**Fixture Location:** `tests/conftest.py` (pytest auto-loads)

**Test Data Patterns:**
```python
# conftest.py
import pytest
from datetime import datetime, timezone
from src.ews_client import Email
from src.summarizer import EmailSummary, DailySummary


@pytest.fixture
def sample_email():
    """Factory for test email."""
    return Email(
        id="msg-001",
        subject="Test Email",
        sender_name="John Doe",
        sender_email="john@example.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="This is a test email preview.",
        body_content="This is a test email with more content. Contains important information.",
        has_attachments=False
    )


@pytest.fixture
def sample_emails(sample_email):
    """Factory for multiple test emails."""
    return [
        sample_email,
        Email(
            id="msg-002",
            subject="Second Email",
            sender_name="Jane Smith",
            sender_email="jane@example.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="Action required: review document.",
            body_content="Action required: review document by end of week.",
            has_attachments=True
        ),
        Email(
            id="msg-003",
            subject="FYI: Update",
            sender_name="System",
            sender_email="system@example.com",
            received_datetime=datetime.now(timezone.utc),
            body_preview="System maintenance scheduled.",
            body_content="System maintenance scheduled for Friday night.",
            has_attachments=False
        )
    ]


@pytest.fixture
def sample_daily_summary(sample_emails):
    """Factory for daily summary."""
    return DailySummary(
        date="Monday, February 23, 2026",
        total_count=len(sample_emails),
        email_summaries=[
            EmailSummary(
                subject=email.subject,
                sender=email.sender_name,
                sender_email=email.sender_email,
                time=email.received_time_local,
                key_points="Test summary",
                has_attachments=email.has_attachments,
                category="test"
            )
            for email in sample_emails
        ],
        categories={"test": []},
        executive_digest={"summary": "Test digest"}
    )


@pytest.fixture
def mock_config(monkeypatch):
    """Mock configuration for testing."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("USER_EMAIL", "test@example.com")
    monkeypatch.setenv("SHARED_MAILBOX", "shared@example.com")
    monkeypatch.setenv("SUMMARY_RECIPIENT", "recipient@example.com")
```

**Location:** `tests/conftest.py` for shared fixtures used across tests

## Coverage

**Current Status:** No coverage tracking in place

**Recommended Requirements:**
- Minimum 70% line coverage for business logic modules
- 100% coverage for error handling paths
- Focus on critical paths first:
  - Config validation
  - State persistence
  - Email summarization logic
  - Error handling across all modules

**View Coverage Command:**
```bash
# Install coverage
pip install pytest-cov

# Run tests with coverage
pytest --cov=src --cov-report=html tests/

# Generate and view HTML report
# Coverage report available in htmlcov/index.html
```

**Pytest configuration for coverage:**
```ini
# pytest.ini
[tool.pytest.ini_options]
addopts = --cov=src --cov-report=term-missing --cov-report=html
```

## Test Types

**Unit Tests:**
- **Scope:** Individual functions and methods
- **Approach:** Fast execution, comprehensive mocking of external dependencies
- **Examples:**
  - Config parsing and validation
  - State file load/save
  - Email summarization (without LLM)
  - HTML formatting
  - Error handling
- **Location:** `tests/test_*.py` files
- **Expected:** 60+ unit tests (one per function + edge cases)

**Integration Tests:**
- **Scope:** Multiple modules working together
- **Approach:** Use real config, mocked external APIs
- **Examples:**
  - Config validation + state initialization
  - Email fetch + summarization pipeline
  - Summary generation with mock emails
- **Location:** `tests/integration/` subdirectory or `test_*_integration.py`
- **Expected:** 10-15 integration tests covering major workflows

**End-to-End Tests (Optional):**
- **Scope:** Full application flow with real credentials
- **Approach:** Requires actual Azure AD setup, real mailbox access
- **Note:** Use only in staging environment with test accounts
- **Examples:** Full email fetch → summarize → send cycle
- **Location:** `tests/e2e/` or separate test suite
- **Execution:** Manual or dedicated staging pipeline

## Common Patterns

**Async Testing:** Not applicable - application is synchronous

**Error Testing Pattern:**
```python
def test_summarize_email_handles_missing_body():
    """Test email summarization with missing body content."""
    email = Email(
        id="msg-001",
        subject="No Body Email",
        sender_name="Test",
        sender_email="test@example.com",
        received_datetime=datetime.now(timezone.utc),
        body_preview="",
        body_content="",
        has_attachments=False
    )

    summarizer = EmailSummarizer(use_llm=False)
    summary = summarizer._summarize_email(email)

    assert summary.key_points == "(No content)"


def test_ews_client_handles_connection_error():
    """Test EWS client handles connection failures."""
    with patch('src.ews_client.Account') as mock_account:
        mock_account.side_effect = Exception("Connection refused")

        client = EWSClient(Mock())

        with pytest.raises(EWSClientError) as exc_info:
            client.get_shared_mailbox_emails("shared@example.com")

        assert "Connection refused" in str(exc_info.value)
```

**State Testing Pattern:**
```python
def test_state_manager_persists_timestamp(tmp_path):
    """Test state manager correctly persists timestamps."""
    state_file = tmp_path / ".state.json"
    manager = StateManager(state_file=state_file)

    # Set timestamp
    now = datetime.now(timezone.utc)
    manager.set_last_run(now)

    # Create new manager with same file
    manager2 = StateManager(state_file=state_file)
    loaded_timestamp = manager2.get_last_run()

    assert loaded_timestamp.isoformat() == now.isoformat()


def test_state_manager_handles_corrupt_file(tmp_path):
    """Test state manager recovers from corrupt JSON."""
    state_file = tmp_path / ".state.json"
    state_file.write_text("{invalid json")

    manager = StateManager(state_file=state_file)
    assert manager.get_last_run() is None
```

## Testing Best Practices for This Codebase

1. **Mock all external APIs** - Azure AD, Exchange Online, OpenAI
2. **Test error paths explicitly** - Each try-except block should have corresponding test
3. **Use parametrization for variants** - Test multiple email types, categories, etc.
4. **Test configuration edge cases** - Missing vars, empty strings, malformed env vars
5. **Test state persistence** - File I/O with real temp files via pytest tmp_path
6. **Mock LLM responses** - Test JSON parsing, error handling, fallback behavior
7. **Test email data model edge cases** - No sender, no body, special characters
8. **Keep tests isolated** - Each test independent, no shared state between tests
9. **Use fixtures for common setup** - Reduce duplication with conftest.py
10. **Document complex test setups** - Clear comments on mock behavior

---

*Testing analysis: 2026-02-23*
