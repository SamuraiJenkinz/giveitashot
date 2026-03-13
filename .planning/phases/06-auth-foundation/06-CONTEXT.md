# Phase 6: Auth Foundation - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

App authenticates to Microsoft Graph using MSAL client credentials flow, acquiring a bearer token that works against Graph endpoints. Replaces EWS auth entirely. No dual-mode, no fallback to EWS.

</domain>

<decisions>
## Implementation Decisions

### Authentication mechanism
- MSAL client credentials flow (confidential client application)
- Direct REST calls via `requests` + MSAL — not msgraph-sdk (async-only, daemon bug)
- Bearer token returned as plain string for `Authorization: Bearer {token}` header

### Environment variables
- Four required env vars, all validated at startup (fail fast if any missing):
  - `MICROSOFT_TENANT_ID` — Azure AD Directory ID
  - `MICROSOFT_CLIENT_ID` — Application (Client) ID from app registration
  - `MICROSOFT_CLIENT_SECRET` — Client Secret VALUE (not the Secret ID); expires in 24 months
  - `SENDER_EMAIL` — Shared mailbox sender address
- `EWS_SERVER` is removed — no longer referenced anywhere

### Scope configuration
- Scope: `https://graph.microsoft.com/.default` (application-level permissions)
- Required Graph permissions: `Mail.Read` and `Mail.Send` (application, not delegated)
- Admin consent required before live testing (code can be written first)

### Dependency strategy
- Zero new dependencies beyond MSAL (`msal` package)
- `exchangelib` removed from requirements.txt in Phase 8 (not this phase)

### Claude's Discretion
- Token caching strategy (MSAL built-in vs fresh acquisition per run)
- Error handling on auth failure (retry logic, logging, exit behavior)
- Internal module structure and class design

</decisions>

<specifics>
## Specific Ideas

- Client secret expires in 24 months — consider adding a comment or log reminder about rotation
- Smoke test is blocked until IT/security grants admin consent on Azure app registration
- Marsh McLennan tenant mailbox scoping approach (ApplicationAccessPolicy vs Exchange RBAC) still needs IT clarification — not blocking code, just live integration testing

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-auth-foundation*
*Context gathered: 2026-03-13*
