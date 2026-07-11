"""Tests for pulse_bot.card module (M4-T2: make_slug)."""
import pytest
from pulse_bot.card import make_slug, build_card_path, render_card
from datetime import datetime, timezone


def test_make_slug_basic_ascii():
    """ASCII 文本应转为 kebab-case."""
    assert make_slug("Hello World") == "hello-world"


def test_make_slug_chinese():
    """中文应保留但限制长度."""
    slug = make_slug("想做个 skills 管理器")
    # 中文保留或转 pinyin；最简方案：保留 unicode，去掉特殊字符
    assert len(slug) > 0
    assert len(slug) <= 50


def test_make_slug_special_chars():
    """特殊字符应替换为破折号."""
    slug = make_slug("What's up?! @#$")
    assert "?" not in slug
    assert "@" not in slug
    assert "!" not in slug


def test_make_slug_length_limit():
    """超过 50 字符应截断."""
    long_text = "a" * 100
    slug = make_slug(long_text)
    assert len(slug) <= 50


def test_make_slug_empty_after_cleanup():
    """纯特殊字符应返回 fallback 'idea'."""
    assert make_slug("!@#$%") == "idea"

def test_build_card_path_format():
    """Card path 格式: YYYY-MM-DD_HHMMSS_<slug>.md."""
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    path = build_card_path("想做个 skills 管理器", when)
    assert path.name.startswith("2026-07-09_202345_")
    assert path.name.endswith(".md")
    assert path.parent.name == "_pulse"


def test_build_card_path_no_collision_same_text_same_instant():
    """Same text + same `when` must produce DIFFERENT paths (UUID suffix guarantees this)."""
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    p1 = build_card_path("hello world", when)
    p2 = build_card_path("hello world", when)
    assert p1 != p2, f"Same-instant same-text paths must differ; both were {p1}"

def test_render_card_includes_required_fields():
    """渲染的卡片包含所有必填 frontmatter 字段."""
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    card = render_card("想做个 skills 管理器", user_id=12345, intent="idea", when=when)
    assert "tags:" in card
    assert "- pulse" in card
    assert "- inbox" in card
    assert "status: pulse" in card
    assert 'source: "telegram:12345"' in card
    assert "intent: idea" in card
    assert "raw_text:" in card
    assert "想做个 skills 管理器" in card

def test_render_card_includes_timestamp():
    """渲染的卡片包含原始消息段."""
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    card = render_card("测试消息", user_id=999, intent="task", when=when)
    assert "### 原始消息" in card
    assert "测试消息" in card
    assert "### 后续处理" in card


def test_render_card_multiline_yaml_parsable():
    """Multi-line text must produce a frontmatter block that yaml.safe_load can parse.

    Regression for: `raw_text: |\\n  {text}` only indented first line; subsequent lines
    had 0 indent → YAML parser saw them as top-level keys, breaking the card.
    """
    import yaml
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    multiline_text = "第一行\n第二行 with details\n第三行 ending"
    card = render_card(multiline_text, user_id=12345, intent="idea", when=when)

    # Extract frontmatter (between first --- and second ---)
    parts = card.split("---", 2)
    assert len(parts) >= 3, "Card must have valid frontmatter delimiters"
    fm = yaml.safe_load(parts[1])

    # All lines must be preserved under raw_text
    assert "raw_text" in fm, f"raw_text missing from parsed frontmatter: {fm}"
    assert "第一行" in fm["raw_text"]
    assert "第二行 with details" in fm["raw_text"]
    assert "第三行 ending" in fm["raw_text"]
    # Other expected fields still parse cleanly
    assert fm["intent"] == "idea"
    assert fm["source"] == "telegram:12345"


def test_render_card_multiline_with_trailing_newline():
    """Trailing newline must not break YAML parsing."""
    import yaml
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    card = render_card("line1\nline2\n", user_id=1, intent="task", when=when)
    parts = card.split("---", 2)
    assert len(parts) >= 3
    fm = yaml.safe_load(parts[1])
    assert "raw_text" in fm
    assert "line1" in fm["raw_text"]
    assert "line2" in fm["raw_text"]
