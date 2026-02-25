# Phase 4: AI Enhancement - Research

**Researched:** 2026-02-24
**Domain:** Azure OpenAI structured outputs, LLM action extraction, deadline countdown display
**Confidence:** HIGH

## Summary

This phase adds AI-powered action extraction from major update emails using the existing Azure OpenAI integration. Research confirms that Azure OpenAI's structured outputs feature (introduced in 2024, stable in 2026) provides robust JSON schema validation, making it ideal for extracting actionable admin tasks with strict validation. The existing `llm_summarizer.py` pattern uses httpx for API calls with 60-second timeouts, which aligns with current best practices. Action extraction should use short imperative commands (3-5 words) for digest readability, and deadline countdowns should display "X days remaining" inline with action dates for immediate comprehension.

Key findings: Azure OpenAI structured outputs with Pydantic models enable reliable schema validation, graceful degradation patterns ensure digest delivery even during LLM failures, and one LLM call per email provides optimal error isolation.

**Primary recommendation:** Use Pydantic models for structured output validation, implement per-email error handling with body preview fallback, and display actions inline within major update cards with countdown format "Action Required: [Date] (X days remaining)".

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.27+ | HTTP client for Azure OpenAI API | Already used in project, supports timeout config, async-capable |
| Pydantic | 2.8+ | JSON schema validation and data models | Industry standard for LLM structured outputs, automatic validation |
| Azure OpenAI API | 2024-08-01-preview+ | Structured output generation | Provides guaranteed JSON schema adherence vs older JSON mode |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | stdlib | Type hints for Pydantic models | All model definitions |
| json | stdlib | Fallback JSON parsing | Error handling when structured outputs unavailable |
| logging | stdlib | Error and debug logging | All LLM interactions for observability |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic | dataclasses + manual validation | Less robust validation, more error-prone |
| httpx | requests | Less modern, no native async support |
| Azure OpenAI structured outputs | JSON mode + manual parsing | Weaker guarantees, more parsing code needed |

**Installation:**
```bash
# All dependencies already present in project
# Pydantic: pip install pydantic>=2.8
# httpx: pip install httpx>=0.27
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── llm_summarizer.py       # Existing LLM client - add action extraction method
├── action_extractor.py     # NEW - Pydantic models + extraction logic
├── summarizer.py           # Update format_major_updates_html to include actions
└── extractor.py            # Existing - MajorUpdateFields dataclass
```

### Pattern 1: Pydantic-Based Structured Output
**What:** Define Pydantic models that mirror desired JSON schema, use Azure OpenAI's `response_format` parameter for guaranteed validation.

**When to use:** All LLM calls requiring structured data extraction (action items, deadlines, roles).

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs
from pydantic import BaseModel, Field
from typing import Optional

class AdminAction(BaseModel):
    """Single actionable task extracted from major update."""
    action: str = Field(description="Short imperative command (3-5 words)")
    details: Optional[str] = Field(default=None, description="Brief explanation if needed")
    role: Optional[str] = Field(default=None, description="Target role (e.g. 'Global Admin')")

class ActionExtraction(BaseModel):
    """Collection of actions extracted from an email."""
    actions: list[AdminAction] = Field(default_factory=list, max_length=5)
    confidence: str = Field(description="HIGH, MEDIUM, or LOW extraction confidence")

# Usage in LLM call
payload = {
    "messages": [...],
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "action_extraction",
            "schema": ActionExtraction.model_json_schema()
        }
    }
}
```

### Pattern 2: Isolated Per-Email LLM Calls
**What:** One LLM call per major update email, with independent error handling and fallback.

**When to use:** When processing multiple items where individual failures should not cascade.

**Example:**
```python
# Source: Existing llm_summarizer.py pattern
def extract_actions_batch(self, updates: list[MajorUpdateFields]) -> dict[str, ActionExtraction]:
    """Extract actions from multiple emails with isolation."""
    results = {}
    for update in updates:
        try:
            actions = self._extract_actions_single(update)
            results[update.mc_id] = actions
        except LLMSummarizerError:
            logger.warning(f"Action extraction failed for {update.mc_id}, using fallback")
            # Email still renders without actions section
            results[update.mc_id] = None
    return results
```

### Pattern 3: Graceful Degradation Hierarchy
**What:** Multiple fallback levels to ensure digest always sends with best available data.

**When to use:** Production systems where uptime > feature completeness.

**Example:**
```python
# Source: https://markaicode.com/implement-graceful-degradation-llm-frameworks/
# Level 1: Full AI extraction
try:
    actions = extractor.extract_actions(email)
except LLMTimeout:
    # Level 2: Cached response if seen before
    actions = cache.get(email.mc_id)
    if actions is None:
        # Level 3: Send digest without actions
        actions = None
        logger.info(f"Sending {email.mc_id} without AI actions (LLM unavailable)")
