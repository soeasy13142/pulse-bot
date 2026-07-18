# Error Handling + Dead Letter Queue Implementation Plan

> **For agentic workers:** TDD required. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix 3 issues: (1) `/promote` still shown in help text, (2) `handle_message` lacks try/except around file/git ops, (3) failed push after retries has no dead letter queue.

**Architecture:**
- Delete `/promote` line from help text (following same pattern as `/dashboard` removal in a73dbdb)
- Wrap `handle_message` file write + git commit/push in try/except with user-facing error messages
- New `pulse_bot/dead_letter.py` module — JSONL-based persistent retry queue
- Integrate dead letter into bot.py: enqueue on push failure, flush on startup + before each new card

**Files touched:**
- Modify: `pulse_bot/bot.py` — help text, error handling, dead letter integration
- Create: `pulse_bot/dead_letter.py` — new module
- Create: `tests/test_dead_letter.py` — full test suite
- Modify: `tests/test_bot.py` — add error handling tests

---

## Global Constraints

1. TDD: write tests first, confirm RED, implement, confirm GREEN
2. Coverage ≥ 80% (keep current ~93%)
3. Immutable patterns: no mutation of shared state without clear ownership
4. Dead letter file path must be configurable (like GitSync retries)
5. Dead letter must survive bot restart (persist to disk as JSONL)
6. Error messages in Telegram must be user-friendly, not raw tracebacks

---

### Task 1: Fix help text

**Files:**
- Modify: `pulse_bot/bot.py:139-147`

**Interfaces:** None (cosmetic)

- [ ] **Step 1: Remove `/promote` from help text**

Replace:
```python
    help_text = """Pulse Bot commands:

/p <text> - Create a Pulse Card (or just send plain text)
/recent [N] - List recent N cards (default 10, 1-20)
/promote <card-id> - Promote a card to a real note (TODO: M4-T8)
/help - Show this message

Capture takes <10 seconds. Just send your idea!
"""
```

With:
```python
    help_text = """Pulse Bot commands:

/p <text> - Create a Pulse Card (or just send plain text)
/recent [N] - List recent N cards (default 10, 1-20)
/help - Show this message

Capture takes <10 seconds. Just send your idea!
"""
```

- [ ] **Step 2: Verify tests still pass**

Run: `pytest tests/ -q`
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add pulse_bot/bot.py
git commit -m "fix(pulse-bot): drop unimplemented /promote from help text"
```

---

### Task 2: Write dead letter module (TDD)

**Files:**
- Create: `pulse_bot/dead_letter.py`
- Create: `tests/test_dead_letter.py`

**Interfaces:**
- Consumes: none (standalone module)
- Produces: `DeadLetterQueue` class with `enqueue(path, message, error)`, `flush(git_sync) -> int`, `count` property

- [ ] **Step 1: Write failing tests**

```python
"""Tests for dead letter queue."""
import json
from pathlib import Path
from datetime import datetime, timezone
import pytest
from pulse_bot.dead_letter import DeadLetterQueue


class FakeGitSync:
    """Mock GitSync for testing."""
    def __init__(self, succeed_after: int = 0):
        self.call_count = 0
        self.succeed_after = succeed_after
    
    def commit_and_push(self, file_path: Path, message: str) -> bool:
        self.call_count += 1
        return self.call_count > self.succeed_after


def test_enqueue_appends_entry(tmp_path):
    """Enqueue should add entry and persist to disk."""
    dl = DeadLetterQueue(path=tmp_path / "dead.jsonl")
    dl.enqueue("00_Inbox/_pulse/test.md", "pulse: test", "push failed")
    assert dl.count == 1
    assert dl.pending_paths == ["00_Inbox/_pulse/test.md"]
    # Verify persistence
    lines = (tmp_path / "dead.jsonl").read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["path"] == "00_Inbox/_pulse/test.md"
    assert entry["message"] == "pulse: test"
    assert entry["error"] == "push failed"
    assert entry["attempts"] == 0


