# Project Research Summary

**Project:** InboxIQ - M365 Message Center Major Updates Detection
**Domain:** Email classification and multi-digest summarization
**Researched:** 2026-02-23
**Confidence:** MEDIUM-HIGH

## Executive Summary

Adding Message Center major update detection to the existing InboxIQ email summarization system requires implementing classification-first architecture with dual digest workflows. The good news: **no new dependencies are required** — existing exchangelib, Python stdlib, and Azure OpenAI capabilities are sufficient. The recommended approach uses multi-signal pattern matching (sender + subject + body + Message ID) with optional LLM classification fallback for ambiguous cases. A new EmailClassifier module sits between email fetch and summarization, splitting emails into two independent digest streams (regular and major updates) with separate recipients and specialized LLM prompts.

The primary technical risks cluster around detection reliability (brittle pattern matching when Microsoft changes email formats), state management corruption (tracking two digest types in single invocation), and LLM structured output reliability (extracting deadlines and actions). However, all risks have well-documented mitigation strategies from 2026 research. The architecture extends naturally from the existing v0.3 codebase with minimal disruption to the working regular digest.

**Critical timeline constraint:** EWS (Exchange Web Services) is deprecated by Microsoft with default disablement in August 2026 and complete shutdown in 2027. This feature delivers value on a known-to-be-deprecated API, requiring Graph API migration within 12-18 months. The research recommends proceeding with EWS implementation for faster delivery, with Graph migration as a separate v2.0 project.

## Key Findings

### Recommended Stack

**Verdict: No new dependencies required.** The existing Python 3.10+ standard library, exchangelib, and Azure OpenAI integration provide all necessary capabilities for Message Center detection and dual-digest generation.

**Core technologies (existing):**
- **exchangelib (≥5.4.0)**: EWS email filtering and metadata access — already supports sender filtering and extended properties investigation if needed
- **Azure OpenAI (via openai ≥1.0.0)**: Text classification and admin-focused summarization — extend with major update-specific prompts
- **Python stdlib re module**: Regex pattern matching for sender addresses, subject MC IDs, and body content — sufficient for reliable detection

**What NOT to add:**
- **scikit-learn/spaCy**: Overkill for binary classification with no training data, Azure OpenAI provides superior zero-shot classification
- **Microsoft Graph API SDK**: Redundant (Message Center emails already arrive in shared mailbox), adds auth complexity, out of project scope
- **HTML parsing libraries (beautifulsoup4/lxml)**: Existing `_strip_html()` method sufficient, don't need structured parsing

**Detection strategy:** Multi-signal approach with weighted scoring:
1. **Layer 1 (Sender):** Filter by `@email2.microsoft.com` (verified legitimate sender) — reduces search space
2. **Layer 2 (Patterns):** Regex on subject (`MC\d{7}` Message ID) and body (`major update`, `admin impact`, `retirement` keywords)
3. **Layer 3 (LLM fallback):** Optional Azure OpenAI classification when rule-based detection uncertain

**Critical finding:** Microsoft actively evolves Message Center email formats. Static pattern matching will eventually break, requiring LLM-based fallback for resilience to format changes.

### Expected Features

**Must have (table stakes):**
- **Email Detection** — Reliably identify Message Center major updates in mailbox (multi-signal: sender + subject + body)
- **Exclusion from Regular Digest** — Prevent duplicates across digest types
- **Separate Recipients** — `MAJOR_UPDATE_TO/CC/BCC` env vars with fallback to regular recipients
- **Message ID Display** — MC# for admin reference in conversations and tickets
- **Action Required Date** — Prominently displayed deadline for planning
- **Affected Services** — Which service(s) impacted (Exchange, Teams, SharePoint, etc.)
- **Update Category Tags** — MAJOR UPDATE, ADMIN IMPACT, USER IMPACT, RETIREMENT, BREAKING CHANGE
- **Published/Updated Dates** — Track original post and revision dates
- **HTML Email Formatting** — Professional, consistent with existing digest
- **Urgency Visual Indicators** — Color-coded urgency levels based on deadline proximity

