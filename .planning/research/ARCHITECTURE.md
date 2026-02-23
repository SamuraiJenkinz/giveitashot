# Architecture Patterns: Major Update Detection Integration

**Domain:** Email summarization with classification and multiple digest types
**Researched:** 2026-02-23
**Confidence:** HIGH

## Executive Summary

The major update detection feature requires classification-first architecture where emails are categorized immediately after fetch and before summarization. This enables clean separation of digest types while maintaining the existing layered pipeline. Key integration points: new EmailClassifier module between fetch and summarize, shared configuration with separate recipient lists, unified state management with digest type tracking, and sequential orchestration of two independent digest workflows in main.py.

## Recommended Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         main.py Orchestrator                        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
         ┌──────────▼────────────┐   ┌─────────▼──────────┐
         │  Regular Digest Flow  │   │ Major Update Flow  │
         └──────────┬────────────┘   └─────────┬──────────┘
                    │                           │
    ┌───────────────┴──────────────┐           │
    │                              │           │
┌───▼────┐  ┌──────────┐  ┌───────▼──┐  ┌─────▼─────┐
│  Auth  │─>│ Fetch    │─>│ Classify │─>│ Split     │
└────────┘  │ (EWS)    │  │ (New)    │  │ (New)     │
            └──────────┘  └──────────┘  └───┬───┬───┘
                                            │   │
                        ┌───────────────────┘   └──────────────┐
                        │                                       │
                   ┌────▼─────┐                        ┌───────▼──────┐
                   │ Regular  │                        │ Major Update │
                   │Summarize │                        │  Summarize   │
                   └────┬─────┘                        └───────┬──────┘
                        │                                      │
                   ┌────▼─────┐                        ┌───────▼──────┐
                   │  Format  │                        │   Format     │
                   │  (HTML)  │                        │  (HTML+)     │
                   └────┬─────┘                        └───────┬──────┘
                        │                                      │
                   ┌────▼─────┐                        ┌───────▼──────┐
                   │   Send   │                        │    Send      │
                   │ (EWS)    │                        │   (EWS)      │
                   └──────────┘                        └──────────────┘
```

## Component Design

### 1. Email Classification (NEW)

**Module:** `src/classifier.py`

**Purpose:** Detect and classify Message Center major update emails

**Integration Point:** Between fetch and summarization (after EWSClient.get_shared_mailbox_emails, before EmailSummarizer.summarize_emails)

**Rationale:**
- Classification must happen immediately after fetch to split email streams
- Early classification prevents major updates from entering regular summarization
- Enables clean separation of digest types with different LLM prompts
- Follows industry pattern: "After the fetch stage... classification happening before the summarization step" ([source](https://dev.to/malok/building-an-ai-email-assistant-that-prioritizes-sorts-and-summarizes-with-llms-34m8))

**Implementation:**

```python
from dataclasses import dataclass
from typing import Optional
from .ews_client import Email

@dataclass
class ClassificationResult:
    """Result of email classification."""
    is_major_update: bool
    confidence: float
    detected_tags: list[str]
    message_id: Optional[str] = None
    service: Optional[str] = None
    impact_level: Optional[str] = None
    deadline: Optional[str] = None

