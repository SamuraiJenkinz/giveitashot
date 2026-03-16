# InboxIQ - Email Summarizer Agent

A Python tool that reads emails from an Exchange Online shared mailbox via Microsoft Graph API, generates AI-powered summaries using Azure OpenAI, and sends HTML digest emails to recipients. Includes a dual-digest system: regular email summaries plus a dedicated M365 Message Center major updates digest with deadline tracking and AI-extracted admin actions.

## Features

- **Microsoft Graph API** for email reading and sending (replaced EWS in v2.0)
- **App-only authentication** with MSAL client credentials (no user interaction needed)
- Reads emails from a shared mailbox with OData filtering and pagination
- **AI-Powered Summarization** (Azure OpenAI):
  - Executive digest summarizing all emails at a glance
  - Intelligent per-email summaries highlighting key points and action items
  - Smart categorization (Action Required, FYI, Meetings, Urgent, etc.)
- **Dual-Digest System**:
  - Regular digest for general email summaries
  - Major Updates digest for M365 Message Center notifications with:
    - Multi-signal weighted classification (sender, subject, body patterns)
    - Urgency-based color-coding (Critical/High/Normal)
    - AI-extracted admin actions with deadline countdown
    - MC metadata display (Message ID, affected services, categories)
- Fallback to basic summarization if LLM unavailable
- Error isolation — failure in one digest type never blocks the other
- Independent state management per digest type
- HTML-formatted email with professional styling
- Sends to multiple recipients (TO/CC/BCC support) with SendAs
- Incremental fetching (only new emails since last run)

## Prerequisites

- Python 3.10 or higher
- An Azure AD (Entra ID) app registration with:
  - **Mail.Read** application permission (for reading shared mailbox)
  - **Mail.Send** application permission (for sending digest emails)
  - Client secret
  - Admin consent granted
- Azure OpenAI endpoint (for AI summaries)

## Azure AD App Registration

### Step 1: Register the Application

