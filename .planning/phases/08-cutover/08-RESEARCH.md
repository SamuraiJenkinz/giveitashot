# Phase 8: Cutover - Research

**Researched:** 2026-03-15
**Domain:** Python codebase refactoring — dependency removal, import path migration, test cleanup
**Confidence:** HIGH

---

## Summary

Phase 8 is a surgical codebase cleanup. There are no new libraries to learn, no API contracts to discover, and no runtime behavior to change. The GraphClient is already implemented and tested (Phase 7). The work is: remove the EWS transport layer entirely, rewire `main.py` to use `GraphClient`, update all import paths from `src.ews_client` to `src.graph_client`, and delete the backward-compat shims that were kept alive for this transition.

The `Email` dataclass already exists identically in both `ews_client.py` (old) and `graph_client.py` (new). All consuming modules (`classifier.py`, `extractor.py`, `llm_summarizer.py`, `summarizer.py`) import `Email` from `src.ews_client`. All test files that use `Email` also import from `src.ews_client`. After `ews_client.py` is deleted, every one of these imports must redirect to `src.graph_client`.

The current test count is **214 tests** (not 167 as ROADMAP states — that was stale when graph_client tests were added in Phase 7). Three tests must be deleted (they test EWS shims being removed). After deletion, the target is **211 passing tests**. The ROADMAP.md success criteria must be updated to reflect the real number.

**Primary recommendation:** Execute the cutover as a single coordinated atomic change across all affected files, verify with `pytest` and a `grep exchangelib` scan, then commit. The Email dataclass stays in `graph_client.py` (no extraction to `models.py` needed — the module is already well-scoped).

---

## Standard Stack

Phase 8 uses only what already exists in the project. No new libraries.

### Core (existing)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `requests` | >=2.32.5 | HTTP to Graph API | Already in requirements.txt |
| `msal` | >=1.28.0 | OAuth token acquisition | Already in requirements.txt |
| `python-dotenv` | >=1.0.0 | Config loading | Already in requirements.txt |
| `pytest` | >=7.4.0 | Test runner | Already in requirements-dev.txt |
| `pytest-mock` | >=3.12.0 | Mock support | Already in requirements-dev.txt |

### Removing

| Library | From | Why |
|---------|------|-----|
| `exchangelib>=5.4.0` | `requirements.txt` | EWS client removed — zero downstream use after cutover |

### Alternatives Considered

Not applicable — this phase has no technology choices, only cleanup.

---

## Architecture Patterns

### Current State (Before Cutover)

```
src/
├── ews_client.py        # DELETING: Email, EWSClient, EWSClientError
├── graph_client.py      # KEEPING: Email (identical), GraphClient, GraphClientError
├── auth.py              # Contains: GraphAuthenticator + EWSAuthenticator alias + get_ews_credentials() shim
├── config.py            # Contains: EWS_SERVER, USER_EMAIL alias (both deprecated)
├── main.py              # Uses: EWSAuthenticator, EWSClient, EWSClientError, Config.USER_EMAIL
├── classifier.py        # Imports: Email from .ews_client → REDIRECT
├── extractor.py         # Imports: Email from .ews_client → REDIRECT
├── llm_summarizer.py    # Imports: Email from .ews_client → REDIRECT
└── summarizer.py        # Imports: Email from .ews_client → REDIRECT
tests/
├── conftest.py          # Imports: Email from src.ews_client → REDIRECT
├── test_auth.py         # Contains: 3 EWS shim tests → DELETE those 3
├── test_classifier.py   # Imports: Email from src.ews_client → REDIRECT
├── test_extractor.py    # Imports: Email from src.ews_client → REDIRECT
├── test_integration.py  # Imports: Email from src.ews_client → REDIRECT
└── test_integration_dual_digest.py  # Imports: Email from src.ews_client → REDIRECT
```

### Target State (After Cutover)

