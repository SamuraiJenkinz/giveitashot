# Phase 3: Digest Content Extraction - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract Message Center fields from major update emails and format them into a professional HTML digest email. Each update displays MC ID, action-required date, affected services, category, and published/updated dates. Digest uses urgency color-coding based on deadline proximity. AI-powered action extraction is Phase 4; this phase handles structured field extraction and HTML formatting only.

</domain>

<decisions>
## Implementation Decisions

### Urgency & color-coding
- Traffic light color scheme: Red (critical), Amber/Orange (high), Green (normal)
- Updates with no action-required date treated as Normal urgency tier
- Urgency displayed via left-border accent on each update card (consistent with existing regular digest pattern for urgent/action items)
- Claude's Discretion: Exact day thresholds for Critical/High/Normal tiers

### Email layout & structure
- Updates sorted by urgency tier first, then by deadline (soonest first) within each tier
- Grouped visually by urgency tier with section headers ("Critical", "High", "Normal")
- Stats header at top showing total updates + count per urgency tier (e.g., "2 Critical, 5 High, 3 Normal")
- Claude's Discretion: Body text depth per update (preview vs full)

### Field extraction & formatting
- Claude's Discretion: Extraction approach (subject line, body HTML parsing, or combination) based on email format analysis
- Claude's Discretion: Date display format (relative+absolute vs absolute-only)
- Claude's Discretion: Affected services display format (tag badges vs comma-separated)
- Claude's Discretion: Missing field handling (placeholder vs omit, per-field basis)

### Empty & edge states
- Duplicate MC IDs: Show latest version only, display "Updated" badge to indicate revision
- Claude's Discretion: Whether to send email on zero major updates (likely skip to reduce noise)
- Claude's Discretion: High volume handling (20+ updates)
- Claude's Discretion: Email subject line format (urgency counts vs simple)

### Claude's Discretion
- Urgency tier day thresholds (Critical/High/Normal cutoffs)
- Body text preview depth per update
- Field extraction parsing approach
- Date display format
- Affected services display format
- Missing field handling strategy
- Zero-update behavior
- High-volume display strategy
- Email subject line format

</decisions>

<specifics>
## Specific Ideas

- Traffic light colors (red/amber/green) are universally understood — stick with this over the existing digest's Material Design palette for urgency specifically
- Left-border accent pattern already exists in regular digest (urgent items, action items sections) — reuse this visual language
- Stats header with urgency counts mirrors the regular digest's stats bar pattern — familiar layout for recipients who get both digests
- Deduplication by MC ID with "Updated" badge ensures admins see only the latest version but know it was revised

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-digest-content-extraction*
*Context gathered: 2026-02-24*
