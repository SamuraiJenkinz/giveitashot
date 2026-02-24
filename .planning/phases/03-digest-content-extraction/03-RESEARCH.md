# Phase 3: Digest Content Extraction - Research

**Researched:** 2026-02-24
**Domain:** HTML email digest generation with structured field extraction
**Confidence:** HIGH

## Summary

This phase focuses on extracting Message Center fields from major update emails and formatting them into a professional HTML digest. The existing codebase already has a proven HTML email template system (summarizer.py) that uses table-based layout, inline CSS, and a 600px width with professional styling. The primary technical challenges are: (1) extracting structured fields (MC ID, dates, services, categories) from email content using regex patterns, (2) implementing urgency-based color coding with traffic light colors, and (3) handling edge cases like deduplication and missing fields.

Python's standard library provides all core capabilities needed: regex for pattern extraction, datetime for date parsing, html.unescape for text cleaning, and f-strings for HTML generation. No additional dependencies required. The existing Email dataclass already captures body_content and classification metadata, providing the foundation for field extraction.

**Primary recommendation:** Extend the existing format_summary_html pattern in summarizer.py with a new format_major_updates_html method that reuses the proven table layout, color palette system, and inline CSS approach while adding urgency-based sorting and traffic light color-coding via left-border accents.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python re | stdlib | Regex pattern extraction | Built-in, proven for MC ID, date, service extraction |
| Python datetime | stdlib | Date parsing and formatting | Built-in, handles email dates via strptime |
| html.unescape | stdlib | HTML entity decoding | Built-in, already used in ews_client.py line 118 |
| f-strings | Python 3.10+ | HTML template generation | Native Python, used in existing summarizer.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| exchangelib | 5.4.0+ | Email body HTML access | Already integrated, provides body_content |
| email.utils | stdlib | RFC 5322 date parsing | If email dates need standards-compliant parsing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure regex | BeautifulSoup4 | BS4 adds 100KB+ dependency for minimal benefit when body_content is already text-stripped |
| Inline CSS | External CSS | External CSS fails in 90% of email clients (Gmail, Outlook) |
| Jinja2 templates | f-string templates | Jinja2 adds dependency complexity when f-strings work perfectly for this use case |

**Installation:**
```bash
# No additional packages needed - all stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── summarizer.py          # Add format_major_updates_html method here
├── ews_client.py          # Already provides Email.body_content
├── classifier.py          # Already provides Email.classification
└── main.py                # Pipeline: fetch → classify → summarize major → send major
```

### Pattern 1: Extend Existing HTML Formatter
**What:** Add major update digest formatting to existing EmailSummarizer class
**When to use:** This phase only (reuse proven layout system)
**Example:**
```python
class EmailSummarizer:
    def format_major_updates_html(
        self,
        major_updates: list[Email],
        urgency_tiers: dict[str, list[dict]]
    ) -> str:
        """Format major updates with urgency color-coding."""
        # Reuse existing color palette
        colors = self._get_color_palette()

        # Add traffic light colors for urgency
        urgency_colors = {
            "Critical": colors["danger"],   # Red #ea4335
            "High": colors["warning"],      # Amber #fbbc04
            "Normal": colors["success"]     # Green #34a853
        }

        # Same table-based layout as regular digest
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: {colors['bg_light']};
             font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0"
                       style="background-color: {colors['bg_card']}; border-radius: 12px;">
                    <!-- Header, stats, urgency sections here -->
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
        return html
```