def test_flush_success_removes_entry(tmp_path):
    """Flush should remove entry when git_sync succeeds."""
    dl = DeadLetterQueue(path=tmp_path / "dead.jsonl")
    dl.enqueue("test.md", "pulse: test")
    git_sync = FakeGitSync(succeed_after=0)  # succeeds immediately
    flushed = dl.flush(git_sync)
    assert flushed == 1
    assert dl.count == 0


def test_flush_failure_keeps_entry_and_increments_attempts(tmp_path):
    """Flush should keep entry when git_sync fails, incrementing attempts."""
    dl = DeadLetterQueue(path=tmp_path / "dead.jsonl")
    dl.enqueue("test.md", "pulse: test", "initial error")
    git_sync = FakeGitSync(succeed_after=999)  # always fails
    flushed = dl.flush(git_sync)
    assert flushed == 0
    assert dl.count == 1
    assert dl._entries[0]["attempts"] == 1
    assert "initial error" in dl._entries[0]["error"]


def test_flush_empty_queue_returns_zero(tmp_path):
    """Flush on empty queue should return 0."""
    dl = DeadLetterQueue(path=tmp_path / "dead.jsonl")
    assert dl.flush(None) == 0


def test_multiple_entries_flush_partial(tmp_path):
    """With multiple entries, should flush successes and keep failures."""
    dl = DeadLetterQueue(path=tmp_path / "dead.jsonl")
    dl.enqueue("will_fail.md", "msg1")
    dl.enqueue("will_succeed.md", "msg2")
    
    # First call fails, second succeeds
    call_count = [0]
    class ConditionalSync:
        def commit_and_push(self, path, msg):
            call_count[0] += 1
            return call_count[0] > 1  # second call succeeds
    flushed = dl.flush(ConditionalSync())
    assert flushed == 1
    assert dl.count == 1
    assert dl.pending_paths == ["will_fail.md"]


def test_load_persisted_entries_on_init(tmp_path):
    """Loading a new instance should read existing entries from disk."""
    path = tmp_path / "dead.jsonl"
    # Pre-write an entry
    entry = {"path": "pre_existing.md", "message": "msg", "attempts": 2, "last_failure": "2026-01-01T00:00:00", "error": ""}
    path.write_text(json.dumps(entry) + "\n")
    
    dl = DeadLetterQueue(path=path)
    assert dl.count == 1
    assert dl.pending_paths == ["pre_existing.md"]
    assert dl._entries[0]["attempts"] == 2
```

- [ ] **Step 2: Run tests — confirm RED**

```bash
pytest tests/test_dead_letter.py -v
```
Expected: all tests FAIL (DeadLetterQueue not defined)

- [ ] **Step 3: Write implementation**

```python
"""Dead letter queue for cards that failed to push."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """Persistent queue for cards that failed to push.
    
    Entries are stored as JSONL (one JSON object per line).
    Survives bot restarts.
    """
    
    def __init__(self, path: Path):
        self.path = Path(path)
        self._entries: list[dict] = []
        self._load()
    
    def _load(self) -> None:
        """Load entries from disk on init."""
        if self.path.exists():
            with open(self.path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._entries.append(json.loads(line))
    
    def _save(self) -> None:
        """Persist all entries to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            for entry in self._entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def enqueue(self, card_path: str, commit_message: str, error: str = "") -> None:
        """Add a failed card to the queue."""
        self._entries.append({
            "path": card_path,
            "message": commit_message,
            "attempts": 0,
            "last_failure": datetime.now(timezone.utc).isoformat(),
            "error": error,
        })
        self._save()
        logger.info("Dead letter enqueued: %s (queue: %d)", card_path, len(self._entries))
    
    def flush(self, git_sync) -> int:
        """Retry all entries via git_sync. Returns number of successfully flushed."""
        if not self._entries:
            return 0
        
        remaining = []
        flushed = 0
        for entry in self._entries:
            entry["attempts"] += 1
            file_path = Path(entry["path"])
            if git_sync.commit_and_push(file_path, entry["message"]):
                flushed += 1
                logger.info("Dead letter flushed: %s", entry["path"])
            else:
                entry["last_failure"] = datetime.now(timezone.utc).isoformat()
                entry["error"] = f"retry attempt {entry['attempts']} failed"
                remaining.append(entry)
                logger.warning("Dead letter retry failed: %s (attempt %d)",
                              entry["path"], entry["attempts"])
        
        self._entries = remaining
        self._save()
        return flushed
    
    @property
    def count(self) -> int:
        return len(self._entries)
    
    @property
    def pending_paths(self) -> list[str]:
        return [e["path"] for e in self._entries]
