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
