import subprocess
from pathlib import Path
import pytest
from pulse_bot.git_sync import GitSync


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


def test_commit_and_push_creates_commit(tmp_git_repo):
    """写入新文件 → 调用 commit_and_push → 应产生新 commit."""
    sync = GitSync(repo_dir=tmp_git_repo, remote_name="origin", branch="master")
    new_file = tmp_git_repo / "new_idea.md"
    new_file.write_text("# new idea")
    sync.commit_and_push(new_file, message="pulse: new idea")

    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_git_repo, capture_output=True, text=True
    )
    assert "pulse: new idea" in log.stdout


def test_commit_and_push_dry_run_no_actual_push(tmp_git_repo):
    """无 remote 时不应抛错（dry run 模式）。"""
    sync = GitSync(repo_dir=tmp_git_repo, remote_name="origin", branch="master", dry_run=True)
    new_file = tmp_git_repo / "idea2.md"
    new_file.write_text("idea 2")
    result = sync.commit_and_push(new_file, message="pulse: idea 2")
    assert result is True

    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_git_repo, capture_output=True, text=True
    )
    assert "pulse: idea 2" in log.stdout


def test_commit_and_push_retries_on_failure(tmp_git_repo, monkeypatch):
    """push 失败后应按 retries 次数重试并返回 False."""
    sync = GitSync(repo_dir=tmp_git_repo, remote_name="origin", branch="master", retries=2)
    push_attempts = []
    real_run = subprocess.run

    def fake_run(*args, **kwargs):
        command = args[0]
        if command[:2] == ["git", "push"]:
            push_attempts.append(command)
            class Result:
                returncode = 1
                stderr = "fatal: could not push"
                stdout = ""
            return Result()
        return real_run(*args, **kwargs)

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    new_file = tmp_git_repo / "idea3.md"
    new_file.write_text("idea 3")
    result = sync.commit_and_push(new_file, message="pulse: idea 3")
    assert result is False
    assert len(push_attempts) == 2
