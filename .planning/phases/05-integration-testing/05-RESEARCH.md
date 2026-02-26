# Phase 5: Integration Testing - Research

**Researched:** 2026-02-26
**Domain:** Integration testing for dual-digest email system with state management
**Confidence:** HIGH

## Summary

Integration testing for a dual-digest email system requires validating end-to-end workflows across multiple consecutive runs, focusing on state transition correctness, failure isolation, and edge case handling. The phase validates Phases 1-4 implementation without adding new features.

**Key research areas:**
1. **Test fixture management** for .eml file handling, sanitization, and realistic test data
2. **State transition testing** patterns for simulating consecutive hourly runs
3. **Failure isolation patterns** ensuring one digest type failure doesn't crash the other
4. **Dry-run HTML preview** functionality with browser auto-open capability
5. **State corruption recovery** strategies for production resilience

**Primary recommendation:** Use pytest parametrize for multi-scenario simulation, fixture-based .eml file management with PII sanitization, and transaction-like state testing patterns with explicit rollback scenarios for corruption handling.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0+ | Testing framework | De facto Python testing standard in 2026, replacing unittest |
| pytest-mock | 3.14+ | Mocking support | Cleaner mocking interface than unittest.mock directly |
| pytest-cov | 6.0+ | Coverage reporting | Standard coverage integration for pytest |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-html | 4.1+ | HTML test reports | When test report visualization needed (optional for this phase) |
| pytest-xdist | 3.6+ | Parallel test execution | When test suite grows beyond 100+ tests (optional for now) |
| webbrowser | stdlib | Browser auto-open | Opening HTML previews in default browser |
| pathlib | stdlib | File path handling | Cross-platform file operations |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | pytest has simpler syntax, better fixtures, extensive plugins - no reason to use unittest for new tests |
| pytest-mock | unittest.mock directly | pytest-mock provides cleaner interface via mocker fixture |

**Installation:**
```bash
# Already installed in project
pytest>=9.0
pytest-mock>=3.14
pytest-cov>=6.0
```

## Architecture Patterns

### Recommended Project Structure
```
tests/
├── fixtures/           # .eml test files
│   ├── real/          # Sanitized real samples (gitignored before sanitization complete)
│   ├── synthetic/     # Hand-crafted edge cases
│   └── README.md      # Sanitization checklist
├── test_integration_*.py  # New integration tests for Phase 5
├── conftest.py        # Shared fixtures (already exists)
└── __init__.py

output/                 # Dry-run HTML outputs (gitignored)
├── regular_digest.html
└── major_digest.html
```

### Pattern 1: Multi-Run State Simulation

**What:** Simulate consecutive hourly runs by managing state file snapshots and email fixture sequences.

**When to use:** Testing state transitions across multiple runs (empty inbox → regular emails → mixed → major only).

**Example:**
```python
# Source: pytest fixture patterns - https://docs.pytest.org/en/stable/how-to/fixtures.html
import pytest
from pathlib import Path
import shutil

@pytest.fixture
def state_manager(tmp_path):
    """Fixture: Isolated state manager with temporary state file."""
    from src.state import StateManager

    state_file = tmp_path / "test_state.json"
    manager = StateManager(state_file=state_file)

    yield manager

    # Cleanup after test
    if state_file.exists():
        state_file.unlink()

def test_multi_run_sequence(state_manager, emails_run1, emails_run2):
    """Simulate 2 consecutive hourly runs with state persistence."""
    # Run 1: Process initial emails
    state_manager.set_last_run("regular", "2026-02-26T10:00:00Z")

    # Run 2: Process new emails (state should persist from run 1)
    last_run = state_manager.get_last_run("regular")
    assert last_run == "2026-02-26T10:00:00Z"

    state_manager.set_last_run("regular", "2026-02-26T11:00:00Z")
```

### Pattern 2: Parametrized Test Scenarios

**What:** Use pytest.mark.parametrize to test multiple consecutive run sequences efficiently.

**When to use:** Testing different sequences (empty→regular, regular→mixed, mixed→major, etc.).

