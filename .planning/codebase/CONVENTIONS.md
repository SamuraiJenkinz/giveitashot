# Coding Conventions

**Analysis Date:** 2026-02-23

## Naming Patterns

**Files:**
- PascalCase for logical module names: `auth.py`, `config.py`, `ews_client.py`, `llm_summarizer.py`
- Dunder files for package init: `__init__.py`
- State/utility files are lowercase: `state.py`, `summarizer.py`, `main.py`

**Functions:**
- snake_case for all function and method names
- Private methods prefixed with single underscore: `_get_config()`, `_strip_html()`, `_load()`
- Property decorators used for simple getters: `@property` on `received_time_local`, `app`
- Descriptive action verbs: `get_`, `set_`, `clear_`, `summarize_`, `format_`

**Variables:**
- snake_case for local variables and parameters
- Instance variables prefixed with underscore: `self._app`, `self._credentials`, `self._state`
- Class variables in UPPER_SNAKE_CASE for constants: `DEFAULT_STATE_FILE`, `TOKEN_CACHE_FILE`
- Module-level constants: `DEFAULT_STATE_FILE = Path(...)`

**Types:**
- PascalCase for class names: `Config`, `Email`, `EmailSummary`, `DailySummary`, `EWSClient`
- Exception classes follow PascalCase + "Error": `AuthenticationError`, `EWSClientError`, `LLMSummarizerError`
- Type hints using modern syntax: `list[str]`, `dict[str, list[int]]`, `Optional[str]`, `datetime | None`

**Dataclasses:**
- Use `@dataclass` decorator for simple data models: `Email`, `EmailSummary`, `DailySummary`
- Include docstrings describing purpose and fields

## Code Style

**Formatting:**
- Python 3.10+ syntax with type hints throughout
- 4-space indentation (PEP 8 standard)
- Line length follows PEP 8 conventions (soft limit ~88 chars for readability)
- Blank lines: 2 between top-level definitions, 1 between methods

**Linting:**
- No explicit linter config found, follows PEP 8 conventions
- Style appears consistent with Black formatter defaults
- Import sorting: stdlib imports first, then third-party, then local imports

**String quotes:**
- Double quotes used throughout: `"string"` not `'string'`
- Triple double quotes for docstrings: `"""`

## Import Organization

**Order:**
1. Standard library imports: `logging`, `json`, `argparse`, `sys`, `os`, `pathlib`, `datetime`, `dataclasses`, `typing`, `collections`, `html`, `re`
2. Third-party imports: `dotenv`, `msal`, `exchangelib`, `httpx`
3. Local imports: `.auth`, `.config`, `.ews_client`, `.state`, `.summarizer`, `.llm_summarizer`

**Path Aliases:**
- Relative imports within package: `from .config import Config`
- Absolute imports for standard library: `import logging`, `from pathlib import Path`
- Consistent pattern: `from .module import Class` for local modules

**Typical pattern from codebase:**
```python
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from exchangelib import Account, Configuration

from .config import Config
from .ews_client import Email

logger = logging.getLogger(__name__)
```

## Error Handling

**Patterns:**
- Custom exception classes inherit from `Exception`: `class AuthenticationError(Exception): pass`
- Try-except blocks used for external API calls and I/O operations
- Specific exception types caught before generic `Exception`
- Graceful fallback when APIs unavailable (LLM failures fall back to basic text extraction)
- Logging of errors with context before raising: `logger.error(f"Message: {e}")` then `raise CustomError(f"...{e}")`

**Examples from codebase:**
```python
# auth.py: Specific error handling with context
except Exception as e:
    if isinstance(e, AuthenticationError):
        raise
    raise AuthenticationError(f"Authentication failed: {e}")

# llm_summarizer.py: Graceful fallback
except (json.JSONDecodeError, LLMSummarizerError) as e:
    logger.error(f"Failed to generate daily digest: {e}")
    return {
        "summary": "Unable to generate AI summary.",
        "urgent_items": [],
        "action_items": [],
        "themes": []
    }

# main.py: Multiple specific exception handlers
except AuthenticationError as e:
    logger.error(f"Authentication failed: {e}")
    return 1
except EWSClientError as e:
    logger.error(f"EWS error: {e}")
    return 1
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    return 1
```

## Logging

**Framework:** Python standard `logging` module

**Setup pattern:**
```python
def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if debug else logging.INFO
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
```

**Module-level logger:**
- Every module creates logger: `logger = logging.getLogger(__name__)`
- Used for consistent namespace in logs