```
src/
├── graph_client.py      # Canonical: Email, GraphClient, GraphClientError
├── auth.py              # Cleaned: GraphAuthenticator only — no alias, no shim, no exchangelib import
├── config.py            # Cleaned: no EWS_SERVER, no USER_EMAIL alias
├── main.py              # Rewired: GraphAuthenticator, GraphClient, GraphClientError
├── classifier.py        # Redirected: Email from .graph_client
├── extractor.py         # Redirected: Email from .graph_client
├── llm_summarizer.py    # Redirected: Email from .graph_client
└── summarizer.py        # Redirected: Email from .graph_client
tests/
├── conftest.py          # Redirected: Email from src.graph_client
├── test_auth.py         # Cleaned: EWSAuthenticator alias test, get_ews_credentials tests removed
├── test_classifier.py   # Redirected: Email from src.graph_client
├── test_extractor.py    # Redirected: Email from src.graph_client
├── test_integration.py  # Redirected: Email from src.graph_client, docstring updated
└── test_integration_dual_digest.py  # Redirected: Email from src.graph_client
```

### Pattern: Coordinated Import Redirect

The `Email` dataclass is identical in both modules (same fields, same types, same properties). The redirect is a pure path substitution with no logic changes:

```python
# Before (in all consuming modules):
from .ews_client import Email          # src modules
from src.ews_client import Email       # test modules

# After:
from .graph_client import Email        # src modules
from src.graph_client import Email     # test modules
```

### Pattern: main.py Rewiring

`main.py` currently instantiates EWSAuthenticator, calls `get_ews_credentials()`, and passes credentials to `EWSClient`. After cutover, it uses `GraphAuthenticator` directly and passes the authenticator to `GraphClient`:

```python
# Before (main.py lines 145-159):
authenticator = EWSAuthenticator()
credentials = authenticator.get_ews_credentials()
ews_client = EWSClient(credentials)

# After:
authenticator = GraphAuthenticator()
graph_client = GraphClient(authenticator)
```

The `clear_cache()` call at line 150 maps directly — `GraphAuthenticator.clear_cache()` already exists with identical behavior.

Call sites also change:
```python
# Before:
emails = ews_client.get_shared_mailbox_emails(...)
ews_client.send_email(...)

# After:
emails = graph_client.get_shared_mailbox_emails(...)
graph_client.send_email(...)
```

### Pattern: Config Cleanup

Two deprecated attributes must be removed from `config.py`:

1. `EWS_SERVER` (line 41) — only used by `ews_client.py` which is being deleted
2. `USER_EMAIL` alias (line 47) — alias for `SENDER_EMAIL`, used by `ews_client.py` and `main.py`

The `get_send_from()` method at line 115 returns `cls.USER_EMAIL` as fallback. After removing `USER_EMAIL`, this must return `cls.SENDER_EMAIL`:

```python
# Before:
return cls.SEND_FROM if cls.SEND_FROM else cls.USER_EMAIL

# After:
return cls.SEND_FROM if cls.SEND_FROM else cls.SENDER_EMAIL
```

**Important:** `test_config.py` contains a `test_user_email_aliases_sender_email` test that explicitly tests `Config.USER_EMAIL`. This test must be removed when `USER_EMAIL` is removed from Config. Additionally, several other tests in `test_config.py` set both `Config.SENDER_EMAIL = "user@test.com"` and `Config.USER_EMAIL = "user@test.com"` as part of test setup — after removal, the `Config.USER_EMAIL` lines in those tests become dead assignments that should be cleaned up.

### Pattern: auth.py Cleanup

Three items must be removed from `auth.py`:

1. `from exchangelib import OAuth2Credentials, Identity` (line 12)
2. `get_ews_credentials()` method (lines 83-101) — the Phase 8 shim
3. `EWSAuthenticator = GraphAuthenticator` alias (line 110)

The `get_access_token()` flow is unchanged. The `clear_cache()` method is unchanged. The `GRAPH_SCOPE` constant and `GraphAuthenticator` class stay intact.

One comment in `auth.py` also becomes stale: the `# Kept for backward-compat get_ews_credentials() shim — remove when main.py migrates to Graph client (Phase 8)` comment at line 11.

### Anti-Patterns to Avoid

