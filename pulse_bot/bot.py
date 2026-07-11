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


def _is_authorized(user_id: int, allowed_ids) -> bool:
    # Defensive: config validation should reject non-list, but guard runtime too
    if not isinstance(allowed_ids, list):
        return False
    return user_id in allowed_ids


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
