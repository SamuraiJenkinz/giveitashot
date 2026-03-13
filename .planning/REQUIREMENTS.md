# Requirements: InboxIQ v2.0 Graph API Migration

**Defined:** 2026-03-13
**Core Value:** Busy teams get a clear, actionable summary of their shared mailbox without reading every email

## v2.0 Requirements

Requirements for Graph API migration. Each maps to roadmap phases.

### Authentication & Permissions

- [ ] **AUTH-01**: App authenticates to Microsoft Graph using MSAL client credentials flow
- [ ] **AUTH-02**: Auth uses Graph API scope (`graph.microsoft.com/.default`) instead of EWS scope
- [ ] **AUTH-03**: Config supports Graph env vars (MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, SENDER_EMAIL)
- [ ] **AUTH-04**: Bearer token is acquired and attached to all Graph API requests

### Email Reading

- [ ] **READ-01**: App fetches emails from shared mailbox via Graph REST API (`/users/{mailbox}/messages`)
- [ ] **READ-02**: Emails are filtered by receivedDateTime since last run (incremental fetch)
- [ ] **READ-03**: Email properties extracted: subject, sender, body, receivedDateTime, internetMessageId
- [ ] **READ-04**: Pagination handled (follows `@odata.nextLink` until all matching emails retrieved)
- [ ] **READ-05**: Email dataclass contract preserved (downstream classifier/summarizer unchanged)

### Email Sending

- [ ] **SEND-01**: App sends HTML digest emails via Graph REST API (`/users/{sender}/sendMail`)
- [ ] **SEND-02**: TO/CC/BCC recipients supported
- [ ] **SEND-03**: SendAs supported via `from` property in message body
- [ ] **SEND-04**: Both regular and major update digests send successfully via Graph

### Cleanup & Cutover

- [ ] **CLEAN-01**: exchangelib dependency removed from requirements.txt
- [ ] **CLEAN-02**: ews_client.py replaced with graph_client.py
- [ ] **CLEAN-03**: main.py imports updated to use GraphClient
- [ ] **CLEAN-04**: EWS-specific config vars removed
- [ ] **CLEAN-05**: Test mocks updated from EWS objects to Graph JSON fixtures
- [ ] **CLEAN-06**: All existing tests pass with Graph implementation

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
| AUTH-01 | Pending | Pending |
| AUTH-02 | Pending | Pending |
| AUTH-03 | Pending | Pending |
| AUTH-04 | Pending | Pending |
| READ-01 | Pending | Pending |
| READ-02 | Pending | Pending |
| READ-03 | Pending | Pending |
| READ-04 | Pending | Pending |
| READ-05 | Pending | Pending |
| SEND-01 | Pending | Pending |
| SEND-02 | Pending | Pending |
| SEND-03 | Pending | Pending |
| SEND-04 | Pending | Pending |
| CLEAN-01 | Pending | Pending |
| CLEAN-02 | Pending | Pending |
| CLEAN-03 | Pending | Pending |
| CLEAN-04 | Pending | Pending |
| CLEAN-05 | Pending | Pending |
| CLEAN-06 | Pending | Pending |

**Coverage:**
- v2.0 requirements: 18 total
- Mapped to phases: 0
- Unmapped: 18 ⚠️

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-13 after initial definition*
