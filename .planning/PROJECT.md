# InboxIQ - Email Summarizer Agent

## What This Is

A Python tool that reads emails from an Exchange Online shared mailbox via EWS, generates AI-powered summaries using Azure OpenAI, and sends HTML digest emails to recipients. Now includes a dual-digest system: regular email summaries plus a dedicated M365 Message Center major updates digest with deadline tracking and AI-extracted admin actions. Runs hourly via Windows Task Scheduler with incremental fetching.

## Core Value

Busy teams get a clear, actionable summary of their shared mailbox without reading every email.

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
- Validated M365 Message Center major update detection (multi-signal weighted scoring) -- v1.0
- Validated Major update exclusion from regular digest -- v1.0
- Validated Separate Major Updates digest with professional HTML formatting -- v1.0
- Validated Configurable major update recipients (MAJOR_UPDATE_TO/CC/BCC) -- v1.0
- Validated AI-powered admin action extraction with deadline countdown -- v1.0
- Validated Urgency-based visual indicators (Critical/High/Normal color-coding) -- v1.0
- Validated MC metadata display (Message ID, affected services, categories, dates) -- v1.0
- Validated Error isolation (digest failure independence) -- v1.0
- Validated Dual-digest state management (independent state per digest type) -- v1.0

### Active

<!-- Current scope. Building toward these. -->

## Current Milestone: v2.0 Graph API Migration

**Goal:** Replace EWS (exchangelib) with Microsoft Graph API for all email operations before the August 2026 deprecation deadline.

**Target features:**
- Graph API email reading from shared mailbox (replace exchangelib fetch)
- Graph API email sending for both digest types (replace exchangelib send)
- Same app registration with added Graph permissions (Mail.Read, Mail.Send)
- Complete removal of exchangelib dependency and all EWS code
- Pure functional swap — identical behavior, new transport layer

**Context:**
- Existing Graph sending pattern available from MDInsights project (client credentials, MSAL, Mail.Send)
- Same Entra app registration, add Graph permissions alongside existing EWS permissions
- Deadline: EWS disabled by default August 2026, complete shutdown 2027

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Microsoft Graph API integration for Message Center -- Updates already arrive as emails, no need for a second data source (revisit for Graph migration)
- Web dashboard or UI -- CLI tool with email output is sufficient
- Multi-tenant support -- Single tenant deployment only
- Real-time alerting -- Hourly batch digest is the delivery model
- Automated task creation (Planner, etc.) -- Fragile, org-specific workflow
- Full message body in digest -- Posts are lengthy, defeats digest purpose (AI summary + link instead)
- Per-admin filtering -- Complex personalization, not suited to shared digest model

## Context

- **Deployment**: Windows Server with Task Scheduler, runs hourly
- **Organization**: Marsh McLennan (mmc.com), using Exchange Online
- **Shared mailbox**: Receives both regular emails AND M365 Message Center notifications
- **Codebase**: ~4,700 lines Python across 19 source/test files, 167 tests passing
- **Tech stack**: Python 3.10+, exchangelib, msal, openai, pydantic
- **Shipped**: v1.0 Major Updates Digest (2026-02-26)
- **Known timeline**: EWS deprecated by default August 2026, complete shutdown 2027

## Constraints

- **Tech stack**: Python 3.10+, exchangelib, msal, openai -- extend existing stack, no new frameworks
- **Auth**: Must use existing OAuth 2.0 client credentials flow
- **Deployment**: Must work with existing Windows Task Scheduler setup (single invocation handles both digests)
- **API**: Azure OpenAI only (no direct OpenAI API)
- **EWS deadline**: Must plan Graph API migration before August 2026

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Separate email for major updates | Different audience (admins vs general team), different emphasis (deadlines/actions vs general summary) | Good -- clean separation of concerns |
| Different recipients for major updates | Admin team needs these, not necessarily the same people who get the regular digest | Good -- presence-based toggle works well |
| Same hourly schedule | Simplifies deployment -- one scheduled task handles everything | Good -- single invocation, independent state |
| Email-based detection (not Graph API) | Updates already arrive in mailbox, avoid adding new API dependency | Good -- multi-signal detection reliable |
| Classification threshold 70% | Requires 2+ strong signals to reduce false positives | Good -- no false positives in testing |
| Graceful degradation throughout | Classification, AI extraction, digest pipeline all fail safely | Good -- error isolation verified |
| Azure OpenAI structured outputs | Pydantic models with strict JSON schema for action extraction | Good -- reliable structured data |
| Presence-based feature toggle | MAJOR_UPDATE_TO non-empty activates major digest, no separate flag | Good -- simple, intuitive |

---
*Last updated: 2026-03-12 after v2.0 milestone start*