**Should have (competitive differentiation):**
- **Deadline Countdown** — "Action required in X days" vs static date for immediate context
- **Impact Level Summary** — Aggregate tag counts in digest header ("3 Admin Impact, 1 Retirement")
- **Link to Full Message Center Post** — Direct URL to official post for details
- **AI-Powered Admin Action Summary** — Specialized LLM summarization extracting specific admin actions needed

**Defer (v2+):**
- **Service-Grouped Organization** — Group by affected service (helps delegation to service-specific teams)
- **Retirement Timeline** — Dedicated section with visual timeline
- **No Action Needed Digest** — Confirmation email when no updates (peace of mind)
- **Previous Update Reference** — Track Message ID revisions across runs (requires state management complexity)

**Anti-features (explicitly avoid):**
- Microsoft Graph API integration (redundant, adds complexity)
- Real-time push notifications (breaks hourly batch model)
- Automated Planner task creation (fragile, not universal)
- Full message body in digest (defeats purpose, digest becomes overwhelming)
- Historical archive search (scope creep, portal already provides this)

### Architecture Approach

The recommended architecture is **classification-first with dual digest orchestration**. Emails are classified immediately after fetch and before summarization, enabling clean separation of digest types while maintaining the existing layered pipeline. The design introduces a new EmailClassifier module between fetch and summarization, shared configuration with separate recipient lists, unified state management with digest type tracking, and sequential orchestration of two independent digest workflows in main.py.

**Major components:**
1. **EmailClassifier (NEW)** — Multi-signal detection (sender + subject + body + LLM fallback) that returns (regular_emails, major_update_emails) tuple
2. **EmailSummarizer (EXTEND)** — Add `summarize_major_updates()` and `format_major_update_html()` methods with specialized prompts
3. **LLMSummarizer (EXTEND)** — Add `MAJOR_UPDATE_DIGEST_PROMPT` focusing on deadlines, actions, impact, and rollout timelines
4. **StateManager (EXTEND)** — Add `digest_type` parameter to track separate last_run timestamps for regular vs major update digests
5. **Config (EXTEND)** — Add `MAJOR_UPDATE_TO/CC/BCC` env vars with fallback to regular recipients, add `MAJOR_UPDATE_ENABLED` feature flag
6. **main.py (EXTEND)** — Sequential orchestration: fetch → classify → split → (summarize regular + summarize major) → (send regular + send major) → update states

**Data flow:**
```
Auth → Fetch Emails → Classify → Split
                                 ├─> Regular Emails → Summarize (general) → Format → Send (team) → Update State
                                 └─> Major Updates → Summarize (admin) → Format+ → Send (admins) → Update State
```

**Key architectural decisions:**
- **Classification placement:** Between fetch and summarization (industry standard, enables clean stream separation)
- **Module strategy:** New `classifier.py` module (SRP: classification separate from EWS operations)
- **Summarization strategy:** Extend existing EmailSummarizer with major update methods (code reuse, shared LLM connection)
- **Configuration strategy:** Same .env with namespaced variables (simpler deployment, shared auth settings)
- **State strategy:** Single state file with digest type keys (prevents drift, simplifies management)
- **Orchestration strategy:** Sequential in main.py (shared connection, atomic state, simple deployment)

**Build order:** Phase 1 (EmailClassifier with tests), Phase 2 (Config + State extensions), Phase 3 (LLM prompt + Summarizer extension), Phase 4 (Main orchestration), Phase 5 (Testing with corpus validation).

### Critical Pitfalls

1. **Brittle Pattern-Based Detection** — Microsoft evolves Message Center email formats periodically without notice. Pattern matching breaks, causing false positives (regular emails in admin digest) or false negatives (major updates missed entirely). **Mitigation:** Multi-signal detection with weighted scoring (≥3/5 signals required), LLM classification fallback, detection confidence logging, weekly corpus testing to detect pattern drift.

