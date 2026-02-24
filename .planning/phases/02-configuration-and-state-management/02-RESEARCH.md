# Phase 2: Configuration and State Management - Research

**Researched:** 2026-02-24
**Domain:** Configuration management, state persistence, feature toggles, email recipient handling
**Confidence:** HIGH

## Summary

Phase 2 extends existing Config class and StateManager patterns to support dual-digest workflows. The codebase already has strong patterns: Config class with validation, _parse_email_list helper for recipient parsing, StateManager with JSON persistence, and argparse CLI. Research focused on: (1) presence-based feature activation patterns, (2) independent state tracking strategies, (3) backwards-compatible state migration, and (4) configuration validation best practices.

**Key findings:**
- Existing patterns are sufficient, no new libraries needed
- Presence-based activation (MAJOR_UPDATE_TO has recipients = enabled) is idiomatic Python pattern
- State migration requires transparent handling of old `last_run` key to new `regular_last_run` structure
- Validation should happen at Config.validate() time, not runtime

**Primary recommendation:** Extend existing patterns rather than restructure. Follow expand-migrate-contract pattern for state migration to ensure zero-downtime deployments.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-dotenv | Current | Environment variable loading | Already in project, .env file support |
| argparse | stdlib | CLI argument parsing | Already in use, standard library |
| json | stdlib | State persistence | Already in use for .state.json |
| pathlib | stdlib | File path handling | Already used throughout codebase |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging | stdlib | Debug/info logging | Already in use, standard library |
| pytest | Current | Testing | Already in project for unit tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| json | atomicwrites library | More complex, unnecessary for single-writer state file |
| python-dotenv | dynaconf | Too heavyweight for simple env var config |
| argparse | click | Already using argparse, no benefit to switching |

**Installation:**
No new dependencies required. All needed libraries already in project.

## Architecture Patterns

### Recommended Config Class Structure
```python
# Existing pattern to extend
class Config:
    # Existing fields (unchanged)
    SUMMARY_TO: list[str] = _parse_email_list("SUMMARY_TO")
    SUMMARY_CC: list[str] = _parse_email_list("SUMMARY_CC")
    SUMMARY_BCC: list[str] = _parse_email_list("SUMMARY_BCC")

    # New fields (mirror existing pattern)
    MAJOR_UPDATE_TO: list[str] = _parse_email_list("MAJOR_UPDATE_TO")
    MAJOR_UPDATE_CC: list[str] = _parse_email_list("MAJOR_UPDATE_CC")
    MAJOR_UPDATE_BCC: list[str] = _parse_email_list("MAJOR_UPDATE_BCC")

    @classmethod
    def get_major_recipients(cls) -> list[str]:
        """Get TO recipients for major update digest."""
        return cls.MAJOR_UPDATE_TO

    @classmethod
    def is_major_digest_enabled(cls) -> bool:
        """Feature toggle: enabled if MAJOR_UPDATE_TO has recipients."""
        return bool(cls.MAJOR_UPDATE_TO)
```

### Pattern 1: Presence-Based Feature Activation
**What:** Feature activation determined by presence of configuration value, not explicit boolean toggle
**When to use:** Optional features that require configuration to be useful (like additional email digests)
**Example:**
```python
# Source: Research synthesis from feature flag patterns
@classmethod
def is_major_digest_enabled(cls) -> bool:
    """
    Major digest activates when MAJOR_UPDATE_TO has recipients.
    No explicit ENABLE_MAJOR_DIGEST toggle needed.
    """
    return bool(cls.MAJOR_UPDATE_TO)

# Usage in main.py
if Config.is_major_digest_enabled():
    logger.debug("Major digest enabled, will process major updates")
    # ... send major digest logic
else:
    logger.debug("Major digest not configured (MAJOR_UPDATE_TO empty), skipping")
```

**Why this pattern:**
- Self-documenting: if you configure recipients, you want the feature
- Simpler: one config var instead of two (ENABLE_X + X_RECIPIENTS)
- Safer: empty recipient list can't accidentally send emails
- Consistent: matches existing pattern where SUMMARY_TO empty = no digest

### Pattern 2: Independent State Tracking
**What:** Single state file with separate keys per digest type, isolated failure handling
**When to use:** Multiple workflows sharing infrastructure but requiring independent scheduling
**Example:**
```python
# Source: Existing StateManager pattern + research on state isolation
class StateManager:
    def get_last_run(self, digest_type: str = "regular") -> datetime | None:
        """
        Get last run timestamp for specific digest type.

        Args:
            digest_type: "regular" or "major"

        Returns:
            datetime in UTC if available, None if no previous run.
        """
        key = f"{digest_type}_last_run"
        timestamp = self._state.get(key)
        if timestamp:
            return datetime.fromisoformat(timestamp)
        return None

    def set_last_run(self, digest_type: str = "regular", timestamp: datetime | None = None) -> None:
        """
        Set last run timestamp for specific digest type.
        Only called after successful email send.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        key = f"{digest_type}_last_run"
        self._state[key] = timestamp.isoformat()
        self._save()
        logger.info(f"Updated {digest_type} last run time: {timestamp.isoformat()}")
```

