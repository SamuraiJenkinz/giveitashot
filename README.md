# Email Summarizer Agent (EWS)

A Python script that reads emails from an Exchange Online shared mailbox for the current day using Exchange Web Services (EWS), generates AI-powered summaries using Azure OpenAI, and sends the digest to a specified recipient.

## Features

- **App-only authentication** with client credentials (no user interaction needed)
- Reads emails from a shared mailbox via EWS impersonation
- Filters emails to current day only
- **AI-Powered Summarization** (Azure OpenAI):
  - Executive digest summarizing all emails at a glance
  - Intelligent per-email summaries highlighting key points and action items
  - Smart categorization (Action Required, FYI, Meetings, Urgent, etc.)
- Fallback to basic summarization if LLM unavailable
- HTML-formatted email with professional styling
- Sends summary email to multiple recipients (TO/CC/BCC support)

## Prerequisites

- Python 3.10 or higher
- An Azure AD app registration with:
  - EWS application permission (`full_access_as_app`)
  - Client secret
  - Admin consent granted
- Azure OpenAI endpoint (for AI summaries)

## Azure AD App Registration

### Step 1: Register the Application

1. Go to the [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
4. Configure:
   - **Name**: `Email Summarizer Agent`
   - **Supported account types**: `Accounts in this organizational directory only`
5. Click **Register**

### Step 2: Note the Application Details

From the **Overview** page, copy:
- **Application (client) ID** → `AZURE_CLIENT_ID`
- **Directory (tenant) ID** → `AZURE_TENANT_ID`

### Step 3: Create a Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Add a description and expiration
4. Copy the secret value → `AZURE_CLIENT_SECRET`

### Step 4: Configure API Permissions

1. Go to **API permissions**
2. Click **Add a permission**
3. Select **APIs my organization uses**
4. Search for **Office 365 Exchange Online**
5. Select **Application permissions** (not Delegated)
6. Add: `full_access_as_app`
7. Click **Grant admin consent** (requires admin)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/mmctech/giveitashot.git
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
# Azure AD Configuration
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

# Email Configuration
USER_EMAIL=your-email@company.com
SHARED_MAILBOX=shared-mailbox@company.com
EWS_SERVER=outlook.office365.com

# SendAs - Optional: Send from a different address (requires SendAs permission)
# SEND_FROM=shared-mailbox@company.com

# Recipients - Option 1: Single recipient (simple)
SUMMARY_RECIPIENT=recipient@company.com

# Recipients - Option 2: Multiple with TO/CC/BCC
# SUMMARY_TO=manager@company.com,team-lead@company.com
# SUMMARY_CC=team@company.com
# SUMMARY_BCC=archive@company.com

# Azure OpenAI Configuration
CHATGPT_ENDPOINT=https://your-openai-endpoint/chat/completions
AZURE_OPENAI_API_KEY=your-openai-api-key
API_VERSION=2023-05-15
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

### Examples

```bash
# Run and send summary
python -m src.main

# Preview without sending
python -m src.main --dry-run

# Debug mode
python -m src.main --debug
```

## AI Summarization Features

When `USE_LLM_SUMMARY=true`, the agent uses Azure OpenAI to:

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

## Multiple Recipients

The agent supports sending summaries to multiple recipients with full TO/CC/BCC support.

### Option 1: Single Recipient (Simple)

```env
SUMMARY_RECIPIENT=manager@company.com
```

### Option 2: Multiple Recipients

Use comma-separated values for multiple addresses:

```env
# Primary recipients (required)
SUMMARY_TO=manager@company.com,team-lead@company.com

# CC recipients (optional)
SUMMARY_CC=team@company.com,stakeholder@company.com

# BCC recipients (optional) - useful for archiving
SUMMARY_BCC=archive@company.com,compliance@company.com
```

### Option 3: Distribution List

Simply use a distribution list email address:

```env
SUMMARY_RECIPIENT=incident-team-dl@company.com
```

**Note**: If `SUMMARY_TO` is set, it takes precedence over `SUMMARY_RECIPIENT`.

## SendAs (Custom From Address)

By default, summary emails are sent from `USER_EMAIL`. If you have **SendAs** permission on another mailbox (e.g., the shared mailbox), you can send emails that appear to come from that address.

### Configuration

```env
USER_EMAIL=kevin.j.taylor@mmc.com      # Account used for authentication
SEND_FROM=messagingai@marsh.com        # From address (requires SendAs permission)
```

### How It Works

| Setting | Result |
|---------|--------|
| `SEND_FROM` not set | From: kevin.j.taylor@mmc.com |
| `SEND_FROM=messagingai@marsh.com` | From: messagingai@marsh.com |

### Granting SendAs Permission

In Exchange Admin Center or PowerShell:

```powershell
# Grant SendAs permission
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
└── src/
    ├── __init__.py
    ├── auth.py             # OAuth client credentials auth
    ├── config.py           # Configuration management
    ├── ews_client.py       # Exchange Web Services client
    ├── llm_summarizer.py   # Azure OpenAI integration
    ├── main.py             # Main entry point
    └── summarizer.py       # Email summarization logic
```

## Troubleshooting

### Authentication Errors

**"AADSTS7000215: Invalid client secret"**
- Verify `AZURE_CLIENT_SECRET` is correct
- Check if the secret has expired

**"AADSTS700016: Application not found"**
- Verify `AZURE_CLIENT_ID` and `AZURE_TENANT_ID`

### EWS Errors

**"ErrorAccessDenied"**
- Ensure `full_access_as_app` permission is granted
- Verify admin consent was given

**"ErrorNonExistentMailbox"**
- Verify the mailbox email addresses are correct

### LLM Errors

**"LLM API error: 401"**
- Verify `AZURE_OPENAI_API_KEY` is correct

**"LLM API error: 404"**
- Verify `CHATGPT_ENDPOINT` URL is correct

**LLM unavailable**
- The agent will fall back to basic summarization automatically

## Scheduling (Optional)

Use Windows Task Scheduler to run daily:

1. Open Task Scheduler
2. Create new task
3. Set trigger: Daily at preferred time
4. Set action:
   - Program: `C:\path\to\venv\Scripts\python.exe`
   - Arguments: `-m src.main`
   - Start in: `C:\path\to\project`

## Security Notes

- **Never commit `.env`** - contains secrets
- Store client secrets securely
- Rotate secrets periodically
- Use least-privilege permissions where possible
