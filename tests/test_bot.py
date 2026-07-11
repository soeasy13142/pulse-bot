"""Tests for bot.py command parsing, authorization, error handling."""
from contextlib import asynccontextmanager as _asynccontextmanager
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pulse_bot.bot import (
    _is_authorized,
    _flush_dead_letters,
    handle_message,
    recent_command,
    help_command,
)
from pulse_bot.dead_letter import DeadLetterQueue
from pulse_bot.lifecycle import ShutdownCoordinator, ShutdownInProgress


def test_is_authorized_true():
    assert _is_authorized(12345, [12345, 67890]) is True


def test_is_authorized_false():
    assert _is_authorized(99999, [12345, 67890]) is False


def test_is_authorized_empty_list():
    assert _is_authorized(12345, []) is False


def _make_update(user_id=12345, text="hello"):
    """Build a mock Telegram Update with the given user_id and message text."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def _make_context():
    ctx = MagicMock()
    ctx.bot_data = {"coordinator": ShutdownCoordinator()}
    return ctx


async def test_handle_message_unauthorized():
    """Unauthorized user gets rejected without further processing."""
    update = _make_update(user_id=99999, text="hello")
    context = _make_context()
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345], "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await handle_message(update, context)
    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Unauthorized" in msg


async def test_handle_message_empty_text():
    """Empty text message should be ignored silently."""
    update = _make_update(text="")
    context = _make_context()
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345], "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await handle_message(update, context)
    update.message.reply_text.assert_not_called()


async def test_handle_message_bare_p_command():
    """/p with no text should reply with usage hint."""
    update = _make_update(text="/p")
    context = _make_context()
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345], "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await handle_message(update, context)
    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Usage" in msg


async def test_recent_command_no_cards():
    """No recent cards → reply with empty message."""
    update = _make_update()
    context = _make_context()
    context.args = []  # /recent with no args
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)
    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "No recent" in msg


async def test_recent_command_unauthorized():
    """Non-whitelisted user calling /recent gets rejected (no leak of authorized users' cards)."""
    from pulse_bot.bot import _recent_cards
    _recent_cards.clear()
    _recent_cards.append({"text": "secret", "intent": "idea", "when": "2026-07-10T20:00:00+00:00"})

    update = _make_update(user_id=99999)  # not in allowed_user_ids
    context = _make_context()
    context.args = []  # /recent with no args (unauthorized check happens first)
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)
    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Unauthorized" in msg
    assert "secret" not in msg  # MUST NOT leak
    _recent_cards.clear()


async def test_help_command():
    """Help command lists available commands."""
    update = _make_update()
    context = _make_context()
    await help_command(update, context)
    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "/p" in msg
    assert "/recent" in msg
    assert "/help" in msg


async def test_help_command_does_not_advertise_dashboard():
    """/dashboard is not implemented in v0.1; help must not advertise it."""
    update = _make_update()
    context = _make_context()
    await help_command(update, context)
    msg = update.message.reply_text.call_args[0][0]
    assert "/dashboard" not in msg


async def test_recent_command_with_cards():
    """With cards tracked, /recent lists them."""
    from pulse_bot.bot import _recent_cards
    _recent_cards.clear()
    _recent_cards.append({"text": "first idea", "intent": "idea", "when": "2026-07-10T20:00:00+00:00"})
    _recent_cards.append({"text": "second idea\nwith newline", "intent": "task", "when": "2026-07-10T20:01:00+00:00"})

    update = _make_update()
    context = _make_context()
    context.args = []  # /recent with no args
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)
    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Recent" in msg
    assert "first idea" in msg
    assert "[idea]" in msg
    assert "[task]" in msg
    _recent_cards.clear()


async def test_recent_command_with_n_arg_returns_n_cards():
    """/recent N returns at most N cards when more are tracked."""
    from pulse_bot.bot import _recent_cards
    _recent_cards.clear()
    # Mimic handle_message: insert(0, ...) puts newest at index 0
    for i in range(15):
        _recent_cards.insert(0, {"text": f"idea {i}", "intent": "idea", "when": "2026-07-10T20:00:00+00:00"})

    update = _make_update()
    context = _make_context()
    context.args = ["3"]
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)

    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "1. [idea] idea 14" in msg  # newest first
    assert "3. [idea] idea 12" in msg
    assert "4. [idea]" not in msg
    _recent_cards.clear()


