# Codebase Structure

**Analysis Date:** 2026-02-23

## Directory Layout

```
giveitashot/
├── src/                    # Main application code
│   ├── __init__.py        # Package initialization
│   ├── main.py            # Entry point and orchestration
│   ├── auth.py            # OAuth 2.0 authentication
│   ├── config.py          # Environment configuration
│   ├── ews_client.py      # Exchange Web Services client
│   ├── summarizer.py      # Email summarization logic
│   └── llm_summarizer.py  # Azure OpenAI integration (optional)
├── deploy/                # Deployment and scheduling scripts
├── prompts/               # Design documentation
├── .env                   # Runtime configuration (not committed)
├── .env.example           # Configuration template
├── .state.json            # State persistence (not committed)
├── .token_cache.json      # Auth token cache (not committed)
├── .gitignore             # Git exclusion rules
├── requirements.txt       # Python dependencies
└── README.md              # User and setup documentation
```

## Directory Purposes

**src/:**
- Purpose: All Python source code for the email summarizer agent
- Contains: Authentication, configuration, EWS integration, email summarization, LLM integration
- Key files: `main.py` (orchestration), `ews_client.py` (mailbox integration), `summarizer.py` (summary generation)

**deploy/:**
- Purpose: Windows scheduled task setup and management scripts
- Contains: PowerShell scripts for automated hourly execution setup
- Key files: `setup_scheduled_task.ps1`, `manage_service.ps1`

**prompts/:**
- Purpose: Design specifications and planning documentation
- Contains: Architecture specifications and workflow diagrams
- Key files: `001-exchange-mailbox-email-summarizer.md`

## Key File Locations

**Entry Points:**
- `src/main.py`: Main entry point for scheduled execution (line 46, main() function)

**Configuration:**
- `src/config.py`: Centralized configuration management, environment variable loading
- `.env`: Runtime secrets and settings (not committed, created from .env.example)
- `.env.example`: Configuration template with all required variables documented

**Core Logic:**
- `src/auth.py`: OAuth 2.0 authentication with MSAL client credentials flow
- `src/ews_client.py`: Exchange Web Services integration, mailbox access, email sending
- `src/summarizer.py`: Email summarization logic, HTML formatting, categorization
- `src/llm_summarizer.py`: Azure OpenAI integration for intelligent summarization (optional)

**State Management:**
- `src/state.py`: Persistent last-run tracking for incremental email fetching
- `.state.json`: Runtime state file (auto-created, not committed)

**Testing/Validation:**
- Tests not present in repo structure
- Manual testing via `--dry-run` flag recommended for validation

## Naming Conventions

**Files:**
- `snake_case.py`: All Python files use snake_case
- Entry point: `main.py`
- Logic modules: `{domain}.py` (auth, config, ews_client, summarizer, llm_summarizer, state)

**Classes:**
- `PascalCase`: All classes use PascalCase (Config, Email, EmailSummary, DailySummary, EWSClient, EWSAuthenticator, LLMSummarizer, StateManager)
- Exception classes: `PascalCase` ending with `Error` (AuthenticationError, EWSClientError, LLMSummarizerError)

**Functions:**
- `snake_case`: All functions use snake_case
- Private methods: Leading underscore (e.g., `_get_config()`, `_strip_html()`)
- Properties: Decorated with `@property` for computed attributes

**Variables:**
- `snake_case`: Local variables, parameters, module-level constants
- Environment variables: `UPPERCASE_WITH_UNDERSCORES` (AZURE_TENANT_ID, USER_EMAIL, SHARED_MAILBOX)
- Constants: `UPPERCASE_WITH_UNDERSCORES` (DEFAULT_STATE_FILE in state.py line 14)

**Modules/Packages:**
- `src/`: Main package directory
- No deeply nested subdirectories; flat structure for simplicity

## Where to Add New Code

**New Feature:**
- Primary code: `src/summarizer.py` for summary-related features, `src/ews_client.py` for EWS operations, `src/llm_summarizer.py` for LLM-based features
- Tests: Not currently present; recommend creating `tests/test_{module}.py` parallel to `src/{module}.py`
- Configuration: Add new settings to `Config` class in `src/config.py` with environment variable parsing

**New Authentication Method:**
- Implementation: Create new authenticator class in `src/auth.py` alongside EWSAuthenticator
- Pattern: Inherit from common base or implement same interface (get_ews_credentials() method)
- Update: Modify `src/main.py` to instantiate new authenticator based on config flag

**New Summarization Strategy:**
- Implementation: Add method to `EmailSummarizer` class in `src/summarizer.py` or extend `LLMSummarizer`
- Configuration: Add feature flag to `Config` class (e.g., USE_ADVANCED_SUMMARY)
- Integration: Call new method from main summarization flow in `src/summarizer.py` line 102

**New Integration (Slack, Teams, etc.):**
- Implementation: Create new module `src/{service}_sender.py` (e.g., `src/slack_sender.py`)
- Pattern: Implement send method accepting DailySummary object
- Integration: Call from main orchestration in `src/main.py` after summary generation

**Utilities:**
- Shared helpers: Add to existing modules where appropriate or create utility functions in relevant domain modules
- General utilities: Create `src/utils.py` if needed for cross-cutting concerns

## Special Directories

**src/__pycache__/:**
- Purpose: Python bytecode cache (auto-generated)
- Generated: Yes
- Committed: No (excluded by .gitignore)

**.venv/ (or venv/):**
- Purpose: Python virtual environment
- Generated: Yes
- Committed: No (should be excluded by .gitignore)

**deploy/:**
- Purpose: PowerShell scripts for Windows scheduled task automation
- Generated: No
- Committed: Yes

**prompts/:**
- Purpose: Planning and specification documents
- Generated: No
- Committed: Yes

**.planning/:**
- Purpose: GSD codebase mapping documentation
- Generated: Yes (by GSD tools)
- Committed: Yes (maintained in version control)

## Configuration Management

**Environment Variables Hierarchy:**
1. OS environment variables (highest priority)
2. .env file in project root
3. Config class defaults (lowest priority)

**File Locations (Config class in src/config.py):**
- Configuration template: `.env.example` (always committed)
- Runtime configuration: `.env` (never committed, created from template)
- Token cache: `.token_cache.json` in project root (auto-created, never committed)
- State file: `.state.json` in project root (auto-created, never committed)

**Configuration Access Pattern:**
- All code imports Config from `src/config.py`
- Access via `Config.VARIABLE_NAME` (static class attributes)
- Parse lists via `Config._parse_email_list()` helper
- Validate via `Config.validate()` method at startup

## Code Organization Principles

**Single Responsibility:**
- Each module handles one domain (auth, config, ews, summarization, state)
- Each class has single clear purpose (EWSClient for mailbox access, StateManager for persistence)
- Each function does one thing well

**Layered Dependencies:**
```
main.py (orchestrator)
  ↓
auth.py, config.py, ews_client.py, summarizer.py, state.py
  ↓
exchangelib, msal, openai, httpx (external libraries)
```
- Unidirectional dependencies: Lower layers don't import upper layers
- Configuration injected through Config class, not passed through function parameters

**Error Handling:**
- Domain-specific exceptions raised from each module
- Caught and handled in main.py orchestrator
- Descriptive error messages guide operators on resolution

**Logging:**
- Module-level logger: `logger = logging.getLogger(__name__)` in each module
- Consistent format across all modules
- Debug logging for detailed investigation, Info for operations

---

*Structure analysis: 2026-02-23*