**Example:**
```python
# Source: pytest parametrization - https://docs.pytest.org/en/stable/how-to/parametrize.html
import pytest

@pytest.mark.parametrize("scenario,runs,expected_state", [
    ("empty_to_regular", [
        {"emails": [], "digest_type": "regular"},
        {"emails": ["regular1.eml"], "digest_type": "regular"}
    ], {"regular_last_run": "2026-02-26T11:00:00Z"}),

    ("regular_to_mixed", [
        {"emails": ["regular1.eml"], "digest_type": "regular"},
        {"emails": ["regular2.eml", "major1.eml"], "digest_type": "both"}
    ], {"regular_last_run": "2026-02-26T11:00:00Z", "major_last_run": "2026-02-26T11:00:00Z"}),

    ("mixed_to_major_only", [
        {"emails": ["regular1.eml", "major1.eml"], "digest_type": "both"},
        {"emails": ["major2.eml"], "digest_type": "major"}
    ], {"major_last_run": "2026-02-26T12:00:00Z"}),
])
def test_state_transitions(scenario, runs, expected_state, state_manager):
    """Test state transitions across consecutive runs."""
    for run_idx, run_config in enumerate(runs):
        # Process emails for this run
        timestamp = f"2026-02-26T{10+run_idx}:00:00Z"

        # Verify state after each run
        # ... assertions ...
```

### Pattern 3: Fixture-Based .eml File Management

**What:** Load real and synthetic .eml files through pytest fixtures with proper sanitization.

**When to use:** Testing with realistic email data without hardcoding in test files.

**Example:**
```python
# Source: pytest fixture patterns
@pytest.fixture
def eml_loader(tmp_path):
    """Fixture: Load .eml files from fixtures directory."""
    def load_eml(filename: str):
        from email import message_from_file

        fixture_path = Path(__file__).parent / "fixtures" / filename
        with open(fixture_path, "r", encoding="utf-8") as f:
            return message_from_file(f)

    return load_eml

def test_real_message_center_email(eml_loader):
    """Test classification with real sanitized Message Center email."""
    msg = eml_loader("real/mc_major_update_sanitized.eml")

    # Parse to Email object
    email = parse_email_from_message(msg)

    # Test classification
    assert email.is_major_update is True
```

### Pattern 4: State Corruption and Recovery

**What:** Test state file corruption scenarios and recovery strategies using controlled corruption.

