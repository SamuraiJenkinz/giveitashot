---
phase: 08-cutover
verified: 2026-03-16T00:31:06Z
status: passed
score: 6/6 must-haves verified
---

# Phase 8: EWS Cutover Verification Report

**Phase Goal:** EWS is fully removed, `main.py` routes through `GraphClient`, and all 210 tests pass (214 pre-cutover minus 4 deleted EWS shim tests)
**Verified:** 2026-03-16T00:31:06Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `exchangelib` does not appear in `requirements.txt` and cannot be imported from any `.py` file | VERIFIED | `grep -rn "exchangelib" requirements.txt` returns no output; `grep -rn "exchangelib" --include="*.py" src/ tests/` returns no output |
| 2 | `src/ews_client.py` does not exist — no EWS file remains in `src/` | VERIFIED | `test -f src/ews_client.py` fails; `python -c "importlib.import_module('src.ews_client')"` raises `ModuleNotFoundError` |
| 3 | `main.py` executes without importing or referencing any EWS symbol | VERIFIED | `from .auth import GraphAuthenticator` (line 24), `from .graph_client import GraphClient, GraphClientError` (line 27); zero hits for any EWS symbol in `src/main.py` |
| 4 | All 210 tests pass with import paths updated to `src.graph_client` | VERIFIED | `python -m pytest tests/ -q` → `210 passed in 0.52s`; `--collect-only` confirms `210 tests collected` |
| 5 | `grep -rn 'EWSClient\|EWSClientError\|EWSAuthenticator\|ews_client\|get_ews_credentials\|EWS_SERVER'` across all `.py` files returns zero hits | VERIFIED | Comprehensive grep returns exit code 1 (no matches) across `src/` and `tests/` |
| 6 | Every log message, docstring, and comment referencing EWS has been updated to Graph API language | VERIFIED | Greps for `"Exchange Web Services"`, `"via EWS"`, `"EWS path"`, `"EWS behaviour"`, `"EWS pattern"`, `"\(EWS\)"` in all `.py` files return zero hits |

**Score:** 6/6 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/graph_client.py` | Canonical Email dataclass, GraphClient, GraphClientError | VERIFIED | 419 lines; `class GraphClient` present (grep count: 2 class definition + uses); imports clean |
| `src/auth.py` | GraphAuthenticator only — no alias, no shim, no exchangelib import | VERIFIED | 84 lines; `class GraphAuthenticator` present; no `EWSAuthenticator`, no `exchangelib`, no `get_ews_credentials` |
| `src/config.py` | Config without `EWS_SERVER` or `USER_EMAIL`; `get_send_from()` falls back to `SENDER_EMAIL` | VERIFIED | 178 lines; `SENDER_EMAIL` defined at line 41; `get_send_from()` returns `cls.SENDER_EMAIL` at line 109; `hasattr(Config, 'EWS_SERVER')` is False; `hasattr(Config, 'USER_EMAIL')` is False |
| `src/main.py` | Entry point wired to GraphAuthenticator and GraphClient | VERIFIED | 370 lines; `from .auth import GraphAuthenticator, AuthenticationError` (line 24); `from .graph_client import GraphClient, GraphClientError` (line 27); `GraphClient(authenticator)` at line 150; `GraphClientError` caught at line 351 |
| `src/ews_client.py` | Must NOT exist | VERIFIED | File absent; ModuleNotFoundError on import attempt |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/main.py` | `src/graph_client.py` | `from .graph_client import GraphClient, GraphClientError` | WIRED | Line 27 import; `GraphClient(authenticator)` used at line 150; `graph_client.get_shared_mailbox_emails()` at line 173; `graph_client.send_email()` at lines 239 and 325; `GraphClientError` caught at line 351 |
| `src/main.py` | `src/auth.py` | `from .auth import GraphAuthenticator` | WIRED | Line 24 import; `GraphAuthenticator()` instantiated at line 141 — no `EWSAuthenticator` anywhere |
| `src/classifier.py` | `src/graph_client.py` | `from .graph_client import Email` | WIRED | Line 10; `python -c "from src.classifier import EmailClassifier"` passes cleanly |
| `tests/conftest.py` | `src/graph_client.py` | `from src.graph_client import Email` | WIRED | Line 11; Email used in all fixtures; 210 tests pass |
| `tests/test_classifier.py` | `src/graph_client.py` | `from src.graph_client import Email` | WIRED | Line 9 |
| `tests/test_extractor.py` | `src/graph_client.py` | `from src.graph_client import Email` | WIRED | Line 9 |
| `tests/test_integration.py` | `src/graph_client.py` | `from src.graph_client import Email` | WIRED | Line 10 |
| `tests/test_integration_dual_digest.py` | `src/graph_client.py` | `from src.graph_client import Email` | WIRED | Line 22 |

