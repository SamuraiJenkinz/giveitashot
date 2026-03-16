# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-12)

**Core value:** Busy teams get a clear, actionable summary of their shared mailbox without reading every email
**Current focus:** v2.0 Migration COMPLETE — all phases done

## Current Position

Phase: 8 of 8 in v2.0 (Cutover) — COMPLETE
Plan: 1 of 1 in current phase — COMPLETE
Status: v2.0 migration complete
Last activity: 2026-03-15 — Completed 08-01-PLAN.md (EWS cutover, 210 tests green)

Progress: [██████████████] v1.0 complete, v2.0 Phases 6-7-8 done — migration COMPLETE

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
| 7. Graph Client | 07-01 | Complete | ~2 min |
| 7. Graph Client | 07-02 | Complete | ~10 min |
| 8. Cutover | 08-01 | Complete | ~13 min |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0 start]: Clean break — remove EWS entirely, no dual-mode toggle
- [v2.0 start]: Direct REST calls via `requests` + MSAL, not msgraph-sdk (async-only, daemon bug)
- [v2.0 start]: Zero new dependencies — remove exchangelib, add nothing
- [06-01]: Drop `acquire_token_silent` — MSAL 1.23+ handles internal caching in `acquire_token_for_client`; redundant call removed
- [06-01]: aud claim live verification deferred to integration testing — requires IT admin consent for Graph permissions (blocker still active)
- [08-01]: GraphClient takes GraphAuthenticator directly — no OAuth2Credentials intermediary; simpler interface
- [08-01]: EWS shim tests deleted outright (not updated) — shim functionality no longer exists; no equivalent to port
- [07-01]: Email.id uses internetMessageId (RFC2822 stable) as primary, falls back to Graph internal id — stable across folder moves
- [07-01]: HTML body fetched from Graph and stripped locally via _strip_html() (verbatim from ews_client.py) — preserves exact classifier/summarizer input format
- [07-01]: params=None after first pagination page — @odata.nextLink is a complete URL; passing params again duplicates query parameters causing 400 errors
- [07-02]: response.ok (not == 200) for sendMail success — Graph returns 202 Accepted with empty body
- [07-02]: 'from' field in sendMail message only when SEND_FROM differs from SENDER_EMAIL — omitted when same to avoid unnecessary Graph field

### Pending Todos

None — v2.0 migration complete. All cleanup tasks executed in Phase 8.

### Blockers/Concerns

- [Phase 6 prerequisite]: Azure app registration needs `Mail.Read` and `Mail.Send` Graph application permissions with admin consent — IT/security approval required before integration testing. Code can be written first; live smoke test is blocked.
- [Phase 6 prerequisite]: Marsh McLennan tenant mailbox scoping approach unknown (ApplicationAccessPolicy vs Exchange RBAC for Applications) — clarify with IT admin before Phase 6 integration testing.
- [06-01 deferral]: aud claim live verification (roadmap criterion 1) deferred — needs live credentials. Scope string `https://graph.microsoft.com/.default` is correct per RESEARCH.md.

## Session Continuity

Last session: 2026-03-15
Stopped at: Completed 08-01-PLAN.md — v2.0 migration complete, 210 tests green.
Resume file: None
