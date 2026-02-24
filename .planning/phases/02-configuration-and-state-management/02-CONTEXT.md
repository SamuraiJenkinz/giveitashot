# Phase 2: Configuration and State Management - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Infrastructure to support dual-digest workflows: separate recipient configuration for major update digests, independent state tracking per digest type, and configuration validation. Extends existing Config class and StateManager patterns. Does not include digest content formatting, sending logic, or AI features.

</domain>

<decisions>
## Implementation Decisions

### Major Digest Optionality
- If MAJOR_UPDATE_TO is not configured, major digest silently does not run (debug log at most)
- Major digest activates automatically when MAJOR_UPDATE_TO has recipients (opt-out model)
- When no major update emails found, send nothing (no "all clear" emails)
- Major digest failure never blocks regular digest — log the error, regular digest continues

### Recipient Configuration
- MAJOR_UPDATE_TO, MAJOR_UPDATE_CC, MAJOR_UPDATE_BCC are fully independent from SUMMARY_TO/CC/BCC
- No fallback to regular digest recipients — major digest recipients must be explicitly configured
- Overlap between regular and major recipient lists is allowed (same person gets both emails)
- Same SEND_FROM address for both digests — no separate MAJOR_UPDATE_SEND_FROM
- Same comma-separated email format, reuse existing `_parse_email_list()` helper

### State Isolation
- Single `.state.json` file with separate keys: `regular_last_run` and `major_last_run`
- If state is corrupted or missing for one digest type, treat as first run (full fetch) for that type only
- Migrate existing `last_run` key to `regular_last_run` for backwards compatibility
- State updates happen only after successful email send — failed send means retry next run

### Feature Toggle
- Presence-based activation: MAJOR_UPDATE_TO has recipients = enabled, empty/missing = disabled
- No explicit ENABLE_MAJOR_DIGEST toggle — presence of recipients is the toggle
- `--dry-run` mode previews both regular and major digest content and recipients
- Add `--regular-only` and `--major-only` CLI flags for selective execution
- `.env.example` gets a clearly grouped `# Major Update Digest` section with all MAJOR_UPDATE_* vars commented out

### Claude's Discretion
- Internal method naming and organization within Config class
- StateManager refactoring approach (extend vs restructure)
- Validation error message wording
- Logging verbosity levels for debug vs info

</decisions>

<specifics>
## Specific Ideas

- Follow the existing `SUMMARY_TO`/`SUMMARY_CC`/`SUMMARY_BCC` pattern exactly for `MAJOR_UPDATE_TO`/`CC`/`BCC`
- State migration should be transparent — existing deployments upgrade without manual intervention
- The `--regular-only` / `--major-only` flags pair with `--dry-run` for testing individual digest types

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-configuration-and-state-management*
*Context gathered: 2026-02-24*