---

### Requirements Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| CLEAN-01: Delete `src/ews_client.py` | SATISFIED | File absent; ModuleNotFoundError confirmed |
| CLEAN-02: Remove `exchangelib` from `requirements.txt` | SATISFIED | `requirements.txt` contains only Graph API dependencies |
| CLEAN-03: Remove shims from `src/auth.py` | SATISFIED | No `EWSAuthenticator`, no `get_ews_credentials()`, no `exchangelib` import |
| CLEAN-04: Remove deprecated fields from `src/config.py` | SATISFIED | No `EWS_SERVER`, no `USER_EMAIL`; `get_send_from()` uses `SENDER_EMAIL` |
| CLEAN-05: Rewire `src/main.py` to GraphClient | SATISFIED | All imports, instantiation, method calls, and error handling use Graph symbols |
| CLEAN-06: Redirect Email imports + 210 tests pass | SATISFIED | 9 files redirected (4 src + 5 test); `210 passed in 0.52s` |

---

### Anti-Patterns Found

None. No TODO/FIXME comments, no placeholder stubs, no empty handlers, no stub returns in any modified file.

---

### Human Verification Required

None. All success criteria are structurally verifiable and pass automated checks.

---

## Verification Detail

### Structural Checks Run

1. `test -f src/ews_client.py` → FAIL (file absent) — PASS
2. `grep -rn "exchangelib" requirements.txt` → no output — PASS
3. `grep -rn "EWSClient|EWSClientError|EWSAuthenticator|ews_client|get_ews_credentials|EWS_SERVER|exchangelib" --include="*.py" src/ tests/` → exit 1, no matches — PASS
4. `grep -rn "USER_EMAIL|EWS_SERVER" --include="*.py" src/ tests/` → exit 1, no matches — PASS
5. `grep -rn "Exchange Web Services|via EWS|EWS path|EWS behaviour|EWS pattern|(EWS)" --include="*.py" src/ tests/` → exit 1, no matches — PASS
6. `python -c "importlib.import_module('src.ews_client')"` → ModuleNotFoundError — PASS
7. `python -c "from src.graph_client import GraphClient, Email, GraphClientError"` → OK — PASS
8. `python -c "from src.auth import GraphAuthenticator, AuthenticationError"` → OK — PASS
9. `python -c "from src.classifier import EmailClassifier; ..."` → OK — PASS
10. `python -c "from src.config import Config; assert not hasattr(Config, 'EWS_SERVER'); assert not hasattr(Config, 'USER_EMAIL')"` → OK — PASS
11. `python -m pytest --collect-only -q | tail -1` → `210 tests collected in 0.22s` — PASS
12. `python -m pytest tests/ -q` → `210 passed in 0.52s` — PASS

### test_auth.py Function Count

Exactly 7 test functions (3 EWS shim tests confirmed deleted):
- `test_graph_scope_is_correct`
- `test_get_access_token_returns_string`
- `test_get_access_token_raises_on_error`
- `test_get_access_token_raises_on_exception`
- `test_get_access_token_uses_graph_scope`
- `test_acquire_token_silent_not_called`
- `test_clear_cache_resets_app`

No `EWSAuthenticator`, no `exchangelib` import, no `USER_EMAIL` in mock_config fixture.

---

_Verified: 2026-03-16T00:31:06Z_
_Verifier: Claude (gsd-verifier)_
