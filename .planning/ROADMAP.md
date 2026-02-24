# Roadmap: InboxIQ v1.0 Major Updates Digest

## Overview

This milestone extends InboxIQ with a dual-digest system: detect M365 Message Center major update emails, exclude them from the regular digest, and deliver a separate admin-focused digest with deadline emphasis, affected services, and AI-extracted action items. The architecture follows classification-first design, with phases ordered by dependency: detection foundation → state/config infrastructure → digest content formatting → AI enhancement → integration testing.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4, 5): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Detection Foundation** - Multi-signal email classification with Message Center pattern matching
- [x] **Phase 2: Configuration and State Management** - Dual-digest infrastructure with separate recipients and state tracking
- [ ] **Phase 3: Digest Content Extraction** - HTML formatting with Message Center-specific fields
- [ ] **Phase 4: AI Enhancement** - Admin action extraction and deadline countdown
- [ ] **Phase 5: Integration Testing** - End-to-end validation with dual digest orchestration

## Phase Details

### Phase 1: Detection Foundation
**Goal**: Reliably identify M365 Message Center major update emails and exclude them from regular digest
**Depends on**: Nothing (first phase)
**Requirements**: DETECT-01, DETECT-02
**Success Criteria** (what must be TRUE):
  1. System correctly identifies Message Center emails using multi-signal detection (sender, subject MC#, body keywords)
  2. Detected major update emails are excluded from regular digest without breaking existing workflow
  3. Detection logging shows confidence scores and matched signals for operational monitoring
  4. Classification errors are recoverable without disrupting hourly scheduled runs
**Plans:** 2 plans

Plans:
- [x] 01-01-PLAN.md -- EmailClassifier module with multi-signal weighted detection and unit tests
- [x] 01-02-PLAN.md -- Pipeline integration: wire classifier into main.py, exclude major updates from regular digest

### Phase 2: Configuration and State Management
**Goal**: Infrastructure supports dual-digest workflows with separate recipients and independent state tracking
**Depends on**: Phase 1
**Requirements**: DIGEST-08
**Success Criteria** (what must be TRUE):
  1. Major update digest can be sent to different recipients than regular digest (MAJOR_UPDATE_TO/CC/BCC config)
  2. StateManager tracks separate last_run timestamps for regular and major update digests
  3. Configuration validation catches missing or invalid MAJOR_UPDATE_* settings before runtime
  4. State corruption in one digest type does not affect the other (independent state updates)
**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md -- Major update recipient config, feature toggle, validation, and .env.example
- [x] 02-02-PLAN.md -- Digest-type-aware state management, migration, and CLI flags

### Phase 3: Digest Content Extraction
**Goal**: Major updates digest displays all essential Message Center information in professional HTML format
**Depends on**: Phase 2
**Requirements**: DIGEST-01, DIGEST-02, DIGEST-03, DIGEST-04, DIGEST-05, DIGEST-06, DIGEST-07
**Success Criteria** (what must be TRUE):
  1. Each major update displays Message ID (MC######), action-required date, affected services, and category tags
  2. Each major update displays published date and last-updated date for tracking revisions
  3. Digest uses urgency visual indicators with color-coding based on deadline proximity (Critical > High > Normal)
  4. HTML formatting is professional with inline styling consistent with existing regular digest
  5. Digest sent successfully to configured MAJOR_UPDATE_* recipients
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: AI Enhancement
**Goal**: AI extracts actionable admin tasks and displays time-sensitive deadline countdowns
**Depends on**: Phase 3
**Requirements**: AI-01, AI-02
**Success Criteria** (what must be TRUE):
  1. AI extracts specific admin actions from major update body text (e.g., "Update auth settings", "Migrate workflows")
  2. Digest displays deadline countdown showing days remaining until action required
  3. AI extraction failures degrade gracefully without blocking digest delivery
  4. LLM structured output validation catches malformed or hallucinated data before display
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: Integration Testing
**Goal**: Dual-digest system works reliably in production with both digests executing successfully in single hourly run
**Depends on**: Phase 4
**Requirements**: All requirements validated end-to-end
**Success Criteria** (what must be TRUE):
  1. Single hourly scheduled task successfully sends both regular and major update digests
  2. Failure in one digest type does not prevent the other from sending
  3. Empty major updates do not generate unnecessary digest emails
  4. Dry-run mode correctly shows both digest recipients and content preview
  5. State file updates correctly for both digest types across multiple simulated runs
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Detection Foundation | 2/2 | Complete | 2026-02-24 |
| 2. Configuration and State Management | 2/2 | Complete | 2026-02-24 |
| 3. Digest Content Extraction | 0/1 | Not started | - |
| 4. AI Enhancement | 0/1 | Not started | - |
| 5. Integration Testing | 0/1 | Not started | - |

---
*Roadmap created: 2026-02-23*
*Last updated: 2026-02-24*