**Why this pattern:**
- Isolation: Regular digest state corruption doesn't affect major digest
- Flexibility: Each digest type can run on different schedules
- Simplicity: Single file, no complex state coordination
- Backwards compatible: Old `last_run` key can migrate to `regular_last_run`

### Pattern 3: Backwards-Compatible State Migration
**What:** Transparent migration from old state schema to new, zero-downtime deployment
**When to use:** Extending existing state schema without breaking deployed systems
**Example:**
```python
# Source: Django migrations pattern + expand-migrate-contract strategy
def _load(self) -> None:
    """Load state from file with migration support."""
    if self._state_file.exists():
        try:
            with open(self._state_file, "r") as f:
                self._state = json.load(f)

            # Migration: old "last_run" → "regular_last_run"
            if "last_run" in self._state and "regular_last_run" not in self._state:
                self._state["regular_last_run"] = self._state["last_run"]
                # Keep old key temporarily for rollback safety
                logger.info("Migrated state: last_run → regular_last_run")
                self._save()

            logger.debug(f"Loaded state from {self._state_file}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load state file: {e}")
            self._state = {}
    else:
        self._state = {}
```

**Why this pattern:**
- Zero downtime: Old deployments continue working during migration
- Rollback safe: Old key kept temporarily, allows version rollback
- Transparent: No user intervention required
- Standard: Follows Django migrations and expand-migrate-contract strategy

### Pattern 4: Configuration Validation at Startup
**What:** Validate all required and optional config at Config.validate() time, fail fast
**When to use:** Always. Catch configuration errors before processing emails
**Example:**
```python
# Source: Existing Config.validate() pattern + Pydantic validation research
@classmethod
def validate(cls) -> None:
    """Validate required and optional configuration."""
    missing = []

    # Required fields (existing)
    if not cls.TENANT_ID:
        missing.append("AZURE_TENANT_ID")
    # ... other required fields

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Please copy .env.example to .env and fill in your values."
        )

    # Regular digest recipient validation (existing)
    if not cls.get_recipients():
        raise ValueError(
            "No email recipients configured. "
            "Set either SUMMARY_RECIPIENT or SUMMARY_TO in your .env file."
        )

    # Major digest validation (optional but strict if present)
    if cls.is_major_digest_enabled():
        # MAJOR_UPDATE_TO has recipients, validate CC/BCC if present
        invalid_cc = [e for e in cls.MAJOR_UPDATE_CC if "@" not in e]
        invalid_bcc = [e for e in cls.MAJOR_UPDATE_BCC if "@" not in e]

        if invalid_cc or invalid_bcc:
            raise ValueError(
                f"Invalid major digest recipients. "
                f"Invalid CC: {invalid_cc}, Invalid BCC: {invalid_bcc}"
            )

        logger.info(f"Major digest enabled: {len(cls.MAJOR_UPDATE_TO)} TO recipient(s)")
    else:
        logger.debug("Major digest not enabled (MAJOR_UPDATE_TO empty or missing)")
```

**Why this pattern:**
- Fail fast: Catch config errors at startup, not during email send
- Clear errors: Specific error messages guide user to fix
- Consistent: Follows existing Config.validate() pattern
- Safe: Optional features validated only if enabled

### Anti-Patterns to Avoid
- **Shared recipient fallback:** Don't fallback MAJOR_UPDATE_TO to SUMMARY_TO — separate audiences are intentional
- **Complex feature flags:** Don't add ENABLE_MAJOR_DIGEST when presence-based activation is sufficient
- **Runtime config loading:** Don't re-read .env during execution — load once at startup
- **State file per digest:** Don't create .state.regular.json and .state.major.json — single file with keys is simpler
- **BCC in message headers:** Don't add BCC to message headers — only pass to send method (prevents exposure)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file writes | Custom temp file logic | Standard write-then-rename pattern | JSON corruption rare with single writer, stdlib sufficient |
| Email validation | Custom regex | Check for "@" presence | Complex RFC 5322 validation overkill, basic check sufficient |
| State locking | File locks | Single-writer assumption | Scheduled task runs serially, no concurrent access |
| Feature flags | Boolean config vars | Presence-based activation | Self-documenting, one var instead of two |
| Environment loading | Custom parser | python-dotenv + os.getenv | Already in project, battle-tested |

**Key insight:** The project already has solid patterns. Extend rather than replace. The existing StateManager and Config patterns are sufficient for dual-digest requirements.