```

### Anti-Patterns to Avoid
- **Batch LLM calls for multiple emails:** Single failure affects all emails. Use per-email isolation instead.
- **Synchronous retry loops:** Blocks digest sending. Use fail-fast with fallback to body preview.
- **Complex action schemas:** Deep nesting or many fields increase hallucination risk. Keep schemas flat and simple.
- **Visible error messages to recipients:** Breaks "silent degradation" requirement. Log errors server-side only.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema validation | Manual dict checking with if/else | Pydantic models with Field() validation | Handles edge cases, type coercion, nested validation automatically |
| LLM timeout handling | try/except with time.sleep() | httpx.Timeout with exponential backoff | Prevents retry storms, standard pattern for API clients |
| Structured output parsing | Regex or string manipulation | Azure OpenAI `response_format: json_schema` | Guaranteed adherence to schema, no parsing needed |
| Countdown calculation | Manual datetime arithmetic | Existing extractor pattern (lines 167-187) | Already handles overdue, timezone, edge cases |
| HTML injection safety | Manual escaping | Existing summarizer pattern (lines 462-753) | Already sanitizes all text in templates |

**Key insight:** Azure OpenAI structured outputs (2024+) provide stronger guarantees than older JSON mode. JSON mode only ensured valid JSON syntax; structured outputs enforce schema adherence, making manual validation unnecessary.

## Common Pitfalls

### Pitfall 1: API Version Mismatch
**What goes wrong:** Structured outputs fail with 400 Bad Request even with valid schema.

**Why it happens:** Azure OpenAI structured outputs require API version 2024-08-01-preview or later. Project currently uses 2023-05-15 in .env.example.

**How to avoid:**
- Update `API_VERSION` to 2024-08-01-preview or later in .env.example
- Document this requirement in implementation notes
- Add validation check in LLMSummarizer.__init__() to warn if version too old

**Warning signs:**
- Error message: "structured outputs not supported for this API version"
- Successful LLM calls for regular summaries but failures for structured outputs

**Source:** [Azure OpenAI structured outputs requirements](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs)

### Pitfall 2: Schema Too Complex for LLMs
**What goes wrong:** LLM hallucinates fields, returns invalid data despite schema validation.

**Why it happens:** Azure OpenAI structured outputs support up to 100 properties and 5 nesting levels, but complex schemas increase hallucination probability. LLMs struggle with deeply nested structures or ambiguous field descriptions.

**How to avoid:**
- Keep action schema flat (no nested objects beyond 1-2 levels)
- Limit to 3-5 actions per email (prevent overwhelming model)
- Use clear field descriptions in Pydantic Field() annotations
- Avoid optional fields that look required (model may fill them anyway)

**Warning signs:**
- Actions that don't match email content
- Repeated or duplicate actions
- Generic actions like "Review this update" instead of specific tasks

**Source:** [Azure OpenAI schema constraints](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs)

### Pitfall 3: Silent Timeout Failures
**What goes wrong:** LLM calls time out but digest never sends because code waits indefinitely or crashes.

**Why it happens:** Default httpx timeout is 5 seconds for connect, unlimited for read. Existing code uses 60 seconds, but longer prompts (action extraction with full email body) may exceed this.

**How to avoid:**
- Keep existing 60-second timeout for action extraction (matches current pattern)
- Wrap LLM calls in try/except for httpx.TimeoutException
- Log timeout failures but continue digest generation without actions
- Consider prompt size - truncate email body to first 1500 chars if needed

**Warning signs:**
- Digest stops sending entirely when Azure OpenAI is slow
- No error logs, just hanging process
- Action extraction works in testing but fails in production with longer emails

**Source:** [Azure OpenAI timeout best practices](https://dasroot.net/posts/2026/02/implementing-retry-timeout-strategies-ai-apis/)

### Pitfall 4: Countdown Display Ambiguity
**What goes wrong:** Users misinterpret "15 days" as 15 business days or miss urgency context.

**Why it happens:** Bare numbers without context (calendar days vs business days, positive vs negative for overdue) create confusion. Research shows time displays need explicit context.

**How to avoid:**
- Use existing pattern from summarizer.py lines 604-608: "(X days remaining)" format
- Overdue dates use "OVERDUE - X days past deadline" format (lines 606-607)
- Display deadline date alongside countdown: "March 15, 2026 (15 days remaining)"
- Use color coding from urgency tier (already implemented in major digest)

**Warning signs:**
- User questions about "when exactly is this due?"
- Confusion about weekends/holidays counting toward deadline
- Overdue tasks not appearing urgent enough

**Source:** [Expressing Time in UI/UX Design](https://blog.prototypr.io/expressing-time-in-ui-ux-design-5-rules-and-a-few-other-things-eda5531a41a7)

### Pitfall 5: Action Granularity Mismatch
**What goes wrong:** Actions are either too vague ("Take action") or too detailed (multi-paragraph instructions), breaking digest layout.

**Why it happens:** LLMs default to extremes without clear constraints. UX research shows admin tasks need balance: specific enough to be actionable, brief enough to scan quickly.

**How to avoid:**
- Constrain action field to 3-5 words in Pydantic Field(max_length=50)
- Use optional details field for longer explanations (shown on hover or expand)
- Provide examples in prompt: "Update auth settings", "Migrate workflows by March 15"
- Test with real Message Center emails to calibrate length

**Warning signs:**
- Actions like "Review this update" (too vague)
- Actions that repeat the entire email body (too detailed)
- Layout breaks because action text wraps to multiple lines

**Source:** [Task Analysis in UX](https://www.interaction-design.org/literature/article/task-analysis-a-ux-designer-s-best-friend)

## Code Examples

Verified patterns from official sources:

### Action Extraction with Structured Outputs
```python
# Source: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs
import httpx
from pydantic import BaseModel, Field
from typing import Optional