### Pattern 2: Regex-Based Field Extraction
**What:** Extract Message Center fields using compiled regex patterns
**When to use:** For MC ID, dates, services, categories from email content
**Example:**
```python
import re
from typing import Optional, List
from datetime import datetime

class MessageCenterExtractor:
    # Compile once, reuse for performance
    MC_ID_PATTERN = re.compile(r'\bMC(\d{5,7})\b', re.IGNORECASE)
    DATE_PATTERN = re.compile(r'(?:by|deadline:|on)\s*(\d{1,2}/\d{1,2}/\d{4})', re.IGNORECASE)
    SERVICE_PATTERN = re.compile(
        r'\b(Exchange Online|Microsoft 365 Apps|Teams|SharePoint|OneDrive|'
        r'Power Platform|Viva|Intune|Microsoft Entra|Windows)\b',
        re.IGNORECASE
    )

    def extract_mc_id(self, email: Email) -> Optional[str]:
        """Extract MC ID from subject or body."""
        match = self.MC_ID_PATTERN.search(email.subject)
        if match:
            return f"MC{match.group(1)}"
        match = self.MC_ID_PATTERN.search(email.body_content)
        return f"MC{match.group(1)}" if match else None

    def extract_action_date(self, email: Email) -> Optional[datetime]:
        """Extract action-required date from body."""
        match = self.DATE_PATTERN.search(email.body_content)
        if match:
            try:
                return datetime.strptime(match.group(1), "%m/%d/%Y")
            except ValueError:
                return None
        return None

    def extract_services(self, email: Email) -> List[str]:
        """Extract affected services from body."""
        services = self.SERVICE_PATTERN.findall(email.body_content)
        return list(set(services))  # Deduplicate
```

### Pattern 3: Urgency-Based Sorting and Color-Coding
**What:** Calculate urgency from deadline proximity and apply traffic light colors
**When to use:** For organizing major updates by urgency tier
**Example:**
```python
from datetime import datetime, timedelta
from typing import Dict, List

def calculate_urgency(action_date: Optional[datetime]) -> str:
    """Calculate urgency tier based on deadline proximity."""
    if action_date is None:
        return "Normal"

    days_until = (action_date - datetime.now()).days

    if days_until <= 7:
        return "Critical"  # Red
    elif days_until <= 30:
        return "High"      # Amber
    else:
        return "Normal"    # Green

def group_by_urgency(
    major_updates: List[Email],
    extracted_fields: Dict[str, dict]
) -> Dict[str, List[dict]]:
    """Group updates by urgency tier, sort by deadline within tier."""
    tiers = {"Critical": [], "High": [], "Normal": []}

    for email in major_updates:
        mc_id = extracted_fields[email.id]["mc_id"]
        action_date = extracted_fields[email.id]["action_date"]
        urgency = calculate_urgency(action_date)

        tiers[urgency].append({
            "email": email,
            "mc_id": mc_id,
            "action_date": action_date,
            "urgency": urgency
        })

    # Sort within each tier by deadline (soonest first)
    for tier in tiers.values():
        tier.sort(key=lambda x: x["action_date"] or datetime.max)

    return tiers
```

### Pattern 4: Deduplication by MC ID
**What:** Keep only the latest version when duplicate MC IDs exist
**When to use:** Before formatting digest to handle updated Message Center posts
**Example:**
```python
from typing import List, Dict
from datetime import datetime

def deduplicate_by_mc_id(
    major_updates: List[Email],
    extracted_fields: Dict[str, dict]
) -> List[Email]:
    """Keep only the latest version of each MC ID."""
    mc_id_to_email: Dict[str, Email] = {}

    for email in major_updates:
        mc_id = extracted_fields[email.id].get("mc_id")
        if not mc_id:
            continue  # Skip emails without valid MC ID

        # Keep email with latest received_datetime
        if mc_id not in mc_id_to_email or \
           email.received_datetime > mc_id_to_email[mc_id].received_datetime:
            mc_id_to_email[mc_id] = email

    # Mark duplicates with "Updated" badge in extracted_fields
    for email in major_updates:
        mc_id = extracted_fields[email.id].get("mc_id")
        if mc_id and mc_id_to_email[mc_id] != email:
            extracted_fields[email.id]["is_updated"] = True

    return list(mc_id_to_email.values())
```