## Common Pitfalls

### Pitfall 1: BCC Exposure in Email Headers
**What goes wrong:** Adding BCC recipients to email headers exposes them to all recipients
**Why it happens:** Confusion between message headers and SMTP envelope recipients
**How to avoid:** Pass BCC recipients only to send method, never set message["Bcc"] header
**Warning signs:** BCC recipients visible in received emails, privacy complaints
**Code example (WRONG):**
```python
# DON'T DO THIS - exposes BCC to all recipients
message["Bcc"] = ", ".join(bcc_recipients)
```
**Code example (CORRECT):**
```python
# Source: Python email sending best practices
# Pass BCC only to send method, not in message headers
ews_client.send_email(
    to_recipients=to_list,
    cc_recipients=cc_list,
    bcc_recipients=bcc_list,  # Only in method args
    subject=subject,
    body_html=body
)
```

### Pitfall 2: State Corruption Breaking Both Digests
**What goes wrong:** If state file is corrupted or malformed, both regular and major digests fail
**Why it happens:** No graceful degradation when JSON parse fails
**How to avoid:** Treat state load failure as "first run" for affected digest type
**Warning signs:** Both digests stop running after state file corruption, manual intervention required
**Code example:**
```python
# Source: Existing StateManager pattern + research on error handling
def get_last_run(self, digest_type: str = "regular") -> datetime | None:
    """
    Get last run timestamp with graceful degradation.
    If state missing/corrupted for this digest type, return None (first run).
    """
    try:
        key = f"{digest_type}_last_run"
        timestamp = self._state.get(key)
        if timestamp:
            return datetime.fromisoformat(timestamp)
    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"State corrupted for {digest_type} digest, treating as first run: {e}")

    return None  # Treat as first run
```

### Pitfall 3: No Migration Strategy for Existing Deployments
**What goes wrong:** New version deployed, old state file format breaks regular digest
**Why it happens:** Assuming new schema, ignoring existing `last_run` key
**How to avoid:** Implement transparent migration in _load() method
**Warning signs:** Regular digest stops working after deployment, fetches all emails instead of incremental
**Code example:** See Pattern 3: Backwards-Compatible State Migration above

### Pitfall 4: Major Digest Blocking Regular Digest
**What goes wrong:** If major digest fails (config error, send error), regular digest also fails
**Why it happens:** Sequential execution with no error isolation
**How to avoid:** Wrap major digest logic in try/except, log error and continue
**Warning signs:** Regular digest users report missing digests when major digest has issues
**Code example:**
```python
# Source: Resilient workflow design pattern
# Send regular digest first (primary feature)
if regular_emails:
    ews_client.send_email(...)
    state.set_last_run(digest_type="regular")
    logger.info("Regular digest sent successfully")

# Send major digest independently (optional feature)
if Config.is_major_digest_enabled() and major_update_emails:
    try:
        ews_client.send_email(...)
        state.set_last_run(digest_type="major")
        logger.info("Major digest sent successfully")
    except Exception as e:
        logger.error(f"Major digest failed, regular digest unaffected: {e}")
        # Continue execution, don't raise
```

### Pitfall 5: State Updated Before Email Send Succeeds
**What goes wrong:** State timestamp updated, then email send fails — next run skips emails
**Why it happens:** State update before confirmation of successful send
**How to avoid:** Update state only after successful send (existing pattern is correct)
**Warning signs:** Users report missing emails after transient send failures
**Code example (existing pattern is CORRECT):**
```python
# Source: Existing main.py pattern (keep this)
# Send email first
ews_client.send_email(...)
logger.info("Summary email sent successfully!")

# Update state ONLY after success
state.set_last_run()  # Correct order
```

## Code Examples

Verified patterns from existing codebase:

### Email Recipient Parsing
```python
# Source: src/config.py:15-29
def _parse_email_list(env_var: str, default: str = "") -> list[str]:
    """
    Parse a comma-separated list of email addresses from an environment variable.

    Args:
        env_var: Name of the environment variable.
        default: Default value if env var is not set.

    Returns:
        List of email addresses (stripped of whitespace), empty strings filtered out.
    """
    value = os.getenv(env_var, default)
    if not value:
        return []
    return [email.strip() for email in value.split(",") if email.strip()]

# Reuse for major digest recipients:
MAJOR_UPDATE_TO: list[str] = _parse_email_list("MAJOR_UPDATE_TO")
MAJOR_UPDATE_CC: list[str] = _parse_email_list("MAJOR_UPDATE_CC")
MAJOR_UPDATE_BCC: list[str] = _parse_email_list("MAJOR_UPDATE_BCC")
```

