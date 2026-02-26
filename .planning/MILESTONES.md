# Project Milestones: InboxIQ

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
