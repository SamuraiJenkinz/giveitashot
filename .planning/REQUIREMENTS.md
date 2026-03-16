# Requirements: InboxIQ v2.0 Graph API Migration

**Defined:** 2026-03-13
**Core Value:** Busy teams get a clear, actionable summary of their shared mailbox without reading every email

## v2.0 Requirements

Requirements for Graph API migration. Each maps to roadmap phases.

### Authentication & Permissions

- [x] **AUTH-01**: App authenticates to Microsoft Graph using MSAL client credentials flow
- [x] **AUTH-02**: Auth uses Graph API scope (`graph.microsoft.com/.default`) instead of EWS scope
- [x] **AUTH-03**: Config supports Graph env vars (MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, SENDER_EMAIL)
- [x] **AUTH-04**: Bearer token is acquired and attached to all Graph API requests

### Email Reading

- [x] **READ-01**: App fetches emails from shared mailbox via Graph REST API (`/users/{mailbox}/messages`)
- [x] **READ-02**: Emails are filtered by receivedDateTime since last run (incremental fetch)
- [x] **READ-03**: Email properties extracted: subject, sender, body, receivedDateTime, internetMessageId
- [x] **READ-04**: Pagination handled (follows `@odata.nextLink` until all matching emails retrieved)
- [x] **READ-05**: Email dataclass contract preserved (downstream classifier/summarizer unchanged)

### Email Sending

- [x] **SEND-01**: App sends HTML digest emails via Graph REST API (`/users/{sender}/sendMail`)
- [x] **SEND-02**: TO/CC/BCC recipients supported
- [x] **SEND-03**: SendAs supported via `from` property in message body
- [x] **SEND-04**: Both regular and major update digests send successfully via Graph

### Cleanup & Cutover

- [x] **CLEAN-01**: exchangelib dependency removed from requirements.txt
- [x] **CLEAN-02**: ews_client.py replaced with graph_client.py
- [x] **CLEAN-03**: main.py imports updated to use GraphClient
- [x] **CLEAN-04**: EWS-specific config vars removed
- [x] **CLEAN-05**: Test mocks updated from EWS objects to Graph JSON fixtures
- [x] **CLEAN-06**: All existing tests pass with Graph implementation

## Future Requirements

Deferred to later milestones.

### Digest Enhancements

- **ENH-01**: Impact level summary aggregation in digest header
- **ENH-02**: Service-grouped organization for major updates
- **ENH-03**: Retirement timeline visual display
- **ENH-04**: Previous update reference tracking across runs

### Operational

- **OPS-01**: Exchange RBAC scoping automation via PowerShell
- **OPS-02**: Token cache persistence optimization (SerializableTokenCache)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Microsoft Graph SDK (msgraph-sdk) | Async-only, confirmed daemon bug (GitHub #366), unnecessary complexity |
| Dual-mode EWS/Graph toggle | User chose clean break — remove EWS entirely |
| Graph batch API | Unnecessary for hourly single-mailbox fetch |
| New features or digest enhancements | Pure swap milestone — no functional changes |
| Exchange RBAC automation | IT admin responsibility, not application code |
| Graph webhooks/subscriptions | Hourly batch model is sufficient, no real-time needed |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 6 | Complete |
| AUTH-02 | Phase 6 | Complete |
| AUTH-03 | Phase 6 | Complete |
| AUTH-04 | Phase 6 | Complete |
| READ-01 | Phase 7 | Complete |
| READ-02 | Phase 7 | Complete |
| READ-03 | Phase 7 | Complete |
| READ-04 | Phase 7 | Complete |
| READ-05 | Phase 7 | Complete |
| SEND-01 | Phase 7 | Complete |
| SEND-02 | Phase 7 | Complete |
| SEND-03 | Phase 7 | Complete |
| SEND-04 | Phase 7 | Complete |
| CLEAN-01 | Phase 8 | Complete |
| CLEAN-02 | Phase 8 | Complete |
| CLEAN-03 | Phase 8 | Complete |
| CLEAN-04 | Phase 8 | Complete |
| CLEAN-05 | Phase 8 | Complete |
| CLEAN-06 | Phase 8 | Complete |

**Coverage:**
- v2.0 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-15 after Phase 8 completion (CLEAN-01 through CLEAN-06 complete — all v2.0 requirements done)*
