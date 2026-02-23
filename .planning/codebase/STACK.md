# Technology Stack

**Analysis Date:** 2026-02-23

## Languages

**Primary:**
- Python 3.10+ - Core application language, used throughout entire codebase

## Runtime

**Environment:**
- Python 3.10+ (specified in README as minimum requirement)

**Package Manager:**
- pip - Package dependency manager
- Lockfile: requirements.txt (present, contains pinned versions)

## Frameworks

**Core:**
- exchangelib 5.4.0+ - Exchange Web Services (EWS) client for email operations (`src/ews_client.py`)
- msal 1.28.0+ - Microsoft Authentication Library for OAuth 2.0 authentication (`src/auth.py`)
- python-dotenv 1.0.0+ - Environment variable management from .env files (`src/config.py`)

**API & LLM:**
- openai 1.0.0+ - Azure OpenAI API integration (`src/llm_summarizer.py`)
- httpx 0.27.0+ - HTTP client for making requests to external APIs (`src/llm_summarizer.py`)

## Key Dependencies

**Critical:**
- exchangelib 5.4.0+ - Why it matters: Primary integration for accessing Exchange Online shared mailboxes via EWS impersonation
- msal 1.28.0+ - Why it matters: Handles OAuth 2.0 client credentials flow for Azure AD authentication; CVE-2024-35255 fix required
- openai 1.0.0+ - Why it matters: Azure OpenAI integration for intelligent email summarization
- httpx 0.27.0+ - Why it matters: Secure HTTP client with security updates for API communication

**Infrastructure:**
- python-dotenv 1.0.0+ - Loads environment variables from .env file for configuration management

## Configuration

**Environment:**
- Configuration method: Environment variables loaded from `.env` file via `python-dotenv`
- Key configs required:
  - `AZURE_TENANT_ID` - Azure AD tenant ID
  - `AZURE_CLIENT_ID` - Azure AD app registration client ID
  - `AZURE_CLIENT_SECRET` - Azure AD client secret (for OAuth2)
  - `USER_EMAIL` - Email address for authentication
  - `SHARED_MAILBOX` - Shared mailbox email address to read from
  - `CHATGPT_ENDPOINT` - Azure OpenAI API endpoint URL
  - `AZURE_OPENAI_API_KEY` - Azure OpenAI API key
  - `API_VERSION` - OpenAI API version (default: 2023-05-15)
  - `EWS_SERVER` - Exchange Web Services server (default: outlook.office365.com)
  - `USE_LLM_SUMMARY` - Enable/disable LLM summarization (default: true)
  - `DEBUG` - Enable debug logging (default: false)
  - `SUMMARY_RECIPIENT` or `SUMMARY_TO/CC/BCC` - Email recipient configuration

**Build:**
- No build configuration files detected (pure Python application)
- Entry point: `python -m src.main`

## Platform Requirements

**Development:**
- Python 3.10 or higher
- Windows, macOS, or Linux (platform-agnostic Python)
- Virtual environment recommended (venv)

**Production:**
- Deployment target: Windows Task Scheduler (via PowerShell scripts in `deploy/`)
- Alternative: Any OS supporting Python 3.10+
- Azure AD app registration with EWS permissions required
- Access to Azure OpenAI service (for AI summarization)
- Access to Exchange Online shared mailbox

## Authentication & Security

**OAuth 2.0 Flow:**
- Client credentials flow (app-only authentication, no user interaction)
- Implemented via MSAL (`msal.ConfidentialClientApplication`)
- Token caching in `.token_cache.json`
- Scope: `https://outlook.office365.com/.default` for EWS

**Token Management:**
- Cached tokens reused when available
- Manual cache clearing via `--clear-cache` CLI flag
- Automatic token refresh via MSAL

## Dependencies Summary

```
Core Email/Auth:
  - exchangelib >= 5.4.0
  - msal >= 1.28.0
  - python-dotenv >= 1.0.0

External APIs:
  - openai >= 1.0.0
  - httpx >= 0.27.0
```

---

*Stack analysis: 2026-02-23*