```

- [ ] **Step 4: Run tests — confirm GREEN**

```bash
pytest tests/test_dead_letter.py -v
```
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pulse_bot/dead_letter.py tests/test_dead_letter.py
git commit -m "feat(pulse-bot): add DeadLetterQueue for failed push retries (TDD)"
```

---

### Task 3: Add error handling + dead letter to bot.py

**Files:**
- Modify: `pulse_bot/bot.py`
- Modify: `tests/test_bot.py`

**Interfaces:**
- Consumes: `DeadLetterQueue` (from Task 2), `load_config()`, `render_card()`, `infer_intent()`, `GitSync()`
- Produces: updated `handle_message` with try/except, dead letter integration, startup flush

- [ ] **Step 1: Write failing tests for error handling**

Add to `tests/test_bot.py`:

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from pulse_bot.bot import _is_authorized
from pulse_bot.dead_letter import DeadLetterQueue


class FakeGitSync:
    def __init__(self, repo_dir=None, remote_name=None, branch=None, retries=3, dry_run=False):
        self.success = True
        self.last_file = None
        self.last_message = None
    
    def commit_and_push(self, file_path, message):
        self.last_file = file_path
        self.last_message = message
        return self.success


def test_dead_letter_enqueued_on_push_failure(tmp_path, monkeypatch):
    """When commit_and_push fails, a dead letter should be enqueued."""
    from pulse_bot import bot
    
    # Configure
    dl_path = tmp_path / "dead.jsonl"
    monkeypatch.setattr(bot, '_dead_letter', DeadLetterQueue(path=dl_path))
    monkeypatch.setattr(bot, 'GitSync', FakeGitSync)
    monkeypatch.setattr(bot, 'load_config', lambda: {
        "telegram_token": "test",
        "allowed_user_ids": [123],
        "vault_repo_dir": tmp_path / "vault",
        "git_remote": "origin",
        "git_branch": "master",
    })
    
    # Mock update
    update = AsyncMock()
    update.effective_user.id = 123
    update.message.text = "test idea"
    update.message.reply_text = AsyncMock()
    
    # Make commit_and_push fail
    original_build = bot.build_card_path
    bot.GitSync = lambda **kw: FakeGitSync()
    sync = FakeGitSync()
    sync.success = False
    bot.GitSync = lambda **kw: sync
    
    import pulse_bot.card
    monkeypatch.setattr(bot, 'build_card_path', lambda text, when: Path("00_Inbox/_pulse/test.md"))
    
    # Run
    import asyncio
    asyncio.run(bot.handle_message(update, MagicMock()))
    
    # Verify dead letter was enqueued
    assert bot._dead_letter.count == 1
    assert "test.md" in bot._dead_letter.pending_paths[0]
    
    # Clean up
    bot._dead_letter = DeadLetterQueue(path=Path("/tmp/pulse-bot-dl-test.jsonl"))


