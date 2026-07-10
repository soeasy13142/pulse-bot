"""Tests for pulse_bot.card module (M4-T2: make_slug)."""
import pytest
from pulse_bot.card import make_slug


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