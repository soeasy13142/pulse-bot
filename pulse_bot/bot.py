"""Pulse Bot main module: Telegram listener and dispatcher."""
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

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
from pulse_bot.lifecycle import ShutdownCoordinator, ShutdownInProgress, register_signal_handlers
from pulse_bot.observability import setup_logging, WatchdogPinger

logger = logging.getLogger(__name__)

# In-memory recent cards for /recent command
_recent_cards: list[dict] = []


# /recent command defaults and bounds
RECENT_DEFAULT_N = 10
RECENT_MIN_N = 1
RECENT_MAX_N = 20
RECENT_USAGE = f"Usage: /recent [N] where {RECENT_MIN_N} <= N <= {RECENT_MAX_N}"


def _get_dead_letter(config: dict) -> DeadLetterQueue:
    """Build the dead-letter queue using the path from loaded config.

    Path resolution order (config already merged YAML + env by load_config):
    1. config['dead_letter_path'] (already Path instance)
    Falls back to /opt/pulse-bot/dead_letter.jsonl if config did not provide it.
    """
    path = config.get("dead_letter_path") or Path("/opt/pulse-bot/dead_letter.jsonl")
    return DeadLetterQueue(path=Path(path))


def _is_authorized(user_id: int, allowed_ids) -> bool:
    # Defensive: config validation should reject non-list, but guard runtime too
    if not isinstance(allowed_ids, list):
        return False
    return user_id in allowed_ids


async def _handle_message_impl(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle plain text message: create a Pulse Card (unwrapped)."""
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
        dl = _get_dead_letter(config)
        sync_for_flush = GitSync(
            repo_dir=config["vault_repo_dir"],
            remote_name=config["git_remote"],
            branch=config["git_branch"],
        )
        flushed = dl.flush(sync_for_flush)
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
        dl = _get_dead_letter(config)
        dl.enqueue(str(full_path), f"pulse: {first_line}", error="push failed after retries")
        await update.message.reply_text(
            "⚠ Saved locally but push failed. Will retry automatically. "
            "Run `git pull --rebase --autostash` on VPS or check docs/runbook.md."
        )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle plain text message: wrap with coordinator tracking."""
    coord: ShutdownCoordinator = context.bot_data["coordinator"]
    async with coord.track():
        await _handle_message_impl(update, context)


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List recent Pulse Cards (count optional via first arg, default 10, range 1..20)."""
    config = load_config()
    if not _is_authorized(update.effective_user.id, config["allowed_user_ids"]):
        await update.message.reply_text("Unauthorized. Ask the owner to add your user_id.")
        return

    # Parse optional N argument
    n = RECENT_DEFAULT_N
    if context.args:
        if len(context.args) > 1:
            await update.message.reply_text(RECENT_USAGE)
            return
        try:
            parsed = int(context.args[0])
        except ValueError:
            await update.message.reply_text(RECENT_USAGE)
            return
        if not (RECENT_MIN_N <= parsed <= RECENT_MAX_N):
            await update.message.reply_text(RECENT_USAGE)
            return
        n = parsed

    if not _recent_cards:
        await update.message.reply_text("No recent cards.")
        return

    lines = ["Recent Pulse Cards:"]
    for i, card in enumerate(_recent_cards[:n], 1):
        first_line = card["text"].split("\n")[0][:40]
        lines.append(f"{i}. [{card['intent']}] {first_line}")
    await update.message.reply_text("\n".join(lines))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help text."""
    help_text = """Pulse Bot commands:

/p <text> - Create a Pulse Card (or just send plain text)
/recent [N] - List recent N cards (default 10, 1-20)
/help - Show this message

Capture takes <10 seconds. Just send your idea!
"""
    await update.message.reply_text(help_text)


def _flush_dead_letters(sync: GitSync, dl: DeadLetterQueue) -> int:
    """Flush pending dead letters. Returns number flushed."""
    return dl.flush(sync)


class AlertTrigger:
    """Checks DLQ size and sends a Telegram alert when over threshold.

    Cooldown is tracked in-memory; acceptable because bot restart resets it
    and startup will re-alert if the DLQ is still over threshold.
    """

    def __init__(
        self,
        dlq: "DeadLetterQueue",
        send_message: Callable[[str], Awaitable[None]],
        threshold: int = 5,
        cooldown: float = 3600.0,
    ) -> None:
        self._dlq = dlq
        self._send = send_message
        self._threshold = threshold
        self._cooldown = cooldown
        self._last_alert_at: float = 0.0

    async def check(self) -> None:
        count = self._dlq.length() if hasattr(self._dlq, "length") else self._count_lines()
        if count < self._threshold:
            return
        now = time.time()
        if now - self._last_alert_at < self._cooldown:
            return
        self._last_alert_at = now
        try:
            msg = self._format_alert(count)
            await self._send(msg)
        except Exception:
            logger.exception("failed to send DLQ alert")

    def _count_lines(self) -> int:
        try:
            with open(self._dlq.path) as f:
                return sum(1 for _ in f)
        except FileNotFoundError:
            return 0

    def _format_alert(self, count: int) -> str:
        recent = self._dlq.tail(5) if hasattr(self._dlq, "tail") else []
        lines = [
            "⚠ Dead-letter queue alert",
            f"File: {self._dlq.path}",
            f"Entries: {count}",
        ]
        if recent:
            lines.append("Recent errors:")
            for entry in recent:
                lines.append(f"  - {entry.get('error', '?')}")
        lines.append("Inspect: sudo tail -20 " + str(self._dlq.path))
        return "\n".join(lines)


async def main() -> None:
    """Entry point."""
    config = load_config()
    setup_logging(level=config.get("log_level", "INFO"), fmt=config.get("log_format", "json"))

    coord = ShutdownCoordinator(drain_timeout=config.get("shutdown_timeout", 30.0))
    loop = asyncio.get_running_loop()
    register_signal_handlers(loop, coord)

    pinger = WatchdogPinger(interval=10.0)
    pinger.start()

    # Flush dead letters on startup
    try:
        dl = _get_dead_letter(config)
        sync = GitSync(
            repo_dir=config["vault_repo_dir"],
            remote_name=config["git_remote"],
            branch=config["git_branch"],
        )
        flushed = _flush_dead_letters(sync, dl)
        if flushed:
            logger.info("Startup: flushed %d dead letter(s)", flushed)
    except Exception:
        logger.exception("Startup dead letter flush failed (non-fatal)")

    # AlertTrigger: DLQ monitoring and notification
    dlq = _get_dead_letter(config)

    async def _send_to_owner(text: str) -> None:
        owner = config["allowed_user_ids"][0]
        await application.bot.send_message(chat_id=owner, text=text)

    trigger = AlertTrigger(
        dlq=dlq,
        send_message=_send_to_owner,
        threshold=config.get("dlq_alert_threshold", 5),
        cooldown=float(config.get("dlq_alert_cooldown", 3600)),
    )
    dlq._on_new_entry = lambda: asyncio.create_task(trigger.check())
    await trigger.check()  # startup check

    application = Application.builder().token(config["telegram_token"]).build()
    application.bot_data["coordinator"] = coord

    # Command handlers
    application.add_handler(CommandHandler("p", handle_message))
    application.add_handler(CommandHandler("recent", recent_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", help_command))

    # Plain text → pulse card
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Pulse Bot starting...")
    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()

        # Wait for shutdown
        while not coord.is_shutting_down:
            await asyncio.sleep(0.5)

        # Drain
        drained = await coord.wait_drain()
    finally:
        pinger.stop()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

    sys.exit(0 if drained else 1)


if __name__ == "__main__":
    asyncio.run(main())
