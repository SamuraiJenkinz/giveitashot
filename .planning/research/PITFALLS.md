# Pitfalls Research: Graph API Migration

**Domain:** EWS (exchangelib) to Microsoft Graph API — Python email client
**Project:** InboxIQ — Shared mailbox reader + digest sender (mmc.com)
**Researched:** 2026-03-12
**Overall confidence:** HIGH (all critical pitfalls verified against official Microsoft docs and current project source)

---

## Critical Pitfalls (will break the migration)

These will produce 401/403 errors, silent data loss, or complete failure to send/receive.

---

### Pitfall C-1: Wrong MSAL Scope for Graph API

**What goes wrong:** The current `auth.py` uses scope `https://outlook.office365.com/.default`, which issues a token for the EWS resource. Using this token against Graph endpoints (`https://graph.microsoft.com/...`) returns HTTP 401 Unauthorized immediately. The `aud` (audience) claim in the token is `https://outlook.office365.com/` — Graph rejects it because it expects `https://graph.microsoft.com/`.

**Why it happens:** EWS and Graph are separate API surfaces with separate resource URIs. MSAL tokens encode their intended audience. They are not interchangeable between APIs.

**Current code in `auth.py` (must change):**
```python
scopes = ["https://outlook.office365.com/.default"]
```

**Correct code for Graph:**
```python
scopes = ["https://graph.microsoft.com/.default"]
```

**Warning signs:** HTTP 401 on every Graph call immediately after token acquisition appears to succeed. The MSAL call itself returns no error — the token is valid, just for the wrong audience.

**Prevention:** Change the scope constant in the new `auth.py` (or `graph_client.py`) before writing any Graph call code. Test token acquisition in isolation and decode the resulting JWT at jwt.io to confirm `aud` is `https://graph.microsoft.com/`.

**Phase:** Auth module update — first task of the migration.