**Patterns:**
- Log at start of major operations: `logger.info("Fetching emails...")`
- Log at end of operations: `logger.info(f"Total emails retrieved: {len(all_emails)}")`
- Log intermediate steps: `logger.debug("No cached token, acquiring new token...")`
- Log errors with full context: `logger.error(f"Failed to parse email: {e}")`
- Log warnings for recoverable issues: `logger.warning(f"LLM summary failed for email: {email.subject}, using preview")`
- Separator logs for clarity: `logger.info("=" * 60)` with context messages

**Log levels:**
- `INFO`: Normal flow, important milestones, configuration summary, email counts, status messages
- `DEBUG`: Detailed decisions, token acquisition, cache hits, intermediate state
- `WARNING`: Recoverable failures, fallback usage, non-blocking errors
- `ERROR`: Failures that impact functionality, API errors, exception details

## Comments

**When to Comment:**
- Complex logic or non-obvious algorithms
- Business logic that isn't self-documenting
- Workarounds or constraints explained
- Configuration defaults with rationale

**Minimal commenting observed:**
- Code is largely self-documenting through clear naming
- Comments are sparse and purposeful
- Avoid obvious comments like "increment counter"

**Example from ews_client.py:**
```python
# Remove HTML tags
text = re.sub(r'<[^>]+>', ' ', html_content)
# Decode HTML entities
text = unescape(text)
# Normalize whitespace
text = re.sub(r'\s+', ' ', text).strip()
```

**Example with reasoning:**
```python
# EWS scope for client credentials (app-only)
scopes = ["https://outlook.office365.com/.default"]
```

## JSDoc/TSDoc

**Not applicable** - Python codebase uses standard docstrings, not JSDoc

**Docstring Pattern:**
- Triple double quotes: `"""`
- One-line summary for simple functions
- Multi-line format for complex functions:

```python
def get_shared_mailbox_emails(
    self,
    shared_mailbox: str,
    since: datetime | None = None,
    max_emails: int = 100
) -> list[Email]:
    """
    Get emails from a shared mailbox since a specified time.

    Args:
        shared_mailbox: Email address of the shared mailbox.
        since: Fetch emails received after this datetime. If None, defaults to today at midnight.
        max_emails: Maximum number of emails to retrieve.

    Returns:
        list[Email]: List of emails received since the specified time.
    """
```

## Function Design

**Size:** Functions are focused and relatively small (10-40 lines typical)
- Large functions broken into private helper methods with clear names
- Example: `_strip_html()`, `_extract_key_points()`, `_get_sender_domain()`

**Parameters:**
- Type hints always included: `def send_email(self, to_recipients: list[str] | str, ...)`
- Optional parameters with defaults: `since: datetime | None = None`
- Named parameters documented in docstrings with descriptions
- Normalized in function body when needed: handles both string and list inputs for `to_recipients`

**Return Values:**
- Always type-hinted: `-> str`, `-> list[Email]`, `-> dict[str, list[int]]`
- Returns None for setter-style methods
- Multiple return types using union: `-> dict | None`
- Docstring documents return format and structure

**Function naming conventions:**
- Getters: `get_*()` - `get_access_token()`, `get_authority()`
- Boolean queries: `is_*()` - Not observed in codebase
- Setters: `set_*()` - `set_last_run()`
- Clear/reset: `clear_*()` - `clear_cache()`
- Format/transform: `format_*()` - `format_summary_html()`
- Summarize/extract: `summarize_*()` or `_extract_*()` - `summarize_emails()`, `_extract_key_points()`

## Module Design

**Exports:**
- Classes and exceptions exported implicitly (all top-level definitions)
- Private module functions prefixed with underscore not typically imported
- Example: `_parse_email_list()` in config.py is module-level helper

**Barrel Files:**
- `__init__.py` serves as package marker, minimal content
- Version defined: `__version__ = "1.0.0"`
- No re-exports of submodule contents

**Module purposes:**
- `auth.py`: OAuth credentials, custom exceptions
- `config.py`: Environment variables, validation, helper functions
- `ews_client.py`: Email data model, EWS operations, exceptions
- `summarizer.py`: Email summarization logic, data models for summaries
- `llm_summarizer.py`: LLM-powered summarization (separate concern)
- `state.py`: Persistent state management
- `main.py`: CLI entry point, orchestration

**Dependencies:**
- Minimal circular dependencies
- Config used by multiple modules (central dependency)
- summarizer.py uses ews_client.Email model (data dependency)
- llm_summarizer imports optional in summarizer.py (lazy loading)

---

*Convention analysis: 2026-02-23*