- **Keeping re-export shims**: Do not add `from .graph_client import Email` inside a stub `ews_client.py`. The file must be fully deleted.
- **Partial cleanup**: Removing `ews_client.py` without updating all importers will break tests immediately at collection time.
- **Updating tests while leaving src broken**: Update src and tests together — pytest will fail at import if either is inconsistent.
- **Leaving `exchangelib` in requirements.txt**: The verification grep must find zero hits; `requirements.txt` must be updated before running the verification.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic multi-file edits | Custom rollback script | Edit each file, run pytest, commit all at once | Git handles atomicity; pytest is the safety net |
| Import redirect | Compatibility shim in ews_client.py stub | Direct import path change | Phase 8 is a clean break — no shims survive |

---

## Common Pitfalls

### Pitfall 1: Test Count Discrepancy

**What goes wrong:** The ROADMAP says "167 existing tests" but the actual current count is 214. This is because graph_client tests (36 tests) were added in Phase 7, bringing the total from 167 to 214 before Phase 8 even begins. Deleting 3 EWS shim tests from test_auth.py brings it to 211.

**Why it happens:** ROADMAP was written before Phase 7 added test_graph_client.py with 36 tests. The number was never updated.

**How to avoid:** Run `pytest --collect-only -q` before starting and after completion to get the real counts. The ROADMAP success criteria must be updated to "211 tests" (214 - 3 deleted).

**Warning signs:** If pytest shows a number other than 211 after the cutover, investigate before declaring success.

### Pitfall 2: test_config.py USER_EMAIL Tests Break

**What goes wrong:** `test_config.py` has a `test_user_email_aliases_sender_email` test that asserts `Config.USER_EMAIL` exists and equals `Config.SENDER_EMAIL`. After removing `USER_EMAIL` from Config, this test fails with `AttributeError`.

**Why it happens:** The test was written to document the alias behavior, which is being removed.

**How to avoid:** Delete `test_user_email_aliases_sender_email` from `test_config.py`. Also remove the `Config.USER_EMAIL = ...` lines from the `backup_config` fixture and the four `validate_*` tests that set it as part of their setup — those lines become harmlessly dead, but cleaning them avoids confusion.

**Warning signs:** `AttributeError: type object 'Config' has no attribute 'USER_EMAIL'` in test_config.py.

### Pitfall 3: test_auth.py mock_config Still Patches USER_EMAIL

**What goes wrong:** The `mock_config` fixture in `test_auth.py` (line 34) patches `Config.USER_EMAIL`. After removing `USER_EMAIL` from Config, `monkeypatch.setattr(Config, "USER_EMAIL", "sender@test.com")` raises `AttributeError` because the attribute no longer exists.

**Why it happens:** The fixture was patching USER_EMAIL because it was needed by the EWS shim (`get_ews_credentials()` used it). After the shim is removed, this line is dead.

**How to avoid:** Remove the `monkeypatch.setattr(Config, "USER_EMAIL", ...)` line from the `mock_config` fixture in `test_auth.py` when removing the shim tests.

**Warning signs:** `AttributeError` in `mock_config` fixture when any `test_auth.py` test runs.

### Pitfall 4: get_send_from() Still References USER_EMAIL

**What goes wrong:** `Config.get_send_from()` falls back to `cls.USER_EMAIL` (line 115). If `USER_EMAIL` is deleted from Config without updating this method, any call to `get_send_from()` with an unset `SEND_FROM` will raise `AttributeError`.

**Why it happens:** `get_send_from()` was written when `USER_EMAIL` was the canonical sender reference.

**How to avoid:** Update the fallback to `cls.SENDER_EMAIL` at the same time as removing the `USER_EMAIL` class attribute.

**Warning signs:** `AttributeError: type object 'Config' has no attribute 'USER_EMAIL'` at runtime.

### Pitfall 5: `exchangelib` Logger Still Muted in main.py

**What goes wrong:** `main.py` line 48 silences the `exchangelib` logger: `logging.getLogger("exchangelib").setLevel(logging.WARNING)`. After removal, this line is harmlessly inert (logging a non-existent logger is a no-op), but it's a dangling EWS reference that should be cleaned up.

**Why it happens:** The comment on line 47 calls it out explicitly: `# Reduce noise from exchangelib`.