2. **State Management Corruption** — Tracking two digest types in single invocation creates ambiguous state. Partial failures (one digest succeeds, other fails) cause duplicate emails or skipped emails. **Mitigation:** Separate state per digest type (`last_run_regular`, `last_run_major_update`), atomic state updates with rollback, update state ONLY after digest successfully sent, state validation on load with backup file recovery.

3. **LLM Structured Output Reliability** — Azure OpenAI extracting deadlines and actions from natural language produces inconsistent formats, hallucinated dates, or missing fields. LLMs lack "structural fidelity, relational binding, and numerical grounding" for complex extraction. **Mitigation:** Use Azure OpenAI Structured Outputs API (2024-10-21+) with strict JSON Schema, prompt engineering with examples, validation with confidence scoring, human-in-the-loop for high-stakes items (include full email text if `impact_level: HIGH`).

4. **Recipient Configuration Sprawl** — Adding `MAJOR_UPDATE_TO/CC/BCC` creates configuration complexity. No validation until runtime, no sandbox testing without spamming real mailboxes. **Mitigation:** Structured configuration with email validation, environment-based recipient routing (dev vs prod .env files), enhanced dry-run mode showing both digest recipients, mock EWS in tests, recipient audit logging (never log Bcc in plain text).

5. **Scheduled Task Failure Cascade** — Single Windows Task Scheduler invocation runs both digests. Failure in major updates digest prevents regular digest from sending, causing team to miss all updates. **Mitigation:** Independent digest execution with error isolation (try/except per digest), state updates per digest type (allows retry of failed digest only), timeout management (Task Scheduler 10min, LLM calls 30-60s), logging strategy with clear execution boundaries.

**EWS Deprecation (deployment risk):** EWS disabled by default in August 2026, complete shutdown in 2027. This feature delivers value on deprecated API, requiring Graph API migration within 12-18 months. Research recommends proceeding with EWS for faster v1.0 delivery, defer Graph migration to v2.0.

## Implications for Roadmap

Based on research, suggested phase structure follows dependency order and risk mitigation:

### Phase 1: Detection Strategy & Validation
**Rationale:** Detection reliability is foundation for entire feature. Must validate pattern matching against real Message Center emails before building dual-digest infrastructure. Highest risk area requires early validation.

**Delivers:**
- Working EmailClassifier module with multi-signal detection
- Test corpus of Message Center emails for validation
- Detection confidence logging and metrics
- Unit tests with ≥95% accuracy against corpus

**Addresses:**
- Email Detection (table stakes)
- Pitfall #1 (brittle patterns) mitigation
- Pitfall #6 (false negatives) balance

**Avoids:** Building dual-digest infrastructure on unreliable detection foundation

**Research flag:** May need additional phase research if Message Center email samples unavailable. Consider requesting historical emails from IT admin or using `.eml` fixtures.

---

### Phase 2: State & Configuration Foundation
**Rationale:** State management and configuration must be solid before dual-digest orchestration. Extending existing StateManager and Config prevents disruption to working regular digest.

**Delivers:**
- Extended StateManager with digest type tracking
- Extended Config with MAJOR_UPDATE_* env vars and validation
- Backward compatibility with existing state file format
- Migration path from v0.3 to v1.0 state structure

**Uses:**
- Existing state.py patterns (atomic updates, validation)
- Existing config.py patterns (SUMMARY_TO/CC/BCC namespace)

**Implements:** StateManager and Config architectural components

**Addresses:**
- Separate Recipients (table stakes)
- Pitfall #2 (state corruption) mitigation
- Pitfall #4 (config sprawl) mitigation

**Standard pattern:** Well-documented state management patterns from data pipeline research, no deep research needed.

---

### Phase 3: Major Updates Summarization
**Rationale:** LLM prompt engineering and structured output extraction are complex, require iterative testing. Separate from orchestration to enable focused testing of extraction reliability.

