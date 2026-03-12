# Architecture Research: Graph API Migration

**Project:** InboxIQ — EWS to Microsoft Graph API Migration
**Researched:** 2026-03-12
**Confidence:** HIGH (all claims verified against official Microsoft documentation)

---

## Current Architecture (What Changes)

### Component Inventory

```
src/auth.py          CHANGE   — scope switch, new return type (access token only)
src/ews_client.py    REPLACE  — full replacement with graph_client.py
src/main.py          CHANGE   — import swap + error type rename
src/config.py        CHANGE   — remove EWS_SERVER, no new required vars
src/classifier.py    UNTOUCHED
src/summarizer.py    UNTOUCHED
src/llm_summarizer.py UNTOUCHED
src/action_extractor.py UNTOUCHED
src/email_builder.py UNTOUCHED
src/state.py         UNTOUCHED
src/extractor.py     UNTOUCHED
```

### Current Data Flow

```
auth.py           → get_ews_credentials() → OAuth2Credentials (exchangelib object)
ews_client.py     → EWSClient(credentials)
                  → get_shared_mailbox_emails(mailbox, since, max_emails) → list[Email]
                  → send_email(to, subject, body_html, cc, bcc) → None
main.py           → EWSAuthenticator + EWSClient
                  → catch AuthenticationError, EWSClientError
config.py         → EWS_SERVER env var used by EWSClient
```

### The Email Dataclass (Defined in ews_client.py, Used Everywhere)

The `Email` dataclass is the central contract consumed by classifier, summarizer, extractor,
email_builder, conftest fixtures, and all tests. It must remain identical after migration.

```python
@dataclass
class Email:
    id: str
    subject: str
    sender_name: str
    sender_email: str
    received_datetime: datetime     # timezone-aware, UTC
    body_preview: str
    body_content: str               # HTML stripped to plain text
    has_attachments: bool
    classification: Optional[Any] = None
```

The `Email` dataclass must move to a shared location (or remain in `graph_client.py`) so that
`classifier.py`, `conftest.py`, and all test files that import `from src.ews_client import Email`
can be updated to a single import path change.

---

## Migration Architecture (Target State)

### Target Data Flow

```
auth.py           → get_access_token() → str (raw Bearer token, MSAL cached)
graph_client.py   → GraphClient(access_token)
                  → get_shared_mailbox_emails(mailbox, since, max_emails) → list[Email]
                  → send_email(to, subject, body_html, cc, bcc) → None
main.py           → GraphAuthenticator + GraphClient
                  → catch AuthenticationError, GraphClientError
config.py         → remove EWS_SERVER; scope is now hardcoded as "https://graph.microsoft.com/.default"
```

### Module Map: Before and After

| Before | After | Change Type |
|--------|-------|-------------|
| `src/auth.py` — EWSAuthenticator | `src/auth.py` — GraphAuthenticator | Rename class, change scope, change return type |
| `src/ews_client.py` — EWSClient | `src/graph_client.py` — GraphClient | New file, same public interface |
| `src/ews_client.py` — Email dataclass | `src/graph_client.py` — Email dataclass | Move with file |
| `src/main.py` — EWSAuthenticator, EWSClient, EWSClientError | Same file — GraphAuthenticator, GraphClient, GraphClientError | 4 import changes |
| `src/config.py` — EWS_SERVER | Remove EWS_SERVER | Delete unused var |
| `tests/conftest.py` — from src.ews_client import Email | from src.graph_client import Email | 1 import change |
| `tests/test_*.py` — any `from src.ews_client import Email` | from src.graph_client import Email | 1 import change per file |

### Full Component Diagram (Target State)

