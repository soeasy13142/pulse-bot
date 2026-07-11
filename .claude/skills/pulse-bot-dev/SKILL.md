---
name: pulse-bot-dev
description: Use when modifying pulse-bot code, adding features, fixing bugs, or refactoring modules in this project. Enforces TDD workflow and project conventions.
---

# Pulse Bot Development Workflow

This skill enforces the project's development conventions. Invoke BEFORE making any non-trivial change.

## When to Use

- Adding a new feature to `pulse_bot/`
- Modifying existing modules (bot.py, card.py, etc.)
- Adding new tests
- Refactoring
- Fixing bugs

## Workflow

### 1. Read the relevant code first

Before changing anything, read:
- The target module in `pulse_bot/`
- The corresponding test file in `tests/`
- The relevant section in `CLAUDE.md`

### 2. TDD: Test First

```bash
# Write failing test
vim tests/test_<module>.py

# Confirm RED
pytest tests/test_<module>.py -v
# Should show failing tests for new behavior
```

### 3. Implement Minimum to Pass

```bash
vim pulse_bot/<module>.py

# Confirm GREEN
pytest tests/test_<module>.py -v
```

### 4. Refactor

While keeping tests green, improve:
- Naming
- Structure
- Error handling

### 5. Verify Coverage

```bash
pytest --cov=pulse_bot --cov-report=term-missing tests/
```

Coverage must remain ≥ 80% per module.

## Project Conventions

- **Type hints** required on all public functions
- **Immutable** operations preferred
- **No silent failures**: handle errors explicitly, log details server-side, return user-friendly messages client-side
- **Config via env** or YAML, never hardcode
- **One module per file**: if a file approaches 400 lines, split it

## File Layout Reference

```
pulse_bot/
├── bot.py           # Telegram listener (handle_message, recent_command, etc.)
├── card.py          # make_slug, build_card_path, render_card
├── config.py        # load_config (env + YAML)
├── git_sync.py      # GitSync class (commit_and_push with retry)
└── intent.py        # infer_intent (idea/task/question/reference)
```

## Commit Format

```
<type>(pulse-bot): <description>

<optional body explaining why>
```

Types: feat | fix | refactor | docs | test | chore | perf

Examples from this repo:
```
feat(pulse-bot): add make_slug with TDD
fix(pulse-bot): ensure vault_repo_dir is Path and accept str path arg
test(pulse-bot): add full test suite with integration test
```

## Testing Patterns

### Use tmp_path for filesystem

```python
def test_something(tmp_path):
    file = tmp_path / "test.md"
    file.write_text("# test")
    # ...
```

### Use monkeypatch for subprocess

```python
def test_push_failure(monkeypatch):
    def fake_run(*args, **kwargs):
        class Result:
            returncode = 1
            stderr = "fatal"
            stdout = ""
        return Result()
    monkeypatch.setattr("subprocess.run", fake_run)
    # ...
```

### Use tmp git repo for integration

```python
@pytest.fixture
def tmp_git_repo(tmp_path):
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

## Common Pitfalls

1. **Test passes for wrong reason**: Always ask "if the implementation were completely broken, would this test still pass?" If yes, rewrite the test.

2. **Mock at wrong boundary**: Mock `subprocess.run`, not the higher-level helper, to ensure retries actually execute.

3. **Hardcoded paths**: Use `Path(__file__).parent` or config — never `/opt/pulse-bot/vault` in tests.

4. **Forgetting timezone**: Telegram messages are UTC. Always use `datetime.now(timezone.utc)` for `when` parameter.

## Pre-Commit Checklist

- [ ] All tests pass (`pytest tests/`)
- [ ] Coverage ≥ 80%
- [ ] No new broken imports
- [ ] No hardcoded secrets
- [ ] Commit message follows `<type>(pulse-bot): <desc>` format
- [ ] No unrelated changes bundled

## Reference

- `CLAUDE.md` — Full project onboarding
- `plans/2026-07-09_22-30_pulse-system-design_nogit.md` — Design decisions
- `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` — Implementation history