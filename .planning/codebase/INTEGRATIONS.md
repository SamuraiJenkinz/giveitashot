# External Integrations

**Analysis Date:** 2026-02-23

## APIs & External Services

**Email Service (Microsoft Exchange Online):**
- Exchange Web Services (EWS) - Core email reading and sending
  - SDK/Client: `exchangelib` library
  - Server: `outlook.office365.com` (configurable via `EWS_SERVER`)
  - Connection method: OAuth 2.0 credentials with impersonation
  - Implementation: `src/ews_client.py` - EWSClient class

**AI/LLM Service (Azure OpenAI):**
- Azure OpenAI - Email summarization and categorization
  - SDK/Client: `openai` library with httpx for HTTP requests
  - Auth: API key (`AZURE_OPENAI_API_KEY`)
  - Endpoint: `CHATGPT_ENDPOINT` environment variable
  - API version: `2023-05-15` (default, configurable)
  - Implementation: `src/llm_summarizer.py` - LLMSummarizer class
  - Optional: Set `USE_LLM_SUMMARY=false` to disable and use basic summarization fallback

**Authentication Service (Azure AD):**
- Azure Active Directory (Microsoft Entra ID)
  - SDK/Client: `msal` (Microsoft Authentication Library)
  - Auth method: Client credentials flow (app-only)
  - Tenant endpoint: `https://login.microsoftonline.com/{TENANT_ID}`
  - Implementation: `src/auth.py` - EWSAuthenticator class
  - Scope: `https://outlook.office365.com/.default`

## Data Storage

**Databases:**
- None - Application is stateless except for local state file

**File Storage:**
- Local filesystem only
  - State file: `.state.json` - Stores last successful run timestamp for incremental email fetching
  - Token cache: `.token_cache.json` - Caches OAuth tokens locally
  - Configuration: `.env` file - Stores secrets and configuration

**Caching:**
- Local memory caching: OAuth tokens cached in `.token_cache.json` via MSAL
- No external caching service used

## Authentication & Identity

**Auth Provider:**
- Azure AD (Microsoft Entra ID)
  - Implementation approach: OAuth 2.0 client credentials flow (app-only)
  - No user interaction required
  - Requires Azure AD app registration with:
    - `AZURE_TENANT_ID` - Directory/tenant ID
    - `AZURE_CLIENT_ID` - Application (client) ID
    - `AZURE_CLIENT_SECRET` - Client secret
  - Required permission: `full_access_as_app` on Office 365 Exchange Online API
  - Admin consent required for app registration

**SendAs Permission:**
- Optional Exchange Online permission
  - Allows sending emails from different email address
  - Configured via `SEND_FROM` environment variable
  - Default: Uses `USER_EMAIL` if `SEND_FROM` not set
  - May take up to 60 minutes to propagate

## Monitoring & Observability

**Error Tracking:**
- None detected - Application logs errors to stdout

**Logs:**
- Logging approach: Python logging module with stdout handler
  - Log levels: DEBUG (when enabled), INFO, WARNING, ERROR
  - Configuration: `src/main.py` - setup_logging() function
  - Can be enabled via `--debug` CLI flag or `DEBUG=true` environment variable
  - Logs include: Authentication flow, EWS operations, LLM calls, email processing

## CI/CD & Deployment

**Hosting:**
- Windows Task Scheduler (primary deployment target)
  - PowerShell scripts in `deploy/` for automated setup
  - Can also run on any OS supporting Python 3.10+

**CI Pipeline:**
- None detected - No automated CI/CD configuration found

**Deployment Scripts:**
- `deploy/setup_scheduled_task.ps1` - Creates Windows Scheduled Task for hourly execution
- `deploy/manage_service.ps1` - Management commands (status, run-now, logs, stop, remove)

## Environment Configuration

**Required env vars:**
- Azure AD:
  - `AZURE_TENANT_ID` - Azure tenant ID
  - `AZURE_CLIENT_ID` - App registration client ID
  - `AZURE_CLIENT_SECRET` - App registration client secret
- Email Configuration:
  - `USER_EMAIL` - Email for authentication
  - `SHARED_MAILBOX` - Shared mailbox to read from
  - `EWS_SERVER` - EWS server (default: outlook.office365.com)
- Recipients (choose one):
  - `SUMMARY_RECIPIENT` - Single recipient (legacy)
  - `SUMMARY_TO` - Multiple TO recipients (comma-separated)
  - `SUMMARY_CC` - CC recipients (optional, comma-separated)
  - `SUMMARY_BCC` - BCC recipients (optional, comma-separated)
- Azure OpenAI:
  - `CHATGPT_ENDPOINT` - Azure OpenAI endpoint URL
  - `AZURE_OPENAI_API_KEY` - Azure OpenAI API key
  - `API_VERSION` - OpenAI API version (default: 2023-05-15)
- Optional:
  - `SEND_FROM` - Custom from address (requires SendAs permission)
  - `USE_LLM_SUMMARY` - Enable/disable AI summarization (default: true)
  - `DEBUG` - Enable debug logging (default: false)

**Secrets location:**
- `.env` file in project root (loaded by python-dotenv)
- `.token_cache.json` - MSAL token cache (auto-created)
- Note: `.env` should NOT be committed to version control

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- Email sending (via EWS)
  - Sends summary email to configured recipients
  - TO, CC, BCC recipients supported
  - From address configurable via `SEND_FROM`
  - Implementation: `src/ews_client.py` - EWSClient.send_email()

## Data Flow Architecture

1. **Authentication Phase:**
   - `src/auth.py` - Acquires OAuth token from Azure AD
   - Uses client credentials flow (app-only)
   - Token cached in `.token_cache.json`

2. **Email Fetching Phase:**
   - `src/ews_client.py` - Connects to shared mailbox via EWS impersonation
   - Queries inbox for emails since last run (or today if first run)
   - State tracked in `.state.json` for incremental fetching

3. **Summarization Phase:**
   - `src/summarizer.py` - Processes emails
   - `src/llm_summarizer.py` - Calls Azure OpenAI for intelligent summaries (if enabled)
   - Fallback: Basic text extraction if LLM unavailable

4. **Email Delivery Phase:**
   - `src/ews_client.py` - Sends formatted HTML summary email
   - Supports TO/CC/BCC recipients
   - Can send from different address via SendAs

5. **State Update Phase:**
   - `src/state.py` - Updates `.state.json` with current timestamp
   - Enables incremental fetching on next run

## Error Handling & Fallbacks

**LLM Unavailable:**
- Falls back to basic text extraction (first 500 characters of email body)
- Application continues operating without AI features
- Implementation: `src/summarizer.py` - tries LLM, catches exception, uses basic method

**Authentication Failures:**
- Clear error messaging with troubleshooting hints
- Suggests checking Azure AD app registration and credentials
- Exit code: 1 on authentication failure

**EWS Connection Failures:**
- Suggests verifying shared mailbox access and permissions
- Exit code: 1 on EWS error

**Configuration Missing:**
- Validates all required environment variables at startup
- Provides helpful error messages listing missing vars
- Exit code: 1 on configuration error

## Security Considerations

**Secrets Management:**
- OAuth tokens cached locally in `.token_cache.json`
- API keys stored in `.env` (not in version control)
- Client secret never logged or exposed

**Permissions Model:**
- App-only authentication (no user credentials stored)
- Requires admin to grant `full_access_as_app` permission
- Uses principle of least privilege with impersonation

**SendAs Permission:**
- Optional additional permission for sending from different address
- Must be explicitly granted and configured

---

*Integration audit: 2026-02-23*
