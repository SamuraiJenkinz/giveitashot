# Phase 8: Cutover - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove EWS entirely from the codebase. Wire `main.py` through `GraphClient`. All existing tests pass against the new Graph implementation. Pure functional swap — identical behavior, new transport layer. `exchangelib` is fully removed as a dependency.

</domain>

<decisions>
## Implementation Decisions

### Email model location
- Claude's discretion on where `Email` dataclass lives after `ews_client.py` deletion (stay in `graph_client.py` or extract to `models.py`)
- Claude's discretion on whether to consolidate other small data classes if natural
- Claude's discretion on import strategy (all importers update vs. re-export for convenience)
- Email dataclass contract stays identical — same fields, same types, no changes

### App identity & messaging
- Update CLI description from "via EWS" to "via Microsoft Graph API"
- Update ALL log messages that reference EWS to say Graph/Graph API — full consistency across all log levels
- Update ALL module docstrings and comments across the entire codebase that reference EWS — clean slate
- Exception class naming: use `GraphClientError` (matches module name, not transport-neutral)

### EWS test disposition
- Delete the 3 EWS backward-compat shim tests from test_auth.py (test_ews_authenticator_alias, test_get_ews_credentials_returns_oauth2credentials, test_get_ews_credentials_raises_on_auth_failure)
- Verify clean: grep entire codebase for `exchangelib` after cutover — zero hits expected (except .eml fixture content)
- Update ROADMAP.md success criteria to reflect actual test count (not hardcoded "167")
- Update test file comments/docstrings that reference EWS alongside the src/ docstring sweep

### Claude's Discretion
- Email dataclass module location and import organization
- Whether to consolidate data classes into a shared module
- Import re-export strategy for backward compatibility during transition

</decisions>

<specifics>
## Specific Ideas

- Full EWS eradication: every .py file should be EWS-free after cutover (only .eml fixtures may mention EWS as email content)
- The `exchangelib` grep verification step is a hard requirement — must be part of the plan validation

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-cutover*
*Context gathered: 2026-03-15*
