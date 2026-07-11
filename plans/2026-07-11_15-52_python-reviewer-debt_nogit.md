---
tags:
  - plan
  - refactor
  - python-quality
  - pulse-bot
created: 2026-07-11
updated: 2026-07-11
status: draft
source: "python-reviewer findings during 2026-07-11 bug-fix code review"
topic: "pulse-bot pre-existing python-quality debt"
---

# Plan: Address Pre-existing Python Quality Debt

## Background

During the 2026-07-11 bug-fix session, the `python-reviewer` agent flagged 7 pre-existing quality issues that are **not caused by** the current bug fixes but live in the same files. Per project rule "不要在 commit 里夹带无关改动", these were intentionally deferred from the bug-fix commits.

User confirmed on 2026-07-11 15:51 to handle these as a separate plan + commit.

## Scope

**In scope (7 findings)**:

| # | Severity | File | Issue | Fix |
|---|----------|------|-------|-----|
| 1 | HIGH | `tests/test_bot.py` (14 occurrences) | `__import__("pathlib").Path("/tmp")` hack repeated | Top-level `from pathlib import Path` + replace |
| 2 | HIGH | `tests/test_bot.py` | 6-key mock config dict copy-pasted 14× | Extract `mock_config` fixture using `tmp_path` |
| 3 | HIGH | `pulse_bot/bot.py:31` | `_is_authorized` missing type hint on `allowed_ids` | Add `list[int]` annotation |
| 4 | MEDIUM | `pulse_bot/bot.py:79, 132` | Magic numbers `50` and `40` unexplained | Add `COMMIT_SUBJECT_MAX = 50`, `RECENT_DISPLAY_MAX = 40` constants |
| 5 | MEDIUM | `pulse_bot/bot.py:23` | `_recent_cards: list[dict]` too loose | Define `RecentCard(TypedDict)` |
| 6 | MEDIUM | `tests/test_bot.py` (5 tests) | `_recent_cards.clear()` repeated; in-function imports | Top-level import + `recent_cards` fixture with teardown |
| 7 | LOW | `tests/test_bot.py:28-29` | `_make_context()` uses bare `MagicMock()` | Use `MagicMock(spec=ContextTypes.DEFAULT_TYPE)` |

**Out of scope** (deferred further):
- All other findings from `code-reviewer` and `python-reviewer` already handled in bug-fix commits.
- General test infrastructure overhaul (e.g., converting to `pytest-mock` instead of `unittest.mock`).

## Approach

Execute as **single refactor commit** with TDD discipline:

1. **Test-first for behavior changes**:
   - Findings 1, 2, 6, 7: pure test refactor; existing tests must still pass unchanged.
   - Findings 3, 4, 5: type-hint / constant changes; behavior unchanged, mypy/pyright will validate.
2. **One commit, but logically grouped** (project allows single-commit refactor for cohesive cleanup that does not introduce new behavior).
3. **Risk mitigation**: run full test suite + coverage after each sub-step.

## File-by-file change list

### `pulse_bot/bot.py`
- Line 23: replace `list[dict]` with `list[RecentCard]` (after TypedDict defined).
- Line 26-30: add type hint `allowed_ids: list[int]`.
- Line 79: replace `[:50]` with `[:COMMIT_SUBJECT_MAX]`.
- Add module-level constants block: `COMMIT_SUBJECT_MAX = 50`, `RECENT_DISPLAY_MAX = 40`.
- Line 132: replace `[:40]` with `[:RECENT_DISPLAY_MAX]`.

### `tests/test_bot.py`
- Top-level: `from pathlib import Path`, `from telegram.ext import ContextTypes`.
- Replace 14× `__import__("pathlib").Path("/tmp")` → `Path("/tmp")`.
- Add `mock_config(tmp_path)` fixture.
- Add `recent_cards` fixture (clears `_recent_cards` before yield, after return).
- Replace bare `MagicMock()` in `_make_context` → `MagicMock(spec=ContextTypes.DEFAULT_TYPE)`.
- Remove 5× in-function `from pulse_bot.bot import _recent_cards`; use fixture.
- Remove 5× end-of-test `_recent_cards.clear()` (fixture handles teardown).

## Test Strategy

- All 57 existing tests must continue to pass after refactor.
- Coverage must remain ≥ 80% (currently 93%).
- No new tests required (no behavior change).
- Run: `pytest --cov=pulse_bot --cov-report=term-missing tests/`.

## Rollback Plan

- Single commit → revert with `git revert <hash>`.
- All changes are mechanical (rename, add type, extract fixture) — no semantic shift.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Typo during 14× `__import__` → `Path` replacement | Low | Low | Diff review before commit |
| `mock_config` fixture misses a key used by a test | Medium | High | Compare fixture dict to all existing inline dicts before swap |
| `MagicMock(spec=...)` rejects attribute that bare `MagicMock` allowed | Low | Medium | Run tests immediately after spec change |
| `TypedDict` change breaks runtime attribute access | Low | Low | dict access pattern unchanged (still `card["text"]`) |
| Test fixture cleanup causes cross-test pollution | Medium | High | Verify `_recent_cards.clear()` fixture runs in correct order (yield → assert → teardown) |

## Validation Criteria

- [ ] All 57 tests pass
- [ ] Coverage ≥ 80%
- [ ] `mypy pulse_bot/bot.py` clean (if mypy available)
- [ ] `git diff --check` clean (whitespace)
- [ ] `git diff` shows only refactor; no logic changes

## Estimated Effort

~30 min for mechanical edits + test runs.

## Related

- Source review file: `plans/2026-07-11_15-24_code-review-results_nogit.md`
- Bug-fix commits (this session, separate): feat /recent N + drop /dashboard + reject extras + docs sync.