class EmailClassifier:
    """
    Classifies emails to detect Microsoft Message Center major updates.
    Uses rule-based detection with optional LLM enhancement.
    """

    # Major update detection patterns
    MAJOR_UPDATE_KEYWORDS = [
        "major update", "admin impact", "user impact",
        "retirement", "action required", "deprecation"
    ]

    SENDER_PATTERNS = [
        "o365mc@microsoft.com",
        "microsoft 365 message center",
        "@microsoftonline.com"
    ]

    def __init__(self, use_llm: bool = False):
        """
        Initialize classifier.

        Args:
            use_llm: Whether to use LLM for enhanced classification
        """
        self._use_llm = use_llm
        self._llm_classifier = None

        if self._use_llm:
            try:
                from .llm_classifier import LLMEmailClassifier
                self._llm_classifier = LLMEmailClassifier()
            except Exception as e:
                logger.warning(f"LLM classification unavailable: {e}")
                self._use_llm = False

    def classify(self, email: Email) -> ClassificationResult:
        """
        Classify a single email.

        Args:
            email: Email to classify

        Returns:
            ClassificationResult with classification details
        """
        # Rule-based classification (always runs)
        is_major = self._is_major_update_rule_based(email)
        tags = self._extract_tags(email)

        # LLM enhancement (optional)
        if self._use_llm and self._llm_classifier:
            llm_result = self._llm_classifier.classify(email)
            is_major = is_major or llm_result.is_major_update
            tags.extend(llm_result.detected_tags)

        return ClassificationResult(
            is_major_update=is_major,
            confidence=0.95 if is_major else 0.90,
            detected_tags=list(set(tags)),
            message_id=self._extract_message_id(email),
            service=self._extract_service(email),
            impact_level=self._extract_impact_level(email),
            deadline=self._extract_deadline(email)
        )

    def classify_batch(self, emails: list[Email]) -> tuple[list[Email], list[Email]]:
        """
        Classify emails and split into regular vs major update streams.

        Args:
            emails: List of emails to classify

        Returns:
            Tuple of (regular_emails, major_update_emails)
        """
        regular = []
        major_updates = []

        for email in emails:
            result = self.classify(email)
            if result.is_major_update:
                major_updates.append(email)
            else:
                regular.append(email)

        return regular, major_updates

    def _is_major_update_rule_based(self, email: Email) -> bool:
        """Rule-based detection using sender and keywords."""
        # Check sender
        sender_match = any(
            pattern.lower() in email.sender_email.lower()
            for pattern in self.SENDER_PATTERNS
        )

        # Check subject and body for keywords
        content = f"{email.subject} {email.body_content}".lower()
        keyword_match = any(
            keyword.lower() in content
            for keyword in self.MAJOR_UPDATE_KEYWORDS
        )

        return sender_match and keyword_match

    def _extract_tags(self, email: Email) -> list[str]:
        """Extract classification tags from email content."""
        tags = []
        content = f"{email.subject} {email.body_content}".lower()

        if "major update" in content:
            tags.append("MAJOR_UPDATE")
        if "admin impact" in content:
            tags.append("ADMIN_IMPACT")
        if "user impact" in content:
            tags.append("USER_IMPACT")
        if "retirement" in content or "deprecation" in content:
            tags.append("RETIREMENT")
        if "action required" in content:
            tags.append("ACTION_REQUIRED")

        return tags
```

**Decision:** New module vs extending ews_client.py
- **Chosen:** New module `classifier.py`
- **Rationale:** Single Responsibility Principle — EWSClient handles EWS operations, classifier handles classification logic. Enables future enhancement (ML models, custom rules) without touching EWS code. Aligns with existing pattern where summarizer.py is separate from fetch logic.

**Sources:**
- [Email Classification Pipeline Architecture](https://github.com/shxntanu/email-classifier)
- [AI Email Assistant Architecture](https://dev.to/malok/building-an-ai-email-assistant-that-prioritizes-sorts-and-summarizes-with-llms-34m8)

### 2. Dual Summarization Workflows

**Module:** Extend `src/summarizer.py`

**Integration Point:** After classification split, parallel paths for regular vs major update

**Approach:** Add major update-specific methods to EmailSummarizer

```python
class EmailSummarizer:
    """Existing class with new major update methods."""

    def summarize_major_updates(self, emails: list[Email]) -> MajorUpdateSummary:
        """
        Generate major update digest with admin-focused emphasis.

        Args:
            emails: List of classified major update emails

        Returns:
            MajorUpdateSummary with deadlines, actions, impact
        """
        if not emails:
            return MajorUpdateSummary(
                date=datetime.now().strftime("%A, %B %d, %Y"),
                total_count=0,
                updates=[],
                urgent_deadlines=[],
                action_required=[]
            )

        # Use specialized LLM prompt for admin-focused summarization
        if self._llm_summarizer:
            logger.info("Generating major update digest with admin-focused AI...")
            digest = self._llm_summarizer.generate_major_update_digest(emails)
        else:
            digest = self._generate_basic_major_update_digest(emails)

        return digest

    def format_major_update_html(
        self,
        summary: MajorUpdateSummary,
        mailbox: str
    ) -> str:
        """
        Format major update digest with deadline emphasis and impact highlighting.

        Returns:
            HTML with urgent deadline callouts, action items, and service impact cards
        """
        # Enhanced HTML with deadline calendars, impact badges, action checklists
        pass