```
                            ┌──────────────────────────────────┐
                            │          src/auth.py             │
                            │  GraphAuthenticator              │
                            │  MSAL client_credentials flow    │
                            │  scope: graph.microsoft.com/.default │
                            │  → get_access_token() → str      │
                            └────────────────┬─────────────────┘
                                             │ Bearer token
                            ┌────────────────▼─────────────────┐
                            │        src/graph_client.py       │
                            │  GraphClient(access_token: str)  │
                            │  HTTP: requests library          │
                            │                                  │
                            │  get_shared_mailbox_emails(      │
                            │    mailbox, since, max_emails    │
                            │  ) → list[Email]                 │
                            │                                  │
                            │  send_email(                     │
                            │    to, subject, body_html,       │
                            │    cc, bcc                       │
                            │  ) → None                        │
                            │                                  │
                            │  Email (dataclass, same fields)  │
                            └────────────────┬─────────────────┘
                                             │ list[Email]
                            ┌────────────────▼─────────────────┐
                            │          src/main.py             │
                            │  Orchestrator (unchanged logic)  │
                            └───┬───────────────────────┬──────┘
                                │                       │
               ┌────────────────▼──────┐    ┌──────────▼──────────────┐
               │  src/classifier.py    │    │  src/summarizer.py      │
               │  UNTOUCHED            │    │  UNTOUCHED              │
               └───────────────────────┘    └─────────────────────────┘
```

---

## Interface Contract (GraphClient)

GraphClient must expose exactly the same public interface as EWSClient. Internal implementation
changes completely; the external API surface is a drop-in replacement.

### Method 1: get_shared_mailbox_emails

```python
def get_shared_mailbox_emails(
    self,
    shared_mailbox: str,              # e.g. "messagingai@marsh.com"
    since: datetime | None = None,    # timezone-aware UTC; None = today midnight
    max_emails: int = 100
) -> list[Email]:
    """
    Fetch emails from a shared mailbox inbox since `since`.

    Graph API endpoint used:
        GET /users/{shared_mailbox}/mailFolders/inbox/messages
        ?$filter=receivedDateTime ge {since}
        &$orderby=receivedDateTime desc
        &$top={max_emails}
        &$select=id,subject,from,sender,receivedDateTime,bodyPreview,body,hasAttachments

    Permissions required (application):
        Mail.Read (granted tenant-wide or scoped via Exchange RBAC for Applications)

    Returns:
        list[Email] — same Email dataclass, same field semantics as EWSClient
    """
```

**Graph API field mapping:**

| Email field | Graph API field | Notes |
|-------------|-----------------|-------|
| `id` | `message.id` | String, Graph message ID format |
| `subject` | `message.subject` | String |
| `sender_name` | `message.from.emailAddress.name` | Use `from`, not `sender` |
| `sender_email` | `message.from.emailAddress.address` | Use `from`, not `sender` |
| `received_datetime` | `message.receivedDateTime` | ISO 8601 UTC string → datetime |
| `body_preview` | `message.bodyPreview` | First 255 chars, plain text, already stripped |
| `body_content` | `message.body.content` + strip_html() | Graph returns HTML; strip tags same as EWS |
| `has_attachments` | `message.hasAttachments` | Boolean |

**OData filter for date-based incremental fetch:**

```
GET /users/{mailbox}/mailFolders/inbox/messages
    ?$filter=receivedDateTime ge {since.strftime('%Y-%m-%dT%H:%M:%SZ')}
    &$orderby=receivedDateTime desc
    &$top={max_emails}
    &$select=id,subject,from,sender,receivedDateTime,bodyPreview,body,hasAttachments
```

**Critical constraint from official docs:** When using `$filter` and `$orderby` on the same
query, both properties must appear in both parameters in the same order, or the API returns
`InefficientFilter` error. `receivedDateTime` must appear in `$filter` before other properties,
and in `$orderby` in the same position.

**Pagination:** Graph defaults to 10 messages per page. Using `$top=100` eliminates the need
for pagination for InboxIQ's typical volumes. If more than 100 messages are needed in a run,
follow `@odata.nextLink` in the response. For InboxIQ's current scale (hourly runs), this is
unlikely to be required.

### Method 2: send_email

