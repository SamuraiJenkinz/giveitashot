# Roadmap: InboxIQ

## Milestones

- ✅ **v1.0 Major Updates Digest** - Phases 1-5 (shipped 2026-02-26)
- 🚧 **v2.0 Graph API Migration** - Phases 6-8 (in progress)

## Phases

<details>
<summary>✅ v1.0 Major Updates Digest (Phases 1-5) - SHIPPED 2026-02-26</summary>

### Phase 1: Foundation
**Goal**: Project scaffolding and core email fetch pipeline
**Plans**: 2 plans

Plans:
- [x] 01-01: Project setup, config, auth, EWS client skeleton
- [x] 01-02: Email fetch pipeline with state management and CLI

### Phase 2: Summarization
**Goal**: AI-powered email summarization and digest generation
**Plans**: 2 plans

Plans:
- [x] 02-01: Azure OpenAI integration and summarizer
- [x] 02-02: HTML digest builder and email delivery

### Phase 3: Classification
**Goal**: M365 Message Center detection and email routing
**Plans**: 2 plans

Plans:
- [x] 03-01: Multi-signal classifier with weighted scoring
- [x] 03-02: Dual-digest routing and independent state management

### Phase 4: Major Updates Digest
**Goal**: Admin-focused digest with deadline tracking and action extraction
**Plans**: 3 plans

Plans:
- [x] 04-01: Major updates HTML builder with urgency tiers
- [x] 04-02: AI-powered admin action extraction with structured outputs
- [x] 04-03: Dual-digest integration and feature toggle

### Phase 5: Integration Testing
**Goal**: End-to-end validation with real production .eml fixtures
**Plans**: 3 plans

Plans:
- [x] 05-01: Test infrastructure and fixture loading
- [x] 05-02: Classifier and summarizer integration tests
- [x] 05-03: Real .eml fixture integration and full regression suite

</details>

---

### 🚧 v2.0 Graph API Migration (In Progress)

**Milestone Goal:** Replace EWS (exchangelib) with Microsoft Graph REST API for all email operations before the August 2026 deprecation deadline. Pure functional swap — identical behavior, new transport layer. Zero new dependencies beyond removing exchangelib.

#### Phase 6: Auth Foundation
**Goal**: App authenticates to Microsoft Graph with correct scope, acquiring a bearer token that works against Graph endpoints
**Depends on**: Phase 5 (v1.0 complete)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):
  1. Running the auth module in isolation produces a JWT whose `aud` claim is `https://graph.microsoft.com/`
  2. The scope constant in `auth.py` reads `https://graph.microsoft.com/.default` (not the EWS scope)
  3. `MICROSOFT_TENANT_ID`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, and `SENDER_EMAIL` are the only auth env vars required — `EWS_SERVER` is gone
  4. Bearer token is returned as a plain string and usable as an `Authorization: Bearer {token}` header value
**Plans**: 1 plan

Plans:
- [x] 06-01-PLAN.md — GraphAuthenticator + config env var migration with backward compat

---

#### Phase 7: Graph Client
**Goal**: `graph_client.py` reads emails from the shared mailbox and sends HTML digest emails via Graph REST API, with the `Email` dataclass contract fully preserved
**Depends on**: Phase 6
**Requirements**: READ-01, READ-02, READ-03, READ-04, READ-05, SEND-01, SEND-02, SEND-03, SEND-04
**Success Criteria** (what must be TRUE):
  1. `get_shared_mailbox_emails()` returns a list of `Email` objects with correct subject, sender name, sender address, body HTML, received datetime, and internetMessageId populated from Graph JSON
  2. Incremental fetch works — only emails received since the `since` datetime are returned, using a properly formatted UTC OData `$filter`
  3. Pagination is handled — if the mailbox has more emails than the default page size, all matching emails are returned (not just the first 10)
  4. `send_email()` sends an HTML email via `POST /users/{sender}/sendMail` with TO, CC, BCC, and custom From address supported
  5. All unit tests in `test_graph_client.py` pass with mocked HTTP — Graph JSON parsing is fully exercised without requiring live credentials
**Plans**: 2 plans

Plans:
- [ ] 07-01-PLAN.md — Graph client read path (fetch, filter, pagination, field mapping)
- [ ] 07-02-PLAN.md — Graph client send path and unit test suite

---

#### Phase 8: Cutover
**Goal**: EWS is fully removed, `main.py` routes through `GraphClient`, and all 167 existing tests pass against the new implementation
**Depends on**: Phase 7
**Requirements**: CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04, CLEAN-05, CLEAN-06
**Success Criteria** (what must be TRUE):
  1. `exchangelib` does not appear in `requirements.txt` and cannot be imported from the codebase
  2. `src/ews_client.py` is replaced by `src/graph_client.py` — no EWS file remains in `src/`
  3. `python main.py --dry-run` executes without importing or referencing any EWS symbol
  4. All 167 existing tests pass with import paths updated to `src.graph_client` — zero test logic changes required
**Plans**: TBD

Plans:
- [ ] 08-01: EWS removal, import wiring, test migration, full regression

---

## Progress

**Execution Order:**
Phases execute in numeric order: 6 → 7 → 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 2/2 | Complete | 2026-02-23 |
| 2. Summarization | v1.0 | 2/2 | Complete | 2026-02-24 |
| 3. Classification | v1.0 | 2/2 | Complete | 2026-02-25 |
| 4. Major Updates Digest | v1.0 | 3/3 | Complete | 2026-02-25 |
| 5. Integration Testing | v1.0 | 3/3 | Complete | 2026-02-26 |
| 6. Auth Foundation | v2.0 | 1/1 | Complete | 2026-03-13 |
| 7. Graph Client | v2.0 | 0/2 | Planned | - |
| 8. Cutover | v2.0 | 0/TBD | Not started | - |