**Sources:** [Authentication differences EWS vs Graph](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-authentication), [Access both EWS and Graph Q&A](https://learn.microsoft.com/en-us/answers/questions/298599/access-both-ews-and-graph)

---

### Pitfall C-2: App-Only Permissions Grant Tenant-Wide Mailbox Access by Default

**What goes wrong:** When `Mail.Read` and `Mail.Send` are granted as Application permissions in Entra ID with admin consent, the app has read/send access to every mailbox in the entire mmc.com tenant — not just `messagingai@marsh.com`. This is a security violation in an enterprise environment and will either be blocked at the admin consent stage or trigger a security incident after deployment.

**Why it happens:** Graph application permissions (client credentials flow) are organization-scoped by default. There is no per-mailbox consent in Entra ID alone.

**The fix — two options, both require Exchange Online PowerShell:**

Option A: **ApplicationAccessPolicy (AAP)** — Legacy, still fully supported as of March 2026. Creates a mail-enabled security group, adds the shared mailbox, associates the policy with the app registration. Propagation delay: up to 24 hours.

Option B: **RBAC for Applications** — New replacement for AAP. Uses Exchange Online Management Role Assignments scoped to a Management Scope or Admin Unit. Propagation delay: 30 minutes to 2 hours for active apps, 30 minutes for idle apps.

**Important:** If both Entra ID permissions AND RBAC for Applications are configured, access is the union of both. To achieve scoping, the Entra ID organization-wide consent must be removed and only the Exchange RBAC assignment used. Failing to remove the Entra ID grant defeats the scoping entirely.

**Warning signs:** IT/security rejects the permissions request because it is too broad; or the app can read any employee's inbox after permissions are granted.

**Prevention:** Include mailbox access restriction as an explicit, documented prerequisite step — not optional post-deployment hardening. Prepare the Exchange Online PowerShell commands ahead of the admin meeting.

**Phase:** Infrastructure/permissions setup, before any Graph code is deployed to any environment.

**Sources:** [RBAC for Applications in Exchange Online](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac), [Secure Access to Mailboxes via Graph](https://c7solutions.com/2024/09/secure-access-to-mailboxes-via-graph)

---

### Pitfall C-3: Using `/me/sendMail` in App-Only (Client Credentials) Flow

**What goes wrong:** Using `/me/sendMail` returns 401 or routes the request incorrectly because `/me` resolves to the authenticated user — and in client credentials flow there is no authenticated user. The service principal is not a user; it has no `/me` mailbox. The call either fails or sends from an unexpected identity.

**Why it happens:** `/me` is a delegated-flow shorthand. App-only flows must always use `/users/{id}` or `/users/{userPrincipalName}`.

**Correct endpoint for app-only flow:**
```
POST https://graph.microsoft.com/v1.0/users/{sharedMailbox}/sendMail
```
Where `{sharedMailbox}` is the UPN or SMTP address (e.g., `messagingai@marsh.com`).

**Warning signs:** 401 on send calls even though Mail.Send permission is granted and read calls work fine.

**Prevention:** Use `/users/{id}/sendMail` exclusively in the new `graph_client.py`. Add a comment at the definition explaining why `/me` is prohibited.

**Phase:** Graph client implementation — `send_email` method.

**Sources:** [user: sendMail API reference](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0), [Using sendMail with application permissions Q&A](https://learn.microsoft.com/en-us/answers/questions/2225484/using-sendmail-in-graph-api-with-application-permi)

---

### Pitfall C-4: Setting the "from" Field Incorrectly for Shared Mailbox Sending

**What goes wrong:** When sending via `Mail.Send` application permission, Graph allows sending as any user in the tenant. The `from` field in the message body must be explicitly set to the desired sender address. If omitted, the message is sent from the mailbox in the URL path — which may or may not be the desired From address. If set to an address the app does not have permission to send from, Graph returns 403 `ErrorSendAsDenied`.

**EWS equivalent:** `exchangelib` uses `author=Mailbox(email_address=send_from)` on the `Message` object. This maps directly to the `from` field in Graph.

**Current config logic in `config.py`:**
```python
@classmethod
def get_send_from(cls) -> str:
    return cls.SEND_FROM if cls.SEND_FROM else cls.USER_EMAIL
```
This custom From address logic must be preserved in `graph_client.py` by setting the `from` field in the JSON body.

**Correct JSON body for send with custom From:**
```json
{
  "message": {
    "subject": "...",
    "from": {
      "emailAddress": {"address": "messagingai@marsh.com"}
    },
    "toRecipients": [...],
    "body": {"contentType": "HTML", "content": "..."},
    "saveToSentItems": true
  }
}
```

**Warning signs:** 403 `ErrorSendAsDenied` responses; emails arriving from wrong sender; `SEND_FROM` config value being silently ignored.

**Prevention:** In `graph_client.py`, always include the `from` field and map it from `Config.get_send_from()`. Add an integration test that verifies the From address on a sent email.

**Phase:** Graph client implementation (`send_email` method) + integration testing.

**Sources:** [Send Outlook messages from another user](https://learn.microsoft.com/en-us/graph/outlook-send-mail-from-other-user)

---

### Pitfall C-5: Application Permission Type vs. Delegated — Impersonation Does Not Exist in Graph

**What goes wrong:** The current `ews_client.py` uses `access_type=IMPERSONATION` from exchangelib. This EWS mechanism has no equivalent in Graph. If the Entra ID app registration is configured with Delegated permissions instead of Application permissions, all Graph calls to `/users/{id}/...` will fail with 403 in daemon mode because there is no user session.

**Why it happens:** EWS impersonation was a server-side permission grant. Graph uses OAuth 2.0 application permissions with admin consent. During app registration, it is easy to accidentally add the Delegated variant of `Mail.Read`/`Mail.Send` instead of the Application variant — they appear almost identically in the Azure portal.

**How to verify correct setup:** In the Entra ID App Registration under "API permissions":
- Type column must show **Application** (not Delegated) for `Mail.Read` and `Mail.Send`
- Status column must show **Granted for [tenant]** (admin consent completed)

**Warning signs:** Auth works fine when testing interactively (delegated) but fails when running as a Windows Task Scheduler job (no interactive user).

**Prevention:** Screenshot the permissions page after setup. Verify permission type is "Application" before the first end-to-end test run.

**Phase:** App registration setup.

**Sources:** [Authentication differences EWS vs Microsoft Graph](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-authentication)

---

## Moderate Pitfalls (will cause bugs)

These won't cause immediate startup failures but will introduce subtle data loss, wrong results, or behavioral regressions.

---

### Pitfall M-1: Pagination — Default Page Size is 10, Not All Emails

**What goes wrong:** A call to `GET /users/{id}/mailFolders/inbox/messages` returns only 10 messages by default. The current EWS code uses `[:max_emails]` slice which exchangelib handles transparently by fetching pages internally. In Graph using the raw `requests` library, the developer must implement pagination manually. Without it, the hourly run silently processes only 10 emails regardless of how many arrived.

**Specific behavior:**
- The response contains `@odata.nextLink` when more results exist
- `$top` is an upper bound, not an exact count — the API may return fewer
- Maximum `$top` value is 1000
- Do NOT extract `$skip` from `@odata.nextLink` and reconstruct your own URL — use the entire nextLink URL as-is

**Prevention — correct pagination loop:**
```python
url = f"https://graph.microsoft.com/v1.0/users/{mailbox}/mailFolders/inbox/messages"
params = {"$top": 100, "$filter": "...", "$select": "..."}
emails = []
while url:
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    emails.extend(data.get("value", []))
    url = data.get("@odata.nextLink")  # None when no more pages
    params = None  # nextLink already contains all query params
```

**Warning signs:** Emails received in the hour exceed 10 but only 10 appear in the digest; no error logs.

**Phase:** Graph client implementation (`get_shared_mailbox_emails`).

**Sources:** [Paging Microsoft Graph data](https://learn.microsoft.com/en-us/graph/paging), [List messages](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0)

---

### Pitfall M-2: Date Filter Format — ISO 8601 UTC, No Quotes in OData $filter

**What goes wrong:** The current EWS code filters by `datetime_received__gte=since` — exchangelib handles all date formatting internally. Graph uses OData `$filter` with a specific datetime syntax. Quoting the datetime value (like a string), omitting the `Z` UTC suffix, or using local time without conversion will produce 400 errors or silently return wrong results.

**Correct format:**
```
$filter=receivedDateTime ge 2025-03-12T14:00:00Z
```

**Rules:**
1. DateTime values in `$filter` are NOT enclosed in single or double quotes
2. Must use UTC (the `Z` suffix is required; Exchange stores everything in UTC)
3. Local time without conversion will silently filter on wrong hours

**Python code:**
```python
from datetime import timezone

since_utc = since.astimezone(timezone.utc)
filter_str = f"receivedDateTime ge {since_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
```

**Warning signs:** API returns 400 with "Bad request"; or all messages are returned ignoring the time filter; or only messages after the wrong UTC-offset time appear.

**Phase:** Graph client implementation — date filter construction.

**Sources:** [Use the $filter query parameter](https://learn.microsoft.com/en-us/graph/filter-query-parameter), [ReceivedDateTime filter Q&A](https://learn.microsoft.com/en-us/answers/questions/768284/how-to-use-receiveddatetime-filter-in-graph-client)

---

### Pitfall M-3: $filter and $orderby Constraint — Properties Must Align

**What goes wrong:** Combining `$filter` and `$orderby` in the same request has a strict rule: any property in `$orderby` must also appear in `$filter`, in the same order, before any non-`$orderby` filter properties. Violating this returns a 400 error:
- Error code: `InefficientFilter`
- Error message: `The restriction or sort order is too complex for this operation`

**Current EWS equivalent:** `order_by('-datetime_received')` — exchangelib handles this constraint internally.

**Safe pattern for InboxIQ (filter and order on same field):**
```
$filter=receivedDateTime ge 2025-03-12T00:00:00Z&$orderby=receivedDateTime desc
```

**Warning signs:** 400 error on list messages requests with `InefficientFilter` error code.

**Phase:** Graph client implementation.

**Sources:** [List messages — Optional query parameters](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0)

---

### Pitfall M-4: Body Content Is Nested — "body.content" Not a Flat String

**What goes wrong:** The current `ews_client.py` accesses `item.body` directly from exchangelib, which returns a body object that converts to a string. In Graph, the message body is a nested object: `message["body"]["content"]`. Accessing `message["body"]` directly gives the dict, not the HTML string. The `body.contentType` will be `"html"` by default even for emails that were originally plain text but converted to HTML by Exchange.

**Do not use `bodyPreview`:** `bodyPreview` is truncated to 255 characters. The current code generates a custom 200-character preview from the full body — that behavior must be replicated from the full `body.content`, not from `bodyPreview`.

**Graph message body structure:**
```json
{
  "body": {
    "contentType": "html",
    "content": "<html><body>Full email HTML here...</body></html>"
  },
  "bodyPreview": "First 255 characters truncated here..."
}
```

**Migration mapping from `ews_client.py`:**
- EWS: `str(item.body)` → Graph: `message["body"]["content"]`
- EWS: `body_content[:200]` (custom preview) → Graph: still `body_content[:200]` generated from `message["body"]["content"]`

**`body` is not returned by default in list calls:** When using `$select`, `body` must be explicitly listed: `$select=id,subject,sender,receivedDateTime,body,hasAttachments`

**Warning signs:** `body_content` always empty; `body_preview` always exactly 255 chars ending mid-word.

**Phase:** Graph client implementation — email parsing.

**Sources:** [message resource type](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0)

---

### Pitfall M-5: Sender Field Is Nested — Not a Flat Object

**What goes wrong:** EWS/exchangelib exposes `item.sender.name` and `item.sender.email_address` as direct string attributes. Graph nests these inside an `emailAddress` sub-object. Accessing `message["sender"]["name"]` (the flat EWS pattern) raises a `KeyError`.

**Graph sender structure:**
```json
{
  "sender": {
    "emailAddress": {
      "name": "M365 Message Center",
      "address": "microsoft-noreply@microsoft.com"
    }
  }
}
```

**Migration mapping from `ews_client.py`:**
- EWS: `item.sender.name` → Graph: `message["sender"]["emailAddress"]["name"]`
- EWS: `item.sender.email_address` → Graph: `message["sender"]["emailAddress"]["address"]`

**Defensive access:**
```python
sender_info = message.get("sender", {}).get("emailAddress", {})
sender_name = sender_info.get("name", "Unknown")
sender_email = sender_info.get("address", "unknown@unknown.com")
```

**Warning signs:** All emails show "Unknown" sender after migration; `KeyError` on sender access.

**Phase:** Graph client implementation — email parsing.

**Sources:** [message resource type](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0)

---

### Pitfall M-6: Message ID Format Change — Graph IDs Are Not EWS IDs

**What goes wrong:** Graph message IDs are base64-encoded REST format strings, completely incompatible with EWS `ItemId` format. If any code stores message IDs for deduplication across runs and then tries to use them after migration, all stored IDs become invalid lookups.

**Risk assessment for InboxIQ:** InboxIQ uses date-based incremental filtering (`since` timestamp in state), not ID-based deduplication. Review `state.py` to confirm it stores no EWS message IDs. If the state file contains only timestamps, this pitfall does not apply and the state file survives the migration intact.

**If the state file does contain EWS IDs:** The state file must be deleted or migrated before the first Graph-based run, otherwise comparison logic will fail silently.

**Warning signs:** Duplicate emails in digest after migration; or emails from the transition window missing from the first Graph-based digest.

**Prevention:** Audit `state.py` before migration to confirm only timestamps are stored.

**Phase:** Pre-migration code audit.

**Sources:** [Obtain immutable identifiers for Outlook resources](https://learn.microsoft.com/en-us/graph/outlook-immutable-id)

---

### Pitfall M-7: MSAL Token Cache Must Be Preserved Between Runs

**What goes wrong:** If a new `ConfidentialClientApplication` instance is created on every Task Scheduler run (e.g., by calling `clear_cache()` unnecessarily), the MSAL token cache is discarded and a fresh token is fetched from Entra ID on every execution. This adds latency and generates unnecessary token requests.

**Current behavior in `auth.py`:** The existing code correctly calls `acquire_token_silent()` before `acquire_token_for_client()`. This pattern must be preserved in the new auth module. The `ConfidentialClientApplication` instance must be reused within a process lifetime.

**Additional opportunity:** `config.py` already defines `TOKEN_CACHE_FILE` but `auth.py` does not wire it up to MSAL's `SerializableTokenCache`. For a Windows Task Scheduler daemon that creates a new process on each run, persisting the token to disk means tokens survive process restarts and the 1-hour token lifetime is not wasted.

**Warning signs:** Logs show "No cached token, acquiring new token..." on every single hourly run.

**Phase:** Auth module update — token cache handling.

**Sources:** [Acquire and cache tokens with MSAL](https://learn.microsoft.com/en-us/entra/identity-platform/msal-acquire-cache-tokens), [Refreshing MSAL access tokens using Token Cache](https://www.beringer.net/beringerblog/refreshing-msal-access-tokens-using-token-cache/)

---

## Minor Pitfalls (will cause annoyance)

These cause friction during development or produce confusing errors that waste debugging time without breaking core functionality.

---

### Pitfall Mi-1: HTTP 429 Throttling — No Automatic Retry in `requests`

**What goes wrong:** The Graph API rate-limits with HTTP 429 and a `Retry-After` header. The `requests` library does not handle this automatically. During development with rapid test runs (e.g., calling list messages 20 times in 5 minutes), 429 responses will appear and the code will crash unless handled explicitly.

**For InboxIQ in production:** With hourly execution and low email volume, throttling is unlikely in production. However, during development and test iteration, repeated runs against the live mailbox will hit limits.

**Prevention — simple retry wrapper:**
```python
import time

def graph_request(method, url, headers, **kwargs):
    for attempt in range(3):
        resp = requests.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 10))
            time.sleep(wait)
            continue
        return resp
    raise RuntimeError(f"Graph API throttled after retries: {url}")
```

**Sources:** [Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling)

---

### Pitfall Mi-2: `$select` Must Explicitly Include "body" — List Response Omits It by Default

**What goes wrong:** Calling list messages without `$select` returns a default field set that includes most fields but may omit `body` for performance on large responses. When testing in Graph Explorer, body appears because Graph Explorer individually fetches each message. In a list call without explicit `$select`, body can be absent.

**Prevention:** Always include `body` in `$select` when listing messages:
```
$select=id,subject,sender,from,receivedDateTime,body,hasAttachments,isRead
```

**Note:** Including `body` in a list call with large `$top` on a high-volume mailbox can trigger HTTP 504 Gateway Timeout. If this occurs, fetch `body` per-message via individual `GET /messages/{id}` calls instead of including it in the list response.

**Sources:** [List messages](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0)

---

### Pitfall Mi-3: saveToSentItems Behavior — Default May Not Match EWS send_and_save()

**What goes wrong:** The current code uses exchangelib's `message.send_and_save()` which saves a copy to Sent Items. In Graph, `sendMail` has a `saveToSentItems` boolean (defaults to `true`). The question is: which Sent Items folder receives the copy?

**Behavior matrix:**
- Calling `POST /users/{sharedMailbox}/sendMail` → saved to shared mailbox Sent Items (desired)
- Calling `POST /users/{serviceAccount}/sendMail` with `from` pointing elsewhere → saved to service account Sent Items (not desired)

**For InboxIQ:** Use the shared mailbox address in the URL path (not a separate service account address) and set `saveToSentItems: true`. This replicates current EWS behavior.

**Warning signs:** Sent items accumulate in unexpected mailboxes; audit trail gaps.

**Sources:** [Send Outlook messages from another user](https://learn.microsoft.com/en-us/graph/outlook-send-mail-from-other-user)

---

### Pitfall Mi-4: Admin Consent Propagation Delay

**What goes wrong:** After an IT admin grants application permission consent in Entra ID, the permissions are not immediately effective. Calling Graph immediately after consent may still return 403.

**Observed delays:**
- Entra ID permission consent: typically 1–5 minutes, occasionally up to 15 minutes
- ApplicationAccessPolicy (mailbox restriction): up to 24 hours
- Exchange RBAC for Applications: 30 minutes to 2 hours for active apps, 30 minutes for idle apps

**Prevention:** Do not run integration tests immediately after consent. Build in a wait period or retry loop during testing. Document expected wait times in the deployment runbook so IT/security staff understand why testing cannot happen instantly after they approve.

**Sources:** [RBAC for Applications — Limitations section](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac)

---

### Pitfall Mi-5: hasAttachments Is True for Inline Images

**What goes wrong:** `has_attachments` in EWS corresponds to `hasAttachments` in Graph. However, in Graph `hasAttachments` is `true` when the message contains inline images embedded in the HTML body — not just formal file attachments. For InboxIQ which uses `has_attachments` only as metadata (not to download attachments), this is a minor behavioral difference. It will not cause failures but will show `has_attachments: True` on more messages than EWS did.

**Action:** Document the behavioral difference in a comment; no code change required.

**Sources:** [message resource type](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0)

---

## Deployment/Operations Pitfalls

These affect the Windows Task Scheduler daemon behavior and production reliability at Marsh McLennan.

---

### Pitfall D-1: Token Cache Lost on Every Process Exit (Windows Task Scheduler)

**What goes wrong:** The MSAL `ConfidentialClientApplication` object and its in-memory token cache are destroyed when the Python process exits after each hourly Task Scheduler run. The next run starts a fresh process with no cache and acquires a new token from Entra ID.

**This is functional but wasteful.** Graph tokens are valid for 3600 seconds (1 hour). A new token acquisition on every hourly run means the token is always fresh but also means a round-trip to `login.microsoftonline.com` adds ~200–500ms to every run.

**Opportunity:** `config.py` already defines `TOKEN_CACHE_FILE = Path(...) / ".token_cache.json"` but `auth.py` does not use it. Wiring up `SerializableTokenCache` to this file makes the token persist between process restarts. MSAL will automatically refresh when the token nears expiry.

**Risk if ignored:** Not a bug. Adds minor latency. Low priority.

**Sources:** [MSAL token caching documentation](https://learn.microsoft.com/en-us/entra/identity-platform/msal-acquire-cache-tokens)

---

### Pitfall D-2: Environment Variable Changes Must Be Coordinated With Task Scheduler

**What goes wrong:** The current `config.py` references `EWS_SERVER` which is meaningless for Graph. If the `.env` file is updated to add Graph-specific variables while EWS variables remain, the `Config.validate()` method may not catch misconfiguration. More critically: if Windows Task Scheduler passes environment variables directly in the task definition XML (not from `.env`), those must also be updated separately.

**Variables to remove:** `EWS_SERVER`

**Variables to update scope of:**
- `USER_EMAIL` — in EWS this was the impersonation identity; in Graph it becomes the send-from account for the URL path. Confirm this mapping is still correct for the production config.

**Variables to add (if Graph-specific config is needed):** Graph base URL (can be hardcoded as constant rather than env var).

**Prevention:** Audit all `config.py` references during migration. Update `Config.validate()` to require any new Graph-specific env vars. Update `.env.example`. Check the Task Scheduler task definition XML on the Windows Server for hardcoded env vars.

**Phase:** Config module update.

---

### Pitfall D-3: Enterprise Proxy May Block `login.microsoftonline.com`

**What goes wrong:** MSAL token acquisition connects to `https://login.microsoftonline.com`. Graph API calls connect to `https://graph.microsoft.com`. At Marsh McLennan (mmc.com), outbound HTTPS may require proxy configuration. The `requests` library respects `HTTPS_PROXY` environment variables and `proxies` parameter. MSAL also uses `requests` internally for token acquisition.

**Pattern:** Works on developer workstation (direct internet or different proxy) but fails on Windows Server deployment with "connection timeout" or "SSL certificate verification failed" errors.

**Prevention:** Test the complete auth + Graph call chain on the actual Windows Server deployment environment before declaring the migration ready. Verify both `login.microsoftonline.com` and `graph.microsoft.com` are reachable. If proxy is required, add proxy configuration to both the `msal.ConfidentialClientApplication` and the `requests.get()` calls.

---

### Pitfall D-4: Test Suite Will Silently Pass While Testing Old Behavior

**What goes wrong:** The existing 167 tests mock exchangelib objects (`Account`, `Message`, `Mailbox`, `HTMLBody`). After migrating to `graph_client.py`, these mocks no longer test the actual Graph data parsing code. Tests continue to pass because they are testing the old mock behavior — not the new Graph JSON parsing. A developer can break the entire `graph_client.py` without a single test failing.

**What needs updating in the test suite:**
- All `EWSClient` mocks → `GraphClient` mocks using Graph-shaped JSON dicts
- exchangelib object attribute access patterns (`.sender.name`) → Graph nested JSON access (`["sender"]["emailAddress"]["name"]`)
- `EWSClientError` → `GraphClientError` (new exception class)
- New pagination behavior tests: mock a two-page response where the first page includes `@odata.nextLink`
- `conftest.py` fixtures that create `Email` objects from EWS data → fixtures from Graph JSON

**Prevention:** As part of migration, update test fixtures to use Graph-shaped JSON before submitting `graph_client.py` for review. A failing test suite with new fixtures is safer than a passing test suite with wrong fixtures.

**Phase:** Test suite update (must be done before or simultaneously with `graph_client.py` implementation).

---

### Pitfall D-5: No Rollback Plan After Production Cutover

**What goes wrong:** Once `ews_client.py` is replaced by `graph_client.py` in the Task Scheduler deployment, rolling back requires restoring old files AND restoring the EWS scope in `.env`. If the rollback procedure is not pre-documented, an incident recovery under time pressure is likely to fail.

**EWS deprecation timeline:** EWS for Exchange Online is scheduled to be disabled by default in August 2026 and shut down in 2027. This gives time to migrate carefully, but the production cutover should have a documented rollback window.

**Prevention:**
- Keep `ews_client.py` in a git feature branch (do not delete from git until Graph has been stable in production for 2+ weeks)
- Consider a dual-mode validation period: run Graph client in parallel with EWS for 2-3 hourly cycles, compare email counts, then cut over
- Document exact rollback steps: which files to restore, which env vars to change, which Task Scheduler settings to revert
- Tag the last working EWS commit explicitly: `git tag pre-graph-migration`

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Auth module update | C-1: Wrong scope; C-5: Application vs Delegated permission type | Change scope to `graph.microsoft.com/.default`; verify Application permissions in Entra ID portal |
| App registration / permissions setup | C-2: Tenant-wide access by default | Coordinate ApplicationAccessPolicy or Exchange RBAC with IT admin before any testing |
| `graph_client.py` — read emails | M-1: Pagination; M-2: Date filter format; M-3: filter+orderby rule; M-4: body structure; M-5: sender structure | Full pagination loop; UTC ISO 8601 filter; explicit `$select` including `body`; nested JSON access |
| `graph_client.py` — send email | C-3: Wrong URL; C-4: `from` field; Mi-3: saveToSentItems | Use `/users/{id}/sendMail`; set `from` field from `Config.get_send_from()`; set `saveToSentItems: true` |
| Config module update | D-2: Env var coordination | Remove `EWS_SERVER`; update Task Scheduler task definition; update `.env.example` |
| Test suite update | D-4: Stale mocks | Replace exchangelib mocks with Graph JSON fixtures; add pagination test |
| Infrastructure setup | Mi-4: Propagation delay | Build wait time into deployment plan after IT grants permissions |
| Deployment to Windows Server | D-3: Enterprise proxy | Test auth + Graph calls on deployment server before go-live |
| Production cutover | D-5: Rollback plan; D-1: Token cache | Document rollback steps; tag pre-migration commit; consider dual-mode validation period |

---

## Sources

- [Authentication differences EWS vs Microsoft Graph](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-authentication) — HIGH confidence, official docs
- [Migrate EWS apps to Microsoft Graph overview](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-overview) — HIGH confidence, official docs
- [EWS to Microsoft Graph API mappings](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-api-mapping) — HIGH confidence, official docs
- [user: sendMail API reference](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0) — HIGH confidence, official docs
- [Send Outlook messages from another user](https://learn.microsoft.com/en-us/graph/outlook-send-mail-from-other-user) — HIGH confidence, official docs
- [List messages API reference](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0) — HIGH confidence, official docs
- [message resource type (fields reference)](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0) — HIGH confidence, official docs
- [Paging Microsoft Graph data](https://learn.microsoft.com/en-us/graph/paging) — HIGH confidence, official docs
- [Use the $filter query parameter](https://learn.microsoft.com/en-us/graph/filter-query-parameter) — HIGH confidence, official docs
- [Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling) — HIGH confidence, official docs
- [RBAC for Applications in Exchange Online](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac) — HIGH confidence, official Exchange docs (updated 2025-11-25)
- [Obtain immutable identifiers for Outlook resources](https://learn.microsoft.com/en-us/graph/outlook-immutable-id) — HIGH confidence, official docs
- [Acquire and cache tokens with MSAL](https://learn.microsoft.com/en-us/entra/identity-platform/msal-acquire-cache-tokens) — HIGH confidence, official docs
- [Secure Access to Mailboxes via Graph — Brian Reid](https://c7solutions.com/2024/09/secure-access-to-mailboxes-via-graph) — MEDIUM confidence, authoritative community source
- [Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference) — HIGH confidence, official docs
- [ReceivedDateTime filter usage Q&A](https://learn.microsoft.com/en-us/answers/questions/768284/how-to-use-receiveddatetime-filter-in-graph-client) — MEDIUM confidence, Microsoft Q&A