### Anti-Patterns to Avoid
- **External CSS files:** Email clients strip <link> tags and <style> blocks inconsistently
- **Flexbox/Grid layouts:** Only Apple Mail supports these, use tables instead
- **BeautifulSoup for simple extraction:** Adds dependency when regex + stdlib work fine
- **Hard-coded date thresholds:** Make urgency thresholds configurable for future adjustment
- **Duplicating HTML structure:** Reuse summarizer.py's proven color palette and layout patterns

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML entity decoding | Manual replace() chains | html.unescape (stdlib) | Handles 250+ entities correctly, already imported |
| Email date parsing | Custom date parser | datetime.strptime() or email.utils.parsedate_to_datetime() | RFC 5322 compliant, handles timezones |
| CSS inlining | Custom CSS parser | Manual inline styles in f-strings | Email clients require inline anyway, no parser needed |
| Deduplication | Manual loop tracking | Dict with MC ID as key | Python dicts preserve insertion order (3.7+), O(1) lookup |
| Urgency calculation | Complex if-else chains | Simple days_until thresholds | User decides thresholds, keep logic straightforward |

**Key insight:** Python's standard library + existing codebase patterns solve 100% of this phase's technical needs. Adding dependencies (BeautifulSoup, Jinja2, premailer) would increase complexity without meaningful benefit for this specific use case.

## Common Pitfalls

### Pitfall 1: Over-relying on HTML parsing
**What goes wrong:** Adding BeautifulSoup4 to parse email body_content when regex is sufficient
**Why it happens:** Assumption that HTML parsing requires specialized libraries
**How to avoid:** Use regex for structured field extraction since body_content is already text-stripped by ews_client.py (line 177)
**Warning signs:** Considering BeautifulSoup import when existing Email.body_content is plain text

### Pitfall 2: Email client CSS incompatibility
**What goes wrong:** Using modern CSS (flexbox, grid, external stylesheets) that breaks in Outlook/Gmail
**Why it happens:** Assuming email clients support standard web CSS
**How to avoid:** Use table-based layout with inline CSS only, test with https://www.caniemail.com/
**Warning signs:** CSS in <style> blocks, position/float properties, any external CSS files

### Pitfall 3: Inadequate color contrast for accessibility
**What goes wrong:** Using colors that fail WCAG contrast ratios (4.5:1 for text)
**Why it happens:** Choosing visually appealing colors without checking accessibility
**How to avoid:** Use existing color palette from summarizer.py (already WCAG compliant), test with WebAIM Contrast Checker
**Warning signs:** Custom color choices without contrast validation, relying solely on color to convey urgency

### Pitfall 4: Missing MC ID edge cases
**What goes wrong:** Regex fails on MC IDs with different formats (MC01-01, MC1234567890)
**Why it happens:** Assuming consistent MC ID format without checking actual emails
**How to avoid:** Use flexible pattern `\bMC(\d{5,7})\b` to match 5-7 digits as per classifier.py line 38
**Warning signs:** Regex pattern that's too strict (exact digit count) or too loose (matches MC1)

### Pitfall 5: Date parsing ambiguity
**What goes wrong:** Parsing "03/04/2026" differently based on locale (MM/DD vs DD/MM)
**Why it happens:** Not accounting for international date formats
**How to avoid:** Document assumed format (US: MM/DD/YYYY), use explicit strptime format string, log parsing failures
**Warning signs:** Using auto-detect date parsing without format specification

### Pitfall 6: Deduplication losing important data
**What goes wrong:** Deduplicating by MC ID but discarding is_updated information
**Why it happens:** Simple dict[mc_id] = email overwrites without tracking history
**How to avoid:** Track whether email is an update (compare received_datetime), add "Updated" badge in UI
**Warning signs:** Silent overwrites in deduplication logic, no tracking of update status

## Code Examples

Verified patterns from official sources:

