---
name: python-testing
description: Use when writing or reviewing Python tests. Enforces pytest patterns, AAA structure, coverage requirements, and integration test isolation for this project.
---

# Python Testing Conventions

This project uses pytest with strict TDD discipline. Coverage threshold: **80%** (currently 92%).

## When to Use

- Writing a new test
- Reviewing a test (own or peer's)
- Debugging a flaky or misleading test
- Setting up integration tests

## Test Structure (AAA Pattern)

```python
def test_something():
    # Arrange — set up test fixtures
    text = "想做开源项目"
    
    # Act — call the function under test
    intent = infer_intent(text)
    
    # Assert — verify behavior
    assert intent == "idea"
```

## Naming

Use descriptive names that explain the behavior under test:

```python
def test_infer_idea_chinese():           # Good: clear what's tested
def test_infer_priority_order():         # Good: explains the rule
def test_returns_idea_when_chinese_keyword_present():  # Verbose but clear

def test_intent():                       # BAD: too vague
def test_thing():                        # BAD: meaningless
```

## Coverage Requirements

- **Per-module**: each module should have ≥ 80% coverage
- **Overall**: project-wide ≥ 80%
- **Currently at 92%** — do not regress

```bash
# Run with coverage
pytest --cov=pulse_bot --cov-report=term-missing tests/

# HTML report (open in browser)
pytest --cov=pulse_bot --cov-report=html tests/
```

## Fixtures

### Built-in pytest fixtures used in this project

- `tmp_path` — fresh temp directory per test
- `monkeypatch` — patch functions/attributes safely
- `pytest.fixture` — define custom fixtures

### Custom fixture pattern (this repo)

```python
@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a tmp git repo with one commit."""
    repo = tmp_path / "vault"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    return repo
```

## Mocking Subprocess

Mock `subprocess.run` at the lowest level to ensure retry logic actually executes:

```python
def test_commit_and_push_retries_on_failure(tmp_git_repo, monkeypatch):
    sync = GitSync(repo_dir=tmp_git_repo, remote_name="origin", branch="master", retries=2)
    
    # Mock ONLY the push call (not add/commit)
    def fake_run(*args, **kwargs):
        class Result:
            returncode = 1
            stderr = "fatal: could not push"
            stdout = ""
        return Result()
    
    monkeypatch.setattr("subprocess.run", fake_run)
    new_file = tmp_git_repo / "idea3.md"
    new_file.write_text("idea 3")
    result = sync.commit_and_push(new_file, message="pulse: idea 3")
    assert result is False
```

## Common Pitfalls

### Test passes for wrong reason

```python
# BAD: passes even if push retry is broken (because add fails first)
def test_retry():
    sync.commit_and_push(file, "msg")
    # Never actually exercises retry logic

# GOOD: forces push to fail, asserts retry count
def test_retry(monkeypatch):
    monkeypatch.setattr("subprocess.run", fake_push_failure)
    result = sync.commit_and_push(file, "msg")
    assert result is False
```

### Time-dependent tests

```python
# BAD: depends on system clock
def test_now():
    when = datetime.now()  # Non-deterministic

# GOOD: inject time as parameter
def test_with_explicit_time():
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    result = render_card("text", user_id=1, intent="idea", when=when)
    assert "2026-07-09T20:23:45Z" in result
```

## Async Tests

This project uses pytest-asyncio for testing async handlers:

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_handle_message_creates_card():
    # ... use AsyncMock for Telegram update/context
    pass
```

## Commands

```bash
# Run all tests
pytest tests/

# Run specific file
pytest tests/test_card.py -v

# Run specific test
pytest tests/test_card.py::test_make_slug_basic_ascii -v

# With coverage
pytest --cov=pulse_bot --cov-report=term-missing tests/

# Stop on first failure
pytest -x tests/

# Show local variables on failure
pytest -l tests/
```

## Reference

- `pytest.ini` — pytest configuration
- `tests/` — existing test suite (40 tests)
- `pulse_bot/` — code under test
- `CLAUDE.md` §Testing — project testing rules