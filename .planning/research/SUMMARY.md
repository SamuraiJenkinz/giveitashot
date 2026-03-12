# Project Research Summary

**Project:** InboxIQ v2.0 — EWS to Microsoft Graph API Migration
**Domain:** Python email daemon / Microsoft 365 REST API migration
**Researched:** 2026-03-12
**Confidence:** HIGH

---

## Executive Summary

InboxIQ v2.0 is a surgical API swap, not a new product. The sole objective is to replace the `exchangelib`-based EWS client with a Microsoft Graph REST client before Microsoft retires EWS for Exchange Online (hard deadline: October 1, 2026). Every line of business logic — the classifier, summarizer, action extractor, email builder, and state manager — is completely untouched. Only 4 source files change: `auth.py` (scope string and return type), `ews_client.py` (replaced by new `graph_client.py`), `main.py` (4 mechanical import and instantiation lines), and `config.py` (remove one unused env var). The `Email` dataclass moves with `graph_client.py` and all downstream consumers need only their import path updated — not their logic.

The recommended implementation approach is direct REST calls using `httpx` (already in requirements.txt) combined with MSAL token acquisition (also already in requirements.txt). Adding the official `msgraph-sdk` would introduce an async-only SDK with a confirmed event loop closure bug for daemon scripts, add 25 MB of generated code for two API calls, and require `azure-identity` as a new dependency. None of that is warranted here. The net dependency change for this migration is: remove `exchangelib`, add zero new packages.

The primary risks in this migration are not in the code — they are in Azure and Exchange permissions setup. Application-level `Mail.Read` and `Mail.Send` permissions grant tenant-wide mailbox access by default, which the Marsh McLennan IT/security team will require scoping via Exchange Online RBAC for Applications or ApplicationAccessPolicy. This must be resolved before any integration testing can begin, and permission propagation takes 30 minutes to 24 hours depending on the mechanism. Code work can proceed in parallel, but integration testing is blocked on permissions. The secondary risks are implementation bugs in the Graph JSON parsing layer, where nested sender and body structures differ from EWS flat attributes, and the OData filter constraint requiring `$filter` and `$orderby` to reference the same property in the same position.

---

## Key Findings

### Recommended Stack

The migration requires zero new dependencies. `exchangelib` is removed. The two libraries already present in `requirements.txt` — `httpx>=0.27.0` and `msal>=1.28.0` — handle all HTTP and authentication needs. The `msgraph-sdk` (v1.55.0, async-only, 25.8 MB wheel) and `azure-identity` (v1.25.2, only needed with the SDK) are explicitly excluded.

**Core technologies:**
- `msal>=1.28.0`: Token acquisition via client credentials flow — same library, same `ConfidentialClientApplication` constructor, scope changes from `https://outlook.office365.com/.default` to `https://graph.microsoft.com/.default`
- `httpx>=0.27.0` / `requests` (transitive): HTTP client for Graph REST calls — synchronous, no event loop management, `requests.Session` pattern for shared headers
- Graph REST API v1.0: Two endpoints — `GET /users/{mailbox}/mailFolders/inbox/messages` and `POST /users/{sender}/sendMail` — both stable, well-documented, simple JSON