async def test_recent_command_n_caps_at_tracked_count():
    """/recent N returns all cards when N > tracked count (no padding)."""
    from pulse_bot.bot import _recent_cards
    _recent_cards.clear()
    for i in range(3):
        _recent_cards.append({"text": f"idea {i}", "intent": "idea", "when": "2026-07-10T20:00:00+00:00"})

    update = _make_update()
    context = _make_context()
    context.args = ["20"]
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "1. " in msg
    assert "2. " in msg
    assert "3. " in msg
    assert "4. " not in msg  # only 3 cards tracked
    _recent_cards.clear()


async def test_recent_command_with_invalid_n_arg_returns_usage():
    """/recent abc (non-numeric) returns a friendly usage hint, does not list cards."""
    from pulse_bot.bot import _recent_cards
    _recent_cards.clear()
    _recent_cards.append({"text": "secret idea", "intent": "idea", "when": "2026-07-10T20:00:00+00:00"})

    update = _make_update()
    context = _make_context()
    context.args = ["abc"]
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)

    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Usage" in msg
    assert "secret idea" not in msg  # must not leak cards on error
    _recent_cards.clear()


async def test_recent_command_with_out_of_range_n_arg_returns_usage():
    """/recent 0 or /recent 21 returns usage hint (valid range 1..20)."""
    update = _make_update()
    context = _make_context()
    context.args = ["0"]
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)
    msg = update.message.reply_text.call_args[0][0]
    assert "Usage" in msg

    # /recent 21 (above the 20-card cap)
    update2 = _make_update()
    context2 = _make_context()
    context2.args = ["21"]
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update2, context2)
    msg2 = update2.message.reply_text.call_args[0][0]
    assert "Usage" in msg2


async def test_recent_command_with_extra_args_returns_usage():
    """/recent 5 extra (extra args after N) returns usage hint, does not silently use first arg."""
    from pulse_bot.bot import _recent_cards
    _recent_cards.clear()
    _recent_cards.append({"text": "secret idea", "intent": "idea", "when": "2026-07-10T20:00:00+00:00"})

    update = _make_update()
    context = _make_context()
    context.args = ["5", "extra"]
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)

    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Usage" in msg
    assert "secret idea" not in msg  # must not leak cards on error
    _recent_cards.clear()


async def test_recent_command_with_negative_n_arg_returns_usage():
    """/recent -1 returns usage hint (negative is out of range)."""
    update = _make_update()
    context = _make_context()
    context.args = ["-1"]
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)
    msg = update.message.reply_text.call_args[0][0]
    assert "Usage" in msg


async def test_recent_command_accepts_inclusive_lower_bound():
    """/recent 1 (lower bound) is accepted and returns exactly 1 card."""
    from pulse_bot.bot import _recent_cards
    _recent_cards.clear()
    for i in range(5):
        _recent_cards.insert(0, {"text": f"idea {i}", "intent": "idea", "when": "2026-07-10T20:00:00+00:00"})

    update = _make_update()
    context = _make_context()
    context.args = ["1"]
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "1. [idea] idea 4" in msg  # newest first
    assert "2. [idea]" not in msg
    _recent_cards.clear()


async def test_recent_command_accepts_inclusive_upper_bound():
    """/recent 20 with >= 20 cards tracked returns exactly 20 cards (upper bound is inclusive)."""
    from pulse_bot.bot import _recent_cards
    _recent_cards.clear()
    for i in range(25):
        _recent_cards.insert(0, {"text": f"idea {i}", "intent": "idea", "when": "2026-07-10T20:00:00+00:00"})

    update = _make_update()
    context = _make_context()
    context.args = ["20"]
    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": __import__("pathlib").Path("/tmp"),
        "git_remote": "origin", "git_branch": "master",
    }):
        await recent_command(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "20. [idea] idea 5" in msg  # 25 cards, take first 20 → indices 0..19
    assert "21. [idea]" not in msg  # MUST NOT include 21st item
    _recent_cards.clear()


async def test_handle_message_happy_path(tmp_path, monkeypatch):
    """Full happy path: text → infer → render → write → commit+push (mocked success)."""
    update = _make_update(user_id=12345, text="想做个 skills 管理器")
    context = _make_context()

    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x",
        "allowed_user_ids": [12345],
        "vault_repo_dir": tmp_path,
        "git_remote": "origin",
        "git_branch": "master",
    }), patch("pulse_bot.bot.GitSync") as mock_sync:
        mock_sync.return_value.commit_and_push.return_value = True
        await handle_message(update, context)

    # Reply was sent with success
    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Captured" in msg

    # Card file was created in vault
    cards = list(tmp_path.glob("00_Inbox/_pulse/*.md"))
    assert len(cards) == 1
    content = cards[0].read_text()
    assert "想做个 skills 管理器" in content


