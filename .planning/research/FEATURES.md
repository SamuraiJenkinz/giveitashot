# Features Research: Graph API Migration

**Domain:** Microsoft Graph API vs EWS — Email Read/Send Operations
**Project:** InboxIQ — EWS to Graph API swap (no new features)
**Researched:** 2026-03-12
**Overall Confidence:** HIGH (all findings sourced from official Microsoft documentation)

---

## EWS to Graph Operation Mapping

This table maps every current EWS operation in InboxIQ (`ews_client.py`) to its exact Graph API equivalent.

| EWS Operation | EWS Method (exchangelib) | Graph API Equivalent | HTTP Method | Graph URL Pattern |
|---|---|---|---|---|
| Read inbox emails | `inbox.filter(datetime_received__gte=since)` | List messages | GET | `/users/{mailbox}/mailFolders/inbox/messages?$filter=receivedDateTime ge {datetime}` |
| Order by newest first | `.order_by('-datetime_received')` | OData orderby | GET param | `&$orderby=receivedDateTime DESC` |
| Limit results | `[:max_emails]` (slice) | OData top | GET param | `&$top=100` |
| Get email body (HTML) | `item.body` | body property | `$select=body` | `body.content` string, `body.contentType` = "html" |
| Get sender | `item.sender.name`, `item.sender.email_address` | sender property | `$select=sender` | `sender.emailAddress.name`, `sender.emailAddress.address` |
| Get received time | `item.datetime_received` | receivedDateTime | `$select=receivedDateTime` | ISO 8601 UTC string e.g. `2026-03-12T10:00:00Z` |
| Get subject | `item.subject` | subject property | `$select=subject` | String field |
| Check attachments | `item.has_attachments` | hasAttachments | `$select=hasAttachments` | Boolean field |
| Get message ID | `item.id` | id property | (returned by default) | Opaque string (different format than EWS IDs) |
| Send email | `message.send_and_save()` | sendMail | POST | `/users/{sender}/sendMail` |
| Send with HTML body | `body=HTMLBody(html)` in Message | body.contentType=HTML | POST body | `"body": {"contentType": "HTML", "content": "..."}` |
| Send with TO recipients | `to_recipients=[Mailbox(...)]` | toRecipients | POST body | `[{"emailAddress": {"address": "..."}}]` |
| Send with CC recipients | `cc_recipients=[Mailbox(...)]` | ccRecipients | POST body | `[{"emailAddress": {"address": "..."}}]` |
| Send with BCC recipients | `bcc_recipients=[Mailbox(...)]` | bccRecipients | POST body | `[{"emailAddress": {"address": "..."}}]` |
| SendAs (custom From) | `author=Mailbox(email_address=send_from)` | from property | POST body | `"from": {"emailAddress": {"address": "send_from@..."}}` |
| App-only auth | MSAL client credentials + EWS SOAP | MSAL client credentials + REST bearer | HTTP header | `Authorization: Bearer {token}` |
| Auth scope | `https://outlook.office365.com/.default` | `https://graph.microsoft.com/.default` | MSAL scopes | Single string change |
| Impersonation / mailbox targeting | `access_type=IMPERSONATION` on Account | No impersonation — address user directly | URL path | `/users/{mailbox_email}/...` |

**Official source:** [EWS to Graph API Mappings](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-api-mapping) — HIGH confidence

---

## Table Stakes (Must Preserve)

Features that must work identically after migration. Missing or broken = migration failed.

