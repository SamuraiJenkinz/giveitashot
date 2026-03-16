# Project Milestones: InboxIQ

## v2.0 Graph API Migration (Shipped: 2026-03-15)

**Delivered:** Replaced EWS (exchangelib) with Microsoft Graph REST API for all email operations — pure functional swap with identical behavior, zero new dependencies, and all 210 tests green.

**Phases completed:** 6-8 (4 plans total)

**Key accomplishments:**

- GraphAuthenticator with MSAL client credentials flow targeting `graph.microsoft.com/.default` scope
- GraphClient read path with OData-filtered pagination preserving Email dataclass contract
- GraphClient send path via `sendMail` endpoint with TO/CC/BCC/SendAs support
- Complete EWS removal — exchangelib deleted, all imports rewired, zero EWS symbols remain
- 36 new Graph unit tests (mocked HTTP) covering read, send, retry, pagination, error paths
- 210 total tests green — 4 obsolete EWS shim tests deleted, remaining 210 pass with zero logic changes

**Stats:**

- 36 files modified (+4,414 lines, -453 lines)
- 7,060 lines Python total
- 3 phases, 4 plans
- 3 days from milestone start to ship (2026-03-13 to 2026-03-15)
- ~29 min total execution time across 4 plans
- 210 tests, 100% pass rate

**Git range:** `a8f98b1` → `1c400be`

**What's next:** Digest enhancements (impact summaries, service grouping, retirement timelines), operational improvements (RBAC automation, token cache)

---

## v1.0 Major Updates Digest (Shipped: 2026-02-26)

**Delivered:** Dual-digest system that detects M365 Message Center major update emails, excludes them from the regular digest, and sends a separate admin-focused digest with deadline emphasis, affected services, and AI-extracted action items.

**Phases completed:** 1-5 (11 plans total)

**Key accomplishments:**

- Multi-signal email classifier with weighted scoring for M365 Message Center detection (18 unit tests)
- Dual-digest infrastructure with independent recipients, state tracking, and presence-based feature toggle
- Professional HTML major updates digest with urgency tiers, color-coding, and MC metadata extraction
- AI-powered admin action extraction using Azure OpenAI structured outputs with graceful degradation
- 167 integration tests including real production .eml fixture validation
- Full error isolation — failure in one digest type never blocks the other

**Stats:**

- 19 Python files created/modified (+4,716 lines)
- 80 files total (including planning docs)
- 5 phases, 11 plans
- 4 days from milestone start to ship (2026-02-23 to 2026-02-26)
- 167 tests, 100% pass rate

**Git range:** `eb671a0` → `e7fde4b`

**What's next:** Graph API migration (EWS deprecated Aug 2026), digest enhancements (impact summaries, service grouping, retirement timelines)

---
