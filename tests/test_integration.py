"""End-to-end integration tests."""
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from pulse_bot.card import build_card_path, render_card
from pulse_bot.git_sync import GitSync
from pulse_bot.intent import infer_intent


def test_full_pipeline_no_remote(tmp_path):
    """完整流程：生成 card → 写入文件 → commit（dry-run）。"""
    repo = tmp_path / "vault"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

    text = "想做个 skills 管理器"
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    intent = infer_intent(text)

    card_content = render_card(text, user_id=12345, intent=intent, when=when)
    card_path = build_card_path(text, when)
    full_path = repo / card_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(card_content, encoding="utf-8")

    sync = GitSync(repo_dir=repo, remote_name="origin", branch="master", dry_run=True)
    success = sync.commit_and_push(full_path, message=f"pulse: {text[:50]}")
    assert success is True

    # Verify file is in repo
    assert full_path.exists()
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=repo, capture_output=True, text=True
    )
    assert "pulse: " in log.stdout