```python
def send_email(
    self,
    to_recipients: list[str] | str,
    subject: str,
    body_html: str,
    cc_recipients: list[str] | None = None,
    bcc_recipients: list[str] | None = None
) -> None:
    """
    Send an email from the configured USER_EMAIL account.

    Graph API endpoint used:
        POST /users/{Config.USER_EMAIL}/sendMail
        Content-Type: application/json

    For SendAs (SEND_FROM != USER_EMAIL):
        Set message.from.emailAddress.address = Config.get_send_from()
        Graph respects the `from` field when the app has Mail.Send permission

    Permissions required (application):
        Mail.Send

    Raises:
        GraphClientError on non-2xx response
    """
```

**Graph API request body:**

```json
{
  "message": {
    "subject": "string",
    "body": {
      "contentType": "HTML",
      "content": "<html>...</html>"
    },
    "toRecipients": [
      { "emailAddress": { "address": "user@domain.com" } }
    ],
    "ccRecipients": [
      { "emailAddress": { "address": "user@domain.com" } }
    ],
    "bccRecipients": [
      { "emailAddress": { "address": "user@domain.com" } }
    ],
    "from": {
      "emailAddress": {
        "address": "send-from@domain.com"
      }
    }
  },
  "saveToSentItems": true
}
```

Graph returns `202 Accepted` on success (no body). Any non-2xx response should raise
`GraphClientError`.

### Error Class

```python
class GraphClientError(Exception):
    """Raised when a Graph API operation fails."""
    pass
```

This replaces `EWSClientError` in main.py exception handling. The name changes but the
semantics are identical.

### Implementation Approach: requests Library (Not msgraph-sdk)

**Recommendation:** Use the `requests` library directly with Bearer token from MSAL, not
the `msgraph-sdk` package.

**Rationale:**
- `requests` is already a transitive dependency of `httpx` in requirements.txt, and is a
  well-understood standard library.
- `msgraph-sdk` uses `async/await` throughout (kiota-based). InboxIQ's entire codebase is
  synchronous. Introducing `asyncio.run()` wrappers would add complexity with no benefit.
- The two Graph API calls InboxIQ needs (list messages, send mail) are straightforward
  REST calls. The SDK abstraction layer adds installation overhead (~15 packages) without
  architectural benefit for this scope.
- Direct `requests` calls are easier to mock in tests (no SDK object graph to stub).
- MSAL's token caching continues to work identically — get token, pass as Bearer header.

**Token acquisition (no change to MSAL flow):**

```python
# auth.py change: scope switches from EWS to Graph
scopes = ["https://graph.microsoft.com/.default"]  # was: https://outlook.office365.com/.default

# auth.py change: return raw token, not OAuth2Credentials
def get_access_token(self) -> str:
    # Same MSAL acquire_token_for_client logic
    # Returns result["access_token"] directly
```

**HTTP call pattern:**

```python
class GraphClient:
    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, access_token: str):
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        })

    def _get(self, path: str, params: dict = None) -> dict:
        response = self._session.get(f"{self.BASE_URL}{path}", params=params)
        if not response.ok:
            raise GraphClientError(f"Graph API error {response.status_code}: {response.text}")
        return response.json()

    def _post(self, path: str, body: dict) -> None:
        response = self._session.post(f"{self.BASE_URL}{path}", json=body)
        if not response.ok:
            raise GraphClientError(f"Graph API error {response.status_code}: {response.text}")
```

---

## Integration Points

### 1. auth.py Integration

**What changes:**
- Class rename: `EWSAuthenticator` → `GraphAuthenticator`
- Scope: `"https://outlook.office365.com/.default"` → `"https://graph.microsoft.com/.default"`
- Return type of public method: `get_ews_credentials() → OAuth2Credentials` becomes
  `get_access_token() → str`
- Remove `from exchangelib import OAuth2Credentials, Identity` import
- Remove `get_ews_credentials()` method (or keep as deprecated wrapper if backward compat needed)

**What stays identical:**
- MSAL `ConfidentialClientApplication` setup
- `acquire_token_silent` + `acquire_token_for_client` pattern (no change)
- Token caching behavior
- `clear_cache()` method
- `AuthenticationError` exception class
- Config.CLIENT_ID, CLIENT_SECRET, TENANT_ID usage