**Delivers:**
- Extended LLMSummarizer with MAJOR_UPDATE_DIGEST_PROMPT
- Azure OpenAI Structured Outputs implementation (API 2024-10-21+)
- Extended EmailSummarizer with major update methods
- HTML formatting with urgency indicators, deadline calendars, action items
- Validation and confidence scoring for extracted data

**Uses:**
- Existing Azure OpenAI integration
- Existing HTML email formatting infrastructure

**Implements:** Dual summarization architectural component

**Addresses:**
- AI-Powered Admin Action Summary (differentiator)
- HTML Email Formatting (table stakes)
- Urgency Visual Indicators (table stakes)
- Pitfall #3 (LLM reliability) mitigation
- Pitfall #7 (LLM cost explosion) monitoring
- Pitfall #8 (HTML rendering) custom template

**Research flag:** Requires phase research for Azure OpenAI Structured Outputs API integration (2024-10-21+ version requirement, JSON Schema specification, prompt engineering best practices from 2026 research).

---

### Phase 4: Dual-Digest Orchestration
**Rationale:** Integration point requires careful error handling and logging. Sequential execution in main.py with independent digest workflows prevents cascade failures.

**Delivers:**
- Extended main.py with classification → split → dual summarize → dual send logic
- Error isolation per digest type (try/except boundaries)
- Conditional sending (skip empty major updates digest)
- Enhanced logging with execution markers
- Feature flag support (MAJOR_UPDATE_ENABLED)

**Implements:** Orchestration layer architectural component

**Addresses:**
- Exclusion from Regular Digest (table stakes)
- Pitfall #5 (failure cascade) mitigation
- Pitfall #9 (empty digest noise) prevention
- Pitfall #10 (log size) rotation

**Avoids:** Parallel execution complexity, EWS connection thread-safety issues

**Standard pattern:** Sequential orchestration with error isolation, no deep research needed.

---

### Phase 5: Testing & Corpus Validation
**Rationale:** Integration testing with real Message Center email formats validates all components working together. Test corpus approach enables regression testing as Microsoft evolves formats.

**Delivers:**
- Integration tests with mock EWS responses
- Test corpus of Message Center emails (`.eml` fixtures)
- Detection accuracy validation script (run in CI/CD)
- State persistence tests across multiple simulated runs
- Failure injection tests (verify error isolation)
- Dry-run validation with both digest recipients displayed

**Addresses:**
- All pitfalls require testing validation
- Detection accuracy measurement
- State management correctness
- LLM extraction reliability
- Recipient configuration validation

**Research flag:** May need phase research for EWS mocking patterns if exchangelib testing not well-documented. Email testing tools (Mailtrap, MailMock) are alternative approach.

---

### Phase 6: Production Deployment & Monitoring
**Rationale:** Gradual rollout with feature flag enables controlled validation in production. Monitoring and alerting detect issues early.

**Delivers:**
- Feature flag deployment (MAJOR_UPDATE_ENABLED=false default)
- Gradual rollout plan (single admin → team → all recipients)
- Monitoring dashboard (detection confidence, digest success rate, execution duration)
- Alerting for anomalies (pattern drift, state corruption, digest failures)
- Rollback plan and documentation

**Addresses:**
- Production cutover risk mitigation
- Detection monitoring for format drift
- Cost tracking for LLM usage increase

**Avoids:** Big-bang deployment, silent failures in production

**Standard pattern:** Feature flag deployment and gradual rollout are industry standard, no deep research needed.

---

### Phase Ordering Rationale

- **Detection first (Phase 1)** — Foundation must be reliable before building on it, highest risk requires early validation
- **State/config before summarization (Phase 2)** — Infrastructure must be solid before complex LLM work
- **Summarization isolated (Phase 3)** — LLM prompt engineering complex, separate from orchestration for focused testing
- **Orchestration after components (Phase 4)** — Integration only after all pieces validated independently
- **Testing throughout, formal phase at end (Phase 5)** — Integration testing validates components working together
- **Deployment last (Phase 6)** — Production rollout only after thorough testing