### HTML Email Table Layout (600px width, inline CSS)
```python
# Source: https://designmodo.com/html-css-emails/ (2026 best practices)
# Pattern used in existing summarizer.py lines 186-227

html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f8f9fa;
             font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
           style="background-color: #f8f9fa;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0"
                       style="background-color: #ffffff; border-radius: 12px;
                              box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <!-- Content here -->
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
```

### Left-Border Accent for Urgency (Traffic Light Colors)
```python
# Source: Existing summarizer.py line 251 (urgent items pattern)
# Adapted for urgency tiers with traffic light colors

urgency_colors = {
    "Critical": "#ea4335",  # Red (danger)
    "High": "#fbbc04",      # Amber (warning)
    "Normal": "#34a853"     # Green (success)
}

# For each major update card
border_color = urgency_colors[urgency_tier]
html += f"""
<div style="background-color: #f8f9fa; border-left: 4px solid {border_color};
            padding: 16px; border-radius: 0 8px 8px 0; margin-bottom: 12px;">
    <p style="margin: 0 0 8px 0; color: {border_color}; font-size: 12px;
              font-weight: 600; text-transform: uppercase;">
        {urgency_tier}
    </p>
    <!-- MC ID, dates, services, category here -->
</div>
"""
```

### Regex Field Extraction
```python
# Source: https://docs.python.org/3/library/re.html (Python 3.14.3)
# Similar to classifier.py line 38 (MC_NUMBER_PATTERN)

import re
from typing import Optional

# Compile once for performance
MC_ID_PATTERN = re.compile(r'\bMC(\d{5,7})\b', re.IGNORECASE)
DATE_PATTERN = re.compile(
    r'(?:action required by|deadline:|by)\s*(\d{1,2}/\d{1,2}/\d{4})',
    re.IGNORECASE
)

def extract_mc_id(text: str) -> Optional[str]:
    """Extract MC ID from text."""
    match = MC_ID_PATTERN.search(text)
    return f"MC{match.group(1)}" if match else None

def extract_deadline(text: str) -> Optional[datetime]:
    """Extract action-required date."""
    match = DATE_PATTERN.search(text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%m/%d/%Y")
        except ValueError:
            return None
    return None
```

