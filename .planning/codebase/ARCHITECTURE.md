# Architecture

**Analysis Date:** 2026-02-23

## Pattern Overview

**Overall:** Layered pipeline architecture with service-oriented modules

**Key Characteristics:**
- Three functional layers: authentication, integration, and business logic
- Single-responsibility modules with clear input/output contracts
- Configuration-driven flexibility for multiple deployment scenarios
- Optional LLM integration with automatic fallback to basic summarization
- Incremental state management for efficient scheduled execution

## Layers

**Authentication Layer:**
- Purpose: OAuth 2.0 client credentials authentication for Exchange Web Services
- Location: `src/auth.py`
- Contains: EWSAuthenticator class, token acquisition, credential management
- Depends on: MSAL library, Azure AD configuration
- Used by: EWSClient for mailbox access

**Integration Layer:**
- Purpose: Exchange Web Services communication and email operations
- Location: `src/ews_client.py`
- Contains: Email data model, mailbox access via EWS, email sending logic
- Depends on: exchangelib library, authentication credentials
- Used by: Main entry point for fetching and sending emails

**Business Logic Layer:**
- Purpose: Email summarization and formatting
- Location: `src/summarizer.py`, `src/llm_summarizer.py`
- Contains: Summary generation (basic and AI-powered), HTML formatting, categorization
- Depends on: Email objects, LLM API (optional), configuration
- Used by: Main orchestrator to transform emails into summaries

**State Management Layer:**
- Purpose: Persistent tracking of last run timestamp for incremental execution
- Location: `src/state.py`
- Contains: StateManager class, JSON-based state persistence
- Depends on: File system only
- Used by: Main entry point to determine fetch scope

**Configuration Layer:**
- Purpose: Centralized environment variable loading and validation
- Location: `src/config.py`
- Contains: Config class with all settings, environment parsing, defaults
- Depends on: python-dotenv for .env loading
- Used by: All modules for configuration values

**Orchestration Layer:**
- Purpose: Coordinate all layers in proper sequence
- Location: `src/main.py`
- Contains: Argument parsing, error handling, flow control, logging
- Depends on: All other layers
- Used by: Entry point for scheduled execution

## Data Flow

**Email Fetch Flow:**

1. Config initialization and validation (environment variables loaded)
2. Authenticator acquires OAuth token using client credentials
3. EWSClient connects to shared mailbox using impersonation
4. StateManager loads last run timestamp (or None on first run)
5. EWSClient queries inbox for emails since `last_run` (or since midnight if None)
6. Email objects extracted with sender, subject, body, timestamps
7. If no emails found, return early with success status
8. If emails found, pass to summarizer

**Summarization Flow:**

1. EmailSummarizer receives list of Email objects
2. If LLM enabled and available:
   - LLMSummarizer calls Azure OpenAI for executive digest (urgent items, action items, themes)
   - LLMSummarizer categorizes emails intelligently (Action Required, FYI, Meetings, Urgent, Other)
   - LLMSummarizer generates per-email summaries
3. If LLM unavailable or disabled:
   - Basic summarization extracts body preview (first 200 chars)
   - Emails categorized by sender domain
4. DailySummary object created with all summaries and categories
5. Summary formatted as professional HTML with inline styling
6. Subject line generated based on email count and date

**Email Send Flow:**

1. Get list of TO recipients (SUMMARY_TO or SUMMARY_RECIPIENT)
2. Get optional CC and BCC recipients
3. Get FROM address (SEND_FROM or USER_EMAIL)
4. EWSClient creates Message object with HTML body
5. Message sent via impersonation through EWS
6. StateManager updates last_run timestamp for next incremental run

**State Management:**

- Initial state: `.state.json` does not exist, `last_run` is None
- After first successful send: `.state.json` contains ISO-formatted UTC timestamp
- On next run: StateManager loads timestamp, EWSClient filters emails since that time
- `--clear-state` flag allows reset: deletes `.state.json`, forces full fetch next run
- `--full` flag ignores state: queries from midnight regardless of last_run value