```

**LLM Prompt Strategy:**

```python
# In llm_summarizer.py
class LLMSummarizer:

    REGULAR_DIGEST_PROMPT = """
    Summarize these emails for busy professionals.
    Focus on: key decisions, action items, meeting outcomes.
    Tone: Executive summary, concise, business-focused.
    """

    MAJOR_UPDATE_DIGEST_PROMPT = """
    Summarize these Microsoft 365 service update emails for IT admins.
    Focus on: Deadlines, required actions, service impacts, affected users.
    Extract: Effective dates, rollout timelines, user communication needs.
    Prioritize: Retirements, breaking changes, security updates.
    Tone: Technical, action-oriented, deadline-aware.
    Format: Grouped by urgency (immediate action, 30 days, 90+ days).
    """

    def generate_major_update_digest(self, emails: list[Email]) -> dict:
        """Generate admin-focused digest with specialized prompt."""
        messages = [
            {"role": "system", "content": self.MAJOR_UPDATE_DIGEST_PROMPT},
            {"role": "user", "content": self._format_emails_for_prompt(emails)}
        ]
        # Call Azure OpenAI with major update prompt
        response = self._call_openai(messages)
        return self._parse_major_update_response(response)
```

**Decision:** One module with different methods vs separate summarizer classes
- **Chosen:** Extend existing EmailSummarizer with major_update methods
- **Rationale:** Code reuse (shared HTML formatting utilities, LLM connection handling), consistent interface, easier maintenance. Industry pattern: "Different prompts for different email types within same processing system" ([source](https://dev.to/ilbets/empower-your-email-routine-with-llm-agents-10x-efficiency-unlocked-4oke))

**Sources:**
- [LLM Email Processing with Multiple Prompts](https://igorsteblii.medium.com/empower-your-email-routine-with-llm-agents-10x-efficiency-unlocked-e3c81b05d99e)
- [Microsoft Message Center Major Updates](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/message-center?view=o365-worldwide)

### 3. Configuration Strategy

**Module:** Extend `src/config.py`

**Approach:** Add major update config to existing .env file with namespace prefix

```python
# In config.py
class Config:
    """Existing config with major update additions."""

    # Existing fields...

    # Major Update Configuration (new)
    MAJOR_UPDATE_TO: list[str] = _parse_email_list("MAJOR_UPDATE_TO")
    MAJOR_UPDATE_CC: list[str] = _parse_email_list("MAJOR_UPDATE_CC")
    MAJOR_UPDATE_BCC: list[str] = _parse_email_list("MAJOR_UPDATE_BCC")

    MAJOR_UPDATE_ENABLED: bool = os.getenv("MAJOR_UPDATE_ENABLED", "true").lower() == "true"

    @classmethod
    def get_major_update_recipients(cls) -> list[str]:
        """
        Get major update digest recipients.
        Falls back to regular recipients if not configured separately.
        """
        if cls.MAJOR_UPDATE_TO:
            return cls.MAJOR_UPDATE_TO
        return cls.get_recipients()  # Fallback to regular digest recipients

    @classmethod
    def validate(cls) -> None:
        """Extended validation with major update checks."""
        # Existing validation...

        # Major update validation
        if cls.MAJOR_UPDATE_ENABLED and not cls.get_major_update_recipients():
            logger.warning(
                "MAJOR_UPDATE_ENABLED but no recipients configured. "
                "Falling back to regular digest recipients."
            )
```

**Example .env structure:**

```bash
# Regular Digest Configuration
SUMMARY_TO=team@company.com
SUMMARY_CC=manager@company.com

