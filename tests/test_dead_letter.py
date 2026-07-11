"""Tests for dead letter queue."""
import json
from pathlib import Path
import pytest
from pulse_bot.dead_letter import DeadLetterQueue


class FakeGitSync:
    """Mock GitSync for testing flush behavior."""
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

    # Verify persistence on disk
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
    entry = {
        "path": "pre_existing.md",
        "message": "msg",
        "attempts": 2,
        "last_failure": "2026-01-01T00:00:00",
        "error": "",
    }
    path.write_text(json.dumps(entry) + "\n")

    dl = DeadLetterQueue(path=path)
    assert dl.count == 1
    assert dl.pending_paths == ["pre_existing.md"]
    assert dl._entries[0]["attempts"] == 2
