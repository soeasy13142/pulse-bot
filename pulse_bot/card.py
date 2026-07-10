"""Pulse Card generation: filename, frontmatter, body."""
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

SLUG_MAX_LEN = 50
SLUG_FALLBACK = "idea"


def make_slug(text: str) -> str:
    """Convert text to URL-safe kebab-case slug, max 50 chars."""
    # Normalize unicode (NFC form)
    text = unicodedata.normalize("NFKC", text)
    # Lowercase ASCII only
    text = text.lower()
    # Replace non-alphanumeric with hyphen
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    # Collapse whitespace and hyphens
    text = re.sub(r"[\s_]+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    # Truncate
    text = text[:SLUG_MAX_LEN].rstrip("-")
    return text if text else SLUG_FALLBACK