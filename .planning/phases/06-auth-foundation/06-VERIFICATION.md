---
phase: 06-auth-foundation
verified: 2026-03-13T14:35:00Z
status: passed
score: 9/9 must-haves verified
human_verification:
  - test: Acquire a live token against Azure AD and decode the JWT aud claim
    expected: aud claim equals https://graph.microsoft.com/
    why_human: Requires live Azure AD credentials with admin-consented Graph permissions. IT approval not yet obtained. Scope string https://graph.microsoft.com/.default is structurally correct per RESEARCH.md and will produce the correct aud claim in production.
---

# Phase 06: Auth Foundation Verification Report

**Phase Goal:** App authenticates to Microsoft Graph with correct scope, acquiring a bearer token that works against Graph endpoints
**Verified:** 2026-03-13T14:35:00Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | GraphAuthenticator.get_access_token() returns a plain str usable as Authorization: Bearer header value | VERIFIED | Return annotation is -> str; test_get_access_token_returns_string asserts isinstance(token, str) and passes |
| 2  | GraphAuthenticator.get_ews_credentials() returns an OAuth2Credentials object (backward-compat shim for main.py) | VERIFIED | Method exists at src/auth.py:83; test_get_ews_credentials_returns_oauth2credentials passes |
| 3  | Scope constant is https://graph.microsoft.com/.default (not EWS scope) | VERIFIED | GRAPH_SCOPE = ["https://graph.microsoft.com/.default"] at src/auth.py:20; test_graph_scope_is_correct passes; no outlook.office365.com found in get_access_token() path |
| 4  | Config.validate() requires exactly MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, SENDER_EMAIL - EWS_SERVER is NOT required | VERIFIED | Live validation run produced error message listing exactly those 4 vars; EWS_SERVER absent from missing.append calls at lines 140-146 of config.py |
| 5  | Bearer token returned as plain string, no OAuth2Credentials wrapper in get_access_token() path | VERIFIED | src/auth.py:67-71 returns result["access_token"] directly; test_get_access_token_returns_string asserts isinstance(token, str) |
| 6  | EWSAuthenticator alias points to GraphAuthenticator (backward compat for main.py) | VERIFIED | EWSAuthenticator = GraphAuthenticator at src/auth.py:110; test_ews_authenticator_alias asserts EWSAuthenticator is GraphAuthenticator and passes |
| 7  | Config.USER_EMAIL aliases SENDER_EMAIL (backward compat for ews_client.py) | VERIFIED | USER_EMAIL: str = SENDER_EMAIL at src/config.py:47; test_user_email_aliases_sender_email passes |
| 8  | Config.EWS_SERVER still exists as deprecated attribute (backward compat) | VERIFIED | Line 41 in src/config.py; hasattr(Config, 'EWS_SERVER') returns True |
| 9  | No regressions - all 178 tests pass | VERIFIED | python -m pytest tests/ -v returned 178 passed, 0 failed, 0 errors |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| src/auth.py | GraphAuthenticator with Graph scope and backward-compat get_ews_credentials() shim | VERIFIED | 111 lines; GraphAuthenticator class; GRAPH_SCOPE constant; get_access_token() -> str; get_ews_credentials() -> OAuth2Credentials; EWSAuthenticator alias |
| src/config.py | Renamed env vars with backward-compat aliases | VERIFIED | 185 lines; MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, SENDER_EMAIL; USER_EMAIL = SENDER_EMAIL alias; EWS_SERVER retained with deprecation comment |
| tests/test_auth.py | 10 unit tests for GraphAuthenticator | VERIFIED | 168 lines; 10 tests all passing; covers scope, token return type, errors, backward-compat shim, alias, cache clearing |
| tests/test_config.py | Updated config tests with new env var names | VERIFIED | 205 lines; SENDER_EMAIL in validate tests; independent backup/restore of SENDER_EMAIL and USER_EMAIL in fixture; test_user_email_aliases_sender_email present |
| .env.example | Updated env var template with Graph-era names | VERIFIED | MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, SENDER_EMAIL present; deprecated comment above EWS_SERVER |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| src/auth.py | src/config.py | Config.CLIENT_ID, Config.CLIENT_SECRET, Config.get_authority() | WIRED | src/auth.py:45-48 reads all three from Config in app property |
| src/auth.py | msal | acquire_token_for_client(scopes=GRAPH_SCOPE) | WIRED | src/auth.py:67; AST confirms no acquire_token_silent call; test_get_access_token_uses_graph_scope asserts called with GRAPH_SCOPE |
| src/auth.py | exchangelib (backward compat) | get_ews_credentials() shim wraps result into OAuth2Credentials | WIRED | src/auth.py:83-101; calls get_access_token() for validation then constructs OAuth2Credentials |
| src/config.py | SENDER_EMAIL alias | USER_EMAIL = SENDER_EMAIL class-level alias | WIRED | src/config.py:47; get_send_from() references cls.USER_EMAIL; alias ensures backward compat |

### Requirements Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| AUTH-01: App uses Graph API scope not EWS scope | SATISFIED | GRAPH_SCOPE = ["https://graph.microsoft.com/.default"] replaces old EWS scope |
| AUTH-02: Bearer token returned as plain string | SATISFIED | get_access_token() -> str confirmed by annotation and unit test |
| AUTH-03: MICROSOFT_* env vars replace AZURE_* | SATISFIED | All three AZURE_ vars replaced; validate() reports MICROSOFT_ names in errors |
| AUTH-04: EWS_SERVER no longer required | SATISFIED | Exists as deprecated attribute only; not in missing.append list |
| Roadmap criterion 1 (aud claim) | DEFERRED | Requires live credentials; scope string is correct per RESEARCH.md |
| Roadmap criterion 2 (scope constant) | SATISFIED | GRAPH_SCOPE line verified in source |
| Roadmap criterion 3 (only 4 auth vars required) | SATISFIED | Confirmed via live validate() call |
| Roadmap criterion 4 (bearer token as plain string) | SATISFIED | Return type annotation and unit test |

### Anti-Patterns Found

None. No TODOs, FIXMEs, placeholder returns, or empty handlers found in modified files.

The comment on src/auth.py:66 ("acquire_token_silent is redundant") is an architectural decision note, not a placeholder.

### Human Verification Required

#### 1. Live JWT aud Claim Verification

**Test:** Configure .env with real Azure AD credentials (admin-consented Mail.Read and Mail.Send Graph permissions), call GraphAuthenticator().get_access_token(), decode the JWT and inspect the aud claim (e.g., via jwt.ms or python-jwt decode with verify_signature=False).
**Expected:** aud claim equals https://graph.microsoft.com/
**Why human:** Requires live Azure AD tenant credentials. IT/security approval from Marsh McLennan tenant is a documented blocker in STATE.md. The scope string https://graph.microsoft.com/.default is architecturally correct per RESEARCH.md - tokens acquired with this scope always produce aud: https://graph.microsoft.com/.

### Gaps Summary

No gaps. All 9 must-have truths verified against the actual codebase.

The one item deferred to human verification (aud claim) is an environmental constraint, not a code deficiency. The scope string in the code is structurally correct to produce the expected aud claim. This deferral was documented in the PLAN before execution as a known limitation pending IT credential approval.

---

_Verified: 2026-03-13T14:35:00Z_
_Verifier: Claude (gsd-verifier)_
