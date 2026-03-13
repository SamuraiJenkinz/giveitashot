# Phase 6: Auth Foundation - Research

**Researched:** 2026-03-13
**Domain:** MSAL Python client credentials flow for Microsoft Graph API
**Confidence:** HIGH

---

## Summary

Phase 6 replaces the existing `EWSAuthenticator` (which wraps exchangelib's `OAuth2Credentials`) with a `GraphAuthenticator` that returns a plain bearer token string. The MSAL mechanics are already in place — the existing code already uses `msal.ConfidentialClientApplication` and `acquire_token_silent` + `acquire_token_for_client`. The only meaningful changes are: (1) swap the scope constant from `https://outlook.office365.com/.default` to `https://graph.microsoft.com/.default`, (2) remove the exchangelib credential wrapping, (3) rename env vars from `AZURE_*` to `MICROSOFT_*` and `USER_EMAIL` to `SENDER_EMAIL`, and (4) drop `EWS_SERVER` from config and validation.

The standard approach for client credentials / daemon authentication against Microsoft Graph is `ConfidentialClientApplication.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])`. Since MSAL Python 1.23, this call automatically checks the in-memory cache before hitting the token endpoint — no separate `acquire_token_silent` call is needed (unlike the current code pattern, which calls both). The installed version is 1.34.0, well past that threshold.

Token lifetime from Microsoft Entra is 60-90 minutes (randomized). MSAL's in-memory cache handles reuse within a single process run. For a short-lived daemon that runs once and exits, in-memory caching (the MSAL default) is appropriate and sufficient — cross-run file-based persistence is optional complexity that the CONTEXT.md defers to Claude's discretion.

**Primary recommendation:** Rewrite `auth.py` using `ConfidentialClientApplication` + `acquire_token_for_client` returning a plain `str`. Update `config.py` to rename the four env vars and remove `EWS_SERVER`. The MSAL in-process cache is sufficient for this use case; skip file-based `SerializableTokenCache`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| msal | >=1.28.0 (installed: 1.34.0) | Microsoft identity platform tokens | Official Microsoft library; already in requirements.txt |

### No New Dependencies Required

The decision is locked: zero new dependencies. `msal` already handles the full client credentials flow. `exchangelib` stays in requirements.txt until Phase 8 (out of scope for Phase 6).

### Alternatives Considered (locked out by CONTEXT.md)

| Instead of | Could Use | Why Locked Out |
|------------|-----------|----------------|
| msal direct | msgraph-sdk | Async-only, daemon process bug — rejected in CONTEXT.md |
| msal direct | requests-oauthlib | No benefit over MSAL for this scenario |

**Installation:** No changes to requirements.txt in this phase.

---

## Architecture Patterns

### Recommended Project Structure (no change)

```
src/
├── auth.py      # Replace EWSAuthenticator with GraphAuthenticator
├── config.py    # Rename env vars, remove EWS_SERVER
└── main.py      # Update imports (Phase 7+ concern, not Phase 6)
```

Phase 6 scope is strictly `auth.py` and `config.py`. Files that import from `auth.py` (`main.py`) are updated in a later phase.

### Pattern 1: acquire_token_for_client with built-in cache check

**What:** Since MSAL Python 1.23, `acquire_token_for_client` automatically checks the in-memory cache first and only calls the token endpoint on cache miss. The old pattern of calling `acquire_token_silent` first then falling back to `acquire_token_for_client` is no longer needed.

**When to use:** Always, for client credentials (daemon / app-only) flows.

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
import msal

app = msal.ConfidentialClientApplication(
    client_id=Config.CLIENT_ID,
    client_credential=Config.CLIENT_SECRET,
    authority=Config.get_authority()
)

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)

if "access_token" in result:
    token: str = result["access_token"]
else:
    error = result.get("error", "Unknown error")
    error_description = result.get("error_description", "No description available")
    raise AuthenticationError(f"Authentication failed: {error} - {error_description}")
```

### Pattern 2: Token used as Authorization header

**What:** The returned string is placed directly into the Authorization header.

```python
# Usage by downstream callers (Graph client, Phase 7+)
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}
response = requests.get("https://graph.microsoft.com/v1.0/...", headers=headers)
```

### Pattern 3: Lazy MSAL app initialization (preserve existing pattern)

**What:** Current code lazily creates `_app` on first access via a property. This is safe and correct — preserves the in-memory token cache for the process lifetime.

```python
@property
def app(self) -> msal.ConfidentialClientApplication:
    if self._app is None:
        self._app = msal.ConfidentialClientApplication(
            client_id=Config.CLIENT_ID,
            client_credential=Config.CLIENT_SECRET,
            authority=Config.get_authority()
        )
    return self._app