**How to avoid:** Delete lines 47-48 of `main.py` during the cutover.

**Warning signs:** Not a runtime failure — purely a cleanliness issue. Will survive the `grep exchangelib` verification scan.

### Pitfall 6: graph_client.py Has Stale EWS References in Comments

**What goes wrong:** `graph_client.py` contains several comments that reference the EWS path (lines 236, 241, 383). These are not functional problems but violate the "clean slate" requirement for EWS references.

**Specific locations:**
- Line 236: `# continue receiving the same format they receive from the EWS path`
- Line 241: `# Compute body_preview from stripped content (matches EWS behaviour)`
- Line 383: `# Log sender and recipient info (matching EWSClient pattern)`

**How to avoid:** Update these comments to neutral language during the docstring/comment sweep.

### Pitfall 7: EWS_SERVER Env Var in .env Files

**What goes wrong:** If the production `.env` file (not committed) contains `EWS_SERVER=...`, removing Config.EWS_SERVER from config.py means `python-dotenv` will still load the env var, but Config will no longer read it. This is benign (unused env vars are fine) but worth documenting.

**How to avoid:** Note in the plan that `EWS_SERVER` can be removed from `.env` manually — it's not a code issue. No test will fail from this.

---

## Code Examples

### main.py: Auth + Client Initialization (After)

```python
# Source: Derived from existing GraphAuthenticator and GraphClient interfaces

from .auth import GraphAuthenticator, AuthenticationError
from .graph_client import GraphClient, GraphClientError

# In main():
authenticator = GraphAuthenticator()

if args.clear_cache:
    logger.info("Clearing token cache...")
    authenticator.clear_cache()

logger.info("Initializing Graph client...")
graph_client = GraphClient(authenticator)
```

### main.py: Log Messages (After)

```python
# Description updated:
description="Email Summarizer Agent - Summarizes daily emails from a shared mailbox via Microsoft Graph API"

# Startup banner updated:
logger.info("Email Summarizer Agent Starting (Graph API)")

# Sender account log updated:
logger.info(f"Sender account: {Config.SENDER_EMAIL}")

# Error handler updated:
except GraphClientError as e:
    logger.error(f"Graph API error: {e}")
    logger.error("Please verify you have access to the shared mailbox.")
```

### config.py: EWS_SERVER Removal (After)

```python
# REMOVE these two lines entirely:
# EWS_SERVER: str = os.getenv("EWS_SERVER", "outlook.office365.com")
# USER_EMAIL: str = SENDER_EMAIL

# UPDATE get_send_from() fallback:
@classmethod
def get_send_from(cls) -> str:
    """
    Get the From address for sending emails.
    Uses SEND_FROM if set, otherwise falls back to SENDER_EMAIL.
    """
    return cls.SEND_FROM if cls.SEND_FROM else cls.SENDER_EMAIL
```

### auth.py: After Cleanup

```python
"""
OAuth 2.0 Authentication module for Microsoft Graph API using client credentials flow.
Uses app-only authentication with client secret for Microsoft Graph.
"""

import logging
from typing import Optional

import msal

from .config import Config

logger = logging.getLogger(__name__)

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class GraphAuthenticator:
    # ... (unchanged)

    def get_access_token(self) -> str:
        # ... (unchanged)

    def clear_cache(self) -> None:
        # ... (unchanged)

# NO EWSAuthenticator alias
# NO get_ews_credentials() method
# NO exchangelib import
```

### Verification Command (After Cutover)

```bash
# Must return zero hits (except .eml fixtures which are exempt):
grep -rn "exchangelib" . --include="*.py" --include="*.txt"

# Must return zero hits:
grep -rn "EWSClient\|EWSClientError\|EWSAuthenticator\|ews_client\|get_ews_credentials\|EWS_SERVER" . --include="*.py"

# Must pass all tests:
python -m pytest tests/ -v

# Must execute cleanly:
python -m src.main --dry-run
```

---

## Complete Change Inventory

Exhaustive file-by-file list of every change required:

### Files to Delete
| File | Reason |
|------|--------|
| `src/ews_client.py` | The EWS transport layer — replaced by graph_client.py |

### Files to Edit: src/