**What NOT to add:**
- `msgraph-sdk`: Async-only SDK, known event loop closure bug for daemon scripts (GitHub issue #366, confirmed unresolved), 25.8 MB for 2 endpoints; requires `azure-identity` as a new dependency
- `azure-identity`: Only required by `msgraph-sdk`; MSAL handles all token acquisition directly
- `aiohttp` or async HTTP: InboxIQ is and remains a synchronous Windows Task Scheduler daemon

See `.planning/research/STACK.md` for full rationale.

---

### Expected Features / Operation Mapping

This migration preserves all existing behavior exactly. There are no new user-facing features. All 14 EWS operations used by InboxIQ have confirmed Graph API equivalents.

**Must preserve (table stakes — if any of these break, the migration has failed):**
- Read shared mailbox inbox filtered by received date — `GET /users/{mailbox}/mailFolders/inbox/messages?$filter=receivedDateTime ge {UTC_ISO8601}`
- Order by newest first — `&$orderby=receivedDateTime DESC` (must appear in both `$filter` and `$orderby`)
- Max email limit — `&$top={max_emails}` (explicit; Graph default is 10, not unlimited)
- Retrieve HTML body for LLM summarization — `message["body"]["content"]` (must be in `$select`; not returned by default)
- Sender name and email — `message["from"]["emailAddress"]["name"]` and `["address"]` (nested, not flat)
- Received datetime as UTC-aware datetime — parsed from ISO 8601 `receivedDateTime` string
- `has_attachments` flag — `message["hasAttachments"]` boolean
- Send HTML digest email with TO/CC/BCC — `POST /users/{sender}/sendMail` with JSON body
- SendAs (custom From address) — `"from": {"emailAddress": {"address": "..."}}` in message body
- Save to Sent Items — `saveToSentItems: true` in request body (Graph default)
- App-only client credentials auth — same MSAL flow, different scope

**Behavioral differences (not regressions — things that are now better or simply different):**
- `bodyPreview`: Graph provides a native 255-character plain-text preview natively — use `message["bodyPreview"]` directly; no HTML stripping needed for the preview field
- HTML sanitization: Graph strips unsafe JavaScript from body HTML by default — cleaner input to LLM summarizer with no code change needed
- Pagination: Graph returns 10 messages per page by default; `$top=100` covers InboxIQ's typical volume but a pagination loop for `@odata.nextLink` is required for correctness
- Message ID format: Graph IDs are different strings from EWS IDs; InboxIQ uses only time-based state, so this has zero functional impact
- sendMail returns 202 Accepted (not delivery confirmation) — semantically identical to how EWS always worked

**Anti-features (do not build during this migration):**
- `msgraph-sdk` async adoption — requires full async rewrite of `main.py`, out of scope
- Graph delta query / incremental sync tokens — existing `StateManager` is correct and working
- Exchange RBAC mailbox scoping — valid security hardening, post-migration task, not a prerequisite
- Webhook/push notifications — InboxIQ uses polling (Task Scheduler), switching models is out of scope
- Immutable message IDs — ID format change has zero functional impact on InboxIQ

See `.planning/research/FEATURES.md` for the full EWS-to-Graph operation mapping table.

---

### Architecture Approach

The migration is a single-component swap within an existing clean layered architecture. The pipeline (classify → split → summarize → format → send → update state) is completely unchanged. Only the data source layer changes. The `Email` dataclass is the central integration contract — it has identical fields and types before and after migration, so all downstream modules require only an import path update, not logic changes.

**Component change map:**

| Component | Action | Estimated effort |
|-----------|--------|------------------|
| `src/auth.py` | Rename class, change scope string, change return type to `str` | ~1 hour |
| `src/ews_client.py` | Replace entirely with new `src/graph_client.py` | 4-6 hours |
| `src/main.py` | 4 mechanical line swaps (imports, instantiation, error handler rename) | 30 min |
| `src/config.py` | Remove `EWS_SERVER` field | 15 min |
| `tests/conftest.py` | Update 1 import path | 5 min |
| `tests/test_*.py` | Update import path(s) per file | 5 min each |
| `tests/test_graph_client.py` | New file — Graph JSON mock tests | 2-4 hours |

**Recommended build order (dependency-driven — each step independently testable):**
1. `auth.py` — validate token acquisition in isolation first; unblocks everything else
2. `graph_client.py` — core deliverable; unit tests with mocked HTTP + live smoke test
3. `config.py` — pure deletion cleanup, no risk
4. `main.py` — mechanical wiring, depends on steps 1 and 2
5. Test import updates — unlock existing regression suite
6. `test_graph_client.py` — new Graph JSON parsing coverage

**Public interface contract (unchanged — drop-in replacement):**

```python
# GraphClient exposes exactly the same interface as EWSClient:
get_shared_mailbox_emails(mailbox: str, since: datetime | None, max_emails: int) -> list[Email]
send_email(to, subject, body_html, cc=None, bcc=None) -> None

# Email dataclass: identical fields, identical types, identical semantics
# Only the import path changes: from src.ews_client → from src.graph_client
```

**Test strategy:** The existing test suite is structured around the `Email` dataclass, not EWS internals. After updating the import path in `conftest.py`, all existing tests must pass unchanged — this is the primary regression guard. New tests in `test_graph_client.py` cover the Graph JSON parsing layer that the existing suite does not exercise.

See `.planning/research/ARCHITECTURE.md` for the full component diagram, implementation patterns, and test strategy.

---

### Critical Pitfalls

Top 7 pitfalls in priority order — 5 will cause hard failures, 2 will cause silent data loss:

1. **Wrong MSAL token scope (C-1) — hard failure.** Using the current EWS scope (`outlook.office365.com/.default`) against Graph endpoints returns HTTP 401 immediately because the JWT audience claim does not match. The MSAL call appears to succeed, making this particularly deceptive. Fix: change the scope constant in `auth.py` before writing any other Graph code. Validate by decoding the resulting JWT at jwt.io and confirming `aud` is `https://graph.microsoft.com/`.

2. **Tenant-wide mailbox access by default (C-2) — security/approval blocker.** `Mail.Read` application permission grants read access to every mailbox in the mmc.com tenant, not just the shared mailbox. IT/security will block this or require scoping. Fix: coordinate ApplicationAccessPolicy or Exchange RBAC for Applications scoping with the IT admin before any testing in a real environment. This is a deployment prerequisite, not optional post-migration hardening.

3. **Using `/me/sendMail` in app-only flow (C-3) — hard failure.** `/me` resolves to the authenticated user; in client credentials flow there is no user. Returns 401 even when `Mail.Send` is granted. Fix: always use `/users/{id}/sendMail` in `graph_client.py` and add an inline comment explaining why `/me` is prohibited.

4. **Missing pagination loop (M-1) — silent data loss.** Graph defaults to 10 results per page. Without following `@odata.nextLink`, the hourly digest silently processes at most 10 emails regardless of actual inbox volume — no errors, just missing emails. Fix: implement `while url: ... url = data.get("@odata.nextLink")` in `get_shared_mailbox_emails`; set `params = None` on the second iteration.

5. **Wrong OData filter/orderby syntax (M-2 + M-3) — hard failure or wrong results.** Date values must be UTC ISO 8601 without quotes (`receivedDateTime ge 2026-03-12T10:00:00Z`). When using both `$filter` and `$orderby` on `receivedDateTime`, the property must appear in both — violating this returns `InefficientFilter` 400. Using local time without UTC conversion silently returns wrong results. Fix: always format datetimes as `since.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')`.

6. **Nested JSON field access vs EWS flat attributes (M-4, M-5) — `KeyError` on parse.** EWS uses `item.sender.name`; Graph uses `message["sender"]["emailAddress"]["name"]`. EWS body is `str(item.body)`; Graph body is `message["body"]["content"]`. `body` is not returned by default in list calls and must be in `$select`. Fix: use defensive nested dict access (`.get()` chains); always include `body` in `$select`.

7. **Stale test suite passes but does not test Graph behavior (D-4) — false safety.** After migrating, exchangelib mocks continue to pass because they mock the old interface. A broken `graph_client.py` will fail zero existing tests. Fix: update `conftest.py` fixtures to Graph-shaped JSON dicts before submitting `graph_client.py` for review; treat any existing test failure after the import path change as a regression signal.

See `.planning/research/PITFALLS.md` for the full pitfall catalog with code examples and phase warnings.

---

## Implications for Roadmap

Research suggests a 4-phase structure driven by the dependency chain, the permissions-are-the-critical-path finding, and the risk profile.

### Phase 1: Permissions and Infrastructure Setup

**Rationale:** The highest-risk item in this migration is not code — it is Azure/Exchange permissions. Admin consent for `Mail.Read` and `Mail.Send` application permissions, plus mailbox scoping, involves IT/security approval and propagation delays (up to 24 hours for ApplicationAccessPolicy, 30 minutes to 2 hours for RBAC for Applications). This cannot be accelerated by a developer and must start first. Code work for Phase 2 can proceed in parallel, but no integration testing is possible until this phase completes.
**Delivers:** App registration with Graph application permissions (`Mail.Read`, `Mail.Send`) granted with admin consent; Exchange RBAC scoping to shared mailbox configured; verified token acquisition returning a valid Graph-audience JWT; rollback plan documented
**Addresses:** Pitfall C-2 (tenant-wide access default), C-5 (Application vs Delegated permission type), Mi-4 (propagation delay)
**Research flag:** The specific Marsh McLennan tenant configuration is unknown — clarify with IT admin whether ApplicationAccessPolicy or Exchange RBAC for Applications is preferred before starting. Both paths are documented with PowerShell commands in STACK.md.

---

### Phase 2: Core Client Implementation

**Rationale:** Once auth is unblocked (or proceeding optimistically with mocked tokens), `auth.py` and `graph_client.py` are the primary engineering deliverables. Build and unit-test in isolation before wiring into `main.py`. The build order within this phase is: auth module first (validates token acquisition), then the Graph client (uses the token, implements both operations). Unit tests use mocked HTTP and do not require live permissions — they can be written before Phase 1 completes.
**Delivers:** `src/auth.py` (GraphAuthenticator, scope updated, returns raw Bearer token string), `src/graph_client.py` (GraphClient with `get_shared_mailbox_emails` and `send_email`, Email dataclass, pagination loop, OData filter, nested JSON field mapping, GraphClientError), `tests/test_graph_client.py` (mocked HTTP unit tests for all behaviors)
**Uses:** `msal`, `httpx`/`requests`, Graph REST v1.0 endpoints
**Implements:** Data source layer — the only new code in the migration
**Avoids:** C-1 (scope), M-1 (pagination), M-2+M-3 (date filter and orderby), M-4+M-5 (nested JSON), C-3+C-4 (send endpoint and from field)
**Research flag:** No additional research needed — all endpoints, field structures, and patterns are fully documented in FEATURES.md and ARCHITECTURE.md with HIGH confidence official sources.

---

### Phase 3: Integration and Wiring

**Rationale:** Once `graph_client.py` has passing unit tests, the remaining changes are mechanical. `main.py` requires 4 line changes. `config.py` requires 1 deletion. This phase also finalizes the test layer: update import paths so the existing 167-test suite runs against the new module, and confirm all tests pass without logic changes.
**Delivers:** Updated `src/main.py` (import swaps, instantiation change, error handler rename), updated `src/config.py` (EWS_SERVER removed), all test import paths updated (`conftest.py` and any other files importing from `src.ews_client`), full test suite green
**Avoids:** D-4 (stale test suite), D-2 (env var coordination — update `.env.example` and Task Scheduler definition)
**Research flag:** No research needed — purely mechanical changes.

---

### Phase 4: Validation and Production Cutover

**Rationale:** Before replacing EWS in production, run a parallel validation period: execute both clients against the same mailbox and compare email counts and field values. This requires Phase 1 to be complete (live permissions) and Phase 3 to be complete (fully wired codebase). Cut over on a low-volume window, monitor for one complete hourly cycle, and document the rollback procedure before decommissioning EWS resources.
**Delivers:** Parallel comparison validation script (temporary, run once), successful production cutover, rollback procedure documented (`git tag pre-graph-migration` applied), `EWS.AccessAsApp` permission removed from Entra app registration after stable period, `ews_client.py` archived in git (not deleted until 2+ weeks of stable production)
**Avoids:** D-5 (no rollback plan), D-3 (enterprise proxy — test on production Windows Server before go-live), D-1 (token cache — optionally wire `SerializableTokenCache` during this phase)
**Research flag:** No research needed — operational deployment patterns are well-defined.

---

### Phase Ordering Rationale

- Phase 1 must start first because IT/security approval and permission propagation are on the critical path and cannot be accelerated by technical work alone.
- Phase 2 can begin before Phase 1 completes. Unit tests use mocked HTTP and do not require live permissions. Integration smoke testing (live mailbox call) is blocked on Phase 1 completion.
- Phase 3 is gated on Phase 2 producing a working `graph_client.py` — the import path changes require the new file to exist.
- Phase 4 requires both Phase 1 (production environment unblocked) and Phase 3 (fully wired codebase) to be complete.
- Total estimated effort: ~10-15 engineering hours across Phases 2 and 3. Elapsed calendar time is largely determined by the IT/security approval process in Phase 1.

### Research Flags

**Phases with well-documented patterns — no additional research-phase needed:**
- Phase 2: All Graph REST endpoints, OData parameters, JSON field structures, MSAL token patterns, and pagination behavior are documented in the research files with HIGH confidence from official Microsoft sources.
- Phase 3: Mechanical changes with no new APIs or patterns.
- Phase 4: Standard deployment and validation practices.

**Phase that may need operational verification:**
- Phase 1: The exact Marsh McLennan tenant configuration is unknown. Verify with IT admin which mailbox scoping mechanism is in use (ApplicationAccessPolicy vs Exchange RBAC for Applications) before choosing the PowerShell approach. The technical research is complete; the uncertainty is organizational.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations verified against official Microsoft documentation. Zero new dependencies is definitive. The `msgraph-sdk` async limitation is a confirmed, unresolved open GitHub issue as of 2026-03-12. |
| Features | HIGH | EWS-to-Graph operation mapping sourced from the official Microsoft EWS migration mapping documentation. All 14 operations have confirmed Graph equivalents with specific endpoint and field mapping. |
| Architecture | HIGH | Scope of changes determined by reading actual InboxIQ source code alongside official Graph API docs. The 4-file migration scope is confirmed by direct code analysis, not inference. |
| Pitfalls | HIGH | All critical pitfalls verified against official Microsoft documentation. The tenant-wide access risk (C-2) is documented default behavior. Propagation delay timings sourced from official RBAC for Applications docs updated 2025-11-25. |

**Overall confidence:** HIGH

The research quality for this migration is unusually strong because: (a) the Graph API is mature and extensively documented, (b) Microsoft provides an official EWS-to-Graph migration guide with explicit operation mappings, (c) the actual InboxIQ source code was read during architecture research to confirm the exact change scope, and (d) all four research dimensions agree on the same low-complexity migration scope. The remaining uncertainty is organizational (IT/security approval process and tenant configuration), not technical.

### Gaps to Address

- **Marsh McLennan tenant permission scoping approach:** It is unknown whether the mmc.com tenant already has ApplicationAccessPolicy configured for the existing EWS app registration, and which scoping mechanism IT/security prefers for Graph. Clarify with the admin before Phase 1 begins. Both ApplicationAccessPolicy and Exchange RBAC for Applications are documented with PowerShell commands in STACK.md — the choice affects only which commands are run.

- **`Config.USER_EMAIL` semantics post-migration:** In EWS, `USER_EMAIL` was the impersonation identity used to open an EWS account object. In Graph, it becomes the URL path component for `sendMail` (`/users/{USER_EMAIL}/sendMail`). If `USER_EMAIL` differs from the shared mailbox address, verify that `Mail.Send` is correctly granted and that `Config.get_send_from()` correctly maps to the `from` field. Validate in the Phase 4 smoke test with a live send.

- **Enterprise proxy on the deployment Windows Server:** The production environment has not been tested for direct reachability to `login.microsoftonline.com` and `graph.microsoft.com`. If a corporate proxy is required, it must be configured in both the MSAL `ConfidentialClientApplication` (via `proxies` parameter) and the `requests.Session`. Test this during Phase 4 on the actual Windows Server deployment target before declaring go-live readiness.

- **Token cache file wiring (optional improvement):** `config.py` defines `TOKEN_CACHE_FILE` but `auth.py` does not use it. For a Windows Task Scheduler daemon that creates a new Python process each hourly run, wiring `SerializableTokenCache` to this file would make the MSAL token persist across process restarts, avoiding a round-trip to `login.microsoftonline.com` on every execution. This is not a migration blocker — tokens will be acquired fresh each run and it works correctly. Decide whether to include this in Phase 2 or treat it as a separate follow-up ticket.

---

## Sources

### Primary (HIGH confidence — official Microsoft documentation)

- [EWS to Microsoft Graph API mappings](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-api-mapping) — complete operation-level mapping table
- [Authentication differences EWS vs Graph](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-authentication) — scope, token audience differences
- [Migrate EWS apps to Microsoft Graph overview](https://learn.microsoft.com/en-us/graph/migrate-exchange-web-services-overview) — migration guidance, EWS retirement deadline (Oct 1, 2026)
- [List messages API reference (v1.0)](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0) — endpoint, OData parameters, pagination, InefficientFilter error
- [sendMail API reference (v1.0)](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0) — request body structure, from/cc/bcc fields, 202 response
- [Message resource type (v1.0)](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0) — all field names, nesting structure, types, bodyPreview behavior
- [Send mail from another user](https://learn.microsoft.com/en-us/graph/outlook-send-mail-from-other-user) — SendAs pattern, from vs sender distinction, app-only behavior
- [Shared/delegated folder access](https://learn.microsoft.com/en-us/graph/outlook-share-messages-folders) — app-only mailbox access via `/users/{email}` path
- [Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference) — Mail.Read application vs delegated; Mail.Read.Shared delegated-only clarification
- [RBAC for Applications in Exchange Online](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac) — mailbox scoping, replaces ApplicationAccessPolicy, propagation delays (updated 2025-11-25)
- [Paging Microsoft Graph data](https://learn.microsoft.com/en-us/graph/paging) — nextLink pagination, do not reconstruct URL
- [Use the $filter query parameter](https://learn.microsoft.com/en-us/graph/filter-query-parameter) — OData filter syntax, UTC datetime requirement
- [Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling) — 429 handling, Retry-After header
- [Acquire and cache tokens with MSAL](https://learn.microsoft.com/en-us/entra/identity-platform/msal-acquire-cache-tokens) — SerializableTokenCache, process-restart persistence
- [Build Python apps with Microsoft Graph (app-only)](https://learn.microsoft.com/en-us/graph/tutorials/python-app-only) — app-only auth patterns confirmed
- [msgraph-sdk PyPI (v1.55.0, released 2026-02-20)](https://pypi.org/project/msgraph-sdk/) — SDK version, async-only design confirmed, dependency weight
- [azure-identity PyPI (v1.25.2, released 2026-02-11)](https://pypi.org/project/azure-identity/) — dependency only required for SDK route
- [Obtain immutable identifiers for Outlook resources](https://learn.microsoft.com/en-us/graph/outlook-immutable-id) — Graph ID format, ImmutableId opt-in

### Secondary (MEDIUM confidence — verified from multiple sources)

- [Access Shared Mailbox via Graph API — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/1406369/access-shared-mailbox-via-graph-api) — `/users/{sharedMailbox}/messages` pattern for application permissions confirmed
- [Permissions to access shared mailbox — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2149155/permissions-to-access-shared-mailbox-to-read-and-s) — Mail.Read application permission works for shared mailboxes via `/users/{mailbox}`
- [Using sendMail with application permissions — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2225484/using-sendmail-in-graph-api-with-application-permi) — `/users/{id}/sendMail` for app-only; `/me` prohibition explained
- [ReceivedDateTime filter usage — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/768284/how-to-use-receiveddatetime-filter-in-graph-client) — OData datetime format examples
- [Secure Access to Mailboxes via Graph — Brian Reid, c7solutions.com](https://c7solutions.com/2024/09/secure-access-to-mailboxes-via-graph) — Exchange RBAC for Applications implementation guidance
- [Refreshing MSAL access tokens using Token Cache — Beringer](https://www.beringer.net/beringerblog/refreshing-msal-access-tokens-using-token-cache/) — SerializableTokenCache implementation examples

### Tertiary (LOW confidence — verify before using)

- [msgraph-sdk asyncio event loop issue — GitHub issue #366](https://github.com/microsoftgraph/msgraph-sdk-python/issues/366) — event loop closure bug for daemon script pattern; status unresolved as of 2026-03-12; verify if SDK route is reconsidered

---

*Research completed: 2026-03-12*
*Ready for roadmap: yes*
