---
phase: 08-cutover
plan: 01
subsystem: api
tags: [graph-api, ews, migration, exchangelib, msal, requests, python]

# Dependency graph
requires:
  - phase: 07-graph-client
    provides: GraphClient, GraphClientError, Email dataclass — complete Graph REST API transport layer
  - phase: 06-auth-foundation
    provides: GraphAuthenticator with MSAL client credentials flow
provides:
  - EWS fully removed — exchangelib gone from requirements.txt and all .py files
  - src/ews_client.py deleted — no EWS transport module remains in src/
  - main.py wired to GraphAuthenticator + GraphClient + GraphClientError exclusively
  - All Email imports redirected from src.ews_client to src.graph_client across src/ and tests/
  - 210 tests passing — 4 EWS shim tests deleted, all remaining 210 green
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GraphClient is sole email transport: all callers import Email, GraphClient, GraphClientError from src.graph_client"
    - "GraphAuthenticator is sole authenticator: no aliases, no shims, single class in src.auth"
    - "Config.SENDER_EMAIL is sole sender-identity field: EWS_SERVER and USER_EMAIL removed"

key-files:
  created: []
  modified:
    - src/auth.py
    - src/config.py
    - src/main.py
    - src/classifier.py
    - src/extractor.py
    - src/llm_summarizer.py
    - src/summarizer.py
    - src/graph_client.py
    - requirements.txt
    - tests/conftest.py
    - tests/test_auth.py
    - tests/test_config.py
    - tests/test_classifier.py
    - tests/test_extractor.py
    - tests/test_integration.py
    - tests/test_integration_dual_digest.py
    - .planning/ROADMAP.md

key-decisions:
  - "Delete src/ews_client.py entirely — no stub, no re-export shim"
  - "Remove exchangelib from requirements.txt (zero new dependencies added)"
  - "GraphClient takes GraphAuthenticator directly — no credentials object intermediary"
  - "4 EWS shim tests deleted (not updated): test_ews_authenticator_alias, test_get_ews_credentials_returns_oauth2credentials, test_get_ews_credentials_raises_on_auth_failure from test_auth.py; test_user_email_aliases_sender_email from test_config.py"

patterns-established:
  - "Single transport module: src/graph_client.py is the canonical email I/O module for all phases forward"
  - "Config has no legacy aliases: all env-var-backed fields are authoritative; no USER_EMAIL, no EWS_SERVER"

# Metrics
duration: 13min
completed: 2026-03-15
---

# Phase 8 Plan 1: EWS Cutover Summary

**Exchangelib fully removed and all code rewired to Microsoft Graph API — 210 tests green, zero EWS symbols in codebase**

## Performance

- **Duration:** 13 min
- **Started:** 2026-03-15T23:58:48Z
- **Completed:** 2026-03-15T23:11:44Z
- **Tasks:** 2
- **Files modified:** 17 (+ 1 deleted)

## Accomplishments
- Deleted src/ews_client.py and removed exchangelib from requirements.txt — EWS transport layer fully gone
- Rewired main.py to GraphAuthenticator + GraphClient + GraphClientError with updated log messages, argparse description, and startup banner
- Redirected Email dataclass imports in 9 files (4 src modules + 5 test files) from src.ews_client to src.graph_client
- Removed backward-compat shims from auth.py (get_ews_credentials(), EWSAuthenticator alias) and config.py (EWS_SERVER, USER_EMAIL)
- Deleted 4 EWS shim tests; 210 remaining tests pass with zero modifications to test logic

## Task Commits

Each task was committed atomically:

1. **Task 1: EWS removal and source code rewiring** - `ff1b0c4` (feat)
2. **Task 2: Test migration, docstring sweep, and full regression** - `1b55397` (feat)

**Plan metadata:** See final docs commit.

## Files Created/Modified
- `src/ews_client.py` - DELETED — EWS transport layer removed
- `requirements.txt` - Removed exchangelib dependency line
- `src/auth.py` - Removed get_ews_credentials() shim, EWSAuthenticator alias, exchangelib import
- `src/config.py` - Removed EWS_SERVER and USER_EMAIL; get_send_from() falls back to SENDER_EMAIL
- `src/main.py` - Wired to GraphAuthenticator, GraphClient, GraphClientError; updated all logs/descriptions
- `src/classifier.py` - Email import redirected to graph_client
- `src/extractor.py` - Email import redirected to graph_client
- `src/llm_summarizer.py` - Email import redirected to graph_client
- `src/summarizer.py` - Email import redirected to graph_client
- `src/graph_client.py` - Removed 3 EWS comment references
- `tests/conftest.py` - Email import redirected to src.graph_client
- `tests/test_auth.py` - Deleted 3 EWS shim tests; removed exchangelib import and EWSAuthenticator import; updated docstring and mock_config fixture
- `tests/test_config.py` - Deleted test_user_email_aliases_sender_email; removed USER_EMAIL from backup_config fixture and 4 validate tests; updated docstrings
- `tests/test_classifier.py` - Email import redirected to src.graph_client
- `tests/test_extractor.py` - Email import redirected to src.graph_client
- `tests/test_integration.py` - Email import redirected; docstring updated from EWS to API
- `tests/test_integration_dual_digest.py` - Email import redirected to src.graph_client
- `.planning/ROADMAP.md` - Updated Phase 8 test count from 167 to 210; corrected plan count

## Decisions Made
- GraphClient takes GraphAuthenticator directly (not OAuth2Credentials object) — cleaner interface, no credentials intermediary
- Deleted EWS shim tests outright rather than updating them — the shim functionality no longer exists, tests had no surviving equivalent
- Updated test_auth.py mock_config fixture to remove USER_EMAIL patch — Config no longer has USER_EMAIL attribute

## Deviations from Plan

None - plan executed exactly as written.

One minor addition: changed "not EWS scope" comment in test_auth.py docstring to "not Exchange scope" to eliminate the last grep hit for "EWS" in .py files. This was a one-line docstring cleanup, not a code change, and improves hygiene without altering any test logic.

## Issues Encountered
None - all changes applied cleanly in one pass, full regression passed on first run.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- v2.0 migration is complete: EWS fully removed, Graph API transport operational, 210 tests green
- Phase 8 is the final phase — no subsequent phases planned
- Remaining prerequisite for live operation: Azure app registration with Mail.Read and Mail.Send Graph permissions (IT admin consent required — documented in STATE.md blockers since Phase 6)

---
*Phase: 08-cutover*
*Completed: 2026-03-15*
