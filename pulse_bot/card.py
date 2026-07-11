"""Pulse Card generation: filename, frontmatter, body."""
import re
import unicodedata
import uuid
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

def build_card_path(text: str, when: datetime) -> Path:
    """Build full path for a Pulse Card: 00_Inbox/_pulse/<timestamp>_<uuid>_<slug>.md."""
    ts = when.strftime("%Y-%m-%d_%H%M%S")
    slug = make_slug(text)
    suffix = uuid.uuid4().hex[:6]
    filename = f"{ts}_{suffix}_{slug}.md"
    return Path("00_Inbox/_pulse") / filename


def render_card(text: str, user_id: int, intent: str, when: datetime) -> str:
    """Render full Pulse Card markdown content."""
    ts_iso = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_human = when.strftime("%Y-%m-%d %H:%M")
    first_line = text.strip().split("\n")[0][:80]
    safe_first_line = first_line.replace('"', '\\"')

    frontmatter = f"""---
tags:
  - pulse
  - inbox
created: {ts_iso}
updated: {ts_iso}
source: "telegram:{user_id}"
status: pulse
raw_text: |
  {text.replace(chr(10), chr(10) + "  ")}
intent: {intent}
captured_at: {ts_iso}
---

## {safe_first_line}

> 这是 {ts_human} 通过 Telegram 捕获的碎片想法。
> 尚未规范化。处理时调用 vault-enhance 或手动编辑。

### 原始消息
{text}

### 后续处理
<!-- 在这里由人或 agent 补：tags、链接、关联计划等 -->
"""
    return frontmatter