```

### Anti-Patterns to Avoid

- **Calling acquire_token_silent before acquire_token_for_client:** Unnecessary since MSAL 1.23. `acquire_token_for_client` already does the cache check internally. The current `auth.py` does this redundantly; remove it.
- **Constructing the bearer token manually:** Never call the token endpoint directly via `requests`. MSAL handles expiry, caching, and error normalization.
- **Creating a new `ConfidentialClientApplication` instance per token request:** Each instantiation creates a fresh in-memory cache. Instantiate once and reuse.
- **Returning anything other than `result["access_token"]`:** The token value is a plain string. Do not wrap it in a credentials object.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token expiry tracking | Manual `exp` claim decode + datetime check | `acquire_token_for_client` (MSAL built-in cache) | MSAL tracks expiry and pre-empts expiration automatically |
| Token endpoint HTTP call | `requests.post` to `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token` | `msal.ConfidentialClientApplication` | MSAL handles retry, error normalization, tenant routing |
| In-process token cache | Dict keyed by scope | MSAL in-memory cache (built-in) | MSAL cache is scope-aware and handles all edge cases |

**Key insight:** MSAL's in-memory cache is always active with no configuration needed. For a process that runs once and exits (like this daemon), cross-run persistence (file-based `SerializableTokenCache`) adds complexity with marginal benefit — one extra network call per process start is acceptable.

---

## Common Pitfalls

### Pitfall 1: Wrong scope string format

**What goes wrong:** Using `"Mail.Read Mail.Send"` (space-separated) or `["Mail.Read", "Mail.Send"]` as the scope for client credentials.

**Why it happens:** Application-level permissions (client credentials) don't work with individual permission scopes. The identity platform pre-authorizes all granted permissions under the `/.default` scope. Only `["https://graph.microsoft.com/.default"]` is valid.

**How to avoid:** Always use `["https://graph.microsoft.com/.default"]` as the scopes list for `acquire_token_for_client`. The permissions (`Mail.Read`, `Mail.Send`) are configured in Azure AD app registration and consented by admin — they don't appear in code.

**Warning signs:** Token is acquired but Graph API returns `403 Forbidden` or `401 Insufficient scope`.

### Pitfall 2: Using the old EWS scope

**What goes wrong:** Scope remains `"https://outlook.office365.com/.default"` — tokens acquire successfully but Graph API calls fail with 401.

**Why it happens:** Copy-paste error during migration, or testing against the wrong scope. The EWS scope produces a token with `aud` claim `https://outlook.office365.com/` instead of `https://graph.microsoft.com/`.

**How to avoid:** Define scope as a named constant in the module — one place to change, impossible to miss.

**Warning signs:** Success criteria check: the `aud` claim in the acquired JWT must equal `https://graph.microsoft.com/`. Decode via `jwt.ms` or base64 the middle segment.

### Pitfall 3: Config class attributes are class-level variables (evaluated at import time)

**What goes wrong:** Renaming env vars but keeping old default values. For example, `TENANT_ID: str = os.getenv("MICROSOFT_TENANT_ID", "")` must replace `TENANT_ID: str = os.getenv("AZURE_TENANT_ID", "")` — both the env var name AND the class attribute should be updated.

**Why it happens:** Config is a plain class (not a Pydantic model), so all attributes are evaluated once at module import. Missing a rename leaves the old env var silently unset.