**main.py call site change:**

```python
# Before
authenticator = EWSAuthenticator()
credentials = authenticator.get_ews_credentials()
ews_client = EWSClient(credentials)

# After
authenticator = GraphAuthenticator()
access_token = authenticator.get_access_token()
graph_client = GraphClient(access_token)
```

### 2. graph_client.py Integration

**Consumes:**
- `access_token: str` from `GraphAuthenticator.get_access_token()`
- `Config.USER_EMAIL` (sender account for `sendMail`)
- `Config.get_send_from()` (from address, may differ from USER_EMAIL)

**Produces:**
- `list[Email]` — consumed by `classifier.py`, `summarizer.py`, `extractor.py`
- `None` (send_email) — side effect only

**The `Email` dataclass stays in this file** (same as it was in `ews_client.py`). All
downstream consumers need only their import path updated, not their code.

### 3. main.py Integration

Four changes, each mechanical:

```python
# Line 1: import change
from .graph_client import GraphClient, GraphClientError  # was: from .ews_client import EWSClient, EWSClientError

# Line 2: import change
from .auth import GraphAuthenticator, AuthenticationError  # was: EWSAuthenticator

# Line 3: instantiation change (in main())
authenticator = GraphAuthenticator()
access_token = authenticator.get_access_token()
graph_client = GraphClient(access_token)

# Line 4: error handler rename
except GraphClientError as e:            # was: except EWSClientError as e:
    logger.error(f"Graph API error: {e}")

# Line 5: remove logging noise suppression for exchangelib
# Remove: logging.getLogger("exchangelib").setLevel(logging.WARNING)

# Line 6: banner text update (cosmetic)
logger.info("Email Summarizer Agent Starting (Graph API)")  # was: (EWS)
```

**All pipeline logic in main.py is untouched** — the classify → split → summarize →
format → send → update state sequence is identical.

### 4. config.py Integration

**Remove:**
- `EWS_SERVER` field (no longer used)

**No new required vars:** The Graph API base URL is hardcoded in `graph_client.py`.
The `.default` scope is hardcoded in `auth.py`.

**Optional new env var** (if mailbox scoping via Exchange RBAC is configured):
No change to config needed — the Graph API uses the same CLIENT_ID/CLIENT_SECRET/TENANT_ID
already present.

### 5. Test File Integration

**conftest.py:**

```python
# Before
from src.ews_client import Email

# After
from src.graph_client import Email
```

All fixture `Email()` constructor calls are identical — field names and types are unchanged.

**test_classifier.py, test_integration.py, test_integration_dual_digest.py, etc.:**
Any file containing `from src.ews_client import Email` needs the same one-line import change.

**test_ews_client.py** (if it exists): This becomes `test_graph_client.py` — full rewrite
to test Graph API calls using mocked `requests` responses.

### 6. Microsoft Entra App Registration

**Azure AD permission changes (admin action required, not code):**

| Current (EWS) | New (Graph API) | Action |
|---------------|-----------------|--------|
| `EWS.AccessAsApp` (application) | Remove | Revoke in Azure portal |
| — | `Mail.Read` (application) | Grant + admin consent |
| — | `Mail.Send` (application) | Grant + admin consent |

**Exchange RBAC scoping (optional but recommended for enterprise):**
To restrict the app to only the configured shared mailbox (security best practice):

```powershell
# Exchange Online PowerShell — scope app to specific mailbox
New-ServicePrincipal -AppId <CLIENT_ID> -ObjectId <SP_OBJECT_ID> -DisplayName "InboxIQ"

New-ManagementScope -Name "InboxIQ-Mailboxes" `
    -RecipientRestrictionFilter "PrimarySmtpAddress -eq 'messagingai@marsh.com'"

