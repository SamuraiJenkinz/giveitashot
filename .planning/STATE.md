# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-23)

**Core value:** Busy teams get a clear, actionable summary of their shared mailbox without reading every email
**Current focus:** Phase 5 - Integration Testing

## Current Position

Phase: 5 of 5 (Integration Testing)
Plan: 1 of 3 complete
Status: In progress
Last activity: 2026-02-26 — Completed 05-01-PLAN.md (Integration test foundation)

Progress: [█████████░] 83%

## Performance Metrics

**Velocity:**
- Total plans completed: 9
- Average duration: 8.4 minutes
- Total execution time: 1.62 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Detection Foundation | 2/2 | 0.12h | 4 min |
| 2. Configuration and State | 2/2 | 0.15h | 4.5 min |
| 3. Digest Content Extraction | 2/2 | 0.36h | 11 min |
| 4. AI Enhancement | 2/3 | 0.30h | 9 min |
| 5. Integration Testing | 1/3 | 0.38h | 23 min |

**Recent Trend:**
- Last 5 plans: 04-01 (15m), 04-02 (3m), 05-02 (19m), 05-01 (23m)
- Trend: Phase 5 integration testing with comprehensive test coverage (20 tests in 05-01)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Separate email for major updates — Different audience (admins vs general team), different emphasis (deadlines/actions vs general summary)
- Different recipients for major updates — Admin team needs these, not necessarily the same people who get the regular digest
- Same hourly schedule — Simplifies deployment, one scheduled task handles everything
- Email-based detection (not Graph API) — Updates already arrive in mailbox, avoid adding new API dependency
- MC pattern flexibility (01-01) — Accept 5-7 digits for MC numbers to allow format variations
- Classification threshold 70% (01-01) — Requires 2+ strong signals to reduce false positives
- pytest framework (01-01) — Use pytest over unittest for modern testing practices
- Classification field Optional[Any] (01-02) — Avoid circular imports by using Any type for Email.classification
- Classification fallback all regular (01-02) — Classification failure treats all emails as regular (non-blocking)
- Attach classification to Email (01-02) — EmailClassifier.classify_batch sets classification field on Email objects
- Presence-based feature toggle (02-01) — MAJOR_UPDATE_TO non-empty activates major digest without separate ENABLE flag
- No fallback MAJOR_UPDATE_TO to SUMMARY_TO (02-01) — Different audiences require explicit configuration
- Validate major digest only when enabled (02-01) — Empty MAJOR_UPDATE_TO means feature unused, invalid CC/BCC irrelevant
- digest_type parameter with default (02-02) — get_last_run/set_last_run use digest_type="regular" default for backwards compatibility
- State migration (02-02) — Automatic migration from old last_run to regular_last_run on first load
- Rollback safety (02-02) — Old last_run key preserved after migration for rollback capability
- Corruption isolation (02-02) — Corrupted state for one digest type does not affect other types
- Selective clear (02-02) — clear() supports both full state clear and per-digest-type clear
- CLI flags (02-02) — --regular-only and --major-only flags added for selective digest execution
- Multi-format date support (03-01) — Both MM/DD/YYYY and "Month DD, YYYY" formats for action date extraction
- Urgency boundaries (03-01) — <=7 days Critical, <=30 days High, >30 days or no date Normal
- Deduplication strategy (03-01) — Keep latest by received_datetime, set is_updated=True, never deduplicate None MC IDs
- Service/category normalization (03-01) — Title case for services, uppercase for categories for display consistency
- Body preview truncation (03-01) — 200 chars at word boundary with "..." suffix
- HTML gradient header (03-02) — Red-to-blue gradient for major digest visually distinguishes from regular digest
- Urgency section grouping (03-02) — Critical/High/Normal sections with updates sorted by action date
- Left-border color-coding (03-02) — 4px borders in traffic light colors (red/amber/green) for urgency tiers
- Error isolation (03-02) — Major digest failure does not crash program or prevent regular digest success
- Color palette refactor (03-02) — Extracted into _get_color_palette method for reuse across digest types
- API version 2024-08-01-preview (04-01) — Required for Azure OpenAI structured outputs (json_schema with strict=True)
- Graceful AI degradation (04-01) — Action extraction returns None on failure instead of raising exceptions
- Body truncation 1500 chars (04-01) — Balances LLM context completeness with cost and latency for action extraction
- Action items limit 3 per update (04-02) — Prevents email layout issues with excessively long action lists
- Silent degradation for failed extractions (04-02) — No visible error indicators when extraction fails, body preview serves as fallback
- Backward compatible actions parameter (04-02) — Optional parameter with None default allows existing code to work unchanged
- Path.as_uri() for file URLs (05-02) — Cross-platform file:// URL generation for browser auto-open in dry-run mode
- Graceful browser failure (05-02) — Browser open failures are non-fatal with warning log and manual fallback instruction
- Preserve console output (05-02) — HTML preview is additive, not replacement for existing console dry-run output
- Synthetic .eml fixtures (05-01) — Sanitized test data with @company.com and generic names safe for git commit
- StateManager tmp_path isolation (05-01) — Test state isolation prevents pollution of real .state.json
- Real .eml sanitization (05-01) — tests/fixtures/README.md provides checklist for sanitizing production .eml files

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 1 Validation Needed (from 01-01-SUMMARY.md):**
- Real Message Center email corpus testing recommended — patterns need validation against production formats
- False positive/negative rate monitoring after integration — track classification accuracy
- Need sample Message Center emails for validation — may require requesting from IT admin or using historical .eml files

**EWS Deprecation Timeline:**
- EWS disabled by default August 2026, complete shutdown 2027
- This feature delivers value on deprecated API, requiring Graph API migration within 12-18 months
- Proceeding with EWS for faster v1.0 delivery, defer Graph migration to v2.0

## Session Continuity

Last session: 2026-02-26 (phase 5 plan 1 execution complete)
Stopped at: Completed 05-01-PLAN.md — Integration test foundation with 20 tests (158/158 tests pass)
Resume file: None
