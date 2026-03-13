# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-12)

**Core value:** Busy teams get a clear, actionable summary of their shared mailbox without reading every email
**Current focus:** Phase 6 — Auth Foundation (v2.0 Graph API Migration)

## Current Position

Phase: 6 of 8 in v2.0 (Auth Foundation)
Plan: 1 of TBD in current phase
Status: In progress
Last activity: 2026-03-13 — Completed 06-01-PLAN.md (GraphAuthenticator + config renames)

Progress: [██████░░░░░░░░] v1.0 complete, v2.0 Plan 06-01 done

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 11
- Average duration: ~30 min
- Total execution time: ~5.5 hours

**By Phase (v1.0):**

| Phase | Plans | Status |
|-------|-------|--------|
| 1. Foundation | 2/2 | Complete |
| 2. Summarization | 2/2 | Complete |
| 3. Classification | 2/2 | Complete |
| 4. Major Updates Digest | 3/3 | Complete |
| 5. Integration Testing | 3/3 | Complete |

**v2.0 progress:**

| Phase | Plan | Status | Duration |
|-------|------|--------|----------|
| 6. Auth Foundation | 06-01 | Complete | ~4 min |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0 start]: Clean break — remove EWS entirely, no dual-mode toggle
- [v2.0 start]: Direct REST calls via `requests` + MSAL, not msgraph-sdk (async-only, daemon bug)
- [v2.0 start]: Zero new dependencies — remove exchangelib, add nothing
- [06-01]: Drop `acquire_token_silent` — MSAL 1.23+ handles internal caching in `acquire_token_for_client`; redundant call removed
- [06-01]: `get_ews_credentials()` shim retained through Phase 7 — main.py line 154 depends on it; remove in Phase 8
- [06-01]: `USER_EMAIL = SENDER_EMAIL` class-level alias documented with test — the alias is evaluated once at class definition; tests must update both independently
- [06-01]: aud claim live verification deferred to integration testing — requires IT admin consent for Graph permissions (blocker still active)

### Pending Todos

- Phase 8 cleanup: Remove `EWSAuthenticator` alias, `get_ews_credentials()` shim, `USER_EMAIL` alias, `EWS_SERVER` from config

### Blockers/Concerns

- [Phase 6 prerequisite]: Azure app registration needs `Mail.Read` and `Mail.Send` Graph application permissions with admin consent — IT/security approval required before integration testing. Code can be written first; live smoke test is blocked.
- [Phase 6 prerequisite]: Marsh McLennan tenant mailbox scoping approach unknown (ApplicationAccessPolicy vs Exchange RBAC for Applications) — clarify with IT admin before Phase 6 integration testing.
- [06-01 deferral]: aud claim live verification (roadmap criterion 1) deferred — needs live credentials. Scope string `https://graph.microsoft.com/.default` is correct per RESEARCH.md.

## Session Continuity

Last session: 2026-03-13 14:31 UTC
Stopped at: Completed 06-01-PLAN.md. Two tasks committed (a8f98b1, 051fe9c). SUMMARY at .planning/phases/06-auth-foundation/06-01-SUMMARY.md.
Resume file: None