def test_handle_message_file_write_error_replies_friendly(tmp_path, monkeypatch):
    """When file write fails, user should get a friendly error, not a crash."""
    from pulse_bot import bot
    
    dl_path = tmp_path / "dead.jsonl"
    monkeypatch.setattr(bot, '_dead_letter', DeadLetterQueue(path=dl_path))
    monkeypatch.setattr(bot, 'GitSync', FakeGitSync)
    monkeypatch.setattr(bot, 'load_config', lambda: {
        "telegram_token": "test",
        "allowed_user_ids": [123],
        "vault_repo_dir": tmp_path / "vault",
        "git_remote": "origin",
        "git_branch": "master",
    })
    
    update = AsyncMock()
    update.effective_user.id = 123
    update.message.text = "test idea"
    update.message.reply_text = AsyncMock()
    
    # Make file write fail
    import pulse_bot.card
    original_write = pulse_bot.card.Path.write_text
    def failing_write(self, *args, **kwargs):
        raise OSError("Disk full")
    monkeypatch.setattr(pulse_bot.card.Path, "write_text", failing_write)
    
    import asyncio
    asyncio.run(bot.handle_message(update, MagicMock()))
    
    # Should have replied with error message, not crashed
    reply = update.message.reply_text
    assert reply.called
    error_text = reply.call_args[0][0]
    assert "error" in error_text.lower() or "fail" in error_text.lower()
    
    # Restore
    monkeypatch.setattr(pulse_bot.card.Path, "write_text", original_write)


def test_dead_letter_flushed_on_startup(tmp_path, monkeypatch):
    """Dead letter should be flushed when bot starts."""
    from pulse_bot import bot
    
    dl_path = tmp_path / "dead.jsonl"
    dl = DeadLetterQueue(path=dl_path)
    dl.enqueue("old_card.md", "pulse: old")
    
    monkeypatch.setattr(bot, '_dead_letter', dl)
    monkeypatch.setattr(bot, 'load_config', lambda: {
        "telegram_token": "test",
        "allowed_user_ids": [123],
        "vault_repo_dir": tmp_path / "vault",
        "git_remote": "origin",
        "git_branch": "master",
    })
    
    # Create the vault dir with the old card
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "old_card.md").write_text("old content")
    
    # Ensure git is initialized
    import subprocess
    subprocess.run(["git", "init"], cwd=vault, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=vault, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=vault, check=True)
    (vault / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=vault, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=vault, check=True)
    
    # Import the real GitSync (dry_run mode)
    from pulse_bot.git_sync import GitSync
    gs = GitSync(repo_dir=vault, dry_run=True)
    
    flushed = bot._flush_dead_letters(gs)
    assert flushed == 1
    assert bot._dead_letter.count == 0
```

- [ ] **Step 2: Implement error handling + dead letter in bot.py**

The updated `bot.py` should:
1. Import `DeadLetterQueue`
2. Create module-level `_dead_letter` instance
3. Add `_flush_dead_letters()` helper
4. Wrap `handle_message` in try/except
5. On push failure: enqueue dead letter
6. In `main()`: flush dead letters before polling

```python
"""Pulse Bot main module: Telegram listener and dispatcher."""
import logging
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from pulse_bot.card import build_card_path, render_card
from pulse_bot.git_sync import GitSync
from pulse_bot.intent import infer_intent
from pulse_bot.config import load_config
from pulse_bot.dead_letter import DeadLetterQueue

logger = logging.getLogger(__name__)

# In-memory recent cards for /recent command
_recent_cards: list[dict] = []

# Dead letter queue for failed pushes
_dead_letter = DeadLetterQueue(path=Path("/opt/pulse-bot/dead_letter.jsonl"))

# /recent command defaults and bounds
RECENT_DEFAULT_N = 10
RECENT_MIN_N = 1
RECENT_MAX_N = 20
RECENT_USAGE = f"Usage: /recent [N] where {RECENT_MIN_N} <= N <= {RECENT_MAX_N}"

