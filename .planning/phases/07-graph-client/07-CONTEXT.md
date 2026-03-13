# Phase 7: Graph Client - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace `ews_client.py` with `graph_client.py` that reads emails from the shared mailbox and sends HTML digest emails via Microsoft Graph REST API. The `Email` dataclass contract must be fully preserved — same fields, same types, same behavior. All downstream consumers (classifier, summarizer, extractor, tests) continue working unchanged. Phase 8 handles the cutover (import rewiring, EWS removal).

</domain>

<decisions>
## Implementation Decisions

### Sent Items behavior
- Save sent emails to Sent Items — match current EWS `send_and_save()` behavior
- Both regular and major digests save to Sent Items (consistent rule, no per-digest-type toggle)
- Graph's `sendMail` with `saveToSentItems: true` handles this atomically

### Error handling
- Single error type: `GraphClientError` (matches current `EWSClientError` pattern)
- Error messages MUST include HTTP status code and Graph error details (e.g., "Failed to retrieve emails: 403 Forbidden - Insufficient permissions for mailbox")
- Individual email parse failures: log warning, skip the bad email, continue processing the rest (matches current EWS behavior)
- Token expiry mid-pagination: silently re-authenticate via MSAL and retry the failed page (don't fail the whole operation)

### Throttling resilience
- Retry on 429 (throttled) AND transient 5xx (502, 503, 504) errors
- Maximum 3 retry attempts per request, respecting Graph's `Retry-After` header
- Log each retry attempt (e.g., "Throttled by Graph API, retrying in 5s (attempt 2/3)")
- If all retries exhausted, raise `GraphClientError` with details

### Body content mapping
- `body_content`: Claude's discretion on whether to strip HTML from Graph's `body.content` or use Graph's text representation — goal is preserving what classifier/summarizer currently receive
- `body_preview`: Keep current truncation approach (first 200 chars of body_content), do NOT use Graph's `bodyPreview` field
- `received_datetime`: Parse Graph's ISO 8601 string to timezone-aware UTC datetime (matches current behavior)

### Claude's Discretion
- `body_content` source: strip HTML from `body.content` vs use Graph's text — whichever best preserves current summarizer/classifier input
- `Email.id` source: `internetMessageId` vs Graph's internal `id` — pick what's most useful for deduplication and tracing
- Exact retry backoff timing (respect `Retry-After` header, use exponential backoff as fallback)
- Pagination implementation details (follow `@odata.nextLink` vs manual `$skip`)
- Internal HTTP helper structure

</decisions>

<specifics>
## Specific Ideas

- Error messages should aid production debugging — include HTTP status + Graph error description, not just generic wrapping
- Retry logging should be visible in normal (non-debug) log output so operators know when throttling occurs
- The `Email` dataclass stays in `graph_client.py` (mirrors current placement in `ews_client.py`) — Phase 8 rewires all imports

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-graph-client*
*Context gathered: 2026-03-13*