**How to avoid:** Update all four class attributes plus the `validate()` missing-list strings simultaneously. Grep for every occurrence of `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `USER_EMAIL`, `EWS_SERVER` before committing.

**Warning signs:** `Config.validate()` does not raise even with old env vars in `.env`; or raises with wrong variable name in error message.

### Pitfall 4: `get_authority()` uses `TENANT_ID` attribute — must stay consistent

**What goes wrong:** Renaming the env var but the `get_authority()` method still references `cls.TENANT_ID`. Since the class attribute name (`TENANT_ID`) is not being renamed (only the env var from `AZURE_TENANT_ID` to `MICROSOFT_TENANT_ID`), this is fine — but the attribute name must stay `TENANT_ID` or `get_authority()` must be updated too.

**How to avoid:** Keep the internal Python attribute names (`TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET`) unchanged. Only the env var *keys* (the string passed to `os.getenv()`) and the validation error messages change.

### Pitfall 5: `Config.USER_EMAIL` is referenced in `ews_client.py` — do not break it in Phase 6

**What goes wrong:** Removing `USER_EMAIL` from `Config` breaks `ews_client.py` which is still active until Phase 8.

**Why it happens:** `ews_client.py` references `Config.USER_EMAIL` on lines 238 and 259-260. `main.py` references it on line 131. Removing the attribute crashes those files at import time.

**How to avoid:** In Phase 6, add `SENDER_EMAIL` as a new attribute (reading from `MICROSOFT_SENDER_EMAIL`... wait — the CONTEXT.md says env var is `SENDER_EMAIL` not `MICROSOFT_SENDER_EMAIL`). Add `SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "")` alongside the existing `USER_EMAIL` attribute, validated in `validate()`. Only remove `USER_EMAIL` when `ews_client.py` is decommissioned (Phase 8+).

**Warning signs:** `AttributeError: type object 'Config' has no attribute 'USER_EMAIL'` when running existing EWS paths.

### Pitfall 6: Admin consent required before live token test

**What goes wrong:** Code is written correctly but `acquire_token_for_client` returns an error like `AADSTS7000218: The request body must contain the following parameter: 'client_assertion'` or `AADSTS65001: The user or administrator has not consented to use the application`.

**Why it happens:** The Azure AD app registration must have `Mail.Read` and `Mail.Send` application permissions with admin consent granted. Without this, the token is denied regardless of MSAL code correctness.

**How to avoid:** Test auth module in isolation using `jwt.ms` to inspect the token claims structure. The success criterion — `aud` equals `https://graph.microsoft.com/` — can be verified structurally even without a real tenant. Integration smoke test is blocked on IT consent.

---

## Code Examples

### GraphAuthenticator class (complete pattern)

```python
# Source: https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
# Source: https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-daemon-app-python-acquire-token

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
    """
    Handles OAuth 2.0 authentication for Microsoft Graph API.
    Uses MSAL client credentials flow (app-only, no user interaction).
    """

    def __init__(self):
        Config.validate()
        self._app: Optional[msal.ConfidentialClientApplication] = None

    @property
    def app(self) -> msal.ConfidentialClientApplication:
        if self._app is None:
            self._app = msal.ConfidentialClientApplication(
                client_id=Config.CLIENT_ID,
                client_credential=Config.CLIENT_SECRET,
                authority=Config.get_authority()
            )
        return self._app

    def get_access_token(self) -> str:
        """
        Acquire a bearer token for Microsoft Graph API.

        Returns:
            str: A valid access token usable as 'Authorization: Bearer {token}'.

        Raises:
            AuthenticationError: If authentication fails.
        """
        logger.info("Acquiring Graph API token using client credentials flow...")

        try:
            # acquire_token_for_client checks in-memory cache automatically (MSAL >= 1.23)
            result = self.app.acquire_token_for_client(scopes=GRAPH_SCOPE)

            if "access_token" in result:
                logger.info("Token acquired successfully")
                return result["access_token"]

            error = result.get("error", "Unknown error")
            error_description = result.get("error_description", "No description available")
            raise AuthenticationError(
                f"Authentication failed: {error} - {error_description}"
            )

        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Authentication failed: {e}")

    def clear_cache(self) -> None:
        """Clear the in-memory token cache by re-creating the MSAL app instance."""
        self._app = None
        logger.info("Token cache cleared")
```

### Config changes (env var renames only)

```python
# BEFORE (current state)
TENANT_ID: str = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID: str = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET: str = os.getenv("AZURE_CLIENT_SECRET", "")
EWS_SERVER: str = os.getenv("EWS_SERVER", "outlook.office365.com")
USER_EMAIL: str = os.getenv("USER_EMAIL", "kevin.j.taylor@mmc.com")

# AFTER (Phase 6)
TENANT_ID: str = os.getenv("MICROSOFT_TENANT_ID", "")
CLIENT_ID: str = os.getenv("MICROSOFT_CLIENT_ID", "")
CLIENT_SECRET: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")
SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "")
# USER_EMAIL kept as alias until Phase 8 (EWSClient still references it)
USER_EMAIL: str = SENDER_EMAIL  # Alias — remove when ews_client.py is decommissioned
# EWS_SERVER: removed from class
```

### validate() changes (error messages only)

