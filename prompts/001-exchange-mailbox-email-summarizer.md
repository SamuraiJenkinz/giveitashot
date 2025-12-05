<objective>
Build a Python script/agent that reads emails from an Exchange Online shared mailbox for the current day, summarizes them using AI, and sends the summary to a specified recipient.

This automation will help process daily communications from the messagingai@marsh.com shared mailbox by providing a concise summary delivered to kevin.j.taylor@mmc.com each time it runs.
</objective>

<context>
- **Platform**: Windows 11 workstation on corporate network
- **Authentication**: OAuth 2.0 using kevin.j.taylor@mmc.com credentials
- **Shared Mailbox**: messagingai@marsh.com (read access via delegated permissions)
- **Summary Recipient**: kevin.j.taylor@mmc.com
- **Email Scope**: Current day only (from midnight to current time)

The script will leverage Microsoft Graph API for Exchange Online access, which is the modern approach for interacting with M365 mailboxes programmatically.

Follow Python best practices and PEP 8 conventions.
</context>

<requirements>
<functional>
1. **Authentication**:
   - Implement OAuth 2.0 authentication flow for Microsoft Graph API
   - Support interactive login for initial token acquisition
   - Cache tokens securely for subsequent runs (token refresh support)
   - Use delegated permissions (user context) since accessing via personal credentials

2. **Email Retrieval**:
   - Connect to the shared mailbox messagingai@marsh.com
   - Filter emails to current day only (receivedDateTime >= today at 00:00)
   - Retrieve email subject, sender, received time, and body content
   - Handle pagination if there are many emails

3. **Email Summarization**:
   - Generate a concise summary of each email's key points
   - Group or categorize emails if patterns emerge (e.g., by sender domain, topic)
   - Include total email count and time range in the summary
   - Format the summary for easy readability in an email body

4. **Summary Delivery**:
   - Send the formatted summary email to kevin.j.taylor@mmc.com
   - Use a clear subject line indicating it's a daily summary with the date
   - Handle the case where no emails exist for the current day (send "No emails received today" message)

5. **Error Handling**:
   - Graceful handling of authentication failures
   - Network timeout handling
   - Clear error messages for troubleshooting
</functional>

<technical>
- Use Python 3.x (verify installed version)
- Use `msal` library for Microsoft Authentication Library
- Use `requests` or `httpx` for Graph API calls (or `msgraph-sdk` if preferred)
- Store configuration (client ID, tenant ID) in a separate config file or environment variables
- Log operations for debugging/audit trail
</technical>
</requirements>

<implementation>
<approach>
1. **Project Setup**:
   - Create virtual environment
   - Install required packages: `msal`, `requests`, `python-dotenv`
   - Create configuration file for Azure AD app registration details

2. **Azure AD App Registration** (document requirements):
   - The script will need an Azure AD app registration with:
     - Microsoft Graph delegated permissions: `Mail.Read.Shared`, `Mail.Send`
     - Redirect URI for interactive auth (e.g., `http://localhost:8400`)
   - Document these requirements for the user to set up

3. **Authentication Module**:
   - Implement MSAL PublicClientApplication for interactive auth
   - Token caching to avoid repeated logins
   - Token refresh handling

4. **Graph API Integration**:
   - GET /users/{user-id}/mailFolders/inbox/messages for shared mailbox
   - Use `$filter` for date filtering
   - Use `$select` for efficient field retrieval
   - Use `$top` and `$skip` or `@odata.nextLink` for pagination

5. **Summarization Logic**:
   - Extract key information from email bodies
   - Create structured summary with sections:
     - Overview (count, date range)
     - Email summaries (sender, subject, key points)
     - Categories if applicable

6. **Email Sending**:
   - POST /me/sendMail for sending the summary
   - HTML formatted email body for better readability
</approach>

<constraints>
- Do NOT hardcode credentials or tokens in the script (security risk)
- Do NOT store client secrets in code (use environment variables or secure config)
- Use UTC or local timezone consistently for date filtering - document which is used
- Keep email body retrieval efficient (use `$select` to limit fields)
</constraints>
</implementation>

<output>
Create the following files with relative paths:

- `./src/config.py` - Configuration management (loads from .env or config file)
- `./src/auth.py` - OAuth authentication module using MSAL
- `./src/graph_client.py` - Microsoft Graph API client for email operations
- `./src/summarizer.py` - Email summarization logic
- `./src/main.py` - Main entry point orchestrating the workflow
- `./.env.example` - Example environment file with required variables
- `./requirements.txt` - Python dependencies
- `./README.md` - Setup and usage instructions including Azure AD app registration steps
</output>

<verification>
Before declaring complete, verify:

1. **Syntax Check**: Run `python -m py_compile ./src/main.py` to verify no syntax errors
2. **Dependencies**: Confirm all imports are included in requirements.txt
3. **Configuration**: Verify .env.example contains all required variables
4. **Documentation**: README includes clear setup steps for:
   - Azure AD app registration
   - Required Graph API permissions
   - Environment configuration
   - Running the script
5. **Code Review**: Ensure no hardcoded credentials or sensitive data
</verification>

<success_criteria>
- Script authenticates successfully via OAuth using kevin.j.taylor@mmc.com credentials
- Script can read emails from the shared mailbox messagingai@marsh.com
- Script correctly filters to current day's emails only
- Script generates a readable summary of the emails
- Script sends the summary email to kevin.j.taylor@mmc.com
- Script handles edge cases (no emails, auth failures, network issues)
- README provides complete setup instructions
- Code follows Python best practices and is well-documented
</success_criteria>
