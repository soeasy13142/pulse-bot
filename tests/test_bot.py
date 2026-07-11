"""Tests for bot.py command parsing and authorization."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pulse_bot.bot import _is_authorized, handle_message, recent_command, help_command


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
    return MagicMock()


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


async def test_handle_message_push_fails(tmp_path):
    """If commit_and_push returns False, user sees push failure warning."""
    update = _make_update(user_id=12345, text="hello world")
    context = _make_context()

    with patch("pulse_bot.bot.load_config", return_value={
        "telegram_token": "x", "allowed_user_ids": [12345],
        "vault_repo_dir": tmp_path, "git_remote": "origin", "git_branch": "master",
    }), patch("pulse_bot.bot.GitSync") as mock_sync:
        mock_sync.return_value.commit_and_push.return_value = False
        await handle_message(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "push failed" in msg
    assert "pulse-pull.sh" in msg  # honest pointer to manual recovery path