class AdminAction(BaseModel):
    """Single actionable admin task."""
    action: str = Field(max_length=50, description="Short imperative: 'Update auth settings'")
    details: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = Field(default=None, description="Global Admin, Teams Admin, etc.")

class ActionExtraction(BaseModel):
    """Actions extracted from major update."""
    actions: list[AdminAction] = Field(default_factory=list, max_length=5)
    confidence: str = Field(pattern="^(HIGH|MEDIUM|LOW)$")

def extract_actions(self, update: MajorUpdateFields) -> Optional[ActionExtraction]:
    """Extract actions from a single major update email."""
    system_prompt = """Extract actionable admin tasks from this Microsoft 365 update.

Focus on:
- Specific configuration changes needed
- Deadline-driven tasks (e.g., "Migrate workflows by March 15")
- User communication requirements

Rules:
- Return 1-5 actions only (prioritize most important)
- Each action: 3-5 words, imperative verb form
- Include role if task is role-specific (Global Admin, etc.)
- Confidence: HIGH if actions clearly stated, LOW if inferred"""

    user_prompt = f"""MC ID: {update.mc_id}
Subject: {update.subject}
Action Required By: {update.action_required_date.strftime('%B %d, %Y') if update.action_required_date else 'None'}
Body: {update.body_preview[:1500]}

Extract admin actions as JSON."""

    schema = ActionExtraction.model_json_schema()
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,  # Lower temp for more deterministic extraction
        "max_tokens": 500,   # Actions are short, limit tokens
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "action_extraction",
                "schema": schema,
                "strict": True
            }
        }
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(self._endpoint, headers=self._headers, json=payload)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return ActionExtraction.model_validate_json(content)
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.warning(f"Action extraction failed for {update.mc_id}: {e}")
        return None  # Graceful degradation
```

### HTML Rendering with Actions
```python
# Source: Existing summarizer.py pattern (lines 688-700)
# Add to format_major_updates_html within update card loop

# After body_preview_html section:
actions_html = ""
if actions and actions.actions:
    actions_html += f"""
                                                <div style="margin: 12px 0 0 0; padding: 12px; background-color: {colors['bg_card']}; border: 1px solid {colors['border']}; border-radius: 6px;">
                                                    <p style="margin: 0 0 8px 0; color: {colors['text_dark']}; font-size: 12px; font-weight: 600;">
                                                        ⚡ ACTION ITEMS
                                                    </p>
"""
    for action in actions.actions[:3]:  # Limit to 3 for layout
        role_badge = ""
        if action.role:
            role_badge = f'<span style="display: inline-block; background-color: {colors["primary"]}; color: #ffffff; font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-left: 4px;">{action.role}</span>'

        actions_html += f"""
                                                    <p style="margin: 4px 0; color: {colors['text_dark']}; font-size: 13px;">
                                                        • {action.action}{role_badge}
                                                    </p>
"""
    actions_html += """
                                                </div>
"""
```

### Countdown Display Format
```python
# Source: Existing summarizer.py lines 604-608 (already implemented)
# Countdown calculation and display (already in format_major_updates_html):

