# Phase 7: Graph Client - Research

**Researched:** 2026-03-13
**Domain:** Microsoft Graph REST API (Mail read + send), Python `requests`, retry/throttling patterns, unit test mocking
**Confidence:** HIGH

---

## Summary

Phase 7 replaces `ews_client.py` with `graph_client.py` using direct REST calls via the `requests` library. The codebase already has `httpx>=0.27.0` but the prior decision mandates `requests` + MSAL (no new dependencies beyond adding `requests`). The Graph v1.0 mail endpoints are well-documented and stable. All decisions made in CONTEXT.md are supported by verified official documentation.

The read path uses `GET /users/{mailbox}/messages` with an OData `$filter` on `receivedDateTime`, `$select` for field projection, `$top` for page sizing, and `@odata.nextLink` for pagination. The send path uses `POST /users/{sender}/sendMail` with a JSON body — `from`, `toRecipients`, `ccRecipients`, `bccRecipients`, `saveToSentItems: true`, and `body.contentType: "HTML"`. Both paths require a Bearer token from `GraphAuthenticator.get_access_token()` which is already implemented in Phase 6.

**Primary recommendation:** Use the `requests` library for all Graph HTTP calls with a single `_make_request()` helper that attaches the Bearer token, handles 429/5xx retries (up to 3 attempts, `Retry-After` header respected), and raises `GraphClientError` with status code + Graph error detail on failure.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | 2.32.5 | HTTP calls to Graph REST API | Decision locked — zero new async deps, simple mocking |
| `msal` | >=1.28.0 | Token acquisition (already present) | Phase 6 deliverable — `get_access_token()` ready |
| `python-dotenv` | >=1.0.0 | Config loading (already present) | Already in requirements.txt |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `re` | stdlib | HTML tag stripping for body_content | Same pattern as current `_strip_html()` in ews_client.py |
| `html` | stdlib | HTML entity decoding | Same pattern as current ews_client.py |
| `datetime` | stdlib | ISO 8601 parsing and UTC normalization | receivedDateTime is always UTC from Graph |
| `unittest.mock` | stdlib | Mocking `requests.Session.get/post` in tests | No extra test dependencies needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `requests` | `httpx` (already in requirements) | Decision locked: use `requests`. httpx is async-first; `requests` is simpler for sync daemon code |
| Manual retry loop | `requests.adapters.HTTPAdapter` + `urllib3.util.retry.Retry` | urllib3 Retry does NOT respect Graph's `Retry-After` header for 429 by default; manual loop gives full control |
| `unittest.mock.patch` | `responses` library | `unittest.mock` is stdlib; no new test dep needed |

**Installation:**
```bash
pip install requests>=2.32.5
```

Add to `requirements.txt`:
```
requests>=2.32.5
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── graph_client.py    # New file: Email dataclass, GraphClient, GraphClientError
├── auth.py            # Phase 6 deliverable — GraphAuthenticator.get_access_token()
├── config.py          # Config.SHARED_MAILBOX, Config.SENDER_EMAIL, Config.get_send_from()
└── ...                # All other files unchanged in Phase 7
tests/
└── test_graph_client.py  # New: fully mocked unit test suite
```

### Pattern 1: Single HTTP Helper with Retry

**What:** A private `_make_request()` method that wraps all Graph HTTP calls, attaches the Bearer token, handles token refresh mid-pagination, and implements the 3-attempt retry loop for 429 + transient 5xx.

**When to use:** Every Graph API call — both GET (read) and POST (send).

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/graph/throttling
import time
import requests

RETRY_STATUS_CODES = {429, 502, 503, 504}
MAX_RETRIES = 3
BASE_GRAPH_URL = "https://graph.microsoft.com/v1.0"