**Dependency flow:** Detection → State/Config → Summarization → Orchestration → Testing → Deployment

**Risk mitigation:** Each phase addresses specific pitfalls before moving to next phase, preventing compound failures.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Detection):** Need sample Message Center emails for corpus testing — may require requesting from IT admin or using historical `.eml` files
- **Phase 3 (Summarization):** Azure OpenAI Structured Outputs API integration patterns (API version 2024-10-21+ requirement, JSON Schema specification, 2026 prompt engineering best practices)
- **Phase 5 (Testing):** EWS mocking patterns for integration tests if exchangelib testing not well-documented

Phases with standard patterns (skip research-phase):
- **Phase 2 (State/Config):** State management and configuration patterns well-established in existing codebase
- **Phase 4 (Orchestration):** Sequential orchestration with error isolation is straightforward Python pattern
- **Phase 6 (Deployment):** Feature flag deployment and gradual rollout are industry standard practices

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies required, existing stack verified sufficient. Detection strategy proven with multi-signal approach. |
| Features | HIGH | Table stakes identified from Microsoft official docs and admin workflow research. Differentiators aligned with UX best practices. |
| Architecture | HIGH | Classification-first pattern industry standard. Existing codebase patterns extend naturally. Integration points well-defined. |
| Pitfalls | MEDIUM-HIGH | All major pitfalls documented with mitigation strategies from 2026 research. Detection reliability requires validation with real emails. LLM structured outputs proven but prompt tuning may be needed. |

**Overall confidence:** MEDIUM-HIGH

Research is comprehensive with authoritative sources (Microsoft official docs, Azure OpenAI patterns, email classification architectures). Primary uncertainty is Message Center email format variability — needs validation with real email samples in Phase 1.

### Gaps to Address

- **Message Center Email Format Validation:** Research identified sender patterns and subject structure, but exact body format inferred from documentation, not observed in real emails. **Handle during Phase 1:** Request sample Message Center emails from IT admin, build test corpus, validate detection patterns against real data.

- **LLM Prompt Tuning for Admin-Focused Summarization:** Major update digest prompt documented but not tested against actual Message Center email content. **Handle during Phase 3:** Iterative testing of MAJOR_UPDATE_DIGEST_PROMPT with sample emails, validate extraction accuracy, adjust prompt based on failure modes.

- **Azure OpenAI Structured Outputs API Version Compatibility:** Research confirms Structured Outputs require API version 2024-10-21+, but current project's Azure OpenAI client version unknown. **Handle during Phase 3:** Check current `openai` package version, upgrade if needed, validate API version parameter in client initialization.

- **EWS Extended Properties for Detection Enhancement:** Research found low confidence that Message Center emails have custom X-headers or categories. **Handle during Phase 1 (optional):** Test extended properties in production environment during detection validation, add to multi-signal detection if reliable patterns discovered. Not critical for MVP.

- **Recipient Privacy for Bcc Testing:** Research notes Bcc testing difficult because most tools don't support it. **Handle during Phase 5:** Use mock EWS in tests for Bcc validation, or use environment-based routing to test mailbox that allows inspection. Never log Bcc addresses in plain text.

## Sources

### Primary (HIGH confidence)