| Feature | Current EWS Behavior | Graph API Equivalent | Confidence |
|---|---|---|---|
| Read shared mailbox inbox | `IMPERSONATION` access to `Config.SHARED_MAILBOX` | `GET /users/{SHARED_MAILBOX}/mailFolders/inbox/messages` | HIGH |
| Filter by received date | `datetime_received__gte=since` with `EWSTimeZone` | `$filter=receivedDateTime ge 2026-03-12T10:00:00Z` (must be UTC) | HIGH |
| Order newest first | `.order_by('-datetime_received')` | `$orderby=receivedDateTime DESC` | HIGH |
| Retrieve HTML body | `str(item.body)` returns HTML string | `body.content` returns HTML string by default | HIGH |
| Sender name and email | `item.sender.name`, `item.sender.email_address` | `sender.emailAddress.name`, `sender.emailAddress.address` | HIGH |
| Received datetime as UTC | Manual conversion using `timezone.utc` | `receivedDateTime` is already ISO 8601 UTC | HIGH |
| has_attachments flag | `item.has_attachments` boolean | `hasAttachments` boolean property | HIGH |
| Send HTML email | `body=HTMLBody(html)` | `"body": {"contentType": "HTML", "content": "..."}` | HIGH |
| TO/CC/BCC recipients | `Mailbox(email_address=...)` lists | `[{"emailAddress": {"address": "..."}}]` arrays | HIGH |
| SendAs (custom From) | `author=Mailbox(email_address=send_from)` | `"from": {"emailAddress": {"address": send_from}}` in message | HIGH |
| Send saved to Sent Items | `message.send_and_save()` always saves | `sendMail` defaults to `saveToSentItems: true` | HIGH |
| App-only client credentials | MSAL `acquire_token_for_client()` | Same MSAL call, different scope URL | HIGH |
| Max emails limit | `[:max_emails]` exchangelib slice | `$top=100` query parameter (max 1000 per page) | HIGH |
| Error isolation between digests | Independent try/except around each digest | Same pattern, exception type changes from `EWSClientError` to `requests.HTTPError` | HIGH |

**Official sources:**
- [List messages API](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0)
- [sendMail API](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0)
- [Message resource type](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0)

---

## Behavioral Differences

Critical differences that require code changes during migration.

### 1. Pagination — Graph Requires Explicit Handling

**EWS behavior:** exchangelib transparently applies `[:max_emails]` as a server-side slice. You get back a list you iterate once.

**Graph behavior:** Graph returns results in pages. Default page size is 10 messages. Maximum page size with `$top` is 1000. When more results exist, the response contains `@odata.nextLink` — a URL you must GET to retrieve the next page. If you ignore `@odata.nextLink`, you silently miss emails beyond the first page.

**Impact on InboxIQ:** A single request with `$top=100` handles the normal case (hourly run, low email volume). However, correctness requires a pagination loop. The code must check for `@odata.nextLink` in the response and follow it until exhausted.

Pagination loop pattern in plain `requests`:
```python
url = f"https://graph.microsoft.com/v1.0/users/{mailbox}/mailFolders/inbox/messages"
params = {"$filter": f"receivedDateTime ge {since_utc}", "$orderby": "receivedDateTime DESC", "$top": 100, "$select": "..."}
while url:
    response = session.get(url, params=params)
    data = response.json()
    emails.extend(data["value"])
    url = data.get("@odata.nextLink")
    params = {}  # nextLink already contains all params
```

**Official source:** [List messages — paging](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0) — HIGH confidence

---

### 2. Date Filtering — UTC Required, Format Strict

**EWS behavior:** exchangelib accepts `EWSTimeZone.localzone()` datetimes and converts internally.

**Graph behavior:** `receivedDateTime` filter values must be ISO 8601 UTC. The `Z` suffix or `+00:00` offset is required. Local timezone is not accepted and will produce incorrect results or errors.

**Filter + orderby constraint:** When using both `$filter` and `$orderby` on the same property, Graph requires `$orderby` properties also appear in `$filter`, in the same order, and before non-orderby properties in `$filter`. The correct form is:

```
?$filter=receivedDateTime ge 2026-03-12T00:00:00Z&$orderby=receivedDateTime DESC
```

Incorrect forms (will return `InefficientFilter` error):
```
?$filter=... &$orderby=receivedDateTime    # missing filter on receivedDateTime
?$orderby=receivedDateTime&$filter=...    # wrong parameter order
```

**Impact on InboxIQ:**
- The `StateManager` already stores datetimes as UTC via `datetime.now(timezone.utc)`. Incremental mode timestamps are already correct — convert with `.isoformat().replace('+00:00', 'Z')`.
- The "today at midnight" fallback uses `EWSTimeZone.localzone()` — must change to `datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)`.

**Official source:** [List messages — filter and orderby constraint](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0) — HIGH confidence

---

### 3. Shared Mailbox Access — Direct URL, No Impersonation

**EWS behavior:** `access_type=IMPERSONATION` on the `Account` object. exchangelib sets SOAP impersonation headers. Separate accounts opened for shared mailbox (reading) and sender account (sending).

**Graph behavior:** No impersonation concept in Graph. Access any mailbox directly by addressing the `/users/{email}` endpoint. With `Mail.Read` application permission, the app can access any mailbox in the tenant by email address or user ID.

URL pattern for shared mailbox inbox:
```
GET https://graph.microsoft.com/v1.0/users/messagingai@marsh.com/mailFolders/inbox/messages
```