def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
    """
    Make a Graph API request with retry on throttling/transient errors.
    Refreshes token on 401 and retries the failed page.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        token = self._authenticator.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        response = self._session.request(method, url, headers=headers, **kwargs)

        if response.status_code == 401 and attempt < MAX_RETRIES:
            # Token may have expired mid-pagination — re-auth is silent via MSAL
            continue

        if response.status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES:
            retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
            logger.info(
                f"Throttled by Graph API, retrying in {retry_after}s "
                f"(attempt {attempt}/{MAX_RETRIES})"
            )
            time.sleep(retry_after)
            continue

        return response

    raise GraphClientError(
        f"Request failed after {MAX_RETRIES} attempts: {url}"
    )
```

### Pattern 2: Read Path — Filter, Select, Paginate

**What:** `GET /users/{mailbox}/messages` with OData `$filter`, `$select`, `$top`, then follow `@odata.nextLink` until exhausted.

**When to use:** `get_shared_mailbox_emails()`.

**Critical constraint from official docs:** When using `$filter` and `$orderby` together, properties in `$orderby` MUST also appear in `$filter` and in the same order. Violating this returns `InefficientFilter` error. Since ordering by `receivedDateTime` desc, the filter must also include `receivedDateTime`.

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0
def get_shared_mailbox_emails(
    self,
    shared_mailbox: str,
    since: datetime | None = None,
    max_emails: int = 100,
) -> list[Email]:
    if since is None:
        now = datetime.now(timezone.utc)
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Format: Graph requires UTC ISO 8601, no quotes in $filter
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "$filter": f"receivedDateTime ge {since_str}",
        "$select": "id,subject,sender,from,body,receivedDateTime,hasAttachments,internetMessageId",
        "$orderby": "receivedDateTime desc",
        "$top": min(max_emails, 100),  # Graph max $top is 1000; 100 is a safe default
    }

    url = f"{BASE_GRAPH_URL}/users/{shared_mailbox}/messages"
    all_emails: list[Email] = []

    while url and len(all_emails) < max_emails:
        response = self._make_request("GET", url, params=params if "messages" in url else None)
        if not response.ok:
            self._raise_graph_error("retrieve emails", response)

        data = response.json()
        for msg in data.get("value", []):
            try:
                email = self._parse_message(msg)
                all_emails.append(email)
            except Exception as e:
                logger.warning(f"Failed to parse email {msg.get('id', '?')}: {e}")

        url = data.get("@odata.nextLink")  # None when last page
        params = None  # nextLink already contains all params

    return all_emails[:max_emails]
```

### Pattern 3: Send Path — sendMail with From/BCC

**What:** `POST /users/{sender}/sendMail` with JSON body. `from` property enables SendAs for custom From address.

**When to use:** `send_email()`.

**Important:** The `sender` authenticating and the user in the URL path (`{sender}`) should be `Config.SENDER_EMAIL` (the actual mailbox used to send). The `from` property is set only when `Config.get_send_from()` differs from `Config.SENDER_EMAIL`, enabling SendAs. For app-only tokens with `Mail.Send`, the app can send from any mailbox in the org — the Exchange SendAs permission controls appearance.

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0
# Source: https://learn.microsoft.com/en-us/graph/outlook-send-mail-from-other-user
def send_email(
    self,
    to_recipients: list[str] | str,
    subject: str,
    body_html: str,
    cc_recipients: list[str] | None = None,
    bcc_recipients: list[str] | None = None,
) -> None:
    if isinstance(to_recipients, str):
        to_recipients = [to_recipients]
    to_recipients = [r for r in to_recipients if r]
    cc_recipients = [r for r in (cc_recipients or []) if r]
    bcc_recipients = [r for r in (bcc_recipients or []) if r]

    if not to_recipients:
        raise GraphClientError("At least one TO recipient is required")

    def _make_recipient(addr: str) -> dict:
        return {"emailAddress": {"address": addr}}

    message: dict = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body_html},
        "toRecipients": [_make_recipient(r) for r in to_recipients],
    }
    if cc_recipients:
        message["ccRecipients"] = [_make_recipient(r) for r in cc_recipients]
    if bcc_recipients:
        message["bccRecipients"] = [_make_recipient(r) for r in bcc_recipients]

    send_from = Config.get_send_from()
    if send_from and send_from != Config.SENDER_EMAIL:
        message["from"] = _make_recipient(send_from)

    payload = {"message": message, "saveToSentItems": True}
    url = f"{BASE_GRAPH_URL}/users/{Config.SENDER_EMAIL}/sendMail"
    response = self._make_request("POST", url, json=payload)

    if not response.ok:
        self._raise_graph_error("send email", response)
    # 202 Accepted — no response body
```

### Pattern 4: Graph JSON to Email Dataclass Mapping

**What:** Parse Graph message JSON into the `Email` dataclass, preserving the exact field contract.

**Key mappings (verified against Graph v1.0 message resource):**
```python
# Source: https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0
def _parse_message(self, msg: dict) -> Email:
    # Email.id — use internetMessageId for stable cross-folder identity
    # Graph's 'id' changes on folder move; internetMessageId (RFC2822) is stable
    email_id = msg.get("internetMessageId") or msg.get("id", "")

    subject = msg.get("subject") or "(No Subject)"

    # sender field: {"emailAddress": {"name": "...", "address": "..."}}
    sender = msg.get("sender") or msg.get("from") or {}
    sender_addr = sender.get("emailAddress", {})
    sender_name = sender_addr.get("name") or "Unknown"
    sender_email = sender_addr.get("address") or "unknown@unknown.com"

    # body: {"contentType": "html", "content": "<html>..."}
    # Graph returns HTML by default (official docs confirmed)
    # Use _strip_html() to preserve what classifier/summarizer expect (plain text)
    body_obj = msg.get("body") or {}
    raw_body = body_obj.get("content", "")
    body_content = self._strip_html(raw_body)

    # body_preview: first 200 chars of stripped content (NOT Graph's bodyPreview)
    body_preview = body_content[:200]

    # receivedDateTime: ISO 8601 UTC string e.g. "2026-03-13T10:30:00Z"
    received_str = msg.get("receivedDateTime", "")
    received_datetime = self._parse_datetime(received_str)

    has_attachments = bool(msg.get("hasAttachments", False))

    return Email(
        id=email_id,
        subject=subject,
        sender_name=sender_name,
        sender_email=sender_email,
        received_datetime=received_datetime,
        body_preview=body_preview,
        body_content=body_content,
        has_attachments=has_attachments,
    )

def _parse_datetime(self, dt_str: str) -> datetime:
    """Parse Graph ISO 8601 UTC string to timezone-aware datetime."""
    if not dt_str:
        return datetime.now(timezone.utc)
    # Graph always returns UTC: "2026-03-13T10:30:00Z"
    try:
        # Python 3.11+ fromisoformat handles 'Z'; use replace for 3.9/3.10 compat
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        logger.warning(f"Could not parse datetime: {dt_str!r}")
        return datetime.now(timezone.utc)
```

### Pattern 5: Error Raising Helper

**What:** Extract Graph error details from JSON response for production-useful error messages.

```python
def _raise_graph_error(self, operation: str, response: requests.Response) -> None:
    """Raise GraphClientError with HTTP status and Graph error details."""
    try:
        err = response.json().get("error", {})
        graph_msg = err.get("message", response.text)
        graph_code = err.get("code", "")
        detail = f"{graph_code} - {graph_msg}" if graph_code else graph_msg
    except Exception:
        detail = response.text
    raise GraphClientError(
        f"Failed to {operation}: {response.status_code} {response.reason} - {detail}"
    )
```

### Pattern 6: Unit Test with Mocked `requests.Session`

**What:** Patch `requests.Session` at the module level, configure mock responses for GET/POST, verify JSON parsing without live credentials.

```python
# Source: https://docs.python.org/3/library/unittest.mock.html
from unittest.mock import MagicMock, patch
import pytest

SAMPLE_GRAPH_RESPONSE = {
    "value": [
        {
            "id": "AAMkABC123",
            "internetMessageId": "<abc123@msg.microsoft.com>",
            "subject": "Test Email",
            "sender": {
                "emailAddress": {
                    "name": "Test Sender",
                    "address": "sender@example.com"
                }
            },
            "body": {
                "contentType": "html",
                "content": "<html><body><p>Hello world</p></body></html>"
            },
            "receivedDateTime": "2026-03-13T10:00:00Z",
            "hasAttachments": False,
        }
    ],
    "@odata.nextLink": None  # omit to test single-page
}

@pytest.fixture
def mock_authenticator():
    auth = MagicMock()
    auth.get_access_token.return_value = "fake-token-xyz"
    return auth

@pytest.fixture
def graph_client(mock_authenticator):
    from src.graph_client import GraphClient
    return GraphClient(mock_authenticator)

def test_get_shared_mailbox_emails_parses_fields(graph_client):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_GRAPH_RESPONSE

    with patch.object(graph_client._session, "request", return_value=mock_response):
        from datetime import datetime, timezone
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)
        emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

    assert len(emails) == 1
    assert emails[0].subject == "Test Email"
    assert emails[0].sender_name == "Test Sender"
    assert emails[0].id == "<abc123@msg.microsoft.com>"
    assert emails[0].body_content == "Hello world"
    assert emails[0].received_datetime.tzinfo is not None
```

### Anti-Patterns to Avoid

- **Using `$skip` for manual pagination:** Official docs explicitly warn against extracting `$skip` from `@odata.nextLink`. Always follow the full nextLink URL as-is.
- **Using `$filter` + `$orderby` on different property sets:** Must satisfy the constraint that `$orderby` properties appear in `$filter` first. The safest approach: `$filter=receivedDateTime ge {since}` + `$orderby=receivedDateTime desc`.
- **Setting `Prefer: outlook.body-content-type="text"` on read:** This gives Graph's server-side plain-text which loses some formatting. Better to fetch HTML and run our own `_strip_html()` — same code already validated in EWS path.
- **Calling `get_access_token()` per-request in the retry loop:** Call it once per retry attempt (401 triggers re-auth); do not call on every page.
- **Using Graph's `bodyPreview` field (first 255 chars):** Decision locked — use first 200 chars of `body_content` instead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry-After parsing | Custom header parser | `int(response.headers.get("Retry-After", default))` | Graph returns integer seconds (not HTTP-date) per official docs |
| OData datetime format | Custom formatter | `since.strftime("%Y-%m-%dT%H:%M:%SZ")` | Graph requires UTC ISO 8601 without quotes in $filter |
| Pagination | `$skip` parameter | Follow `@odata.nextLink` URL directly | Official docs warn $skip in nextLink is opaque implementation detail |
| JSON recipient list | Custom class | Dict comprehension `{"emailAddress": {"address": addr}}` | Graph's expected format is simple nested dict |
| HTML stripping | New regex | Copy `_strip_html()` from `ews_client.py` verbatim | Already tested, same output as EWS path |
| Token management | Manual cache | `GraphAuthenticator.get_access_token()` (Phase 6) | MSAL handles caching internally since v1.23+ |

**Key insight:** Graph's JSON responses are straightforward nested dicts. The complexity is in the retry/throttle loop and OData filter syntax — those two areas justify careful implementation; everything else is mechanical mapping.

---

## Common Pitfalls

### Pitfall 1: $filter + $orderby Property Mismatch

**What goes wrong:** `InefficientFilter` error from Graph when `$orderby=receivedDateTime desc` is used without `receivedDateTime` in `$filter`.
**Why it happens:** Graph Exchange backend requires filter and sort properties to align for query optimization.
**How to avoid:** Always include `receivedDateTime ge {since}` in `$filter` when ordering by `receivedDateTime`.
**Warning signs:** HTTP 400 response with `InefficientFilter` error code.

### Pitfall 2: Naive datetime from Graph

**What goes wrong:** `received_datetime` is timezone-naive if `datetime.fromisoformat()` on Python 3.9/3.10 is called without handling the `Z` suffix.
**Why it happens:** Python 3.10 and earlier do not support `Z` as UTC in `fromisoformat()`.
**How to avoid:** Use `.replace("Z", "+00:00")` before `fromisoformat()`.
**Warning signs:** `datetime.tzinfo is None` assertions fail in tests.

### Pitfall 3: nextLink Parameters Duplication

**What goes wrong:** Passing `params=` dict on the second and subsequent pages while also following `@odata.nextLink` that already contains all parameters — causes duplicated/conflicting query parameters.
**Why it happens:** Developer forgets that `@odata.nextLink` is a complete URL.
**How to avoid:** Pass `params=None` (or omit it) when the URL is a nextLink. Pattern: set `params = None` after using the first URL.
**Warning signs:** Graph returns 400 or unexpected results on page 2+.

### Pitfall 4: sendMail Returns 202, Not 200

**What goes wrong:** Code checks `response.status_code == 200` for success.
**Why it happens:** Most REST APIs use 200; Graph sendMail uses 202 Accepted.
**How to avoid:** Use `response.ok` (True for 2xx) or check `response.status_code == 202`.
**Warning signs:** `GraphClientError` raised even though email is actually sent.

### Pitfall 5: Graph `id` Changes on Folder Move

**What goes wrong:** Using Graph's internal `id` for `Email.id` — it changes when a message is moved between folders.
**Why it happens:** Graph's `id` is a store-specific entry ID, not a permanent message identifier.
**How to avoid:** Use `internetMessageId` (RFC2822 Message-ID header) for `Email.id`. It is stable across folder moves. Fall back to `id` only if `internetMessageId` is absent.
**Warning signs:** Deduplication or tracing failures in downstream consumers.

### Pitfall 6: Retry Loop Swallows Final Error

**What goes wrong:** After 3 attempts, loop ends silently without raising.
**Why it happens:** Missing `raise` after the loop exits.
**How to avoid:** Always raise `GraphClientError` after the retry loop is exhausted.

### Pitfall 7: `requests.Session` Not Used

**What goes wrong:** Each request creates a new TCP connection; also makes mocking harder (need to patch `requests.get` globally).
**Why it happens:** Convenience of `requests.get()` top-level functions.
**How to avoid:** Instantiate `requests.Session()` in `__init__` and use `self._session.request()`. This enables clean mock patching via `patch.object(client._session, "request", ...)`.

---

## Code Examples

### Complete $select Field List for Read

```python
# Source: https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0
# All fields needed to populate Email dataclass
SELECT_FIELDS = (
    "id,"
    "internetMessageId,"
    "subject,"
    "sender,"
    "from,"
    "body,"
    "receivedDateTime,"
    "hasAttachments"
)
# Note: bodyPreview is NOT selected — we compute it from body_content[:200]
```

### OData Filter Construction

```python
# Source: https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0
# receivedDateTime values NOT enclosed in quotes in OData $filter expressions
since_utc = since.astimezone(timezone.utc)
filter_str = f"receivedDateTime ge {since_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
# Correct: receivedDateTime ge 2026-03-13T00:00:00Z
# Wrong:   receivedDateTime ge '2026-03-13T00:00:00Z'  ← quoted, will fail
```

### Retry Logic with Retry-After

```python
# Source: https://learn.microsoft.com/en-us/graph/throttling
RETRY_STATUSES = {429, 502, 503, 504}

for attempt in range(1, MAX_RETRIES + 1):
    response = self._session.request(method, url, headers=headers, **kwargs)
    if response.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
        # Retry-After contains integer seconds per Graph documentation
        retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
        logger.info(
            f"Throttled by Graph API, retrying in {retry_after}s "
            f"(attempt {attempt}/{MAX_RETRIES})"
        )
        time.sleep(retry_after)
        continue
    return response
```

### sendMail JSON Body Structure

```python
# Source: https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0
payload = {
    "message": {
        "subject": "Daily Digest - messagingai@marsh.com",
        "body": {
            "contentType": "HTML",       # capital HTML — Graph is case-insensitive but this is canonical
            "content": "<html>...</html>"
        },
        "toRecipients": [
            {"emailAddress": {"address": "user@example.com"}}
        ],
        "ccRecipients": [
            {"emailAddress": {"address": "cc@example.com"}}
        ],
        "bccRecipients": [
            {"emailAddress": {"address": "bcc@example.com"}}
        ],
        "from": {
            "emailAddress": {"address": "messagingai@marsh.com"}
        }
        # sender property NOT set — Graph sets it automatically from the URL path mailbox
    },
    "saveToSentItems": True   # boolean, not string
}
# POST to /users/{Config.SENDER_EMAIL}/sendMail
# Success: 202 Accepted, empty body
```

### Mocking Pattern for Pagination Test

```python
# Two-page response to test @odata.nextLink following
page1 = {
    "value": [build_msg("msg1")],
    "@odata.nextLink": "https://graph.microsoft.com/v1.0/users/mb/messages?$skiptoken=xyz"
}
page2 = {
    "value": [build_msg("msg2")],
    # no @odata.nextLink = last page
}

mock_response_1 = MagicMock()
mock_response_1.ok = True
mock_response_1.json.return_value = page1

mock_response_2 = MagicMock()
mock_response_2.ok = True
mock_response_2.json.return_value = page2

with patch.object(client._session, "request", side_effect=[mock_response_1, mock_response_2]):
    emails = client.get_shared_mailbox_emails("mb@example.com", since=since)

assert len(emails) == 2
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| EWS + exchangelib + impersonation | Graph REST API v1.0 + app-only permissions | v2.0 migration | Simpler auth, no impersonation requirement |
| `acquire_token_silent` + `acquire_token_for_client` | `acquire_token_for_client` only | MSAL 1.23+ | Redundant call removed (Phase 6 decision) |
| Graph SDK (msgraph-sdk) | Direct `requests` calls | Architecture decision | SDK is async-only, has daemon bug; direct HTTP is explicit and testable |
| Graph `$skip` pagination | Follow `@odata.nextLink` | Current Graph best practice | `$skip` value in nextLink is opaque; direct follow is documented correct approach |

**Deprecated/outdated:**
- `exchangelib` OAuth2Credentials for Graph: Phase 6 already uses MSAL Graph scope — the EWS shim will be removed in Phase 8
- EWS Server URL (`EWS_SERVER` config): deprecated, kept for backward compat until Phase 8

---

## Body Content Decision (Claude's Discretion)

The CONTEXT.md marks `body_content` source as Claude's discretion. Research finding:

**Recommendation: Fetch HTML from Graph, strip locally using `_strip_html()` copied from ews_client.py.**

Rationale:
1. Graph's `Prefer: outlook.body-content-type="text"` header returns server-side plain text. This uses different line-break and whitespace normalization than our current approach.
2. Our existing `_strip_html()` is: strip tags → decode HTML entities → normalize whitespace. This is already validated against real email content by the existing classifier and summarizer tests.
3. Fetching HTML and stripping locally preserves exact behavior continuity — the downstream consumers (classifier, summarizer) get the same format they always have.
4. Graph's default response is HTML (official docs confirmed). No header needed.

## Email.id Decision (Claude's Discretion)

**Recommendation: Use `internetMessageId` as primary, fall back to Graph `id`.**

Rationale:
- `internetMessageId` is the RFC2822 Message-ID header — stable across folder moves, cross-system traceable.
- Graph's internal `id` changes when a message moves between folders.
- Current EWS `id` was EWS-specific and not used for deduplication by downstream consumers (they use `mc_id` from subject for that).
- `internetMessageId` values look like `<abc123@msg.microsoft.com>` — distinctive for logging/tracing.

---

## Open Questions

1. **ApplicationAccessPolicy vs Exchange RBAC scope**
   - What we know: `Mail.Read` (application) grants access to ALL mailboxes in the tenant. Marsh McLennan IT may require ApplicationAccessPolicy to restrict the app to only `messagingai@marsh.com`.
   - What's unclear: Whether IT has applied this policy restriction, and if so, what errors occur without it.
   - Recommendation: Code works the same either way (no client-side change needed). Document for IT admin. Return 403 if policy blocks access.

2. **`Mail.Send` application permission and SendAs**
   - What we know: With `Mail.Send` application permission, the app can POST to `/users/{sender}/sendMail` to send from that mailbox. Setting the `from` property to a different address requires Exchange "Send As" permission granted at the mailbox level.
   - What's unclear: Whether the Marsh McLennan Azure app registration currently has `Mail.Send` granted with admin consent (separate from `Mail.Read`).
   - Recommendation: Code the `from` property correctly now; if IT hasn't granted `Mail.Send` yet, integration testing will surface a `403 ErrorSendAsDenied`.

3. **Graph `bodyPreview` field length**
   - What we know: Graph's `bodyPreview` is "the first 255 characters" (official docs). Decision is to NOT use it — use `body_content[:200]` instead.
   - Recommendation: Confirmed — do not select `bodyPreview` in `$select`.

---

## Sources

### Primary (HIGH confidence)

- [Graph v1.0 List messages API](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0) — endpoint, permissions, $filter/$orderby constraints, default page size (10), $top max (1000), @odata.nextLink behavior, body content type header
- [Graph v1.0 message resource type](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0) — all field names, types, JSON structure: id, internetMessageId, subject, sender, from, body, bodyPreview (255 chars), receivedDateTime, hasAttachments
- [Graph v1.0 sendMail API](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0) — endpoint, permissions (Mail.Send application), request body structure, saveToSentItems, 202 response
- [Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling) — 429 status, Retry-After header format (integer seconds), best practices, exponential backoff fallback
- [Send mail from another user](https://learn.microsoft.com/en-us/graph/outlook-send-mail-from-other-user) — `from` property usage, Send As vs Send On Behalf, ErrorSendAsDenied error, application token behavior
- [Read messages with body format control](https://learn.microsoft.com/en-us/graph/outlook-create-send-messages#reading-messages-with-control-over-the-body-format-returned) — Prefer header, HTML default, text format option, Preference-Applied response header
- [PyPI requests 2.32.5](https://pypi.org/project/requests/) — current stable version

### Secondary (MEDIUM confidence)

- [Python unittest.mock docs](https://docs.python.org/3/library/unittest.mock.html) — patch, MagicMock, side_effect for multi-call mocking
- WebSearch verified: Retry-After header contains integer seconds for Graph 429 responses

### Tertiary (LOW confidence)

- Community observations: `internetMessageId` can theoretically change in draft→sent transition on Outlook Desktop, but this does not apply to received messages read from a shared mailbox (server-side only).

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — requests 2.32.5 confirmed on PyPI; MSAL already implemented in Phase 6
- Architecture: HIGH — Graph v1.0 API documented, all endpoints verified with official docs
- Field mappings: HIGH — message resource type properties confirmed with official schema
- Retry patterns: HIGH — throttling guidance is explicit on Retry-After integer seconds
- SendAs/from property: HIGH — official how-to guide with exact JSON examples verified
- Pagination: HIGH — @odata.nextLink behavior explicitly documented, $skip warning documented
- Body content decision: MEDIUM — HTML strip approach matches EWS behavior; no live test yet
- Email.id decision: MEDIUM — internetMessageId stability documented for received messages

**Research date:** 2026-03-13
**Valid until:** 2026-06-13 (90 days — Graph v1.0 is stable API)