| File | Changes |
|------|---------|
| `requirements.txt` | Remove `exchangelib>=5.4.0` line |
| `src/auth.py` | Remove `from exchangelib import ...` import; remove `get_ews_credentials()` method; remove `EWSAuthenticator = GraphAuthenticator` alias; update module docstring; remove backward-compat comment |
| `src/config.py` | Remove `EWS_SERVER` class attribute; remove `USER_EMAIL` class attribute; update `get_send_from()` fallback from `USER_EMAIL` to `SENDER_EMAIL`; update docstring comment on deprecated items |
| `src/main.py` | Replace `EWSAuthenticator` import with `GraphAuthenticator`; replace `EWSClient, EWSClientError` import with `GraphClient, GraphClientError`; remove `from .ews_client import EWSClient, EWSClientError` line; remove `exchangelib` logger suppression (lines 47-48); update `argparse` description; update startup log message; remove `get_ews_credentials()` call; replace EWSClient instantiation with GraphClient; replace `ews_client.get_shared_mailbox_emails(...)` with `graph_client.get_shared_mailbox_emails(...)`; replace both `ews_client.send_email(...)` calls with `graph_client.send_email(...)`; replace `except EWSClientError` with `except GraphClientError`; update EWS error message; update `Config.USER_EMAIL` reference to `Config.SENDER_EMAIL`; update module docstring |
| `src/classifier.py` | Change `from .ews_client import Email` to `from .graph_client import Email` |
| `src/extractor.py` | Change `from .ews_client import Email` to `from .graph_client import Email` |
| `src/llm_summarizer.py` | Change `from .ews_client import Email` to `from .graph_client import Email` |
| `src/summarizer.py` | Change `from .ews_client import Email` to `from .graph_client import Email` |
| `src/graph_client.py` | Update comments at lines 236, 241, 383 to remove EWS references; update module docstring |

### Files to Edit: tests/

| File | Changes |
|------|---------|
| `tests/conftest.py` | Change `from src.ews_client import Email` to `from src.graph_client import Email` |
| `tests/test_auth.py` | Remove `from exchangelib import OAuth2Credentials` import; remove `EWSAuthenticator` from import line; remove `test_ews_authenticator_alias` test function; remove `test_get_ews_credentials_returns_oauth2credentials` test function; remove `test_get_ews_credentials_raises_on_auth_failure` test function; remove `monkeypatch.setattr(Config, "USER_EMAIL", ...)` from `mock_config` fixture; update module docstring to remove EWS references |
| `tests/test_classifier.py` | Change `from src.ews_client import Email` to `from src.graph_client import Email` |
| `tests/test_extractor.py` | Change `from src.ews_client import Email` to `from src.graph_client import Email` |
| `tests/test_integration.py` | Change `from src.ews_client import Email` to `from src.graph_client import Email`; update module docstring (remove "without requiring live EWS connections") |
| `tests/test_integration_dual_digest.py` | Change `from src.ews_client import Email` to `from src.graph_client import Email` |
| `tests/test_config.py` | Remove `test_user_email_aliases_sender_email` test; remove `Config.USER_EMAIL` lines from `backup_config` fixture; remove `Config.USER_EMAIL = "user@test.com"` from validate test setups; update module docstring |

### Files to Edit: .planning/

| File | Changes |
|------|---------|
| `.planning/ROADMAP.md` | Update Phase 8 success criteria: "167" → "211" tests (214 current - 3 deleted); update goal line similarly |

---

## Test Count Analysis

| Metric | Count | Source |
|--------|-------|--------|
| Current total tests | 214 | `pytest --collect-only -q` |
| Tests being deleted | 3 | `test_ews_authenticator_alias`, `test_get_ews_credentials_returns_oauth2credentials`, `test_get_ews_credentials_raises_on_auth_failure` |
| Expected final count | 211 | 214 - 3 |
| ROADMAP claims | 167 | Stale — written before Phase 7 added 36 test_graph_client.py tests |