1. Go to the [Azure Portal](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** > **App registrations**
3. Click **New registration**
4. Configure:
   - **Name**: `InboxIQ Email Summarizer`
   - **Supported account types**: `Accounts in this organizational directory only`
5. Click **Register**

### Step 2: Note the Application Details

From the **Overview** page, copy:
- **Application (client) ID** > `MICROSOFT_CLIENT_ID`
- **Directory (tenant) ID** > `MICROSOFT_TENANT_ID`

### Step 3: Create a Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Add a description and expiration
4. Copy the secret value > `MICROSOFT_CLIENT_SECRET`

### Step 4: Configure API Permissions

1. Go to **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Select **Application permissions** (not Delegated)
5. Add:
   - `Mail.Read` — read emails from shared mailbox
   - `Mail.Send` — send digest emails
6. Click **Grant admin consent** (requires admin)

### Step 5: Scope Mailbox Access (Recommended)

To restrict the app to only the shared mailbox (not all mailboxes in the tenant), configure an Application Access Policy:

```powershell
# Create a mail-enabled security group containing only the shared mailbox
# Then restrict the app to that group:
New-ApplicationAccessPolicy -AppId "<your-client-id>" `
    -PolicyScopeGroupId "<security-group-id>" `
    -AccessRight RestrictAccess `
    -Description "Restrict InboxIQ to shared mailbox only"
```

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/SamuraiJenkinz/giveitashot.git
cd giveitashot
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

### 3. Activate the Virtual Environment

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

```bash
copy .env.example .env
```

Edit `.env` with your values:

```env
# Azure AD / Microsoft Entra ID Configuration
MICROSOFT_TENANT_ID=your-tenant-id
MICROSOFT_CLIENT_ID=your-client-id
MICROSOFT_CLIENT_SECRET=your-client-secret

# Email Configuration
SENDER_EMAIL=your-email@company.com
SHARED_MAILBOX=shared-mailbox@company.com

# SendAs - Optional: Send from a different address (requires SendAs permission)
# SEND_FROM=shared-mailbox@company.com

# Regular Digest Recipients
SUMMARY_TO=manager@company.com,team-lead@company.com
# SUMMARY_CC=team@company.com
# SUMMARY_BCC=archive@company.com

# Major Updates Digest Recipients (enables feature when MAJOR_UPDATE_TO is set)
# MAJOR_UPDATE_TO=admin@company.com,it-lead@company.com
# MAJOR_UPDATE_CC=it-team@company.com
# MAJOR_UPDATE_BCC=compliance@company.com

# Azure OpenAI Configuration
CHATGPT_ENDPOINT=https://your-resource.openai.azure.com/openai/deployments/your-deployment/chat/completions
AZURE_OPENAI_API_KEY=your-openai-api-key
API_VERSION=2024-08-01-preview
USE_LLM_SUMMARY=true

DEBUG=false
```

## Usage

### Basic Usage

```bash
python -m src.main
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug logging |
| `--clear-cache` | Clear cached credentials |
| `--dry-run` | Generate summary but don't send email |
| `--full` | Fetch all emails from today (ignore last run time) |
| `--clear-state` | Clear state file (forces full fetch on next run) |
| `--major-only` | Process only major updates digest (skip regular digest) |

### Incremental Mode (Default)

By default, the agent only fetches emails received **since the last successful run**. This prevents duplicate summaries when running hourly.

- State is stored in `.state.json` (auto-created)
- After each successful send, the timestamp is updated
- On first run (or after `--clear-state`), fetches all emails from today
- Regular and major update digests maintain independent state

### Examples

```bash
# Run incrementally (only new emails since last run)
python -m src.main

# Fetch all emails from today (ignore state)
python -m src.main --full

# Preview without sending (does not update state)
python -m src.main --dry-run

# Reset state and fetch everything
python -m src.main --clear-state

# Debug mode
python -m src.main --debug
```

## AI Summarization Features

When `USE_LLM_SUMMARY=true`, the agent uses Azure OpenAI to generate:

### 1. Executive Digest
A high-level summary of all emails highlighting:
- Most important/urgent items
- Required actions and deadlines
- Recurring themes

### 2. Per-Email Summaries
Each email gets an intelligent summary with:
- Main purpose or request
- Action items and deadlines
- Key information extracted

### 3. Smart Categorization
Emails are automatically categorized:
- **Action Required**: Needs response or action
- **FYI/Informational**: Updates, newsletters
- **Meetings**: Calendar-related
- **Urgent**: Time-sensitive items
- **Other**: Everything else

### Disabling AI

Set `USE_LLM_SUMMARY=false` to use basic text extraction instead.

## Major Updates Digest

When `MAJOR_UPDATE_TO` is set, InboxIQ automatically detects M365 Message Center major update emails and routes them to a separate admin-focused digest.

### How Detection Works

A multi-signal weighted classifier scores each email:
- Sender address (`o365mc@email2.microsoft.com`)
- Subject patterns (MC IDs, "Major update", "Action required")
- Body content (admin impact, deadlines, affected services)
- Emails scoring above 70% threshold are classified as major updates

### Major Updates Digest Contents

- **Urgency tiers**: Critical (red), High (orange), Normal (blue)
- **MC metadata**: Message ID, affected services, categories, published/action dates
- **AI-extracted actions**: Specific admin steps with deadline countdown
- **Graceful degradation**: Falls back to basic formatting if AI is unavailable

### Configuration

Major updates digest activates automatically when `MAJOR_UPDATE_TO` has recipients (presence-based toggle):

```env
MAJOR_UPDATE_TO=admin@company.com,it-lead@company.com
MAJOR_UPDATE_CC=it-team@company.com
```

## Multiple Recipients

### Option 1: Single Recipient (Simple)

```env
SUMMARY_RECIPIENT=manager@company.com
```

### Option 2: Multiple Recipients

```env
SUMMARY_TO=manager@company.com,team-lead@company.com
SUMMARY_CC=team@company.com,stakeholder@company.com
SUMMARY_BCC=archive@company.com,compliance@company.com
```

### Option 3: Distribution List

```env
SUMMARY_RECIPIENT=incident-team-dl@company.com
```

**Note**: If `SUMMARY_TO` is set, it takes precedence over `SUMMARY_RECIPIENT`.

## SendAs (Custom From Address)

By default, emails are sent from `SENDER_EMAIL`. If you have **SendAs** permission on another mailbox, you can send emails that appear to come from that address.

### Configuration

```env
SENDER_EMAIL=kevin.j.taylor@mmc.com      # Account used for authentication
SEND_FROM=messagingai@marsh.com           # From address (requires SendAs permission)
```

### How It Works

| Setting | Result |
|---------|--------|
| `SEND_FROM` not set | From: kevin.j.taylor@mmc.com |
| `SEND_FROM=messagingai@marsh.com` | From: messagingai@marsh.com |

### Granting SendAs Permission

```powershell
Add-RecipientPermission -Identity "messagingai@marsh.com" `
    -Trustee "kevin.j.taylor@mmc.com" `
    -AccessRights SendAs
```

**Note**: SendAs permission may take up to 60 minutes to propagate.

## File Structure

```
├── .env                    # Your configuration
├── .env.example            # Configuration template
├── README.md               # This documentation
├── requirements.txt        # Python dependencies
├── src/
│   ├── __init__.py
│   ├── auth.py             # MSAL client credentials auth (GraphAuthenticator)
│   ├── config.py           # Configuration management
│   ├── graph_client.py     # Microsoft Graph API client (read + send)
│   ├── classifier.py       # M365 Message Center email classifier
│   ├── extractor.py        # MC metadata extraction (dates, services, IDs)
│   ├── action_extractor.py # AI-powered admin action extraction
│   ├── llm_summarizer.py   # Azure OpenAI integration
│   ├── summarizer.py       # Email summarization and HTML digest builder
│   ├── state.py            # Incremental state management
│   └── main.py             # Main entry point and orchestration
├── tests/
│   ├── conftest.py         # Shared fixtures
│   ├── fixtures/           # Test email fixtures (.eml files)
│   ├── test_auth.py
│   ├── test_config.py
│   ├── test_classifier.py
│   ├── test_extractor.py
│   ├── test_graph_client.py
│   ├── test_integration.py
│   └── test_integration_dual_digest.py
└── deploy/
    ├── setup_scheduled_task.ps1
    └── manage_service.ps1
```

## Troubleshooting

### Authentication Errors

**"AADSTS7000215: Invalid client secret"**
- Verify `MICROSOFT_CLIENT_SECRET` is correct
- Check if the secret has expired

**"AADSTS700016: Application not found"**
- Verify `MICROSOFT_CLIENT_ID` and `MICROSOFT_TENANT_ID`

### Graph API Errors

**"403 Forbidden"**
- Ensure `Mail.Read` and `Mail.Send` permissions are granted
- Verify admin consent was given
- Check Application Access Policy if mailbox scoping is configured

**"404 Not Found"**
- Verify the shared mailbox email address is correct
- Ensure the mailbox exists and is accessible

**"429 Too Many Requests"**
- InboxIQ handles throttling automatically with Retry-After headers
- If persistent, reduce fetch frequency

### LLM Errors

**"LLM API error: 401"**
- Verify `AZURE_OPENAI_API_KEY` is correct

**"LLM API error: 404"**
- Verify `CHATGPT_ENDPOINT` URL is correct

**LLM unavailable**
- The agent will fall back to basic summarization automatically

## Scheduling

Use the included deployment scripts to set up automated hourly execution.

### Automated Setup (Recommended)

```powershell
# Run as Administrator
.\deploy\setup_scheduled_task.ps1
```

This creates a Windows Scheduled Task that runs every hour, 24/7.

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-AppPath` | `C:\m365incidents` | Installation directory |
| `-TaskName` | `M365EmailSummarizer` | Scheduled task name |
| `-IntervalHours` | `1` | Hours between runs |
| `-StartTime` | `00:00` | Initial start time |
| `-RunNow` | - | Run immediately after setup |

**Examples:**

```powershell
# Default: Run every hour
.\deploy\setup_scheduled_task.ps1

# Run every 2 hours
.\deploy\setup_scheduled_task.ps1 -IntervalHours 2

# Run immediately after setup
.\deploy\setup_scheduled_task.ps1 -RunNow
```

### Management Commands

```powershell
# Check status
.\deploy\manage_service.ps1 -Action status

# Run manually
.\deploy\manage_service.ps1 -Action run-now

# View logs
.\deploy\manage_service.ps1 -Action logs

# Disable task
.\deploy\manage_service.ps1 -Action stop

# Remove task
.\deploy\manage_service.ps1 -Action remove
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

210 tests covering auth, config, Graph client (read/send), classifier, extractor, action extraction, summarization, and full integration flows.

## Security Notes

- **Never commit `.env`** — contains secrets
- Store client secrets securely
- Rotate secrets periodically
- Use Application Access Policy to scope mailbox access
- Graph permissions use least-privilege (Mail.Read + Mail.Send only)

## Version History

- **v2.0** (2026-03-15) — Replaced EWS with Microsoft Graph API. exchangelib removed, all email operations via Graph REST API. 210 tests passing.
- **v1.0** (2026-02-26) — Dual-digest system with M365 Message Center major updates detection, AI-powered action extraction, and 167 tests.
