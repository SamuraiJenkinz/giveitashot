# Phase 5: Integration Testing - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

End-to-end validation of the dual-digest system running as a single hourly scheduled task. Both regular and major update digests execute correctly, failures are isolated, edge cases (empty inbox, state corruption) are handled, and dry-run mode provides visual HTML previews. This phase does NOT add new features — it validates what's already built across Phases 1-4.

</domain>

<decisions>
## Implementation Decisions

### Test email samples
- User will provide real Message Center .eml files exported from the shared mailbox
- Claude decides the minimum number needed for meaningful coverage
- .eml files must be sanitized (strip tenant-specific details, real names, internal URLs) before committing
- Sanitized .eml files committed to repo (e.g., tests/fixtures/) as test fixtures
- Supplement with synthetic fixtures for edge cases real samples don't cover

### Dry-run experience
- Dry-run saves generated HTML digests to `output/` folder in project root (gitignored)
- Separate files: `regular_digest.html` and `major_digest.html`
- Auto-open HTML files in default browser after saving
- Keep existing console summary output (recipients, counts, urgency breakdown) alongside HTML file saves
- Console output prints the file path for reference

### Multi-run state simulation
- Integration tests simulate 3-5 consecutive hourly runs to validate state transitions
- Test sequence: empty inbox, regular only, mixed (regular + major), major only — verify state is correct after each
- State corruption is the primary concern — tests must cover corrupted/malformed state file recovery
- State corruption recovery: Claude's discretion on safest strategy

### Production readiness
- Manual dry-run against real mailbox required before enabling production sends
- Workflow: tests pass with real .eml fixtures -> manual `--dry-run` against live mailbox -> visual verify both digests -> enable sending
- State corruption is the top concern to validate against

### Claude's Discretion
- State corruption recovery strategy (reset vs skip vs other)
- Minimum number of real .eml samples needed
- Exact test scenario sequencing for multi-run simulation
- Which edge cases need synthetic fixtures beyond real samples
- Whether to add any logging/alerting for production failure detection

</decisions>

<specifics>
## Specific Ideas

- State corruption is the user's biggest production concern — prioritize state transition testing
- User wants visual HTML preview as part of dry-run (not just console logs) — this is a dry-run enhancement
- Manual dry-run against real mailbox is the final gate before production — not just automated tests passing

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-integration-testing*
*Context gathered: 2026-02-25*