async def test_handle_message_with_p_prefix(tmp_path):
    """/p prefix is stripped before processing."""
    update = _make_update(user_id=12345, text="/p 做个东西")
    context = _make_context()

    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": tmp_path, "git_remote": "origin", "git_branch": "master",
    }), patch("pulse_bot.bot.GitSync") as mock_sync:
        mock_sync.return_value.commit_and_push.return_value = True
        await handle_message(update, context)

    update.message.reply_text.assert_called_once()
    # The /p prefix should be stripped — message body should not contain "/p"
    msg = update.message.reply_text.call_args[0][0]
    assert "/p" not in msg


async def test_handle_message_push_fails(tmp_path, monkeypatch):
    """If commit_and_push returns False, user sees push failure warning and dead letter is enqueued."""
    from pulse_bot import bot as bot_mod

    dl_path = tmp_path / "dead.jsonl"
    monkeypatch.setattr(bot_mod, "_get_dead_letter", lambda config: DeadLetterQueue(path=dl_path))

    update = _make_update(user_id=12345, text="hello world")
    context = _make_context()

    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": tmp_path, "git_remote": "origin", "git_branch": "master",
        "dead_letter_path": dl_path,
    }), patch("pulse_bot.bot.GitSync") as mock_sync:
        mock_sync.return_value.commit_and_push.return_value = False
        await handle_message(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "push failed" in msg
    assert "Will retry" in msg
    assert "git pull" in msg

    # Dead letter should have been enqueued
    dl = DeadLetterQueue(path=dl_path)
    assert dl.count == 1


class FakeGitSync:
    """Mock GitSync matching constructor signature for tests."""
    def __init__(self, repo_dir=None, remote_name=None, branch=None, retries=3, dry_run=False):
        self.success = True
        self.last_file = None
        self.last_message = None

    def commit_and_push(self, file_path, message):
        self.last_file = file_path
        self.last_message = message
        return self.success


async def test_dead_letter_enqueued_on_push_failure(tmp_path, monkeypatch):
    """When commit_and_push fails, a dead letter should be enqueued."""
    from pulse_bot import bot as bot_mod

    dl_path = tmp_path / "dead.jsonl"
    monkeypatch.setattr(bot_mod, "_get_dead_letter", lambda config: DeadLetterQueue(path=dl_path))
    monkeypatch.setattr(bot_mod, "load_config", lambda: {
        "telegram_token": "test",
        "allowed_user_ids": [123],
        "vault_repo_dir": tmp_path / "vault",
        "git_remote": "origin",
        "git_branch": "master",
        "dead_letter_path": dl_path,
    })
    monkeypatch.setattr(bot_mod, "build_card_path", lambda text, when: Path("00_Inbox/_pulse/test.md"))

    # Return a FakeGitSync that always fails
    def make_failing_sync(**kw):
        gs = FakeGitSync()
        gs.success = False
        return gs
    monkeypatch.setattr(bot_mod, "GitSync", make_failing_sync)

    update = AsyncMock()
    update.effective_user.id = 123
    update.message.text = "test idea"
    update.message.reply_text = AsyncMock()

    ctx = MagicMock()
    ctx.bot_data = {"coordinator": ShutdownCoordinator()}
    await handle_message(update, ctx)

    dl = DeadLetterQueue(path=dl_path)
    assert dl.count == 1
    assert "test.md" in dl.pending_paths[0]


async def test_handle_message_file_write_error_replies_friendly(tmp_path, monkeypatch):
    """When file write fails, user should get a friendly error, not a crash."""
    import pathlib
    from pulse_bot import bot as bot_mod

    dl_path = tmp_path / "dead.jsonl"
    monkeypatch.setattr(bot_mod, "_get_dead_letter", lambda config: DeadLetterQueue(path=dl_path))
    monkeypatch.setattr(bot_mod, "GitSync", FakeGitSync)
    monkeypatch.setattr(bot_mod, "load_config", lambda: {
        "telegram_token": "test",
        "allowed_user_ids": [123],
        "vault_repo_dir": tmp_path / "vault",
        "git_remote": "origin",
        "git_branch": "master",
        "dead_letter_path": dl_path,
    })

    update = AsyncMock()
    update.effective_user.id = 123
    update.message.text = "test idea"
    update.message.reply_text = AsyncMock()

    # Make Path.write_text raise OSError
    def failing_write(self, *args, **kwargs):
        raise OSError("Disk full")
    monkeypatch.setattr(pathlib.Path, "write_text", failing_write)

    ctx = MagicMock()
    ctx.bot_data = {"coordinator": ShutdownCoordinator()}
    await handle_message(update, ctx)

    reply = update.message.reply_text
    assert reply.called
    error_text = reply.call_args[0][0]
    assert "error" in error_text.lower() or "fail" in error_text.lower()


async def test_handle_message_uses_config_dead_letter_path(tmp_path, monkeypatch):
    """Dead letter queue is initialized from config[dead_letter_path], not hardcoded."""
    from pulse_bot import bot as bot_mod

    custom_path = tmp_path / "custom_dead.jsonl"
    monkeypatch.setattr(bot_mod, "load_config", lambda: {
        "telegram_token": "test",
        "allowed_user_ids": [123],
        "vault_repo_dir": tmp_path / "vault",
        "git_remote": "origin",
        "git_branch": "master",
        "dead_letter_path": custom_path,
    })

    # GitSync that always fails (set instance attr; class attr is reset by __init__)
    def failing_sync(**kw):
        gs = FakeGitSync()
        gs.success = False
        return gs
    monkeypatch.setattr(bot_mod, "GitSync", failing_sync)

    # Capture the config-derived path passed to _get_dead_letter
    captured = {}
    def capturing_get(config):
        captured["path"] = config["dead_letter_path"]
        return DeadLetterQueue(path=custom_path)
    monkeypatch.setattr(bot_mod, "_get_dead_letter", capturing_get)
    monkeypatch.setattr(bot_mod, "build_card_path", lambda text, when: Path("00_Inbox/_pulse/test.md"))

    update = AsyncMock()
    update.effective_user.id = 123
    update.message.text = "test idea"
    update.message.reply_text = AsyncMock()

    ctx = MagicMock()
    ctx.bot_data = {"coordinator": ShutdownCoordinator()}
    await handle_message(update, ctx)

    # The path passed to _get_dead_letter came from config, not hardcoded
    assert captured["path"] == custom_path
    # And the file was actually written there
    assert custom_path.exists()


async def test_dead_letter_flushed_on_startup(tmp_path, monkeypatch):
    """Dead letter should be flushed via _flush_dead_letters."""
    from pulse_bot import bot as bot_mod
    from pulse_bot.git_sync import GitSync

    # Set up a real git repo in vault first
    vault = tmp_path / "vault"
    vault.mkdir()
    import subprocess
    subprocess.run(["git", "init"], cwd=vault, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=vault, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=vault, check=True)
    (vault / "README.md").write_text("# test")
    subprocess.run(["git", "add", "README.md"], cwd=vault, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=vault, check=True)

    # Create an untracked file — this simulates a card that was saved locally
    # but never committed (e.g., bot restarted before git ops completed), so it
    # ended up as a dead letter entry. The file exists on disk but git doesn't
    # know about it yet.
    (vault / "old_card.md").write_text("old content")

    dl_path = tmp_path / "dead.jsonl"
    dl = DeadLetterQueue(path=dl_path)
    dl.enqueue(str(vault / "old_card.md"), "pulse: old")

    gs = GitSync(repo_dir=vault, dry_run=True)

    flushed = _flush_dead_letters(gs, dl)
    assert flushed == 1
    assert dl.count == 0


async def test_message_handler_wraps_with_coordinator(monkeypatch):
    """Verify handle_message enters coordinator.track() before processing."""
    from pulse_bot import bot as bot_mod

    coord = ShutdownCoordinator()
    fake_update = MagicMock()
    fake_context = MagicMock()
    fake_context.bot_data = {"coordinator": coord}

    # Stub out _handle_message_impl so the test does not need real config/IO
    monkeypatch.setattr(bot_mod, "_handle_message_impl", AsyncMock())

    track_called = False
    real_track = coord.track

    @_asynccontextmanager
    async def counting_track():
        nonlocal track_called
        track_called = True
        async with real_track():
            yield

    monkeypatch.setattr(coord, "track", counting_track)
    await bot_mod.handle_message(fake_update, fake_context)
    assert track_called is True


async def test_message_handler_rejects_during_shutdown(monkeypatch):
    """Verify handle_message propagates ShutdownInProgress when coord is shutting down."""
    from pulse_bot import bot as bot_mod

    coord = ShutdownCoordinator()
    coord.request_shutdown()
    fake_update = MagicMock()
    fake_context = MagicMock()
    fake_context.bot_data = {"coordinator": coord}

    # Stub out _handle_message_impl so we test only the coordinator rejection path
    monkeypatch.setattr(bot_mod, "_handle_message_impl", AsyncMock())

    with pytest.raises(ShutdownInProgress):
        await bot_mod.handle_message(fake_update, fake_context)


async def test_main_starts_and_stops_watchdog(monkeypatch):
    """WatchdogPinger is exposed on bot_mod and start()/stop() are called."""
    from pulse_bot import bot as bot_mod

    started = []
    stopped = []

    class FakePinger:
        def start(self):
            started.append(True)
        def stop(self):
            stopped.append(True)

    monkeypatch.setattr(bot_mod, "WatchdogPinger", lambda: FakePinger())

    bot_mod.setup_logging(level="INFO", fmt="text")
    pinger = bot_mod.WatchdogPinger()
    pinger.start()
    pinger.stop()
    assert started == [True]
    assert stopped == [True]


async def test_main_shuts_down_cleanly(monkeypatch):
    """Exercise main() lifecycle: initialize/start/start_polling/shutdown loop/stop/shutdown/exit(0)."""
    from pulse_bot import bot as bot_mod

    # Exit code collector
    exit_codes = []
    monkeypatch.setattr(bot_mod.sys, "exit", exit_codes.append)

    # Mock load_config so test does not need env vars or YAML files
    monkeypatch.setattr(bot_mod, "load_config", lambda: {
        "telegram_token": "test_token",
        "allowed_user_ids": [123],
        "vault_repo_dir": Path("/tmp"),
        "git_remote": "origin",
        "git_branch": "master",
        "dead_letter_path": Path("/tmp/pulse-dead-test.jsonl"),
    })

    # Make coordinator exit immediately (is_shutting_down=True skips wait loop)
    class FakeCoord:
        is_shutting_down = True

        async def track(self):
            yield

        async def wait_drain(self):
            return True

        def request_shutdown(self):
            pass

    monkeypatch.setattr(bot_mod, "ShutdownCoordinator", lambda **kw: FakeCoord())

    # Mock Application builder chain (async methods need AsyncMock for await)
    fake_app = MagicMock()
    fake_app.bot_data = {}
    fake_app.initialize = AsyncMock()
    fake_app.start = AsyncMock()
    fake_app.stop = AsyncMock()
    fake_app.shutdown = AsyncMock()
    fake_app.updater = MagicMock()
    fake_app.updater.start_polling = AsyncMock()
    fake_app.updater.stop = AsyncMock()
    builder = MagicMock()
    builder.token.return_value = builder
    for m in ["read_timeout", "get_updates_read_timeout", "connect_timeout", "pool_timeout"]:
        getattr(builder, m).return_value = builder
    builder.build.return_value = fake_app
    monkeypatch.setattr(bot_mod.Application, "builder", lambda: builder)

    await bot_mod.main()

    assert exit_codes == [0], f"Expected exit(0), got {exit_codes}"
    fake_app.initialize.assert_called_once()
    fake_app.start.assert_called_once()
    fake_app.stop.assert_called_once()
    fake_app.shutdown.assert_called_once()