# Major Update Digest Configuration (separate recipients)
MAJOR_UPDATE_TO=admin-team@company.com,it-managers@company.com
MAJOR_UPDATE_CC=cto@company.com
MAJOR_UPDATE_ENABLED=true
```

**Decision:** Same .env vs separate config file
- **Chosen:** Same .env with namespaced variables
- **Rationale:** Simpler deployment (one config file), shared auth/connection settings prevent duplication, clear namespace (MAJOR_UPDATE_*) prevents confusion, aligns with existing pattern (SUMMARY_TO/CC/BCC)

**Alternative Considered:** Separate .env.major_updates file
- **Why Not:** Increases deployment complexity, requires loading multiple files, duplicates shared settings (auth, mailbox), harder to maintain environment-specific configs

### 4. State Management

**Module:** Extend `src/state.py`

**Approach:** Single state file with digest type tracking

```python
class StateManager:
    """Extended with major update tracking."""

    def get_last_run(self, digest_type: str = "regular") -> datetime | None:
        """
        Get last run timestamp for specific digest type.

        Args:
            digest_type: "regular" or "major_update"

        Returns:
            datetime of last run for this digest type
        """
        key = f"last_run_{digest_type}"
        timestamp = self._state.get(key)
        if timestamp:
            return datetime.fromisoformat(timestamp)

        # Fallback to legacy "last_run" key for regular digest
        if digest_type == "regular":
            legacy = self._state.get("last_run")
            if legacy:
                return datetime.fromisoformat(legacy)

        return None

    def set_last_run(
        self,
        timestamp: datetime | None = None,
        digest_type: str = "regular"
    ) -> None:
        """
        Set last run timestamp for specific digest type.

        Args:
            timestamp: Timestamp to save (defaults to now)
            digest_type: "regular" or "major_update"
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        key = f"last_run_{digest_type}"
        self._state[key] = timestamp.isoformat()

        # Maintain legacy key for backward compatibility
        if digest_type == "regular":
            self._state["last_run"] = timestamp.isoformat()

        self._save()
        logger.info(f"Updated {digest_type} digest last run: {timestamp.isoformat()}")

    def get_state_summary(self) -> dict:
        """Get summary of all tracked digest states."""
        return {
            "regular": self.get_last_run("regular"),
            "major_update": self.get_last_run("major_update"),
            "raw_state": self._state
        }
```

**State file structure:**

```json
{
  "last_run": "2026-02-23T14:30:00+00:00",
  "last_run_regular": "2026-02-23T14:30:00+00:00",
  "last_run_major_update": "2026-02-23T14:30:00+00:00"
}
```

**Decision:** One state file vs separate tracking
- **Chosen:** Single state file with digest type keys
- **Rationale:** Both digests run in same invocation with same fetch time, simplifies state management (one file to backup/clear), prevents state drift between digest types, enables unified --clear-state flag

**Alternative Considered:** Separate .state_regular.json and .state_major_updates.json
- **Why Not:** State could drift if one digest fails, harder to clear state atomically, more complex --clear-state implementation, both digests fetch same emails so separate tracking adds no value

**Sources:**
- [Python State Management in Email Pipelines](https://github.com/KHolodilin/python-email-automation-processor)

### 5. Orchestration Layer

**Module:** Extend `src/main.py`

**Approach:** Sequential orchestration of two digest workflows

```python
def main() -> int:
    """
    Extended main function with major update detection.
    """
    # ... existing setup (logging, config, auth, EWS client) ...

    # Initialize state manager
    state = StateManager()

    # Initialize classifier
    classifier = EmailClassifier(use_llm=Config.USE_LLM_SUMMARY)

    # Determine fetch mode (same for both digests)
    since = None if args.full else state.get_last_run("regular")

    # Fetch emails (shared step)
    logger.info(f"Fetching emails from {Config.SHARED_MAILBOX}...")
    all_emails = ews_client.get_shared_mailbox_emails(Config.SHARED_MAILBOX, since=since)

    if not all_emails:
        logger.info("No new emails found - skipping both digests")
        return 0

    # Classify and split emails
    logger.info(f"Classifying {len(all_emails)} emails...")
    regular_emails, major_update_emails = classifier.classify_batch(all_emails)
    logger.info(f"  Regular: {len(regular_emails)}, Major Updates: {len(major_update_emails)}")

    # Initialize summarizer (used for both digest types)
    summarizer = EmailSummarizer()

    # Process regular digest
    if regular_emails:
        logger.info("=" * 60)
        logger.info("REGULAR DIGEST")
        logger.info("=" * 60)

        summary = summarizer.summarize_emails(regular_emails)
        subject = summarizer.get_subject_line(summary, Config.SHARED_MAILBOX)
        body_html = summarizer.format_summary_html(summary, Config.SHARED_MAILBOX)

        if not args.dry_run:
            ews_client.send_email(
                to_recipients=Config.get_recipients(),
                subject=subject,
                body_html=body_html,
                cc_recipients=Config.SUMMARY_CC,
                bcc_recipients=Config.SUMMARY_BCC
            )
            state.set_last_run(digest_type="regular")
            logger.info("Regular digest sent successfully")
    else:
        logger.info("No regular emails to summarize")

    # Process major update digest
    if major_update_emails and Config.MAJOR_UPDATE_ENABLED:
        logger.info("=" * 60)
        logger.info("MAJOR UPDATE DIGEST")
        logger.info("=" * 60)

        major_summary = summarizer.summarize_major_updates(major_update_emails)
        major_subject = summarizer.get_major_update_subject_line(major_summary)
        major_body_html = summarizer.format_major_update_html(major_summary, Config.SHARED_MAILBOX)

        if not args.dry_run:
            ews_client.send_email(
                to_recipients=Config.get_major_update_recipients(),
                subject=major_subject,
                body_html=major_body_html,
                cc_recipients=Config.MAJOR_UPDATE_CC,
                bcc_recipients=Config.MAJOR_UPDATE_BCC
            )
            state.set_last_run(digest_type="major_update")
            logger.info("Major update digest sent successfully")
    elif major_update_emails:
        logger.info("Major updates found but MAJOR_UPDATE_ENABLED=false")
    else:
        logger.info("No major updates to summarize")

    logger.info("=" * 60)
    logger.info("Email Summarizer Agent Completed Successfully")
    logger.info("=" * 60)
    return 0
```

**Decision:** Sequential vs parallel vs higher-level coordinator
- **Chosen:** Sequential orchestration in main.py
- **Rationale:** Both digests use same EWS connection, state updates must be atomic, simple deployment model (one invocation), shared error handling, easier debugging. Parallel execution adds complexity without performance benefit (both are I/O-bound, share auth/connection).

**Alternative Considered:** Parallel execution with threading
- **Why Not:** EWS client connection not thread-safe, state updates harder to coordinate, error handling becomes complex, minimal performance gain (I/O-bound operations)

**Alternative Considered:** Higher-level coordinator module
- **Why Not:** Over-engineering for two digest types, adds indirection without clear benefit, main.py already serves this role effectively

## Integration Points Summary

| Component | Type | Integration Point | Rationale |
|-----------|------|-------------------|-----------|
| EmailClassifier | NEW | Between fetch and summarize | Early classification enables clean stream separation |
| EmailSummarizer | EXTEND | Add major_update methods | Code reuse, consistent interface, shared LLM connection |
| LLMSummarizer | EXTEND | Add major update prompts | Specialized prompts for admin-focused summarization |
| Config | EXTEND | Add MAJOR_UPDATE_* vars | Shared .env with namespace prevents duplication |
| StateManager | EXTEND | Add digest_type parameter | Unified state file prevents drift, simplifies management |
| main.py | EXTEND | Sequential workflow | Shared connection, atomic state, simple deployment |
| ews_client.py | NO CHANGE | - | Classification separate from EWS operations |

## Data Flow Changes

### Before (Current v0.3)

```
Auth → Fetch Emails → Summarize → Format HTML → Send → Update State
```

### After (v1.0 with Major Updates)

```
Auth → Fetch Emails → Classify → Split
                                   ├─> Regular Emails → Summarize (general) → Format → Send (team) → Update State
                                   └─> Major Updates → Summarize (admin) → Format+ → Send (admins) → Update State
```

## Component Dependencies

```
classifier.py
  └─> ews_client.py (Email dataclass)
  └─> llm_classifier.py (optional, for LLM enhancement)

summarizer.py (extended)
  └─> ews_client.py (Email dataclass)
  └─> llm_summarizer.py (extended with major update prompts)
  └─> config.py

llm_summarizer.py (extended)
  └─> Azure OpenAI
  └─> Different prompts for regular vs major update

main.py (extended)
  └─> classifier.py (NEW)
  └─> summarizer.py (extended)
  └─> state.py (extended)
  └─> config.py (extended)
  └─> ews_client.py (no change)
  └─> auth.py (no change)
```

## Suggested Build Order

Based on dependencies and risk:

### Phase 1: Foundation (Low Risk, Enables Testing)
1. **EmailClassifier module** (`classifier.py`)
   - No dependencies on other changes
   - Can be tested independently with existing Email objects
   - Rule-based detection only (defer LLM enhancement)
   - **Validation:** Unit tests with sample Message Center emails

2. **Config extension** (`config.py`)
   - Add MAJOR_UPDATE_* variables
   - Add recipient getters with fallbacks
   - **Validation:** Config.validate() includes major update checks

### Phase 2: Summarization (Medium Risk, Core Feature)
3. **LLM prompt extension** (`llm_summarizer.py`)
   - Add MAJOR_UPDATE_DIGEST_PROMPT
   - Add generate_major_update_digest() method
   - **Validation:** Test prompt with sample major update emails

4. **Summarizer extension** (`summarizer.py`)
   - Add summarize_major_updates() method
   - Add format_major_update_html() method
   - Add get_major_update_subject_line() method
   - **Validation:** Generate sample major update digest HTML

### Phase 3: State & Orchestration (Higher Risk, Integration)
5. **State management extension** (`state.py`)
   - Add digest_type parameter support
   - Maintain backward compatibility with legacy key
   - **Validation:** Test state read/write with both digest types

6. **Main orchestration** (`main.py`)
   - Integrate classifier after fetch
   - Add major update workflow
   - Add logging for both digest types
   - **Validation:** End-to-end test with --dry-run

### Phase 4: Polish (Optional Enhancements)
7. **LLM classifier** (`llm_classifier.py`, optional)
   - LLM-enhanced classification for edge cases
   - Falls back to rule-based if unavailable
   - **Validation:** Compare LLM vs rule-based accuracy

8. **Enhanced HTML formatting** (optional)
   - Deadline calendars, impact badges, action checklists
   - **Validation:** Visual review of major update digest

## Risk Mitigation

### Existing Pipeline Protection
- **Risk:** Breaking existing regular digest functionality
- **Mitigation:**
  - Classification returns empty list if no major updates found
  - Regular digest path unchanged when major_update_emails is empty
  - Feature flag MAJOR_UPDATE_ENABLED allows disabling
  - Backward compatible state management (legacy "last_run" key maintained)

### Configuration Errors
- **Risk:** Misconfigured recipients or missing variables
- **Mitigation:**
  - Fallback to regular recipients if major update recipients not set
  - Config.validate() extended with major update checks
  - Logged warnings for fallback scenarios

### State Drift
- **Risk:** One digest succeeds, other fails, state becomes inconsistent
- **Mitigation:**
  - Both digests use same fetch timestamp
  - State updates only after successful send
  - Atomic state file writes
  - Clear error boundaries with try/except per digest

### Classification Accuracy
- **Risk:** False positives (regular emails marked as major updates) or false negatives (major updates missed)
- **Mitigation:**
  - Conservative rule-based detection (sender AND keywords)
  - Logged classification results for monitoring
  - Optional LLM enhancement for edge cases
  - Classification can be tuned without changing pipeline

## Scalability Considerations

| Concern | Current Scale | Future Scale | Approach |
|---------|---------------|--------------|----------|
| Email volume | <100/day | <500/day | Classification is O(n), negligible overhead |
| Classification accuracy | Rule-based sufficient | May need ML | Designed for future LLM enhancement |
| Digest types | 2 (regular, major) | 3-5 (add urgent, security) | Pattern extends: classify → split → summarize → send |
| Recipients | <10 per digest | <50 per digest | EWS handles bulk recipients efficiently |
| State complexity | 2 digest types | 5 digest types | StateManager design scales linearly |

## Performance Implications

### Additional Processing Time
- **Classification:** ~50-200ms per email (rule-based), ~1-2s with LLM
- **LLM Summarization:** Separate API calls for major updates (~3-5s)
- **HTML Formatting:** Minimal (<100ms)
- **Email Sending:** One additional send operation (~500ms)

**Total overhead:** ~5-10 seconds for typical batch (50 emails, 5 major updates)

### Token Usage (Azure OpenAI)
- **Current:** ~1000-3000 tokens per regular digest
- **With Major Updates:** +500-1500 tokens for major update digest
- **Classification (if LLM enabled):** +100 tokens per email

**Cost impact:** Minimal (~$0.01-0.03 per run at GPT-4 pricing)

## Testing Strategy

### Unit Tests
- `test_classifier.py`: Test classification rules, edge cases, batch processing
- `test_summarizer.py`: Test major update summarization, HTML formatting
- `test_config.py`: Test recipient fallbacks, validation
- `test_state.py`: Test digest type tracking, backward compatibility

### Integration Tests
- End-to-end with --dry-run flag
- Test classification accuracy with real Message Center emails
- Verify both digests generated with correct recipients
- Validate state updates after each digest

### Validation Criteria
- **Classification accuracy:** >95% for known Message Center patterns
- **No regression:** Regular digest unchanged when no major updates
- **Backward compatibility:** Legacy state file format still works
- **Error handling:** Individual digest failures don't cascade

## Migration Path

### From v0.3 (Current) to v1.0 (Major Updates)

**State Migration:**
```python
# Automatic migration in StateManager._load()
if "last_run" in state and "last_run_regular" not in state:
    state["last_run_regular"] = state["last_run"]
    state["last_run_major_update"] = state["last_run"]
```

**Config Migration:**
```bash
# Add to existing .env
MAJOR_UPDATE_ENABLED=true
MAJOR_UPDATE_TO=admin-team@company.com
# Optional: MAJOR_UPDATE_CC, MAJOR_UPDATE_BCC
```

**Rollback Plan:**
1. Set `MAJOR_UPDATE_ENABLED=false`
2. Regular digest continues unchanged
3. No code removal required (feature flag protects)

## Architecture Anti-Patterns to Avoid

### 1. Classification After Summarization
**Why Bad:** Wastes LLM tokens summarizing emails that will be filtered, requires two classification passes (before split and after summarize)

### 2. Separate Fetch Calls for Each Digest
**Why Bad:** Duplicate EWS API calls, higher latency, potential for missed emails between calls

### 3. Shared Summarization with Conditional Prompts
**Why Bad:** Complex prompt engineering, harder to maintain, tight coupling between digest types

### 4. Multiple State Files
**Why Bad:** State drift risk, complex atomic updates, harder to backup/restore

### 5. Parallel Digest Generation
**Why Bad:** EWS connection not thread-safe, minimal performance gain (I/O-bound), complex error handling

## Future Extension Points

### Additional Digest Types
Pattern extends naturally:
```python
# classifier.py
security_emails, urgent_emails, regular_emails = classifier.classify_multi_type(emails)

# main.py
for digest_type, emails, config in [
    ("security", security_emails, SecurityConfig),
    ("urgent", urgent_emails, UrgentConfig),
    ("regular", regular_emails, RegularConfig)
]:
    process_digest(digest_type, emails, config)
```

### ML-Based Classification
```python
# Future: llm_classifier.py
class LLMEmailClassifier:
    """Enhanced classification using Azure OpenAI."""

    def classify(self, email: Email) -> ClassificationResult:
        prompt = f"Classify this email: {email.subject}"
        response = self._call_openai(prompt)
        return self._parse_classification(response)
```

### Custom Formatting Per Digest Type
```python
# Future: formatter.py
class DigestFormatter:
    """Strategy pattern for different digest formats."""

    def format_regular(self, summary) -> str: pass
    def format_major_update(self, summary) -> str: pass
    def format_security(self, summary) -> str: pass
```

## Confidence Assessment

| Component | Confidence | Source |
|-----------|------------|--------|
| Classification placement | HIGH | Industry standard: classify after fetch, before summarization |
| New module vs extend | HIGH | SOLID principles, existing codebase patterns |
| State management approach | HIGH | Proven pattern in existing codebase |
| Config strategy | HIGH | Consistent with existing SUMMARY_TO/CC/BCC pattern |
| Sequential orchestration | HIGH | Simplicity, shared connection, atomic operations |
| LLM prompt strategy | MEDIUM | Tested pattern, but prompt tuning may be needed |
| Rule-based classification | MEDIUM | Effective for known patterns, may need LLM enhancement |

## Gaps Requiring Investigation

1. **Message Center Email Format:** Need sample emails to validate classification rules
2. **LLM Prompt Tuning:** Major update prompt may need iteration based on actual output
3. **HTML Formatting:** Major update digest design needs mockup/review
4. **Impact Fields:** Exact structure of impact_level, deadline extraction needs validation

## Sources

- [Email Classification Pipeline Architecture](https://github.com/shxntanu/email-classifier) - Classification before summarization pattern
- [AI Email Assistant Architecture](https://dev.to/malok/building-an-ai-email-assistant-that-prioritizes-sorts-and-summarizes-with-llms-34m8) - Multi-step pipeline with classification
- [LLM Email Processing](https://igorsteblii.medium.com/empower-your-email-routine-with-llm-agents-10x-efficiency-unlocked-e3c81b05d99e) - Multiple prompts for different email types
- [Microsoft Message Center](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/message-center?view=o365-worldwide) - Major update characteristics and notification patterns
- [Email Automation Architecture](https://github.com/KHolodilin/python-email-automation-processor) - Modular Python email processing patterns
