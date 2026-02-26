# Test Fixtures

This directory contains email fixtures for testing the dual-digest system.

## Directory Structure

- `synthetic/` - Synthetic .eml files created for testing (safe for git commit)
- `real/` - Real .eml files from production (MUST be sanitized before commit)

## Sanitization Checklist for Real .eml Files

Before committing any real .eml files to the repository, complete this checklist to remove sensitive information:

### 1. Email Addresses
- [ ] Replace all real email addresses with sanitized versions
  - Use `@company.com` for internal emails
  - Use `@email2.microsoft.com` for Microsoft emails
  - Replace user names with generic names (e.g., "Test User", "Admin User")

### 2. Display Names
- [ ] Replace real names with generic placeholders
  - "Test User" for internal senders
  - "Microsoft 365 Message Center" for MC emails
  - "Admin User" for admin emails

### 3. Tenant GUIDs and IDs
- [ ] Remove or replace tenant-specific GUIDs
- [ ] Replace Message-ID headers with generic IDs
- [ ] Replace Exchange item IDs with synthetic values
- [ ] Check for any Azure AD tenant IDs

### 4. Internal Domains
- [ ] Replace real domain names with `company.com`
- [ ] Remove any subdomain references that reveal infrastructure
- [ ] Check URLs in body content for internal domains

### 5. Body Text
- [ ] Remove real employee names
- [ ] Remove project/product code names
- [ ] Remove internal URLs and file paths
- [ ] Remove specific dates that could identify the organization
- [ ] Keep MC message IDs (MC1234567) as they're generic

### 6. Headers
- [ ] Remove or sanitize X-MS-Exchange headers with tenant info
- [ ] Remove authentication-related headers
- [ ] Keep standard headers (From, To, Subject, Date, MIME-Version, Content-Type)

## Verification Command

After sanitization, verify no sensitive information remains:

```bash
# Search for common sensitive patterns
grep -r "yourdomain" tests/fixtures/real/
grep -r "@yourcompany" tests/fixtures/real/
grep -r "tenant-guid-pattern" tests/fixtures/real/
grep -r "employeename" tests/fixtures/real/
```

If any matches are found, review and sanitize those files.

## Using Fixtures in Tests

### Loading .eml Files

Use the `load_eml` fixture from conftest.py:

```python
def test_example(load_eml):
    # Load from synthetic/
    message = load_eml("synthetic", "mc_major_update_action_required.eml")
    assert message["Subject"] == "MC1234567: Major update - Exchange Online auth policy changes"
```

### Creating Email Objects from .eml

Use the `mock_emails_from_eml` fixture:

```python
def test_example(load_eml, mock_emails_from_eml):
    msg1 = load_eml("synthetic", "mc_major_update_action_required.eml")
    msg2 = load_eml("synthetic", "regular_internal.eml")

    emails = mock_emails_from_eml([msg1, msg2])
    assert len(emails) == 2
    assert emails[0].sender_email == "o365mc@email2.microsoft.com"
```

## Available Synthetic Fixtures

1. **mc_major_update_action_required.eml** - Major update with deadline (04/15/2026)
   - Contains: MAJOR UPDATE, Action required, Admin impact
   - Services: Exchange Online, Teams
   - MC ID: MC1234567

2. **mc_major_update_retirement.eml** - Service retirement notice
   - Contains: RETIREMENT, Admin impact
   - Services: Exchange Online
   - MC ID: MC2345678
   - No specific deadline (Normal urgency)

3. **mc_major_update_new_feature.eml** - Major feature with word-format date
   - Contains: MAJOR UPDATE, Action required by March 30, 2026
   - Services: Teams
   - MC ID: MC3456789

4. **mc_minor_update.eml** - Message Center email without major signals
   - OneDrive storage update
   - NO major keywords (should classify as regular)
   - MC ID: MC4567890

5. **regular_internal.eml** - Regular business email
   - No Message Center patterns
   - Internal company communication
   - No MC ID

## Test Isolation

Always use the `isolated_state` fixture for tests that interact with StateManager:

```python
def test_example(isolated_state):
    # isolated_state provides a StateManager with tmp_path
    # No pollution of real .state.json
    isolated_state.set_last_run("regular")
    assert isolated_state.get_last_run("regular") is not None
```
