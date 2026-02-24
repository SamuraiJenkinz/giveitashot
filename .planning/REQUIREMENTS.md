# Requirements: InboxIQ

**Defined:** 2026-02-23
**Core Value:** Busy teams get a clear, actionable summary of their shared mailbox without reading every email

## v1 Requirements

Requirements for milestone v1.0 Major Updates Digest. Each maps to roadmap phases.

### Detection & Filtering

- [x] **DETECT-01**: System detects M365 Message Center major update emails in shared mailbox using multi-signal detection (sender pattern, subject structure, body markers, Message ID regex)
- [x] **DETECT-02**: Detected major update emails are excluded from the regular email digest

### Digest Content

- [ ] **DIGEST-01**: Major updates digest displays Message ID (MC######) for each update
- [ ] **DIGEST-02**: Major updates digest prominently displays action-required dates for each update
- [ ] **DIGEST-03**: Major updates digest displays affected services (Exchange Online, Microsoft 365 Apps, Teams, etc.)
- [ ] **DIGEST-04**: Major updates digest displays update category tags (MAJOR UPDATE, ADMIN IMPACT, USER IMPACT, RETIREMENT)
- [ ] **DIGEST-05**: Major updates digest displays published date and last-updated date for each update
- [ ] **DIGEST-06**: Major updates digest uses urgency visual indicators with color-coding (Critical > High > Normal)
- [ ] **DIGEST-07**: Major updates digest is formatted as professional HTML email with inline styling
- [ ] **DIGEST-08**: Major updates digest is sent to separately configurable recipients (MAJOR_UPDATE_TO/CC/BCC)

### AI Enhancement

- [ ] **AI-01**: AI extracts specific admin actions needed from each major update (e.g., "Update auth settings", "Migrate workflows", "Notify users")
- [ ] **AI-02**: Major updates digest displays deadline countdown showing days remaining until action required

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Digest Enhancements

- **ENHANCE-01**: Impact level summary in digest header (e.g., "3 Admin Impact, 1 Retirement, 2 User Impact")
- **ENHANCE-02**: Updates grouped by affected service instead of chronological
- **ENHANCE-03**: "No new major updates" confirmation email when nothing to report
- **ENHANCE-04**: Direct link to full Message Center post from each update summary
- **ENHANCE-05**: Dedicated retirement timeline section with visual timeline
- **ENHANCE-06**: Previous update reference tracking across digest runs (revision history)

### Infrastructure

- **INFRA-01**: Migration from EWS to Microsoft Graph API (EWS deprecated August 2026)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Microsoft Graph API for Message Center | Updates already arrive as emails, avoid new API dependency for v1 |
| Real-time push notifications | Breaks hourly batch model, not aligned with digest workflow |
| Automated task creation (Planner, etc.) | Fragile, org-specific workflow — admins create tasks in their own systems |
| Full message body in digest | Posts are lengthy, defeats digest purpose — AI summary + link instead |
| Historical archive search | Message Center portal already provides this |
| Per-admin filtering | Complex personalization, not suited to shared digest model |
| Response/acknowledgment tracking | Becomes a ticketing system — out of scope for digest tool |
| Service health incidents | Different category (reactive incidents vs proactive updates) |
| Multi-tenant support | Single tenant deployment meets current need |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DETECT-01 | Phase 1 | Complete |
| DETECT-02 | Phase 1 | Complete |
| DIGEST-01 | Phase 3 | Pending |
| DIGEST-02 | Phase 3 | Pending |
| DIGEST-03 | Phase 3 | Pending |
| DIGEST-04 | Phase 3 | Pending |
| DIGEST-05 | Phase 3 | Pending |
| DIGEST-06 | Phase 3 | Pending |
| DIGEST-07 | Phase 3 | Pending |
| DIGEST-08 | Phase 2 | Pending |
| AI-01 | Phase 4 | Pending |
| AI-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

**Coverage Validation:**
- Phase 1: 2 requirements (DETECT-01, DETECT-02)
- Phase 2: 1 requirement (DIGEST-08)
- Phase 3: 7 requirements (DIGEST-01 through DIGEST-07)
- Phase 4: 2 requirements (AI-01, AI-02)
- Phase 5: Integration testing (validates all requirements end-to-end)

✓ 100% requirement coverage achieved

---
*Requirements defined: 2026-02-23*
*Last updated: 2026-02-24 after Phase 1 completion*