New-ManagementRoleAssignment `
    -App <SP_OBJECT_ID> `
    -Role "Application Mail.Read" `
    -CustomResourceScope "InboxIQ-Mailboxes"

New-ManagementRoleAssignment `
    -App <SP_OBJECT_ID> `
    -Role "Application Mail.Send" `
    -CustomResourceScope "InboxIQ-Mailboxes"

# IMPORTANT: Remove tenant-wide Mail.Read/Mail.Send consent from Azure AD
# The RBAC scope only works if the Azure AD grant is removed
```

Without this scoping, the app can read/send mail for any mailbox in the tenant. The scoping
is a post-migration hardening step, not a prerequisite for the migration to function.

---

## Build Order

Dependencies drive this order. Each step is independently testable before proceeding.

### Step 1: auth.py — Scope and Return Type Change (1-2 hours)

**Why first:** All other work depends on a working token. Validates Azure AD permissions.
**Risk:** LOW — same MSAL flow, one string change for scope.

Changes:
- Add `GraphAuthenticator` class (or rename `EWSAuthenticator`)
- Change scope to `"https://graph.microsoft.com/.default"`
- Add `get_access_token() -> str` method that returns raw token
- Keep `AuthenticationError` identical

Test: Manually run `GraphAuthenticator().get_access_token()` and confirm a JWT is returned.

### Step 2: graph_client.py — Core Implementation (4-6 hours)

**Why second:** The main deliverable. Depends on Step 1 for a working token.
**Risk:** MEDIUM — new API surface, pagination edge cases, HTML stripping.

Changes:
- Create `src/graph_client.py` from scratch
- Copy `Email` dataclass from `ews_client.py` (no field changes)
- Implement `get_shared_mailbox_emails()` using requests + OData filter
- Implement `send_email()` using requests + JSON body
- Define `GraphClientError`

Test with `pytest` via:
- Unit tests using `unittest.mock.patch` on `requests.Session.get` / `.post`
- One manual smoke test against the live shared mailbox with `--dry-run`

### Step 3: config.py — Remove EWS_SERVER (15 minutes)

**Why third:** Cleanup. Remove the unused variable.
**Risk:** VERY LOW — pure deletion.

Changes:
- Remove `EWS_SERVER` field
- Update `validate()` docstring if it mentions EWS

### Step 4: main.py — Import and Instantiation Swap (30 minutes)

**Why fourth:** Depends on Steps 1 and 2. The mechanical wiring.
**Risk:** LOW — purely mechanical changes, no logic changes.

Changes:
- Swap 2 import lines (EWSAuthenticator → GraphAuthenticator, EWSClient → GraphClient)
- Swap 1 instantiation block (credentials → access_token)
- Rename 1 exception handler (EWSClientError → GraphClientError)
- Remove exchangelib logger suppression
- Update banner text

### Step 5: Test File Import Updates (30 minutes)

**Why fifth:** After graph_client.py exists, update all test import paths.
**Risk:** VERY LOW — one-line change per file.

Changes:
- `conftest.py`: update `from src.ews_client import Email`
- Any other test file importing from `src.ews_client`
- Run full test suite: `pytest tests/` — all existing tests must pass

### Step 6: New graph_client Tests (2-4 hours)

**Why last:** Test the new module with mocked HTTP responses.
**Risk:** LOW — tests do not affect runtime behavior.

New file: `tests/test_graph_client.py`

---

## Test Strategy

### Principle: Verify Migration Correctness, Not Just Coverage

The migration is correct when existing tests pass unchanged (modulo import paths) AND
new Graph API tests exercise the new HTTP behavior.

### Layer 1: Existing Tests Must Pass Unmodified (except imports)

All tests in `tests/` currently test behavior downstream of the client (classifier, summarizer,
extractor, state, etc.). These tests use the `Email` dataclass directly via fixtures. After the
import path is updated in `conftest.py`, all these tests must pass without any other changes.

**This is the primary regression guard.** If any existing test fails after the import
path change, something has broken in the `Email` dataclass contract.

Pass criteria: `pytest tests/ -v` with all existing tests green.

### Layer 2: GraphClient Unit Tests (New)

File: `tests/test_graph_client.py`

Test `get_shared_mailbox_emails`:
- Mock `requests.Session.get` to return a Graph-format JSON response
- Verify `Email` fields are populated correctly from Graph response fields
- Verify OData filter includes correct `receivedDateTime` format (ISO 8601 UTC, `Z` suffix)
- Verify `$top` parameter is sent
- Verify HTML stripping works on `body.content`
- Verify `since=None` defaults to today midnight UTC
- Verify `GraphClientError` raised on non-200 response

Test `send_email`:
- Mock `requests.Session.post` to return 202
- Verify request body structure (toRecipients, ccRecipients, bccRecipients, from, body.contentType=HTML)
- Verify `from` field uses `Config.get_send_from()` not `Config.USER_EMAIL` when different
- Verify `GraphClientError` raised on non-202 response
- Verify empty recipient lists are filtered out

Test auth:
- Mock `msal.ConfidentialClientApplication.acquire_token_for_client`
- Verify scope is `"https://graph.microsoft.com/.default"`
- Verify `AuthenticationError` on missing access_token in result

### Layer 3: Migration Verification (Manual + Dry-Run)

**Before decommissioning EWS:**

1. Run both old and new clients against the same mailbox and compare output:
   ```python
   # Verification script (not committed, run once)
   ews_emails = ews_client.get_shared_mailbox_emails(mailbox, since=since)
   graph_emails = graph_client.get_shared_mailbox_emails(mailbox, since=since)
   assert len(ews_emails) == len(graph_emails), "Email count mismatch"
   for e, g in zip(ews_emails, graph_emails):
       assert e.subject == g.subject
       assert e.sender_email == g.sender_email
   ```

2. Run `python -m src.main --dry-run` and verify the digest HTML looks correct.

3. Run `python -m src.main --full --dry-run` to confirm full-fetch mode works.

4. Send one live email (remove --dry-run) and verify delivery.

### Layer 4: Error Case Verification

- Verify behavior when mailbox is empty (no emails since `since`): should return `[]`
- Verify behavior when access token is expired: MSAL cache should auto-refresh
- Verify behavior when Graph returns 429 (throttling): GraphClientError with message
- Verify behavior when `since` is far in the past and >100 emails exist: returns first 100

### Confidence in Test Coverage

The existing test suite is structured around the `Email` dataclass, not around EWS internals.
This means the suite tests the semantics of what the pipeline expects from the client (correct
fields, correct types, correct data), and those tests remain valid without modification. The
migration risk is concentrated in the mapping logic inside `graph_client.py`, which is covered
by the new Layer 2 tests.

---

## Sources

- [Microsoft Graph API: List messages](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0) — Endpoint, OData filter/orderby constraints, permissions. Confidence: HIGH (official docs, updated 2025-07-23).

- [Microsoft Graph API: sendMail](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0) — Request body format, from/cc/bcc fields, 202 response. Confidence: HIGH (official docs, updated 2025-07-23).

- [Microsoft Graph API: message resource](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0) — Field names, types, and formats for all message properties. Confidence: HIGH (official docs, updated 2025-10-24).

- [Exchange RBAC for Applications](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac) — Mailbox scoping for app-only permissions, replaces Application Access Policies. Confidence: HIGH (official Exchange Online docs, updated 2025-11-25).

- [Build Python apps with Microsoft Graph (app-only)](https://learn.microsoft.com/en-us/graph/tutorials/python-app-only) — App-only auth pattern, azure-identity vs MSAL vs requests. Confidence: HIGH (official tutorial, updated 2025-06-03).

- [InboxIQ source code: src/ews_client.py](C:\giveitashot\src\ews_client.py) — Current EWSClient interface, Email dataclass, field semantics.

- [InboxIQ source code: src/auth.py](C:\giveitashot\src\auth.py) — Current MSAL flow, scope, credential return type.

- [InboxIQ source code: src/main.py](C:\giveitashot\src\main.py) — Orchestration layer, call sites that must change.