if update.action_required_date:
    date_formatted = update.action_required_date.strftime("%B %d, %Y")
    days_diff = (update.action_required_date.date() - today.date()).days

    if days_diff < 0:
        # Overdue
        days_text = f'<span style="color: {colors["danger"]}; font-weight: 600;">(OVERDUE - {abs(days_diff)} days past deadline)</span>'
    else:
        # Future deadline
        days_text = f"({days_diff} days remaining)"

    action_date_html = f"""
        <p style="margin: 8px 0 0 0; color: {colors['text_dark']}; font-size: 13px;">
            <strong>Action Required:</strong> {date_formatted} {days_text}
        </p>
    """
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JSON mode (json_object) | Structured outputs (json_schema) | 2024-08-01 | Guaranteed schema adherence, no manual validation needed |
| Manual retry logic | Exponential backoff libraries | 2025-2026 | Standardized retry patterns, prevents API throttling |
| String parsing for actions | Pydantic models with Field validation | 2024+ | Type safety, automatic validation, clear contracts |
| Manual JSON validation | Pydantic model_validate_json() | 2024+ | Built-in validation, clear error messages |
| Generic OpenAI client | Azure-specific endpoints | Ongoing | Better auth, regional compliance, enterprise features |

**Deprecated/outdated:**
- **JSON mode without schema validation:** Azure OpenAI API version <2024-08-01 only supports JSON mode (valid JSON, no schema enforcement). Use 2024-08-01-preview+ for structured outputs.
- **requests library for LLM calls:** Project uses httpx which is modern standard (async support, better timeout control). Don't migrate to requests.
- **openai Python SDK:** Project uses direct REST API calls via httpx. Continue this pattern for consistency (avoids SDK version lock-in).

## Open Questions

Things that couldn't be fully resolved:

1. **Action count limit per email**
   - What we know: UX research suggests 3-5 items for scannable lists, Azure OpenAI schemas support up to 100 array items
   - What's unclear: Optimal count for Message Center updates specifically (some may have 1 action, others 10+)
   - Recommendation: Start with max 5 actions, collect user feedback on whether important actions are missed

2. **Role tagging value**
   - What we know: Message Center often specifies "Global Admin", "Teams Admin", etc. as required roles
   - What's unclear: Whether showing role in digest adds value or just clutters the display
   - Recommendation: Include role as optional field, display as badge if present (see HTML example). Test with real admins.

3. **Prompt length vs accuracy tradeoff**
   - What we know: Full email body provides best context but increases tokens/cost/latency
   - What's unclear: Whether 1500-char truncation (existing body_preview pattern is 200 chars) loses critical action details
   - Recommendation: Use first 1500 chars initially, monitor extraction quality. Adjust if actions are frequently incomplete.

4. **Confidence threshold for display**
   - What we know: Extraction returns HIGH/MEDIUM/LOW confidence
   - What's unclear: Should LOW confidence actions be shown (risk of hallucination) or hidden (risk of missing real actions)?
   - Recommendation: Show all confidence levels initially, log confidence for later analysis. May add threshold in future.

## Sources

### Primary (HIGH confidence)
- [Azure OpenAI Structured Outputs Documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs?view=foundry-classic) - Official Microsoft docs on structured output API usage
- [OpenAI Structured Outputs Guide](https://openai.com/index/introducing-structured-outputs-in-the-api/) - Core concept explanation and best practices
- [Pydantic JSON Schema Documentation](https://docs.pydantic.dev/latest/concepts/json_schema/) - Official Pydantic validation patterns
- [Azure OpenAI Timeout Best Practices](https://dasroot.net/posts/2026/02/implementing-retry-timeout-strategies-ai-apis/) - Retry/timeout strategies for AI APIs in 2026

### Secondary (MEDIUM confidence)
- [LLM Email Action Extraction Research](https://arxiv.org/html/2502.03804v2) - Academic research on LLM email task extraction
- [Prompt Engineering for Data Extraction](https://medium.com/@kofsitho/effective-prompt-engineering-for-data-extraction-with-large-language-models-331ee454cbae) - Best practices for structured extraction prompts
- [UX Time Display Guidelines](https://blog.prototypr.io/expressing-time-in-ui-ux-design-5-rules-and-a-few-other-things-eda5531a41a7) - Research-based time display patterns
- [Graceful Degradation in LLM Systems](https://markaicode.com/implement-graceful-degradation-llm-frameworks/) - Error handling and fallback patterns

### Tertiary (LOW confidence)
- [Task Analysis UX Principles](https://www.interaction-design.org/literature/article/task-analysis-a-ux-designer-s-best-friend) - General UX guidance on task presentation (not LLM-specific)
- Community discussions on timeout configuration - Anecdotal best practices, not official guidance

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in project, well-documented official APIs
- Architecture: HIGH - Patterns verified against existing codebase (llm_summarizer.py, summarizer.py)
- Pitfalls: HIGH - Based on official docs and recent 2025-2026 sources
- Action granularity: MEDIUM - UX research general, not specific to admin digest contexts
- Role tagging value: LOW - No specific research found on badge effectiveness in email digests

**Research date:** 2026-02-24
**Valid until:** 2026-04-24 (60 days - Azure OpenAI API is stable but evolving)
