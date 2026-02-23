# InboxIQ - Email Summarizer Agent

## What This Is

A Python tool that reads emails from an Exchange Online shared mailbox via EWS, generates AI-powered summaries using Azure OpenAI, and sends HTML digest emails to recipients. Runs hourly via Windows Task Scheduler with incremental fetching.

## Core Value

Busy teams get a clear, actionable summary of their shared mailbox without reading every email.

## Current Milestone: v1.0 Major Updates Digest

**Goal:** Add a separate digest that identifies M365 Message Center major update emails, excludes them from the regular summary, and sends a dedicated admin-focused digest highlighting deadlines and required actions.

**Target features:**
- Detect and classify Message Center major update emails in the shared mailbox
- Exclude major updates from the regular email digest
- Generate a separate Major Updates digest email with action-required deadlines, affected services, and impact levels
- Configurable recipients for the major updates digest (independent from regular digest)
- AI summarization tailored for admin-facing service announcements

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- Validated OAuth 2.0 app-only authentication via MSAL (client credentials flow)
- Validated EWS shared mailbox access with impersonation
- Validated AI-powered email summarization (executive digest, per-email summaries, smart categorization)
- Validated Fallback to basic summarization when LLM unavailable
- Validated HTML-formatted digest email delivery (TO/CC/BCC)
- Validated Incremental state management (only new emails since last run)
- Validated Scheduled hourly execution via Windows Task Scheduler
- Validated SendAs support for custom From address
- Validated CLI options (--debug, --dry-run, --full, --clear-state, --clear-cache)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Detect M365 Message Center major update emails in shared mailbox
- [ ] Exclude detected major updates from regular email digest
- [ ] Generate separate Major Updates digest with deadline/action emphasis
- [ ] Configurable major update recipients (MAJOR_UPDATE_TO/CC/BCC)
- [ ] AI summarization tuned for admin service announcements

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Microsoft Graph API integration for Message Center — Updates already arrive as emails, no need for a second data source
- Web dashboard or UI — CLI tool with email output is sufficient
- Multi-tenant support — Single tenant deployment only
- Real-time alerting — Hourly batch digest is the delivery model

## Context

- **Deployment**: Windows Server with Task Scheduler, runs hourly
- **Organization**: Marsh McLennan (mmc.com), using Exchange Online
- **Shared mailbox**: Receives both regular emails AND M365 Message Center notifications
- **Major updates**: Microsoft tags service announcements with "MAJOR UPDATE", "ADMIN IMPACT", "USER IMPACT", "RETIREMENT" — how these tags appear in email form needs investigation
- **Codebase map**: Available at `.planning/codebase/` (7 documents)

## Constraints

- **Tech stack**: Python 3.10+, exchangelib, msal, openai — extend existing stack, no new frameworks
- **Auth**: Must use existing OAuth 2.0 client credentials flow
- **Deployment**: Must work with existing Windows Task Scheduler setup (single invocation handles both digests)
- **API**: Azure OpenAI only (no direct OpenAI API)

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Separate email for major updates | Different audience (admins vs general team), different emphasis (deadlines/actions vs general summary) | -- Pending |
| Different recipients for major updates | Admin team needs these, not necessarily the same people who get the regular digest | -- Pending |
| Same hourly schedule | Simplifies deployment — one scheduled task handles everything | -- Pending |
| Email-based detection (not Graph API) | Updates already arrive in mailbox, avoid adding new API dependency | -- Pending |

---
*Last updated: 2026-02-23 after milestone v1.0 initialization*
