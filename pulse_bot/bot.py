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

logger = logging.getLogger(__name__)

# In-memory recent cards for /recent command
_recent_cards: list[dict] = []


def _is_authorized(user_id: int, allowed_ids: list[int]) -> bool:
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

    when = datetime.now(timezone.utc)
    intent = infer_intent(text)

    # Render card
    card_content = render_card(text, user_id=user_id, intent=intent, when=when)

    # Build path and write
    card_path = build_card_path(text, when)
    full_path = config["vault_repo_dir"] / card_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(card_content, encoding="utf-8")

    # Commit + push
    sync = GitSync(
        repo_dir=config["vault_repo_dir"],
        remote_name=config["git_remote"],
        branch=config["git_branch"],
    )
    first_line = text.split("\n")[0][:50]
    success = sync.commit_and_push(full_path, message=f"pulse: {first_line}")

    # Track in memory
    _recent_cards.insert(0, {
        "path": str(card_path),
        "text": text,
        "intent": intent,
        "when": when.isoformat(),
    })
    if len(_recent_cards) > 20:
        _recent_cards.pop()

    if success:
        await update.message.reply_text(f"✓ Captured: {first_line}")
    else:
        await update.message.reply_text("⚠ Saved locally but push failed. Will retry.")


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List recent Pulse Cards."""
    if not _recent_cards:
        await update.message.reply_text("No recent cards.")
        return

    lines = ["Recent Pulse Cards:"]
    for i, card in enumerate(_recent_cards[:10], 1):
        first_line = card["text"].split("\n")[0][:40]
        lines.append(f"{i}. [{card['intent']}] {first_line}")
    await update.message.reply_text("\n".join(lines))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help text."""
    help_text = """Pulse Bot commands:

/p <text> - Create a Pulse Card (or just send plain text)
/recent [N] - List recent N cards (default 10)
/promote <card-id> - Promote a card to a real note (TODO: M4-T8)
/dashboard - Link to Obsidian dashboard
/help - Show this message

Capture takes <10 seconds. Just send your idea!
"""
    await update.message.reply_text(help_text)


def main() -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    config = load_config()

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
