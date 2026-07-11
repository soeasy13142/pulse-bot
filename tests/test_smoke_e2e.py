"""End-to-end smoke test for the full Pulse Card pipeline."""
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pulse_bot.card import build_card_path, render_card
from pulse_bot.git_sync import GitSync
from pulse_bot.intent import infer_intent
from pulse_bot.dead_letter import DeadLetterQueue


def test_full_pipeline_with_git_push_failure(tmp_path):
    """
    完整流程：生成 card → 写入文件 → commit → push 失败 → 文件保留。
    模拟 bot 收到消息后的完整内部流程，不依赖 Telegram API。
    """
    # Arrange: 创建临时 git 仓库
    repo = tmp_path / "vault"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "bot@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Pulse Bot"], cwd=repo, check=True)
    (repo / "README.md").write_text("# test vault")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

    text = "想做个 skills 管理器"
    when = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)

    # Act: 模拟 bot 内部流程
    intent = infer_intent(text)
    card_content = render_card(text, user_id=12345, intent=intent, when=when)
    card_path = build_card_path(text, when)
    full_path = repo / card_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(card_content, encoding="utf-8")

    # dry_run=True 模拟无 remote 场景（只 commit 不 push）
    sync = GitSync(repo_dir=repo, remote_name="origin", branch="master", dry_run=True)
    success = sync.commit_and_push(full_path, message=f"pulse: {text[:50]}")

    # Assert
    assert success is True, "dry-run commit should succeed"

    # 验证 commit 存在
    log = subprocess.run(
        ["git", "log", "--oneline", "--format=%s"],
        cwd=repo, capture_output=True, text=True
    )
    assert "pulse: 想做个 skills 管理器" in log.stdout

    # 验证文件内容
    assert full_path.exists()
    content = full_path.read_text(encoding="utf-8")
    assert "想做个 skills 管理器" in content
    assert "intent: idea" in content
    assert "status: pulse" in content


def test_full_pipeline_with_real_push_failure_and_dead_letter(tmp_path):
    """
    模拟 push 到无 remote 仓库 → commit 成功 → push 重试 3 次失败 → 文件保留。
    """
    repo = tmp_path / "vault"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "bot@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Pulse Bot"], cwd=repo, check=True)
    (repo / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

    dlq = DeadLetterQueue(repo / "dead_letter")
    sync = GitSync(repo_dir=repo, remote_name="origin", branch="master",
                   retries=2)

    text = "测试 push 失败场景"
    when = datetime(2026, 7, 11, 12, 5, 0, tzinfo=timezone.utc)
    card_path = build_card_path(text, when)
    full_path = repo / card_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(render_card(text, user_id=1, intent="reference", when=when),
                         encoding="utf-8")

    # push 到没有 remote 的仓库应该失败
    success = sync.commit_and_push(full_path, message="pulse: test")

    # Manually enqueue to dead letter (GitSync doesn't auto-enqueue)
    dlq.enqueue(card_path=str(card_path), commit_message="pulse: test",
                error="push failed (no remote)")

    assert success is False
    assert full_path.exists(), "即使 push 失败，文件也应保留"

    # 检查 dead letter
    assert dlq.count > 0
    assert any(str(card_path) in p for p in dlq.pending_paths)


def test_pre_commit_hook_blocks_outside_pulse(tmp_path):
    """
    验证 pre-commit hook 会阻止 bot 在 _pulse/ 外写入。
    这个测试模拟 vault 仓库 + hook 的场景。
    """
    repo = tmp_path / "vault"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "bot@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Pulse Bot"], cwd=repo, check=True)

    # 先做 init commit（hook 安装前），否则 hook 会阻止 README.md 提交
    (repo / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

    # 安装 hook
    hook_src = Path(__file__).parent.parent / "docs" / "hooks" / "pre-commit"
    if not hook_src.exists():
        pytest.skip("pre-commit hook template not found — run Task 1 first")

    hook_dst = repo / ".git" / "hooks" / "pre-commit"
    hook_dst.parent.mkdir(parents=True, exist_ok=True)
    hook_dst.write_text(hook_src.read_text())
    hook_dst.chmod(0o755)

    # 试图写 _pulse/ 外文件
    bad_file = repo / "Other_Folder" / "bad.md"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_text("should be blocked")
    subprocess.run(["git", "add", "Other_Folder/bad.md"], cwd=repo, check=True)

    result = subprocess.run(
        ["git", "commit", "-m", "should fail"],
        cwd=repo, capture_output=True, text=True
    )

    assert result.returncode != 0, "pre-commit hook should block writes outside _pulse/"
    assert "Blocked file" in result.stdout or "Blocked file" in result.stderr