## Key Abstractions

**Email:**
- Purpose: Unified representation of an email message from EWS
- Examples: `src/ews_client.py` lines 31-47
- Pattern: Dataclass with properties for convenient access (e.g., `received_time_local` formats timezone-aware datetime to local time)

**EmailSummary:**
- Purpose: Single email wrapped with summary metadata
- Examples: `src/summarizer.py` lines 20-28
- Pattern: Dataclass pairing Email attributes (subject, sender) with computed summary (key_points, category)

**DailySummary:**
- Purpose: Complete daily digest with metadata and categorization
- Examples: `src/summarizer.py` lines 32-38
- Pattern: Dataclass aggregating all EmailSummary objects, categories dict, and optional executive_digest dict

**Credentials:**
- Purpose: Abstract OAuth token handling for EWS
- Examples: `src/auth.py` lines 84-101 (OAuth2Credentials wrapper)
- Pattern: Wrapper over exchangelib.OAuth2Credentials with lazy token acquisition

## Entry Points

**Main Entry Point:**
- Location: `src/main.py` line 46 (main() function)
- Triggers: `python -m src.main [options]`
- Responsibilities:
  - Parse command-line arguments (--debug, --dry-run, --full, --clear-state, --clear-cache)
  - Setup logging configuration
  - Validate configuration (required environment variables)
  - Initialize authenticator, EWS client, state manager, and summarizer
  - Orchestrate the fetch→summarize→send flow
  - Handle errors gracefully with appropriate exit codes
  - Log all significant actions for operational visibility

**Error Handling:**

**Strategy:** Exception-based, with domain-specific exception classes

**Patterns:**
- `AuthenticationError`: Raised by EWSAuthenticator when OAuth fails (line 17)
- `EWSClientError`: Raised by EWSClient for mailbox access/send failures (line 49)
- `LLMSummarizerError`: Raised by LLMSummarizer for Azure OpenAI API failures (line 17)
- Caught in main() with descriptive logging and non-zero exit codes
- ValueError for configuration errors with helpful messages
- KeyboardInterrupt for graceful shutdown
- Generic Exception fallback with full traceback

## Cross-Cutting Concerns

**Logging:**
- Framework: Python built-in logging module
- Configuration: Hierarchical with module-specific loggers via `logging.getLogger(__name__)`
- Levels: DEBUG (verbose), INFO (operational), WARNING (potential issues), ERROR (failures)
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- exchangelib logger suppressed to WARNING unless DEBUG=true
- All significant state changes logged (auth, fetch, send, state update)

**Validation:**
- Configuration validated at startup (Config.validate() line 96 in main.py)
- Required fields: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, USER_EMAIL
- Recipient validation: At least one recipient required (SUMMARY_TO or SUMMARY_RECIPIENT)
- Email lists parsed with whitespace trimming and empty value filtering
- State file JSON parsing with fallback to empty state on decode error

**Authentication:**
- Approach: OAuth 2.0 app-only (client credentials) with impersonation
- Flow: Client credentials flow via MSAL → access token → EWS OAuth2Credentials
- Token caching: MSAL caches token in memory, --clear-cache flag forces re-auth
- Impersonation: EWSClient uses IMPERSONATION mode for shared mailbox access
- SendAs: Optional SEND_FROM configuration allows sending from different address

**Error Recovery:**
- LLM failures trigger fallback: If LLMSummarizer unavailable, basic summarization used (line 64-66 in summarizer.py)
- Email parsing errors logged but not blocking: Failed individual emails logged, others continue (line 199-201 in ews_client.py)
- EWS connection reused: Shared account cached in _shared_account and _sender_account
- State updates only on successful send: Prevents state corruption on partial failures

---

*Architecture analysis: 2026-02-23*
