# Phase 4: AI Enhancement - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

AI extracts actionable admin tasks from major update email bodies and displays deadline countdowns in the digest. Uses the existing Azure OpenAI integration. Does not add new digest types, new recipients, or new detection logic — those are complete from prior phases.

</domain>

<decisions>
## Implementation Decisions

### Action extraction
- Actions displayed inline within each major update's card/section (not a separate summary section)
- Action detail level and count per email: Claude's discretion — pick what works best for digest readability
- Role tagging (e.g. "Global Admin"): Claude's discretion — include if it adds value without clutter

### LLM interaction
- Use existing Azure OpenAI integration (`llm_summarizer.py` pattern, `CHATGPT_ENDPOINT` + `AZURE_OPENAI_API_KEY`)
- One LLM call per major update email — isolated failures, simpler error handling
- AI extraction is always on when major digest is enabled — no separate toggle
- Reuse existing Azure OpenAI client/config, no new credentials needed

### Failure handling
- AI extraction failure per email: fall back to existing body preview (200 char truncation), no action section shown
- Total Azure OpenAI outage: send major digest without AI-extracted actions — all existing fields (MC ID, dates, urgency, services) still display
- No visible warning to recipients on failure — digest sends with whatever data is available
- Strict structured output validation — reject entries that don't match expected schema (catch hallucinated or malformed data)
- LLM call timeout: Claude's discretion based on existing codebase patterns
- Error logging level: Claude's discretion based on existing project logging patterns

### Deadline countdown
- Display days remaining until action-required date in the digest
- Specific display format and urgency threshold changes: Claude's discretion

### Claude's Discretion
- Action detail level (short imperative vs detailed steps)
- Action count cap per email
- Whether to include role/actor tags on actions
- LLM call timeout duration
- Error logging granularity
- Deadline countdown display format
- Prompt engineering approach and structured output schema
- Loading/processing indicators if needed

</decisions>

<specifics>
## Specific Ideas

- Existing `llm_summarizer.py` already handles Azure OpenAI calls — new extraction should follow the same client pattern
- Existing `USE_LLM_SUMMARY` toggle is for regular digest summaries only — AI action extraction has no separate toggle
- Body preview fallback (200 chars at word boundary with "..." suffix) already exists from Phase 3

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-ai-enhancement*
*Context gathered: 2026-02-24*
