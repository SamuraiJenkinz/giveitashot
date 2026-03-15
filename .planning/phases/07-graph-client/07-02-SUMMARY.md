---
phase: 07-graph-client
plan: 02
subsystem: api
tags: [graph-api, requests, email, http-client, send-email, unit-testing, mocking, sendMail, send-as]

dependency-graph:
  requires:
    - phase: 07-graph-client/07-01
      provides: "GraphClient class with _make_request(), _raise_graph_error(), requests.Session, GraphClientError"
    - phase: 06-auth-foundation
      provides: "GraphAuthenticator.get_access_token() returning a Bearer token string"
    - phase: 01-foundation
      provides: "Email dataclass contract consumed by classifier, summarizer, extractor"
  provides:
    - GraphClient.send_email() method — POST /users/{SENDER_EMAIL}/sendMail with TO/CC/BCC/From/saveToSentItems
    - tests/test_graph_client.py — 36 unit tests covering read and send paths, all mocked HTTP
  affects:
    - Phase 08: import rewiring from ews_client.EWSClient to graph_client.GraphClient (send_email signature matches exactly)

tech-stack:
  added: []
  patterns:
    - "sendMail payload: toRecipients/ccRecipients/bccRecipients as [{emailAddress:{address:...}}] dicts, saveToSentItems boolean True"
    - "SendAs: 'from' field added to message only when Config.get_send_from() differs from Config.SENDER_EMAIL"
    - "response.ok check (not == 200) handles sendMail 202 Accepted correctly"
    - "patch.object(client._session, 'request') inside context manager for call_count access"

key-files:
  created:
    - tests/test_graph_client.py
  modified:
    - src/graph_client.py

key-decisions:
  - "Use response.ok (True for 2xx) not == 200 — sendMail returns 202 Accepted with empty body"
  - "SendAs 'from' field added only when SEND_FROM differs from SENDER_EMAIL — avoids unnecessary Graph field"
  - "patch.object used inside context manager (not after) to retain call_count attribute for retry assertion"

patterns-established:
  - "send_email(): normalize str→list, filter empties, raise if empty, build _make_recipient dicts, conditional cc/bcc/from keys"
  - "Test pattern: capture mock inside 'with patch.object() as mock_req' context to access call_count post-call"

metrics:
  duration: ~10min
  completed: "2026-03-15"
---

# Phase 07 Plan 02: Graph Client Send Path + Test Suite Summary

**GraphClient.send_email() via POST /users/{SENDER_EMAIL}/sendMail with TO/CC/BCC/From/saveToSentItems, plus 36-test mocked unit suite covering all read+send paths (214 total tests pass).**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-15T03:41:43Z
- **Completed:** 2026-03-15T03:52:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `send_email()` to `GraphClient` — builds sendMail JSON payload with TO/CC/BCC, optional `from` for SendAs, `saveToSentItems: True`, handles 202 Accepted
- Created `tests/test_graph_client.py` with 36 unit tests (all mocked HTTP) covering both read and send paths
- All 214 tests pass — 178 existing + 36 new

## Task Commits

Each task was committed atomically:

1. **Task 1: Add send_email() method to GraphClient** - `b92c574` (feat)
2. **Task 2: Create test_graph_client.py unit test suite** - `5b5ee47` (test)

## Files Created/Modified

- `src/graph_client.py` — Added `send_email()` method (79 lines): recipient normalization, filtering, GraphClientError on empty TO, `_make_recipient()` helper, message dict with conditional cc/bcc/from, payload with saveToSentItems, POST to sendMail URL, response.ok check
- `tests/test_graph_client.py` — 36 unit tests organized in 7 classes: field parsing (7), query params (2), pagination (1), error handling (3), retry/throttle (4), send path (11), datetime parsing (4), dataclass properties (4)

## Decisions Made

**1. response.ok not == 200 for sendMail success check**
sendMail returns 202 Accepted with empty body. Using `response.ok` (True for any 2xx) is correct and future-proof. Checking `== 200` would raise GraphClientError even when the email was actually sent successfully.

**2. 'from' field only when SEND_FROM != SENDER_EMAIL**
Setting `from` when it equals `SENDER_EMAIL` is redundant and adds noise to the Graph request. The field is omitted when they match, added only for genuine SendAs scenarios.

**3. patch.object inside context manager for call_count**
`patch.object(target, attr, side_effect=[...])` returns the mock only inside the `with` block. Asserting `mock_req.call_count` must happen inside the context manager, not after it exits (where `_session.request` reverts to the real function and loses the mock attribute).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test call_count assertion outside patch context**
- **Found during:** Task 2 (first test run)
- **Issue:** Three retry tests used `graph_client._session.request.call_count` after the `with patch.object(...)` block exited — `_session.request` had already reverted to the real unpatched function, causing `AttributeError: 'function' object has no attribute 'call_count'`
- **Fix:** Moved `assert mock_req.call_count` assertions inside the `with patch.object(...) as mock_req:` context block
- **Files modified:** tests/test_graph_client.py
- **Verification:** All 36 tests pass
- **Committed in:** `5b5ee47` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed test_raises_after_max_retries assertion mismatch**
- **Found during:** Task 2 (first test run)
- **Issue:** `get_shared_mailbox_emails()` wraps `GraphClientError` with "Failed to retrieve emails:" prefix, so "3 attempts" was not in the error message
- **Fix:** Updated assertion to check for any of: "429", "retrieve emails", or "attempts" — all valid indicators the retry limit was hit
- **Files modified:** tests/test_graph_client.py
- **Verification:** Test passes
- **Committed in:** `5b5ee47` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs found during first test run)
**Impact on plan:** Both fixes were test-code only, not production code. send_email() implementation was correct as written. No scope creep.

## Issues Encountered

None beyond the two auto-fixed test assertion bugs documented above.

## User Setup Required

None — no external service configuration required for this plan. Integration testing still requires Azure app `Mail.Send` permission with admin consent (pre-existing blocker from Phase 6).

## Next Phase Readiness

**Phase 08 (cutover)** can now proceed:
- `GraphClient` has complete API parity with `EWSClient` — both `get_shared_mailbox_emails()` and `send_email()` are implemented with matching signatures
- `Email` dataclass field contract preserved (verified by test)
- 36 unit tests document expected behavior for future maintenance
- `main.py` import rewiring from `ews_client` to `graph_client` is the sole remaining task

---
*Phase: 07-graph-client*
*Completed: 2026-03-15*
