---
phase: 06
plan: 01
subsystem: auth
tags: [msal, graph-api, oauth2, exchangelib, backward-compat, config]

dependency-graph:
  requires: []
  provides:
    - GraphAuthenticator class with Graph API scope and backward-compat get_ews_credentials() shim
    - Updated Config with MICROSOFT_* env vars and SENDER_EMAIL
    - EWSAuthenticator alias for main.py backward compat
  affects:
    - Phase 07: Graph client will use GraphAuthenticator.get_access_token() bearer token
    - Phase 08: Remove EWSAuthenticator alias, get_ews_credentials() shim, USER_EMAIL alias, EWS_SERVER

tech-stack:
  added: []
  patterns:
    - Client credentials flow (MSAL acquire_token_for_client, no acquire_token_silent)
    - Backward-compat alias pattern (EWSAuthenticator = GraphAuthenticator)
    - Class-level env var aliasing (USER_EMAIL = SENDER_EMAIL)

key-files:
  created:
    - tests/test_auth.py
  modified:
    - src/auth.py
    - src/config.py
    - tests/test_config.py
    - .env.example

decisions:
  - description: "Drop acquire_token_silent in get_access_token()"
    rationale: "MSAL 1.23+ handles internal caching in acquire_token_for_client; the silent call was redundant noise"
    alternatives: ["Keep acquire_token_silent for explicit cache check"]
    outcome: "Simpler code, fewer MSAL calls, verified by test_acquire_token_silent_not_called"

  - description: "get_ews_credentials() shim calls get_access_token() to validate auth before constructing OAuth2Credentials"
    rationale: "Validates that Graph auth is working while preserving the contract exchangelib expects"
    alternatives: ["Skip validation, just construct OAuth2Credentials directly"]
    outcome: "test_get_ews_credentials_raises_on_auth_failure confirms the shim surfaces auth errors correctly"

  - description: "USER_EMAIL and SENDER_EMAIL backed up independently in backup_config fixture"
    rationale: "Class-level alias USER_EMAIL = SENDER_EMAIL is evaluated once at class definition; subsequent mutations are independent"
    alternatives: ["Only backup SENDER_EMAIL"]
    outcome: "Prevents test pollution; test_user_email_aliases_sender_email documents the aliasing contract"

  - description: "Defer live aud claim verification to integration testing"
    rationale: "Verifying aud: https://graph.microsoft.com/ requires live Azure AD credentials — IT admin consent not yet obtained"
    alternatives: ["Block plan on IT approval"]
    outcome: "Scope string https://graph.microsoft.com/.default is correct per RESEARCH.md; deferred to Phase 6 integration gate"

metrics:
  duration: "4 minutes"
  completed: "2026-03-13"
---

# Phase 06 Plan 01: Auth Foundation — GraphAuthenticator and Config Update Summary

**One-liner:** GraphAuthenticator with `https://graph.microsoft.com/.default` scope replaces EWSAuthenticator; backward-compat shims preserve main.py and ews_client.py through Phase 8.

## What Was Built

### src/auth.py — GraphAuthenticator

Rewrote `EWSAuthenticator` as `GraphAuthenticator` targeting the Microsoft Graph API scope instead of EWS scope (`outlook.office365.com`).

Key changes:
- `GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]` module-level constant
- `get_access_token()` returns a plain `str` bearer token — usable directly as `Authorization: Bearer <token>` header value
- Removed redundant `acquire_token_silent()` call (MSAL 1.23+ handles internal caching in `acquire_token_for_client`)
- `get_ews_credentials()` backward-compat shim: calls `get_access_token()` to validate auth works, then returns an `OAuth2Credentials` object for exchangelib — preserving the `main.py` line 154 contract through Phase 7
- `EWSAuthenticator = GraphAuthenticator` alias at module level — `from .auth import EWSAuthenticator` in `main.py` continues to work unchanged

### src/config.py — Env Var Renames with Backward Compat Aliases

- `TENANT_ID` now reads from `MICROSOFT_TENANT_ID` (was `AZURE_TENANT_ID`)
- `CLIENT_ID` now reads from `MICROSOFT_CLIENT_ID` (was `AZURE_CLIENT_ID`)
- `CLIENT_SECRET` now reads from `MICROSOFT_CLIENT_SECRET` (was `AZURE_CLIENT_SECRET`)
- `SENDER_EMAIL` added, reads from `SENDER_EMAIL` env var
- `USER_EMAIL = SENDER_EMAIL` class-level alias preserved for `ews_client.py` backward compat (Phase 8 removal)
- `EWS_SERVER` retained with deprecation comment — `ews_client.py` still references it at runtime
- `validate()` checks `SENDER_EMAIL` and reports `MICROSOFT_*` var names in error messages
- `get_send_from()` continues to work via `USER_EMAIL` alias