**Microsoft Official Documentation:**
- [Message center in the Microsoft 365 admin center - Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/message-center?view=o365-worldwide) — Confirmed tag structure (Major Update, Admin Impact), 30-day advance notice, email notification preferences
- [Is o365mc@microsoft.com a legitimate email address? - Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/4694017/is-o365mc@microsoft-com-a-legitimate-email-address) — Confirmed `@email2.microsoft.com` legitimate sender, `o365mc@microsoft.com` phishing
- [How to use structured outputs with Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs?view=foundry-classic) — Azure OpenAI Structured Outputs API patterns, JSON Schema requirements
- [SyncState | Microsoft Learn](https://learn.microsoft.com/en-us/exchange/client-developer/web-service-reference/syncstate-ex15websvcsotherref) — EWS state management patterns

**EWS Deprecation Timeline:**
- [Exchange Online EWS, Your Time is Almost Up](https://techcommunity.microsoft.com/blog/exchange/exchange-online-ews-your-time-is-almost-up/4492361) — Confirmed EWS disabled by default August 2026, shutdown 2027

### Secondary (MEDIUM confidence)

**Email Classification Architecture:**
- [AI Email Assistant Architecture](https://dev.to/malok/building-an-ai-email-assistant-that-prioritizes-sorts-and-summarizes-with-llms-34m8) — Classification before summarization pattern
- [Email Classification Pipeline Architecture](https://github.com/shxntanu/email-classifier) — Multi-stage pipeline with classification
- [LLM Email Processing](https://igorsteblii.medium.com/empower-your-email-routine-with-llm-agents-10x-efficiency-unlocked-e3c81b05d99e) — Multiple prompts for different email types

**LLM Structured Data Extraction:**
- [LLMStructBench: Benchmarking Large Language Model Structured Data Extraction](https://www.arxiv.org/pdf/2602.14743) — LLM structural failures in extraction
- [Diagnosing Structural Failures in LLM-Based Evidence Extraction](https://arxiv.org/abs/2602.10881) — Role reversals, binding drift, numeric misattribution
- [Understanding LLM Limitations: Counting and Parsing Structured Data](https://docs.dust.tt/docs/understanding-llm-limitations-counting-and-parsing-structured-data) — Prompt tuning bottlenecks
- [How to Set Up Prompt Engineering Best Practices for Azure OpenAI GPT-4](https://oneuptime.com/blog/post/2026-02-16-how-to-set-up-prompt-engineering-best-practices-for-azure-openai-gpt-4/view) — 2026 prompt engineering patterns

**State Management & Testing:**
- [Data pipeline state management: An underappreciated challenge](https://www.fivetran.com/blog/data-pipeline-state-management-an-underappreciated-challenge) — Atomic commits with data
- [Advanced state management for incremental loading](https://dlthub.com/docs/general-usage/incremental/advanced-state) — Transactional semantics
- [Python Test Email: Tutorial with Code Snippets [2026]](https://mailtrap.io/blog/python-test-email/) — Email testing patterns
- [21 Best Email Testing Tools in 2026](https://mailtrap.io/blog/email-testing-tools/) — Bcc testing challenges

**Scheduled Task Error Handling:**
- [Error handling in scheduled tasks](https://www.advscheduler.com/error-handling-in-scheduled-tasks) — Separate tasks for phases vs monolithic
- [Windows Task Scheduler Error 0x41301: Complete Fix Guide](https://copyprogramming.com/howto/windows-task-schduler-keep-showing-0x41301) — 2026 best practices (25% time buffer, 15min spacing)

### Tertiary (LOW confidence, needs validation)

**Message Center Email Format:**
- [Updated subject lines for email communications from Message center - M365 Admin](https://m365admin.handsontek.net/updated-subject-lines-for-email-communications-from-message-center/) — Subject line format changes
- [Top 10 Microsoft 365 Message Center & Roadmap Items in February 2026](https://changepilot.cloud/blog/top-10-microsoft-365-message-center-roadmap-items-in-february-2026) — Example Message Center posts with MC IDs

**Pattern Matching Reliability:**
- [How Does AI Email Security Work in 2026](https://strongestlayer.com/blog/ai-email-security-2025-vs-traditional-filters) — Pattern-matching limitations, 50% bypass rate
- [Microsoft Exchange Spam Filtering Update 2026](https://www.getmailbird.com/microsoft-exchange-spam-filtering-update/) — Microsoft shift to AI-based detection

---
*Research completed: 2026-02-23*
*Ready for roadmap: yes*
