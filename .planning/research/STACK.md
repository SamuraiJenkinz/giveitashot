# Stack Research: Graph API Migration

**Project:** InboxIQ v2.0 — EWS to Microsoft Graph API Migration
**Researched:** 2026-03-12
**Scope:** Stack additions/changes required to replace exchangelib with Graph API
**Overall Confidence:** HIGH

---

## Recommended Stack Changes

### Summary

| Change | Action | Reason |
|--------|--------|--------|
| `exchangelib` | REMOVE | Being replaced entirely |
| `msal` | KEEP, re-scope | Same library, different token scope |
| `httpx` | KEEP, repurpose | Already in requirements, used for Graph REST calls |
| `azure-identity` | DO NOT ADD | SDK route not recommended (see below) |
| `msgraph-sdk` | DO NOT ADD | Async-only SDK has friction in sync daemon scripts |

### Net result: zero new dependencies

The migration replaces `exchangelib` with direct Graph REST calls using `httpx` (already present at `>=0.27.0`) and MSAL for token acquisition (already present at `>=1.28.0`). No packages are added; one package is removed.

---

## Microsoft Graph SDK vs Direct REST

**Recommendation: Use direct REST calls via httpx + MSAL. Do not add msgraph-sdk.**

### Why Not msgraph-sdk (1.55.0, released 2026-02-20)

The official Microsoft Graph Python SDK (`msgraph-sdk`) is async-first by design. This is correct for web apps and services, but creates genuine friction for InboxIQ's use case: a synchronous daemon script invoked by Windows Task Scheduler.

**The core problem — asyncio event loop management:**