### tests/test_auth.py — 10 New Unit Tests

| Test | Behavior Verified |
|------|------------------|
| `test_graph_scope_is_correct` | `GRAPH_SCOPE == ["https://graph.microsoft.com/.default"]` |
| `test_get_access_token_returns_string` | Returns plain `str`, not wrapped object |
| `test_get_access_token_raises_on_error` | Raises `AuthenticationError` on MSAL error dict |
| `test_get_access_token_raises_on_exception` | Raises `AuthenticationError` on MSAL exception |
| `test_get_access_token_uses_graph_scope` | `acquire_token_for_client` called with `GRAPH_SCOPE` |
| `test_acquire_token_silent_not_called` | `acquire_token_silent` is never invoked |
| `test_ews_authenticator_alias` | `EWSAuthenticator is GraphAuthenticator` |
| `test_clear_cache_resets_app` | `clear_cache()` sets `_app = None` |
| `test_get_ews_credentials_returns_oauth2credentials` | Shim returns `OAuth2Credentials` instance |
| `test_get_ews_credentials_raises_on_auth_failure` | Shim surfaces auth errors correctly |

### tests/test_config.py — Updated

- `backup_config` fixture now independently saves and restores `SENDER_EMAIL` AND `USER_EMAIL` (prevents test pollution from class-level alias evaluation at import time)
- All validate tests set both `Config.SENDER_EMAIL` and `Config.USER_EMAIL` to the same value (mirrors env-loading behaviour)
- New `test_user_email_aliases_sender_email` test documents the aliasing contract

### .env.example — Updated

- `AZURE_TENANT_ID` → `MICROSOFT_TENANT_ID`
- `AZURE_CLIENT_ID` → `MICROSOFT_CLIENT_ID`
- `AZURE_CLIENT_SECRET` → `MICROSOFT_CLIENT_SECRET`
- `USER_EMAIL` → `SENDER_EMAIL` with updated comment
- `EWS_SERVER` line preceded by `# DEPRECATED — will be removed in v2.0 cutover`

## Success Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `get_access_token()` returns plain `str` | PASS | `test_get_access_token_returns_string` asserts `isinstance(token, str)` |
| `get_ews_credentials()` returns `OAuth2Credentials` | PASS | `test_get_ews_credentials_returns_oauth2credentials` passes |
| `GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]` | PASS | `test_graph_scope_is_correct` passes; confirmed in `src/auth.py` line 20 |
| Config reads from `MICROSOFT_*` vars | PASS | `grep missing.append src/config.py` shows all 4 new names |
| `Config.USER_EMAIL` aliases `SENDER_EMAIL` | PASS | `test_user_email_aliases_sender_email` passes |
| `EWSAuthenticator` aliases `GraphAuthenticator` | PASS | `test_ews_authenticator_alias` passes |
| `Config.EWS_SERVER` still exists | PASS | `hasattr(Config, 'EWS_SERVER')` returns `True` |
| No `acquire_token_silent` call | PASS | `test_acquire_token_silent_not_called` passes |
| `backup_config` saves SENDER_EMAIL and USER_EMAIL independently | PASS | Verified in fixture implementation |
| All 178 tests pass | PASS | `python -m pytest tests/ -v` — 178 passed, 0 failed |

## Deferred Verification

**aud claim live verification (roadmap criterion 1) deferred — requires live credentials.**

Scope string `https://graph.microsoft.com/.default` is correct per RESEARCH.md and will produce `aud: https://graph.microsoft.com/` in production tokens. Live verification (decoding a real JWT and checking the `aud` claim) cannot be performed until:
1. Azure app registration has `Mail.Read` and `Mail.Send` Graph application permissions with admin consent
2. IT/security approval from Marsh McLennan tenant

This verification is gated by the same IT prerequisites noted in STATE.md blockers. It will be performed as part of Phase 6 integration testing once credentials are available.

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: Config and .env.example | `a8f98b1` | `src/config.py`, `tests/test_config.py`, `.env.example` |
| Task 2: auth.py + test_auth.py | `051fe9c` | `src/auth.py`, `tests/test_auth.py` |

## Next Phase Readiness

Phase 07 (Graph Client) can now:
- Call `GraphAuthenticator().get_access_token()` to get a bearer token string
- Use that token directly as `Authorization: Bearer <token>` in `requests` headers to Graph API endpoints

Phase 08 (EWS Cutover) will need to:
- Remove `EWSAuthenticator = GraphAuthenticator` alias from `auth.py`
- Remove `get_ews_credentials()` shim from `GraphAuthenticator`
- Remove `USER_EMAIL = SENDER_EMAIL` alias from `config.py`
- Remove `EWS_SERVER` from `config.py`
- Update `main.py` to call `get_access_token()` directly instead of `get_ews_credentials()`
