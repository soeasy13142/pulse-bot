"""Dead letter queue for cards that failed to push."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """Persistent queue for cards that failed to push.

    Entries are stored as JSONL (one JSON object per line).
    Survives bot restarts.
    """

    def __init__(self, path: Path, on_new_entry: Callable[[], None] | None = None):
        self.path = Path(path)
        self._on_new_entry = on_new_entry
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

    def append(self, card_path: Path | str, error: str = "", payload: dict | None = None) -> None:
        """Add a failed card and invoke on_new_entry callback."""
        self._entries.append({
            "path": str(card_path),
            "error": error,
            "payload": payload or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save()
        if self._on_new_entry is not None:
            try:
                self._on_new_entry()
            except Exception:
                logger.exception("dead_letter on_new_entry callback failed")

    def length(self) -> int:
        """Return the number of entries on disk by counting JSONL lines.

        Uses file I/O so it reflects what a concurrent process may have written;
        use ``.count`` for the in-memory count.
        """
        try:
            with open(self.path) as f:
                return sum(1 for _ in f)
        except FileNotFoundError:
            return 0

    def tail(self, n: int) -> list[dict]:
        """Return the last *n* entries from disk without touching in-memory state."""
        import json

        try:
            with open(self.path) as f:
                lines = f.readlines()
        except FileNotFoundError:
            return []
        return [json.loads(line) for line in lines[-n:]]

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
                entry["error"] = (
                    f"{entry['error']}; " if entry["error"] else ""
                ) + f"retry attempt {entry['attempts']} failed"
                remaining.append(entry)
                logger.warning(
                    "Dead letter retry failed: %s (attempt %d)",
                    entry["path"],
                    entry["attempts"],
                )

        self._entries = remaining
        self._save()
        return flushed

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def pending_paths(self) -> list[str]:
        return [e["path"] for e in self._entries]