### Stats Header with Urgency Counts
```python
# Source: Existing summarizer.py lines 211-226 (stats bar pattern)
# Adapted for urgency tier counts

stats_html = f"""
<tr>
    <td style="padding: 24px 40px; border-bottom: 1px solid #e8eaed;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
            <tr>
                <td width="50%">
                    <p style="margin: 0; color: #80868b; font-size: 12px;
                              text-transform: uppercase; letter-spacing: 0.5px;">
                        Major Updates
                    </p>
                    <p style="margin: 4px 0 0 0; color: #202124; font-size: 14px;
                              font-weight: 500;">
                        {critical_count} Critical, {high_count} High, {normal_count} Normal
                    </p>
                </td>
                <td width="50%" align="right">
                    <p style="margin: 0; color: #80868b; font-size: 12px;
                              text-transform: uppercase; letter-spacing: 0.5px;">
                        Total Updates
                    </p>
                    <p style="margin: 4px 0 0 0; color: #1a73e8; font-size: 28px;
                              font-weight: 700;">
                        {total_count}
                    </p>
                </td>
            </tr>
        </table>
    </td>
</tr>
"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CSS classes with external stylesheet | Inline CSS only | Always (email client requirement) | 100% rendering compatibility across clients |
| Div-based layout | Table-based layout | Always (email client requirement) | Reliable layout in Outlook, Gmail, Apple Mail |
| BeautifulSoup for all HTML | Regex for structured extraction | This project | Zero extra dependencies for simple field extraction |
| Jinja2 templates | f-string templates | This project | Simpler, native Python, faster for this use case |
| Generic color palette | Traffic light colors for urgency | Phase 3 decision | Universally understood urgency indicators |

**Deprecated/outdated:**
- External CSS via <link> tags: Never worked reliably in email clients
- CSS Grid/Flexbox for email: Only Apple Mail supports, Outlook/Gmail break
- Auto-detect date parsing: Too many locale issues, explicit format is safer
- Python 2-style string formatting (%s): f-strings are standard in Python 3.10+

## Open Questions

Things that couldn't be fully resolved:

1. **Exact urgency tier thresholds**
   - What we know: User wants Critical/High/Normal tiers based on deadline proximity
   - What's unclear: Exact day cutoffs (7/30? 14/60? 3/7/30?)
   - Recommendation: Start with 7-day Critical, 30-day High per context decision, make configurable

2. **Body text depth per update**
   - What we know: Each update displays MC ID, dates, services, category
   - What's unclear: Full body preview vs summary sentence vs omit body entirely
   - Recommendation: Start with 200-character preview (similar to regular digest), adjust based on user feedback

3. **Zero major updates email behavior**
   - What we know: Context says "likely skip to reduce noise"
   - What's unclear: Skip always, or send "No major updates" email like regular digest?
   - Recommendation: Skip email when zero major updates (log instead), consistent with context decision

4. **High volume display strategy (20+ updates)**
   - What we know: Grouping by urgency tier with section headers
   - What's unclear: Collapse tiers? Summary-only view? Pagination?
   - Recommendation: Display all with clear tier grouping, no collapse (admins need to see everything)

5. **Missing field handling per field**
   - What we know: Some emails may lack action date, services, or categories
   - What's unclear: Show "N/A" placeholder, omit field, or default to Normal urgency?
   - Recommendation: No action date → Normal urgency, missing services → "Not specified", missing category → extract from body_content keywords

## Sources

### Primary (HIGH confidence)
- Python datetime documentation (https://docs.python.org/3/library/datetime.html) - Date parsing and formatting
- Python re documentation (https://docs.python.org/3/library/re.html) - Regex patterns
- Python email.utils documentation (https://docs.python.org/3/library/email.utils.html) - RFC 5322 date parsing
- Existing codebase (src/summarizer.py, src/ews_client.py, src/classifier.py) - Proven HTML patterns and Email dataclass
- Microsoft 365 Message Center docs (https://learn.microsoft.com/en-us/microsoft-365/admin/manage/message-center) - MC ID format, structure

### Secondary (MEDIUM confidence)
- HTML Email Best Practices 2026 (https://www.textmagic.com/blog/html-email-best-practices/) - Inline CSS, table layout
- Designing High-Performance Email Layouts 2026 (https://medium.com/@romualdo.bugai/designing-high-performance-email-layouts-in-2026-a-practical-guide-from-the-trenches-a3e7e4535692) - 600px width, fluid tables
- Can I Email border-radius (https://www.caniemail.com/features/css-border-radius/) - 91% support, mixed in Outlook
- WebAIM Contrast Checker (https://webaim.org/resources/contrastchecker/) - WCAG 2.1 contrast ratios
- Email Design Trends 2026 (https://www.brevo.com/blog/email-design-best-practices/) - Urgency indicators, responsive design

### Tertiary (LOW confidence)
- BeautifulSoup4 documentation (https://www.crummy.com/software/BeautifulSoup/bs4/doc/) - HTML parsing (not needed for this phase)
- Traffic light color psychology (https://www.jasminedirectory.com/blog/the-psychology-of-color-in-2026-digital-advertising/) - Red/amber/green urgency perception

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All stdlib + existing exchangelib, proven in codebase
- Architecture: HIGH - Reusing proven summarizer.py patterns, clear extension points
- Pitfalls: HIGH - Email client compatibility is well-documented 2026 constraint

**Research date:** 2026-02-24
**Valid until:** 2026-09-24 (6 months - email client standards stable, Python 3.10+ patterns mature)