### CLI Argument Pattern
```python
# Source: src/main.py:54-82
parser = argparse.ArgumentParser(
    description="Email Summarizer Agent - Summarizes daily emails from a shared mailbox via EWS"
)
parser.add_argument("--dry-run", action="store_true", help="Generate summary but don't send email")
parser.add_argument("--full", action="store_true", help="Fetch all emails from today (ignore last run time)")

# Add new flags for Phase 2:
parser.add_argument("--regular-only", action="store_true", help="Send only regular digest (skip major)")
parser.add_argument("--major-only", action="store_true", help="Send only major digest (skip regular)")
```

### State Persistence Pattern
```python
# Source: src/state.py:44-51 (existing pattern)
def _save(self) -> None:
    """Save state to file."""
    try:
        with open(self._state_file, "w") as f:
            json.dump(self._state, f, indent=2)
        logger.debug(f"Saved state to {self._state_file}")
    except IOError as e:
        logger.error(f"Failed to save state file: {e}")

# Note: No atomic writes library needed. Single-writer assumption is valid.
# State file corruption is rare, and graceful degradation handles it.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Boolean feature flags | Presence-based activation | 2024+ | Simpler config, self-documenting |
| Multiple state files | Single file with keys | Current | Simpler management, atomic operations |
| Pydantic validation | Manual validation in Config.validate() | Project start | Lighter weight, no new dependency |
| .env only | .env + .env.example documented | Current | Clear documentation for users |

**Deprecated/outdated:**
- **atomicwrites library:** Overkill for single-writer JSON state files, stdlib sufficient
- **Complex feature flag libraries:** Unnecessary for simple presence-based toggles
- **Environment variable encryption at rest:** Handled at deployment level (Azure Key Vault, etc.), not app level

## Open Questions

Things that couldn't be fully resolved:

1. **Should major digest state update even if zero major emails found?**
   - What we know: Decision says "send nothing" when no major emails found
   - What's unclear: Should we still update major_last_run timestamp?
   - Recommendation: Update timestamp regardless to prevent repeated "no emails" checks — treat as successful run

2. **Should --dry-run preview both digests even if only --regular-only flag provided?**
   - What we know: --dry-run previews content, flags control execution
   - What's unclear: Interaction between preview and selective execution flags
   - Recommendation: --dry-run + --regular-only = preview regular only (respect selective flag in preview)

3. **How long should old "last_run" key remain in state file after migration?**
   - What we know: Keep temporarily for rollback safety
   - What's unclear: When is it safe to remove?
   - Recommendation: Remove in next major version (v2.0), document migration in CHANGELOG

## Sources

### Primary (HIGH confidence)
- Existing codebase patterns: src/config.py, src/state.py, src/main.py, tests/conftest.py
- Python stdlib documentation: json, argparse, pathlib, logging modules

### Secondary (MEDIUM confidence)
- [Environment Variable Management Best Practices 2026](https://www.envsentinel.dev/blog/environment-variable-management-tips-best-practices) - Validation patterns, startup validation
- [Python Environment Variables Guide](https://www.index.dev/blog/python-environment-variables-setup) - Pydantic vs manual validation, type conversion
- [Safe Atomic File Writes for JSON](https://gist.github.com/therightstuff/cbdcbef4010c20acc70d2175a91a321f) - Atomic write patterns (determined unnecessary)
- [Crash-Safe JSON at Scale](https://dev.to/constanta/crash-safe-json-at-scale-atomic-writes-recovery-without-a-db-3aic) - Error handling, graceful degradation
- [Python Atomicwrites Library](https://python-atomicwrites.readthedocs.io/en/latest/) - Atomic writes library (evaluated, not needed)
- [Django Backwards Compatible Migrations](https://forum.djangoproject.com/t/backwards-compatible-migrations/1406) - Expand-migrate-contract pattern
- [Backward Compatible Database Changes](https://planetscale.com/blog/backward-compatible-databases-changes) - State migration strategy
- [Python Feature Flags Guide](https://www.cloudbees.com/blog/python-feature-flag-guide) - Feature toggle patterns
- [Python Multiple Email Recipients](https://medium.com/@python-javascript-php-html-css/sending-emails-to-multiple-recipients-in-python-using-smtplib-d7ec9cc4405b) - TO/CC/BCC handling
- [Sending Emails with CC and BCC](https://www.twilio.com/en-us/blog/how-to-send-emails-with-a-cc-and-bcc-using-python-and-twilio-sendgrid) - BCC privacy best practices

### Tertiary (LOW confidence)
- N/A — All findings verified with existing codebase or authoritative sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in project, no new dependencies
- Architecture: HIGH - Patterns verified against existing codebase, extend not replace
- Pitfalls: HIGH - Based on documented email/state management issues and existing code analysis

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (30 days — stable domain, Python stdlib patterns don't change rapidly)