The SDK provides only an async API. Daemon scripts must wrap calls with `asyncio.run()`, but a known SDK issue (GitHub issue #366, confirmed still open as of 2025) causes failures when multiple `asyncio.run()` calls are made in sequence: the event loop is closed after the first call, and all subsequent calls raise `RuntimeError: Event loop is closed`. The workaround is to manage a persistent event loop manually — which defeats the simplicity benefit of using the SDK.

**Additional SDK concerns:**

- Package size: 25.8 MB wheel with hundreds of generated model files for every Graph API resource. InboxIQ uses two endpoints: list messages and send mail. This is significant overhead.
- Requires `azure-identity` as a new dependency (the SDK does not integrate directly with the existing `msal` token acquisition; it uses `ClientSecretCredential` from `azure-identity`).
- Kiota-generated client adds an abstraction layer that is harder to debug and test than plain HTTP calls.

### Why Direct REST via httpx + MSAL Works Well

**httpx is already present.** The existing `requirements.txt` already pins `httpx>=0.27.0`. InboxIQ already uses it as a transitive dependency via `openai`. Zero new installation required.

**MSAL already handles the token.** The current `EWSAuthenticator` class acquires tokens via `msal.ConfidentialClientApplication.acquire_token_for_client()`. The only change is the scope: `https://outlook.office365.com/.default` (EWS) becomes `https://graph.microsoft.com/.default` (Graph). The token caching, silent refresh, and error handling code remain identical.

**Graph REST API is stable and simple for this use case.** InboxIQ needs two operations:

| Operation | Endpoint | Complexity |
|-----------|----------|------------|
| Read inbox | `GET /v1.0/users/{mailbox}/messages` | Low — filter, select, top, orderby |
| Send mail | `POST /v1.0/users/{sender}/sendMail` | Low — JSON body with to/cc/bcc/from |

Both are covered by a single Bearer token header and straightforward JSON. No pagination complexity for InboxIQ's typical volume (hourly batches, ~100 email max).

**Synchronous code stays synchronous.** No event loop management, no `asyncio.run()`, no `await`. The replacement `GraphClient` class is a drop-in synchronous wrapper — matching the existing `EWSClient` contract exactly.

---

## Authentication (MSAL Integration)

### What Changes

The existing `EWSAuthenticator` in `src/auth.py` is 90% reusable. Only the token scope changes.

| Aspect | Current (EWS) | New (Graph) |
|--------|---------------|-------------|
| MSAL class | `ConfidentialClientApplication` | Same |
| Flow | `acquire_token_for_client` | Same |
| Cache | Silent refresh via `acquire_token_silent` | Same |
| Scope | `https://outlook.office365.com/.default` | `https://graph.microsoft.com/.default` |
| Credentials | CLIENT_ID, CLIENT_SECRET, TENANT_ID | Same values |

The `EWSAuthenticator.get_ews_credentials()` method (which constructs `OAuth2Credentials` for exchangelib) is removed. Its replacement is a `get_access_token()` method that returns a raw Bearer token string — which is exactly what `httpx` requests need.

### Token Use Pattern

```python
# src/auth.py — no structural change needed
class GraphAuthenticator:
    SCOPES = ["https://graph.microsoft.com/.default"]

    def get_access_token(self) -> str:
        result = self.app.acquire_token_silent(scopes=self.SCOPES, account=None)
        if not result:
            result = self.app.acquire_token_for_client(scopes=self.SCOPES)
        # error handling identical to current code
        return result["access_token"]

# src/graph_client.py — usage
headers = {"Authorization": f"Bearer {self._auth.get_access_token()}"}
response = self._http.get(url, headers=headers, params=params)
```

### App Registration Changes (Exchange Side)

The same Entra app registration is used. No new app registration is needed. The admin adds Graph permissions to the existing registration:

1. In Azure Portal > App Registrations > [existing app] > API Permissions:
   - Add `Mail.Read` (Application) — for reading shared mailbox
   - Add `Mail.Send` (Application) — for sending digest emails
   - Grant admin consent for both

2. Optionally (recommended for Marsh McLennan's security posture): Configure Exchange Online RBAC for Applications to scope access to the specific shared mailbox only (see Permissions section below).

The existing `EWS.AccessAsApp` permission on the app registration can be removed once the migration is complete.

### azure-identity Is NOT Required

The `azure-identity` package (`ClientSecretCredential`) is required only when using the `msgraph-sdk` SDK. For direct REST calls with MSAL token acquisition, `azure-identity` adds nothing and should not be added.

**Confidence:** HIGH — verified against Microsoft official authentication provider documentation and MSAL Python documentation.

---

## Required Graph API Permissions

### Minimum Permissions (Entra App Registration)

| Permission | Type | Purpose | Confidence |
|------------|------|---------|------------|
| `Mail.Read` | Application | Read emails from shared mailbox inbox | HIGH |
| `Mail.Send` | Application | Send digest emails as/from configured sender | HIGH |

Both require admin consent. Both are Application permissions (not Delegated) — correct for daemon/service apps using client credentials flow.

### Important: Mail.Read.Shared Does NOT Apply

`Mail.Read.Shared` is a **delegated** permission only. It does not function with application (client credentials) tokens. With application `Mail.Read`, the app can access any mailbox in the tenant using `/users/{mailbox}/messages`. This is the correct approach for InboxIQ.

**Confidence:** HIGH — verified against Microsoft Graph permissions reference and multiple Q&A answers on Microsoft Learn.

### Sending As the Shared Mailbox (SendAs)

The current EWS implementation uses `author=Mailbox(email_address=send_from)` to send from a configured "from" address (which may differ from the authenticated user account — this is the `SEND_FROM` / `USER_EMAIL` config split).

In Graph, the equivalent is setting the `from` property in the message JSON:

```json
{
  "message": {
    "from": { "emailAddress": { "address": "shared-mailbox@mmc.com" } },
    "toRecipients": [...],
    "subject": "...",
    "body": { "contentType": "HTML", "content": "..." }
  }
}
```

The endpoint used is `POST /v1.0/users/{sender_upn}/sendMail` where `sender_upn` is the authenticated app's configured sender identity (equivalent to `Config.USER_EMAIL`). Setting `from` to a different address requires that the sender has SendAs or Send on Behalf permission for that address in Exchange Online — the same requirement as EWS. No new Exchange delegation setup is needed if it already works with EWS.

**Confidence:** HIGH — verified against official Microsoft Graph documentation on sending from another user.

### Scoping Access to Specific Mailboxes (Optional but Recommended)

By default, `Mail.Read` application permission grants access to all mailboxes in the tenant. For Marsh McLennan's environment, consider configuring Exchange Online RBAC for Applications to scope the app to only the specific shared mailbox:

```powershell
# Run in Exchange Online PowerShell
New-ServicePrincipal -AppId <CLIENT_ID> -ObjectId <SERVICE_PRINCIPAL_OBJECT_ID> -DisplayName "InboxIQ"
New-ManagementScope -Name "InboxIQ-Mailbox" -RecipientRestrictionFilter "PrimarySmtpAddress -eq 'shared@mmc.com'"
New-ManagementRoleAssignment -App <SERVICE_PRINCIPAL_OBJECT_ID> -Role "Application Mail.Read" -CustomResourceScope "InboxIQ-Mailbox"
New-ManagementRoleAssignment -App <SERVICE_PRINCIPAL_OBJECT_ID> -Role "Application Mail.Send" -CustomResourceScope "InboxIQ-Mailbox"
```

Note: After scoping via Exchange RBAC, the broad `Mail.Read` and `Mail.Send` grants in Entra ID must also be removed (otherwise they override the scope). RBAC for Applications replaces the deprecated Application Access Policies.

**Confidence:** HIGH — verified against official Exchange Online RBAC for Applications documentation (updated 2026-02-27).

---

## What NOT to Add

### Do Not Add: msgraph-sdk (1.55.0)

**Why:** Async-only SDK with a known event loop closure bug for synchronous callers (GitHub issue #366). Adds 25.8 MB of generated code for two API calls. Requires `azure-identity` as a new dependency. No advantage over httpx + MSAL for this use case.

**When to reconsider:** If InboxIQ were rewritten as an async application, or if the scope of Graph API calls expanded substantially beyond email read/send.

### Do Not Add: azure-identity (1.25.2)

**Why:** Only needed as the credential provider for `msgraph-sdk`. With direct REST calls, MSAL handles token acquisition entirely. Adding `azure-identity` alongside `msal` duplicates authentication responsibility and adds confusion about which library owns tokens.

### Do Not Add: requests

**Why:** httpx is already present and is the superior choice — it supports both sync and async, has a cleaner API, and is already used by the `openai` package in the dependency tree. Adding `requests` would be a redundant HTTP library.

### Do Not Add: aiohttp

**Why:** InboxIQ is a synchronous daemon script. Adding an async HTTP library has no benefit and adds complexity.

### Do Not Add: msgraph-beta-sdk

**Why:** All required endpoints (`/messages`, `/sendMail`) are stable v1.0 endpoints. Beta SDK should not be used in production tooling.

---

## Sources

### HIGH Confidence (Official Documentation)

- [msgraph-sdk PyPI — version 1.55.0, released 2026-02-20](https://pypi.org/project/msgraph-sdk/) — Current version confirmed
- [azure-identity PyPI — version 1.25.2, released 2026-02-11](https://pypi.org/project/azure-identity/) — Current version confirmed
- [Choose a Microsoft Graph authentication provider — Microsoft Learn](https://learn.microsoft.com/en-us/graph/sdks/choose-authentication-providers) — Confirmed client credentials flow uses `ClientSecretCredential` from `azure-identity` with the SDK; also confirmed MSAL is the underlying implementation
- [Send Outlook messages from another user — Microsoft Graph docs](https://learn.microsoft.com/en-us/graph/outlook-send-mail-from-other-user) — Confirmed `from` property behavior, SendAs vs application permission distinction, endpoint for app-only: `/users/{user-id}/sendMail`
- [Role Based Access Control for Applications in Exchange Online — Microsoft Learn](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac) — Confirmed RBAC for Applications replaces Application Access Policies; PowerShell commands for scoping; updated 2026-02-27
- [Add email capabilities to Python apps — Microsoft Graph tutorials](https://learn.microsoft.com/en-us/graph/tutorials/python-email) — Confirmed SDK message reading and sending patterns
- [Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference) — Confirmed Mail.Read.Shared is delegated-only; Mail.Read application permission works for shared mailboxes via `/users/{mailbox}`

### MEDIUM Confidence (Verified from Multiple Sources)

- [Access Shared Mailbox via Graph API — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/1406369/access-shared-mailbox-via-graph-api) — Confirmed endpoint pattern `users/{sharedmailboxaddress}/messages` for application permissions
- [Permissions to access shared mailbox to read and send — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2149155/permissions-to-access-shared-mailbox-to-read-and-s) — Confirmed Mail.Read application permission with client credentials works for shared mailboxes

### LOW Confidence (Inform Decisions, Verify Before Implementing)

- [asyncio.run() event loop issue — GitHub issue #366](https://github.com/microsoftgraph/msgraph-sdk-python/issues/366) — Community-reported issue; status as of research is unresolved for daemon script pattern. Verify before choosing SDK route.
- [Why use Microsoft Graph SDK — Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-cloud/dev/dev-proxy/concepts/why-use-microsoft-graph-sdk) — SDK benefits list; applicable to larger scope use cases than InboxIQ