**When to use:** Validating resilience to malformed state files (user's top concern).

**Example:**
```python
# Source: pytest error handling patterns
def test_corrupted_state_recovery(state_manager, tmp_path):
    """Test recovery from corrupted state file."""
    # Set up valid state
    state_manager.set_last_run("regular", "2026-02-26T10:00:00Z")

    # Corrupt the state file
    state_file = tmp_path / "test_state.json"
    with open(state_file, "w") as f:
        f.write("{ invalid json")

    # Recovery strategy: Reset corrupted digest type, preserve valid ones
    state_manager.load_state()  # Should handle corruption

    # Verify recovery behavior (depends on chosen strategy)
    # Option 1: Reset all state
    # Option 2: Reset only corrupted digest type
    # Option 3: Skip corrupted digest, preserve valid state
```

### Pattern 5: Dry-Run HTML Preview with Browser Open

**What:** Save HTML digests to output/ folder and auto-open in default browser for visual validation.

**When to use:** Manual validation before production deployment.

**Example:**
```python
# Source: Python webbrowser module - https://docs.python.org/3/library/webbrowser.html
import webbrowser
from pathlib import Path

def save_and_open_digest(html_content: str, digest_type: str, output_dir: Path):
    """Save HTML digest and open in browser."""
    output_dir.mkdir(parents=True, exist_ok=True)

    file_path = output_dir / f"{digest_type}_digest.html"

    # Save HTML
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Digest saved: {file_path.absolute()}")

    # Auto-open in default browser
    # Note: file:// URLs don't work reliably, use absolute path
    file_url = f"file:///{file_path.absolute().as_posix()}"

    try:
        webbrowser.open_new_tab(file_url)
        print(f"Opened in browser: {file_url}")
    except Exception as e:
        print(f"Could not auto-open browser: {e}")
        print(f"Please manually open: {file_path}")
```

### Pattern 6: Failure Isolation Testing

**What:** Test that failure in one digest type doesn't prevent the other from succeeding.

**When to use:** Validating resilience and independence between regular and major digests.

**Example:**
```python
# Source: pytest isolation patterns
def test_major_digest_failure_does_not_prevent_regular(mocker, emails_mixed):
    """Test that major digest failure is isolated from regular digest."""
    # Arrange: Mock major digest to raise exception
    mocker.patch(
        'src.summarizer.MajorUpdateSummarizer.generate_digest',
        side_effect=Exception("AI service timeout")
    )

    # Act: Run digest generation
    regular_result, major_result = generate_both_digests(emails_mixed)

    # Assert: Regular succeeded, major failed gracefully
    assert regular_result.success is True
    assert major_result.success is False
    assert major_result.error == "AI service timeout"

    # Assert: Regular digest state was updated
    assert state_manager.get_last_run("regular") is not None

    # Assert: Major digest state was NOT updated (failure)
    assert state_manager.get_last_run("major") is None
```

### Anti-Patterns to Avoid

- **Hardcoding timestamps in tests**: Use relative time (datetime.now(), timedelta) or parametrize timestamps to avoid flaky tests due to date-based assertions
- **Testing implementation details**: Test observable behavior (state file contents, email counts), not internal method calls
- **Shared state across tests**: Use tmp_path fixture for isolated state files, never use a shared state file
- **Not testing edge cases**: Empty inbox, all duplicates, corrupted state, missing config - these are production failure scenarios
- **Ignoring fixture sanitization**: Committing real email data with PII is a security incident

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test data factories | Custom Email builder classes | pytest fixtures with parametrize | Fixtures provide setup/teardown, parametrize handles variations, no need for custom factory |
| Test isolation | Manual state cleanup in each test | pytest tmp_path fixture + fixture scope | tmp_path provides isolated temp directories, fixture scope controls lifetime |
| Email parsing from .eml | Custom .eml parser | Python email.message_from_file | email module handles all RFC 5322 edge cases, MIME parts, encodings |
| PII sanitization | Regex find-replace | Use structured approach (entity recognition, consistent replacement) | Regex misses variations, entity recognition catches emails/names/URLs reliably |
| State corruption scenarios | Random bytes in file | Controlled corruption (truncation, invalid JSON, wrong schema) | Random corruption is non-deterministic, controlled scenarios are reproducible |

**Key insight:** pytest ecosystem has mature solutions for test isolation, parametrization, and fixture management. Leverage these rather than building custom test infrastructure.

## Common Pitfalls

### Pitfall 1: Test Pollution via Shared State

**What goes wrong:** Tests pass individually but fail when run together because state file persists across tests.

**Why it happens:** State manager reads/writes to same file, previous test's state affects next test.

**How to avoid:**
- Use pytest tmp_path fixture for isolated state files per test
- Never use project's actual state file in tests
- Fixture scope: function (default) for isolation, module/session only for expensive setup

**Warning signs:**
- Tests pass with `pytest test_specific.py::test_name` but fail in full suite
- Tests fail with `pytest --lf` (last failed) but pass when re-run alone
- State file contents from previous test visible in current test

**Example prevention:**
```python
# Source: pytest best practices - https://docs.pytest.org/en/stable/explanation/goodpractices.html
@pytest.fixture
def isolated_state(tmp_path):
    """Each test gets its own state file in isolated temp directory."""
    state_file = tmp_path / "state.json"
    manager = StateManager(state_file=state_file)
    return manager
    # tmp_path automatically cleaned up after test
```

### Pitfall 2: Flaky Tests from Hardcoded Timestamps

**What goes wrong:** Tests fail intermittently or on different machines because assertions depend on current date/time.

**Why it happens:** Hardcoded timestamps like "2026-02-26" fail when test runs on different date.

**How to avoid:**
- Use datetime.now() with timezone awareness
- Use relative time (timedelta) for comparisons
- Parametrize tests with multiple date scenarios
- Use freezegun or time-machine libraries for time control

**Warning signs:**
- Tests pass locally but fail in CI
- Tests pass today but fail tomorrow
- Tests fail in different timezones

**Example prevention:**
```python
from datetime import datetime, timezone, timedelta

def test_urgency_calculation():
    """Test urgency without hardcoded dates."""
    now = datetime.now(timezone.utc)

    # Critical: 7 days or less
    critical_date = now + timedelta(days=5)
    assert calculate_urgency(critical_date) == "Critical"

    # High: 8-30 days
    high_date = now + timedelta(days=15)
    assert calculate_urgency(high_date) == "High"
```

### Pitfall 3: Incomplete .eml Sanitization

**What goes wrong:** Real email samples committed with PII (names, emails, tenant IDs, internal URLs).

**Why it happens:** Manual sanitization misses variations (display names vs email addresses, URLs in body).

**How to avoid:**
- **Checklist-based sanitization** before committing any .eml file
- Replace tenant ID (GUID patterns)
- Replace email addresses (both sender and body mentions)
- Replace display names consistently
- Replace internal URLs/domains
- Verify with grep before commit: `grep -E "[a-z]+@mmc\.com" fixtures/`

**Warning signs:**
- Real company name in fixtures
- Real employee names
- Internal domain references
- Tenant GUID visible

**Sanitization checklist:**
```markdown
## .eml Sanitization Checklist

- [ ] Replace From: email (user@mmc.com → user@company.com)
- [ ] Replace From: display name (John Doe → Test User)
- [ ] Replace tenant GUID in message IDs
- [ ] Replace internal domains in URLs (mmc.com → company.com)
- [ ] Replace email mentions in body text
- [ ] Replace names in body text (consistent fake names)
- [ ] Replace meeting links/domains
- [ ] Verify no real data with: grep -E "mmc\.com|actual-name" file.eml
```

### Pitfall 4: State Corruption Not Isolated Between Digest Types

**What goes wrong:** Corruption in major digest state prevents regular digest from running.

**Why it happens:** State recovery logic resets entire state file instead of isolated digest type.

**How to avoid:**
- **Per-digest-type corruption handling**: Catch corruption, reset only affected digest type
- Validate state schema for each digest type independently
- Preserve valid digest state when recovering from corruption
- Log corruption events for monitoring

**Warning signs:**
- Both digests fail when only one state field is corrupted
- State reset affects unrelated digest type
- No distinction between "all state corrupt" vs "one type corrupt"

**Example prevention:**
```python
def load_state(self):
    """Load state with per-digest-type corruption handling."""
    try:
        with open(self.state_file) as f:
            state = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        # Entire file corrupt or missing - reset all
        return self._reset_all_state()

    # Validate per digest type
    for digest_type in ["regular", "major"]:
        try:
            last_run = state.get(f"{digest_type}_last_run")
            # Validate format
            if last_run and not self._is_valid_timestamp(last_run):
                # Corrupt field - reset this type only
                state[f"{digest_type}_last_run"] = None
                self._log_corruption(digest_type)
        except Exception as e:
            # Reset this type only
            state[f"{digest_type}_last_run"] = None
            self._log_corruption(digest_type, error=str(e))

    return state
```

### Pitfall 5: Not Testing Empty/Edge Cases

**What goes wrong:** Production fails with empty inbox, all duplicates, or no major updates when tests only cover happy path.

**Why it happens:** Focus on normal flow, skip edge cases that seem "obvious".

**How to avoid:**
- **Test matrix**: empty inbox, single email, all duplicates, all major, all regular
- Test MAJOR_UPDATE_TO empty (feature disabled)
- Test state file missing, empty, corrupted
- Test AI service timeout/failure

**Warning signs:**
- Production fails with "unexpected empty list"
- Division by zero in summary statistics
- Digest not generated when inbox empty

**Example coverage:**
```python
@pytest.mark.parametrize("inbox_state", [
    pytest.param([], id="empty_inbox"),
    pytest.param([regular_email], id="single_regular"),
    pytest.param([major_email], id="single_major"),
    pytest.param([duplicate1, duplicate2], id="all_duplicates"),
    pytest.param([regular1, regular2, regular3], id="all_regular_no_major"),
    pytest.param([major1, major2, major3], id="all_major_no_regular"),
])
def test_digest_generation_edge_cases(inbox_state):
    """Test digest generation handles all edge cases."""
    result = generate_digests(inbox_state)

    # Should never crash, even with empty inbox
    assert result is not None
```

## Code Examples

Verified patterns from official sources:

### Multi-Run State Transition Test

```python
# Source: pytest parametrize - https://docs.pytest.org/en/stable/how-to/parametrize.html
import pytest
from datetime import datetime, timezone, timedelta

@pytest.fixture
def consecutive_runs():
    """Fixture: Simulates 3 consecutive hourly runs."""
    base_time = datetime.now(timezone.utc)

    return [
        {
            "timestamp": base_time,
            "emails": [],  # Run 1: Empty inbox
            "expected_state": {
                "regular_last_run": base_time.isoformat(),
                "major_last_run": None  # Feature not triggered
            }
        },
        {
            "timestamp": base_time + timedelta(hours=1),
            "emails": ["regular1.eml", "regular2.eml"],  # Run 2: Regular only
            "expected_state": {
                "regular_last_run": (base_time + timedelta(hours=1)).isoformat(),
                "major_last_run": None
            }
        },
        {
            "timestamp": base_time + timedelta(hours=2),
            "emails": ["regular3.eml", "major1.eml"],  # Run 3: Mixed
            "expected_state": {
                "regular_last_run": (base_time + timedelta(hours=2)).isoformat(),
                "major_last_run": (base_time + timedelta(hours=2)).isoformat()
            }
        }
    ]

def test_state_persistence_across_runs(consecutive_runs, state_manager):
    """Test state persists correctly across 3 consecutive hourly runs."""
    for run_idx, run_data in enumerate(consecutive_runs):
        # Simulate processing emails for this run
        process_emails(run_data["emails"], run_data["timestamp"])

        # Verify state after run
        state = state_manager.load_state()

        assert state["regular_last_run"] == run_data["expected_state"]["regular_last_run"], \
            f"Run {run_idx+1}: Regular state mismatch"

        assert state["major_last_run"] == run_data["expected_state"]["major_last_run"], \
            f"Run {run_idx+1}: Major state mismatch"
```

### .eml File Fixture with Sanitization Check

```python
# Source: pytest fixtures + Python email module
import pytest
from pathlib import Path
from email import message_from_file

@pytest.fixture
def eml_fixtures_dir():
    """Fixture: Path to .eml fixtures directory."""
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def load_eml(eml_fixtures_dir):
    """Fixture: Load and parse .eml file."""
    def _load(category: str, filename: str):
        """Load .eml file from fixtures/category/filename."""
        file_path = eml_fixtures_dir / category / filename

        if not file_path.exists():
            pytest.skip(f"Fixture not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            return message_from_file(f)

    return _load

def test_real_message_center_classification(load_eml):
    """Test classification with real sanitized Message Center email."""
    # Load sanitized real sample
    msg = load_eml("real", "mc_major_update_sanitized.eml")

    # Verify sanitization (spot check)
    assert "mmc.com" not in msg.as_string(), "Real domain not sanitized"
    assert "@company.com" in msg["From"], "Email not sanitized"

    # Parse to Email object
    email = parse_message_to_email(msg)

    # Test classification
    classifier = EmailClassifier()
    result = classifier.classify(email)

    assert result.is_major_update is True
    assert result.confidence_score >= 70
```

### State Corruption Recovery Test

```python
# Source: pytest error handling patterns
import json
import pytest

def test_corrupted_state_reset_preserves_valid_digest(state_manager, tmp_path):
    """Test that corrupting major state doesn't reset valid regular state."""
    # Set up valid state for both digest types
    state_manager.set_last_run("regular", "2026-02-26T10:00:00Z")
    state_manager.set_last_run("major", "2026-02-26T10:00:00Z")

    # Manually corrupt major digest state field
    state_file = state_manager.state_file
    with open(state_file, "r") as f:
        state = json.load(f)

    # Corrupt major_last_run (invalid timestamp format)
    state["major_last_run"] = "invalid-timestamp"

    with open(state_file, "w") as f:
        json.dump(state, f)

    # Reload state - should recover from corruption
    recovered_state = state_manager.load_state()

    # Assert: Regular state preserved (not corrupted)
    assert recovered_state["regular_last_run"] == "2026-02-26T10:00:00Z", \
        "Valid regular state should be preserved"

    # Assert: Major state reset (was corrupted)
    assert recovered_state["major_last_run"] is None, \
        "Corrupted major state should be reset"
```

### Dry-Run with HTML Preview

```python
# Source: Python webbrowser module - https://docs.python.org/3/library/webbrowser.html
import webbrowser
from pathlib import Path

def save_digest_preview(html_content: str, digest_type: str, dry_run: bool = False):
    """Save digest HTML and optionally open in browser."""
    if not dry_run:
        # Production mode: send email
        return send_email(html_content)

    # Dry-run mode: Save to output/ and open in browser
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    file_name = f"{digest_type}_digest.html"
    file_path = output_dir / file_name

    # Save HTML
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    abs_path = file_path.absolute()
    print(f"✓ Digest saved: {abs_path}")

    # Auto-open in browser
    # Note: Convert to file:// URL with forward slashes
    file_url = f"file:///{abs_path.as_posix()}"

    try:
        # open_new_tab opens in new tab if browser already open
        webbrowser.open_new_tab(file_url)
        print(f"✓ Opened in browser: {file_url}")
    except Exception as e:
        print(f"⚠ Could not auto-open browser: {e}")
        print(f"  Please manually open: {abs_path}")

    return {"saved": True, "path": str(abs_path)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest framework | pytest | 2020s | Simpler syntax, better fixtures, extensive plugin ecosystem |
| Manual mock setup | pytest-mock mocker fixture | 2018+ | Cleaner interface, automatic cleanup |
| Manual test data files | pytest parametrize with fixtures | 2019+ | DRY principle, better coverage |
| Manual sanitization | Structured entity recognition | 2025+ | Consistent, automated PII removal |
| Test randomization off by default | pytest-randomly enabled | 2023+ | Catches test pollution earlier |

**Deprecated/outdated:**
- unittest.TestCase classes: pytest supports plain functions with fixtures (simpler)
- nose testing framework: Unmaintained since 2015, use pytest
- Hardcoded test data: Use parametrize and fixtures for better coverage and maintainability

## Open Questions

Things that couldn't be fully resolved:

1. **Minimum number of real .eml samples needed**
   - What we know: User will provide real samples, Claude decides minimum
   - What's unclear: Exact count depends on Message Center email variation
   - Recommendation: Start with 5-7 real samples covering common patterns (major update, minor update, action required, retirement, new feature), supplement with synthetic for edge cases (partial MC#, keywords-only, sender-only)

2. **Optimal state corruption recovery strategy**
   - What we know: Three options: (1) reset all state, (2) reset corrupted type only, (3) skip corrupted digest
   - What's unclear: Which provides best production experience
   - Recommendation: Option 2 (reset corrupted type only) - preserves valid state, prevents cascade failures, logs corruption for monitoring. User's discretion based on production risk tolerance.

3. **Fixture sanitization validation tooling**
   - What we know: Manual checklist prone to human error
   - What's unclear: Whether to build automated sanitization validation script
   - Recommendation: Create simple pytest marker `@pytest.mark.sanitized` that runs grep checks for common PII patterns (mmc.com, real names from config) - fails test if found

## Sources

### Primary (HIGH confidence)
- [pytest documentation - Good Integration Practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html) - Official pytest best practices
- [pytest documentation - How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) - Official parametrization guide
- [pytest documentation - How to use fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html) - Official fixture guide
- [Python webbrowser module](https://docs.python.org/3/library/webbrowser.html) - Official Python stdlib documentation

### Secondary (MEDIUM confidence)
- [Pytest Fixtures: The Complete Guide for 2026](https://devtoolbox.dedyn.io/blog/pytest-fixtures-complete-guide) - Modern fixture patterns (verified with official docs)
- [How to Sanitize Production Data for Use in Testing](https://securityboulevard.com/2026/02/how-to-sanitize-production-data-for-use-in-testing-2/) - PII sanitization approaches (2026)
- [End-to-End Python Integration Testing: A Complete Guide](https://www.testmu.ai/learning-hub/python-integration-testing/) - Integration testing patterns
- [Finding test isolation issues with PyTest](https://advancedpython.dev/articles/pytest-randomisation/) - Test isolation patterns

### Tertiary (LOW confidence)
- WebSearch results for state corruption patterns - Limited specific guidance, mostly anti-corruption policy results (not technical state management)
- Community discussions on .eml parsing - Various approaches, verified against official email module docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest 9.0 is current, well-documented, widely adopted
- Architecture: HIGH - Patterns verified against official pytest documentation and existing project structure
- Pitfalls: MEDIUM-HIGH - Based on pytest best practices and common testing anti-patterns, but specific to this project's state management

**Research date:** 2026-02-26
**Valid until:** ~60 days (pytest stable, patterns change slowly)

**Project-specific notes:**
- Project already uses pytest 9.0.2 with pytest-mock
- Existing conftest.py has good fixture patterns to extend
- 131 tests passing - integration tests will add to this suite
- State manager already exists (src/state.py) - focus on testing it, not building new state logic
