---
phase: 07-graph-client
plan: 01
subsystem: api
tags: [graph-api, requests, email, http-client, odata, pagination, retry, dataclass]

dependency-graph:
  requires:
    - phase: 06-auth-foundation
      provides: "GraphAuthenticator.get_access_token() returning a Bearer token string"
    - phase: 01-foundation
      provides: "Email dataclass contract consumed by classifier, summarizer, extractor"
  provides:
    - Email dataclass (identical field contract to ews_client.py)
    - GraphClient class with complete read path (fetch, OData filter, pagination, field mapping)
    - GraphClientError exception class
    - requests>=2.32.5 dependency in requirements.txt
  affects:
    - Phase 07 Plan 02: send_email() will be added to GraphClient
    - Phase 08: import rewiring from ews_client.Email/EWSClient to graph_client.Email/GraphClient

tech-stack:
  added:
    - requests>=2.32.5 (Graph REST API HTTP client)
  patterns:
    - Single _make_request() helper with retry loop (429/5xx Retry-After, 401 silent re-auth)
    - OData $filter + $orderby on receivedDateTime (must match to avoid InefficientFilter)
    - @odata.nextLink pagination (params=None after first request to avoid param duplication)
    - internetMessageId as Email.id primary (stable RFC2822 ID, not Graph's folder-specific id)
    - HTML fetch + local _strip_html() (preserves exact classifier/summarizer input format)

key-files:
  created:
    - src/graph_client.py
  modified:
    - requirements.txt

key-decisions:
  - "HTML body fetched from Graph and stripped locally via _strip_html() (copied verbatim from ews_client.py) — preserves exact format downstream consumers (classifier, summarizer) have always received"
  - "Email.id uses internetMessageId as primary, falls back to Graph internal id — internetMessageId is RFC2822-stable across folder moves"
  - "Retry-After header respected as integer seconds (Graph documented behaviour); exponential backoff (2^attempt) used when header absent"
  - "params=None set after first pagination request — @odata.nextLink is a complete URL with all query params embedded; duplicate params cause 400 errors"

patterns-established:
  - "GraphClient._make_request(): fetch fresh token per retry attempt, 401 triggers silent re-auth (MSAL handles caching)"
  - "get_shared_mailbox_emails(): OData $filter receivedDateTime ge {since} + $orderby receivedDateTime desc (same property in both, satisfies Graph constraint)"
  - "_parse_message(): always use .get() with safe defaults; invalid emails skip with warning, never crash"

metrics:
  duration: "2 minutes"
  completed: "2026-03-13"
---

# Phase 07 Plan 01: Graph Client Read Path Summary

**GraphClient with OData-filtered pagination reads emails from shared mailbox via Graph v1.0 REST API, preserving the exact Email dataclass contract that classifier, summarizer, and extractor depend on.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-13T19:14:31Z
- **Completed:** 2026-03-13T19:16:35Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `src/graph_client.py` with Email dataclass (field-for-field identical to `ews_client.py`), GraphClientError, and GraphClient class
- Implemented complete read path: `get_shared_mailbox_emails()` with OData `$filter`/`$select`/`$orderby`/`$top`, retry loop with Retry-After, and `@odata.nextLink` pagination
- Added `requests>=2.32.5` to `requirements.txt`; all 178 existing tests still pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create graph_client.py with Email dataclass, GraphClientError, and HTTP infrastructure** - `dafc4e1` (feat)
2. **Task 2: Add requests dependency to requirements.txt** - `132fe9c` (chore)

## Files Created/Modified

- `src/graph_client.py` — Email dataclass, GraphClientError, GraphClient with _make_request() retry, get_shared_mailbox_emails() with OData filter + pagination, _parse_message(), _strip_html(), _parse_datetime()
- `requirements.txt` — Added `requests>=2.32.5` between exchangelib and msal entries

## Decisions Made

**1. Body content: HTML fetch + local strip**
Fetch `body.contentType=html` (Graph default) and run `_strip_html()` (copied verbatim from `ews_client.py`) rather than using Graph's `Prefer: outlook.body-content-type="text"` header. Rationale: local stripping preserves the exact whitespace-normalized plain-text format the classifier and summarizer have been tested against. Server-side text conversion uses different normalization.

**2. Email.id: internetMessageId primary**
`internetMessageId` (RFC2822 Message-ID header) used as `Email.id`, falling back to Graph's internal `id`. Rationale: Graph's internal `id` changes when a message is moved between folders; `internetMessageId` is stable across moves and cross-system traceable.

**3. Retry-After as integer seconds**
`int(response.headers.get("Retry-After", 2 ** attempt))` — Graph throttling docs specify integer seconds in the header. Exponential fallback used when header is absent.

**4. params=None after first page**
After following the first URL with query params, set `params = None` so subsequent `@odata.nextLink` URLs are followed as-is. The nextLink is a complete URL; passing params again would duplicate query parameters and cause 400 errors.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required for this plan. Integration testing requires Azure app `Mail.Read` permission with admin consent (pre-existing blocker from Phase 6).

## Next Phase Readiness

**Plan 02 (send path)** can now proceed:
- `GraphClient` class exists with `_make_request()` helper ready for POST calls
- `_raise_graph_error()` helper ready for send error handling
- `requests.Session` created in `__init__` — POST will reuse it

**Phase 08 (cutover)** will:
- Rewire `from .ews_client import Email, EWSClient` → `from .graph_client import Email, GraphClient`
- Remove `ews_client.py`
- Remove `exchangelib` from `requirements.txt`

---
*Phase: 07-graph-client*
*Completed: 2026-03-13*
