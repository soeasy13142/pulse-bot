"""Git operations for pulse-bot: commit + push with retry."""
import subprocess
import time
from pathlib import Path


class GitSync:
    """Wrapper around git add/commit/push with retry logic."""

    def __init__(
        self,
        repo_dir: Path,
        remote_name: str = "origin",
        branch: str = "master",
        retries: int = 3,
        dry_run: bool = False,
    ):
        self.repo_dir = Path(repo_dir)
        self.remote_name = remote_name
        self.branch = branch
        self.retries = retries
        self.dry_run = dry_run

    def commit_and_push(
        self, file_path: Path, message: str
    ) -> bool:
        """Add file, commit, push with retries. Returns True on success."""
        file_path = Path(file_path)
        if not file_path.exists():
            return False

        # git add
        add_result = subprocess.run(
            ["git", "add", str(file_path)],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if add_result.returncode != 0:
            return False

        # git commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if commit_result.returncode != 0:
            return False

        if self.dry_run:
            return True

        # git push with retries
        for attempt in range(self.retries):
            push_result = subprocess.run(
                ["git", "push", self.remote_name, self.branch],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
            )
            if push_result.returncode == 0:
                return True
            if attempt < self.retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff

        return False