The 3 deleted tests are in `tests/test_auth.py`. The 7 remaining tests in that file (`test_graph_scope_is_correct`, `test_get_access_token_returns_string`, `test_get_access_token_raises_on_error`, `test_get_access_token_raises_on_exception`, `test_get_access_token_uses_graph_scope`, `test_acquire_token_silent_not_called`, `test_clear_cache_resets_app`) require NO logic changes — they test `GraphAuthenticator` which is unchanged.

---

## Email Dataclass Decision

The context leaves the `Email` dataclass module location to Claude's discretion. Research finding:

**Leave `Email` in `graph_client.py`. Do not extract to `models.py`.**

Rationale:
- `Email` is already in `graph_client.py` with identical fields and properties
- `GraphClient._parse_message()` returns `Email` — co-location is natural
- Extracting to `models.py` would require a new file + another import redirect wave
- The `Email` dataclass contract is identical — field names, types, and properties are unchanged
- No consumer cares which module `Email` lives in — they just import the class

**Import strategy:** Direct redirect (all importers update). No re-export compatibility shim. The clean break principle applies.

---

## State of the Art

| Old Approach | Current Approach | Changed | Impact |
|--------------|------------------|---------|--------|
| `exchangelib` for EWS mailbox access | `requests` + Graph REST API | Phase 7 | Transport layer only — Email contract unchanged |
| `EWSAuthenticator` + `get_ews_credentials()` → `OAuth2Credentials` | `GraphAuthenticator` + `get_access_token()` → `str` | Phase 6/7 | Simpler — Graph uses Bearer token directly |
| `EWSClient(credentials)` pattern | `GraphClient(authenticator)` pattern | Phase 7 | Authenticator injected, not credentials object |

**Deprecated/outdated (to be removed in Phase 8):**
- `EWSAuthenticator`: alias for `GraphAuthenticator` — no longer needed post-cutover
- `get_ews_credentials()`: returns `OAuth2Credentials` for `exchangelib` — `exchangelib` is leaving
- `EWS_SERVER`: config var pointing to `outlook.office365.com` — Graph uses a fixed URL (`graph.microsoft.com`)
- `USER_EMAIL`: alias for `SENDER_EMAIL` — `EWSClient` needed this; `GraphClient` uses `SENDER_EMAIL` directly

---

## Open Questions

1. **Should `test_config.py::test_user_email_aliases_sender_email` be deleted or repurposed?**
   - What we know: The test exists solely to document `USER_EMAIL = SENDER_EMAIL` alias behavior
   - What's unclear: Whether any downstream .env or deploy script still relies on `USER_EMAIL` as a config key
   - Recommendation: Delete the test. `EWS_SERVER` and `USER_EMAIL` env vars (not `SENDER_EMAIL`) were EWS-era; the Graph path has always used `SENDER_EMAIL`. No deploy dependency exists on `USER_EMAIL` as an env var name.

2. **Do any other test files' docstrings reference EWS beyond the ones identified?**
   - What we know: `test_integration.py` docstring references "live EWS connections"; `test_auth.py` docstring references EWS throughout
   - What's unclear: Whether other test files have EWS in inline comments not caught by the grep
   - Recommendation: Run a final `grep -rn "EWS\|ews_client\|exchangelib" tests/` sweep after all changes and before committing.

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection — all findings verified by reading actual source files
- `pytest --collect-only -q` — test count is definitive (214 tests as of 2026-03-15)
- `grep -rn "exchangelib\|EWSClient\|ews_client"` — complete reference inventory

### Secondary (MEDIUM confidence)

- Phase 7 RESEARCH.md and PLAN.md — confirmed GraphClient API contract and authenticator interface
- Phase 8 CONTEXT.md — locked decisions from prior discussion session

### Tertiary (LOW confidence)

- None — all findings from direct code inspection, no uncertain external sources

---

## Metadata

**Confidence breakdown:**
- Change inventory: HIGH — enumerated from direct grep + file reads
- Test count impact: HIGH — verified by `pytest --collect-only -q`
- Email dataclass recommendation: HIGH — both modules already have identical definitions
- Config.get_send_from() impact: HIGH — confirmed by reading config.py lines 107-115

**Research date:** 2026-03-15
**Valid until:** Indefinite — this is a static codebase snapshot analysis, not framework documentation