... (rest of file unchanged, except handle_message changes below)
```

Update `handle_message` to wrap operations in try/except:

```python
async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle plain text message: create a Pulse Card."""
    config = load_config()
    user_id = update.effective_user.id
    
    if not _is_authorized(user_id, config["allowed_user_ids"]):
        await update.message.reply_text("Unauthorized. Ask the owner to add your user_id.")
        return
    
    text = update.message.text.strip()
    if not text:
        return
    
    # Strip /p prefix if present
    if text.startswith("/p "):
        text = text[3:].strip()
    elif text == "/p":
        await update.message.reply_text("Usage: /p <your idea>")
        return
    
    # Flush any pending dead letters before processing new message
    try:
        sync_for_flush = GitSync(
            repo_dir=config["vault_repo_dir"],
            remote_name=config["git_remote"],
            branch=config["git_branch"],
        )
        flushed = _dead_letter.flush(sync_for_flush)
        if flushed:
            logger.info("Flushed %d dead letter(s)", flushed)
    except Exception:
        logger.exception("Dead letter flush failed (non-fatal)")
    
    when = datetime.now(timezone.utc)
    intent = infer_intent(text)
    
    # Render card
    card_content = render_card(text, user_id=user_id, intent=intent, when=when)
    
    # Build path and write
    card_path = build_card_path(text, when)
    full_path = config["vault_repo_dir"] / card_path
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(card_content, encoding="utf-8")
    except OSError as e:
        logger.error("Failed to write card file %s: %s", full_path, e)
        await update.message.reply_text("⚠ Could not save card due to a file error. Please try again.")
        return
    
    # Commit + push
    sync = GitSync(
        repo_dir=config["vault_repo_dir"],
        remote_name=config["git_remote"],
        branch=config["git_branch"],
    )
    first_line = text.split("\n")[0][:50]
    try:
        success = sync.commit_and_push(full_path, message=f"pulse: {first_line}")
    except Exception as e:
        logger.exception("Git operation failed for %s", full_path)
        success = False
    
    # Track in memory
    _recent_cards.insert(0, {
        "path": str(card_path),
        "text": text,
        "intent": intent,
        "when": when.isoformat(),
    })
    if len(_recent_cards) > RECENT_MAX_N:
        _recent_cards.pop()
    
    if success:
        await update.message.reply_text(f"✓ Captured: {first_line}")
    else:
        # Enqueue dead letter for later retry
        _dead_letter.enqueue(str(full_path), f"pulse: {first_line}", error="push failed after retries")
        await update.message.reply_text(
            "⚠ Saved locally but push failed. Will retry automatically. "
            "Run `bash pulse-pull.sh` on VPS or check docs/runbook.md."
        )
```

Add `_flush_dead_letters` function and update `main()`:

```python
def _flush_dead_letters(sync: GitSync) -> int:
    """Flush pending dead letters. Returns number flushed."""
    return _dead_letter.flush(sync)


def main() -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    config = load_config()
    
    # Flush dead letters on startup
    try:
        sync = GitSync(
            repo_dir=config["vault_repo_dir"],
            remote_name=config["git_remote"],
            branch=config["git_branch"],
        )
        flushed = _flush_dead_letters(sync)
        if flushed:
            logger.info("Startup: flushed %d dead letter(s)", flushed)
    except Exception:
        logger.exception("Startup dead letter flush failed (non-fatal)")
    
    app = Application.builder().token(config["telegram_token"]).build()
    
    # Command handlers
    app.add_handler(CommandHandler("p", handle_message))
    app.add_handler(CommandHandler("recent", recent_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", help_command))
    
    # Plain text → pulse card
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Pulse Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run tests — confirm GREEN**

```bash
pytest tests/ --cov=pulse_bot --cov-report=term-missing -q
```
Expected: all tests pass, coverage ≥ 80%

- [ ] **Step 4: Commit**

```bash
git add pulse_bot/bot.py pulse_bot/dead_letter.py tests/test_bot.py tests/test_dead_letter.py
git commit -m "fix(pulse-bot): add error handling and dead letter queue for failed pushes"
```

---

## Self-Review

1. **Spec coverage**: 
   - `/promote` removed from help ✅
   - File write errors caught with user-friendly message ✅
   - Git operation errors caught with user-friendly message ✅
   - Dead letter queue persists failed pushes for retry ✅
   - Dead letter flushed on startup + before each new card ✅

2. **Placeholder scan**: No TBD/TODO/implement-later found ✅

3. **Type consistency**: 
   - `DeadLetterQueue.enqueue(path: str, message: str, error: str)` ✅
   - `DeadLetterQueue.flush(git_sync) -> int` ✅
   - `_flush_dead_letters(sync: GitSync) -> int` ✅