```python
# BEFORE
if not cls.TENANT_ID:
    missing.append("AZURE_TENANT_ID")
if not cls.CLIENT_ID:
    missing.append("AZURE_CLIENT_ID")
if not cls.CLIENT_SECRET:
    missing.append("AZURE_CLIENT_SECRET")
if not cls.USER_EMAIL:
    missing.append("USER_EMAIL")

# AFTER
if not cls.TENANT_ID:
    missing.append("MICROSOFT_TENANT_ID")
if not cls.CLIENT_ID:
    missing.append("MICROSOFT_CLIENT_ID")
if not cls.CLIENT_SECRET:
    missing.append("MICROSOFT_CLIENT_SECRET")
if not cls.SENDER_EMAIL:
    missing.append("SENDER_EMAIL")
```

### Verifying the aud claim (success criterion 1)

```python
# Quick manual check — not production code
import base64, json

def decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without signature verification (for inspection only)."""
    payload_b64 = token.split(".")[1]
    # Pad to multiple of 4
    padding = 4 - len(payload_b64) % 4
    payload_b64 += "=" * (padding % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))

token = authenticator.get_access_token()
claims = decode_jwt_payload(token)
assert claims["aud"] == "https://graph.microsoft.com/", f"Wrong audience: {claims['aud']}"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `acquire_token_silent` + `acquire_token_for_client` fallback | `acquire_token_for_client` alone (cache-aware) | MSAL 1.23 (2023) | Simplified code; no behavioral change |
| EWS scope `.default` | Graph scope `.default` | This migration | Token audience changes; Graph endpoints accept it |
| `OAuth2Credentials` wrapper | Plain `str` return | This migration | Downstream callers get the string directly |

**Deprecated/outdated:**
- `acquire_token_silent(scopes=..., account=None)` before `acquire_token_for_client`: The existing code calls this first. As of MSAL 1.23, it is redundant for client credentials flow — `acquire_token_for_client` already checks cache internally.

---

## Open Questions

1. **USER_EMAIL backward compatibility**
   - What we know: `ews_client.py` uses `Config.USER_EMAIL` and is not decommissioned until Phase 8.
   - What's unclear: Whether `USER_EMAIL` should be an alias for `SENDER_EMAIL` or kept as a separate env var read.
   - Recommendation: Make `USER_EMAIL` a class-level alias (`USER_EMAIL = SENDER_EMAIL`) so EWS code continues to work without changes, then remove both when Phase 8 removes `ews_client.py`. Planner should document this as a task.

2. **get_send_from() references USER_EMAIL**
   - What we know: `Config.get_send_from()` returns `cls.SEND_FROM if cls.SEND_FROM else cls.USER_EMAIL` — this is also used in `ews_client.py`.
   - What's unclear: Does `SEND_FROM` need to be renamed to align with Graph era?
   - Recommendation: Leave `SEND_FROM` as-is in Phase 6; it's not in the four required vars list and its EWS usage is still live.

3. **Token isolation test (no admin consent yet)**
   - What we know: Admin consent for `Mail.Read` / `Mail.Send` on the Azure app registration is blocked on IT/security approval.
   - What's unclear: Whether the tenant already has a registered app with these permissions partially configured.
   - Recommendation: The auth module's success criterion (correct `aud` claim) can be verified against any tenant where the app has basic Graph API access (even `User.Read`). The `/.default` scope with any Graph permission will produce a token with `aud = https://graph.microsoft.com/`. Full smoke test remains blocked.

---

## Sources

### Primary (HIGH confidence)

- Official MSAL Python docs — `acquire_token_for_client` API, cache behavior since v1.23:
  https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens

- Official Microsoft daemon app quickstart (Python, client secret):
  https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-daemon-app-python-acquire-token

- Access token claims reference (`aud` claim for Graph):
  https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens

- Token cache serialization for confidential clients:
  https://learn.microsoft.com/en-us/entra/msal/python/advanced/msal-python-token-cache-serialization

- Installed MSAL version confirmed via `python -c "import msal; print(msal.__version__)"` → **1.34.0**

### Secondary (MEDIUM confidence)

- MSAL Python 1.35.0 readthedocs (confirms cache behavior in method signature):
  https://msal-python.readthedocs.io/

### Tertiary (LOW confidence)

- Token lifetime documented as 60-90 minutes default for standard tenants; CAE-enabled tenants may issue longer-lived tokens (20-28 hours). Source: official access-tokens page above, but Marsh McLennan tenant configuration is unknown.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — MSAL already installed, version confirmed, API verified against official docs
- Architecture: HIGH — pattern matches official Microsoft daemon sample exactly
- Pitfalls: HIGH for items 1-4 (verified from official docs and code inspection); MEDIUM for item 5 (USER_EMAIL backward-compat is project-specific reasoning)
- Code examples: HIGH — based on official docs patterns + direct inspection of existing `auth.py`

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (MSAL Python API is stable; scope format is stable)