URL pattern for sending from a user's mailbox:
```
POST https://graph.microsoft.com/v1.0/users/kevin.j.taylor@mmc.com/sendMail
```

**Impact on InboxIQ:** The `_get_account()` method and dual `_shared_account` / `_sender_account` pattern has no equivalent. Replace the entire `EWSClient` class with a `GraphClient` class that holds an authenticated `requests.Session` and calls the appropriate URLs directly.

**Official source:** [Shared/delegated folder access](https://learn.microsoft.com/en-us/graph/outlook-share-messages-folders) — HIGH confidence

---

### 4. SendAs — From Property in JSON Body

**EWS behavior:** `author=Mailbox(email_address=send_from)` on the `Message` object sets the From address. The current code sends from `Config.USER_EMAIL` but sets author to `Config.get_send_from()` (which may differ if `SEND_FROM` env var is set).

**Graph behavior:** Set the `from` property in the message JSON body:
```json
{
  "message": {
    "subject": "...",
    "from": {
      "emailAddress": { "address": "shared-address@domain.com" }
    },
    "toRecipients": [...],
    "body": {...}
  }
}
```

The `sender` property is set automatically by Graph based on the mailbox used in the URL. The `from` property controls what recipients see as the From address.

**SendAs vs Send on Behalf distinction:**
- **Send As** (Exchange permission): `from` and `sender` display the same address. No "on behalf of" indicator shown to recipients. Requires Exchange admin to grant SendAs permission on the from mailbox.
- **Send on Behalf** (Exchange permission): `from` shows the from address, `sender` shows the actual sending account. Recipients see "User A on behalf of User B."

For app-only (client credentials flow), the documentation states: "Applications that use application tokens instead of user tokens and have the `Mail.Send` permission consented by an administrator can send mail as any user in the organization." Setting `from` in this context performs a SendAs-style send.

**Impact on InboxIQ:** Remove the dual-account model. POST to `/users/{Config.USER_EMAIL}/sendMail` with `from` set to `Config.get_send_from()` in the message body. If `SEND_FROM` equals `USER_EMAIL`, omit the `from` property — Graph uses the sending mailbox by default.

**Official source:** [Send mail from another user](https://learn.microsoft.com/en-us/graph/outlook-send-mail-from-other-user) — HIGH confidence

---

### 5. Body Content — HTML Returned, Graph Sanitizes by Default

**EWS behavior:** `item.body` returns the raw body content. The `_strip_html()` method removes tags with regex.

**Graph behavior:** `body.content` returns the HTML string. `body.contentType` is `"html"` for HTML emails, `"text"` for text-only emails.

Important Graph-specific behavior: Graph **sanitizes HTML by default**, stripping potentially unsafe elements such as JavaScript before returning the body. To receive the original, unsanitized HTML, include the request header `Prefer: outlook.allow-unsafe-html`.

For the LLM summarization use case, the sanitized HTML is preferable — it removes noise. The existing `_strip_html()` regex approach works on the `body.content` string with no changes needed.

Text-format alternative: Include `Prefer: outlook.body-content-type="text"` to request server-side HTML-to-text conversion. This reduces the need for client-side HTML stripping, but Graph may still return HTML if the message has no text part.

**Impact on InboxIQ:** No change required to HTML stripping logic. The body property access changes from `str(item.body)` to `message["body"]["content"]`. The sanitization behavior is an improvement.

**Official source:** [Reading messages — body format control](https://learn.microsoft.com/en-us/graph/outlook-create-send-messages#reading-messages-with-control-over-the-body-format-returned) — HIGH confidence

---

### 6. Authentication Scope — One String Change

**EWS behavior:** MSAL scope = `["https://outlook.office365.com/.default"]`

**Graph behavior:** MSAL scope = `["https://graph.microsoft.com/.default"]`

The MSAL `ConfidentialClientApplication` constructor arguments (`client_id`, `client_credential`, `authority`) are identical. The `acquire_token_for_client(scopes=...)` call is identical. Only the scopes list value changes.

**Impact on InboxIQ:** One line change in `auth.py`. The `get_ews_credentials()` method becomes a `get_graph_token()` method that returns a raw access token string (not an `OAuth2Credentials` object, since exchangelib is gone).

**Official source:** [Authentication differences EWS vs Graph](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-authentication) — HIGH confidence

---

### 7. Message ID Format — Different but Unused

**EWS behavior:** EWS item IDs are long opaque base64 strings. They change when items are moved between folders.

**Graph behavior:** Graph IDs are also opaque base64 strings with a different encoding. By default they also change on folder move. An immutable ID variant exists via `Prefer: IdType="ImmutableId"` but requires opt-in.

**Impact on InboxIQ:** The `Email.id` field stores the ID in the `Email` dataclass. InboxIQ does not use IDs for deduplication, re-lookup, or state management — it uses time-based state only. The ID format change has zero functional impact.

**Official source:** [Message resource — id property](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0) — HIGH confidence

---

### 8. sendMail Returns 202 Accepted (Not Delivery Confirmation)

**EWS behavior:** `message.send_and_save()` raises an exception on failure.

**Graph behavior:** `POST /sendMail` returns `202 Accepted` on success. This means the request was accepted, not that the message was delivered. Delivery is subject to Exchange Online throttling limits.

**Impact on InboxIQ:** Error handling remains the same pattern — raise on non-2xx HTTP status. A 202 is a success for the API call. The semantic difference (accepted vs delivered) matches how Exchange Online has always worked.

**Official source:** [sendMail API — response](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0) — HIGH confidence

---

### 9. bodyPreview — Native Field Removes Manual Truncation

**EWS behavior:** The current code creates `body_preview = body_content[:200]` after stripping HTML from the full body. This requires fetching the full body just to get a preview.

**Graph behavior:** The `bodyPreview` property is a native 255-character plain text preview generated by Exchange. It is returned by default in list responses (no `$select` needed) and does not require HTML stripping. The current `Email.body_preview` field can be populated directly from this field.

**Impact on InboxIQ:** This is an improvement. Use `message["bodyPreview"]` for the preview. Still fetch `body` separately for full content for LLM summarization.

**Official source:** [Message resource — bodyPreview](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0) — HIGH confidence

---

### 10. internetMessageHeaders — Opt-In Only

**EWS behavior:** Headers are accessible on the exchangelib item object.

**Graph behavior:** `internetMessageHeaders` is a message property but is **only returned when explicitly included in `$select`**. It is read-only after send (cannot modify after creation).

**Impact on InboxIQ:** The current code does not read message headers. No impact. Note for future: if email header inspection is ever needed (e.g., for classifier enhancements), add `internetMessageHeaders` to the `$select` parameter.

**Official source:** [Message resource — internetMessageHeaders](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0) — HIGH confidence

---

## Graph-Specific Considerations

### Required Application Permissions (Entra ID)

The existing Entra ID app registration is reused. Only the API permissions assigned to it change.

| Permission | Type | Purpose | Replaces |
|---|---|---|---|
| `Mail.Read` | Application | Read messages from shared mailbox | `EWS.AccessAsApp` (read) |
| `Mail.Send` | Application | Send emails from user account | `EWS.AccessAsApp` (send) |

Remove `EWS.AccessAsApp` after migration is verified. The AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET environment variables remain unchanged.

**Official source:** [Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference) — HIGH confidence

---

### Mail.Read Grants Tenant-Wide Access by Default

With `Mail.Read` application permission, the app can read any mailbox in the tenant. This is broader than EWS impersonation which was scoped via Exchange configuration. The current EWS `EWS.AccessAsApp` permission also grants broad access, so the security posture is equivalent.

Optional hardening (not required for migration): Use **Exchange Online RBAC for Applications** (`New-ManagementRoleAssignment`) to scope the app to specific mailboxes only. This replaces the older Application Access Policies. To scope correctly, remove the Entra ID `Mail.Read` grant and assign it instead via Exchange RBAC with a management scope targeting only the shared mailbox.

**Official source:** [Exchange RBAC for Applications](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac) — HIGH confidence

---

### $select for Performance and Reliability

Graph returns a default set of fields, not all fields. Specifying `$select` reduces payload size and avoids HTTP 504 gateway timeouts on large mailboxes (explicitly warned about in official docs).

Recommended `$select` for InboxIQ message reads:
```
$select=id,subject,sender,receivedDateTime,body,bodyPreview,hasAttachments
```

Note: `body` is NOT in the default response — it must be in `$select`. All other fields above are in the default response but specifying them explicitly speeds up requests.

**Official source:** [List messages — performance](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0) — HIGH confidence

---

### Python Client Library Decision

Two implementation approaches:

**Option A: `msgraph-sdk` (Microsoft official Python SDK)**
- Install: `pip install msgraph-sdk azure-identity`
- Requires Python >= 3.9 (InboxIQ uses 3.10+, compatible)
- Async-first API — requires `asyncio` / `await` throughout
- Strongly typed objects
- Automatic token refresh via `azure-identity`
- Adds significant dependency weight

**Option B: Direct `requests` + existing `msal`**
- Uses `msal` already in `requirements.txt` — no new dependencies
- Synchronous — fits current `main.py` architecture
- Manual JSON parsing: `response.json()["value"]`
- Manual pagination: `response.json().get("@odata.nextLink")`
- Simpler debugging — raw HTTP, readable payloads

**Recommendation: Option B (direct `requests`).** The existing codebase is synchronous. Adding `msgraph-sdk` would force a refactor of `main.py` to async, which is out of scope for a pure swap. The Graph REST API is simple JSON — no SDK abstraction is needed. `msal` already handles token acquisition.

**Official source:** [msgraph-sdk PyPI](https://pypi.org/project/msgraph-sdk/) — HIGH confidence

---

### EWS Retirement Deadline

Microsoft will retire EWS connections from Exchange Online on **October 1, 2026**. After that date, `exchangelib` will stop working against Exchange Online. This migration has a hard deadline.

**Official source:** [EWS to Graph migration overview](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-overview) — HIGH confidence

---

### Quick Reference: Complete Filter Syntax

The exact Graph query for InboxIQ's shared mailbox email fetch:

```
GET https://graph.microsoft.com/v1.0/users/messagingai@marsh.com/mailFolders/inbox/messages
  ?$filter=receivedDateTime ge 2026-03-12T10:00:00Z
  &$orderby=receivedDateTime DESC
  &$top=100
  &$select=id,subject,sender,receivedDateTime,body,bodyPreview,hasAttachments
```

Rules:
- `receivedDateTime` value must be UTC with `Z` suffix
- When using `$orderby=receivedDateTime`, `$filter` must also reference `receivedDateTime` and it must be listed first in the `$filter` expression
- `$top` max is 1000; default is 10 (always specify it)
- `body` is NOT in the default response — must be in `$select`
- `bodyPreview` is in the default response — 255 chars plain text

---

## Anti-Features (Do Not Build)

Explicitly excluded from this migration. These represent scope creep risks.

| Anti-Feature | Why Avoid | Boundary |
|---|---|---|
| msgraph-sdk async adoption | Requires converting synchronous `main.py` to async. Out of scope for pure swap. | Use `requests` + `msal` directly |
| Delta query incremental sync | Graph's delta tokens are more efficient than time-based state, but the existing `StateManager` works correctly. Replacing it adds risk with no user-visible benefit. | Keep time-based `StateManager` |
| Exchange RBAC scoping | Security hardening improvement. Valid but out of scope. | `Mail.Read` with Entra ID consent |
| Immutable message IDs | InboxIQ does not use IDs for lookups. Not needed. | No ID-based operations |
| Webhook / push notifications | InboxIQ uses polling (Task Scheduler). Switching models is out of scope. | Keep Windows Task Scheduler polling |
| Graph batch requests | Only two API calls per run. Batching adds complexity for no gain. | Sequential individual calls |
| Read receipts, mail flags | Not used by InboxIQ. | Not applicable |
| Streaming large bodies | Only needed if body fetches cause 504 timeouts. Investigate only if observed in production. | Single-call body fetch |
| Mail.Read.Shared delegated permissions | These permissions only work with delegated (user) auth, not app-only. InboxIQ uses app-only. | Use `Mail.Read` application permission |

---

## Sources

| Source | URL | Confidence |
|---|---|---|
| List messages API (v1.0) | https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0 | HIGH |
| sendMail API (v1.0) | https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0 | HIGH |
| Message resource type | https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0 | HIGH |
| Send from another user | https://learn.microsoft.com/en-us/graph/outlook-send-mail-from-other-user | HIGH |
| Create and send messages | https://learn.microsoft.com/en-us/graph/outlook-create-send-messages | HIGH |
| Shared/delegated folder access | https://learn.microsoft.com/en-us/graph/outlook-share-messages-folders | HIGH |
| EWS to Graph API mappings | https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-api-mapping | HIGH |
| Exchange RBAC for Applications | https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac | HIGH |
| Python email tutorial | https://learn.microsoft.com/en-us/graph/tutorials/python-email | HIGH |
| msgraph-sdk Python PyPI | https://pypi.org/project/msgraph-sdk/ | HIGH |
| EWS to Graph migration overview | https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-overview | HIGH |
