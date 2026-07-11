"""Tests for pulse_bot.observability."""
from __future__ import annotations

import json
import logging

import pytest

from pulse_bot.observability import setup_logging


def test_setup_logging_json_format_writes_valid_json(capsys):
    setup_logging(level="INFO", fmt="json")
    logger = logging.getLogger("pulse_bot.test_json")
    logger.info("hello", extra={"user_id": 123})

    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    record = json.loads(line)
    assert record["message"] == "hello"
    assert record["level"] == "INFO"
    assert record["logger"] == "pulse_bot.test_json"
    assert record["user_id"] == 123


def test_setup_logging_text_format_writes_plain_text(capsys):
    setup_logging(level="INFO", fmt="text")
    logger = logging.getLogger("pulse_bot.test_text")
    logger.info("plain message")

    captured = capsys.readouterr()
    assert "plain message" in captured.err
    assert "{user_id" not in captured.err  # not a format string


def test_setup_logging_respects_level(caplog):
    setup_logging(level="WARNING", fmt="text")
    logger = logging.getLogger("pulse_bot.test_level")
    logger.info("should not appear")
    logger.warning("should appear")
    assert "should not appear" not in caplog.text
    assert "should appear" in caplog.text


def test_setup_logging_clears_existing_handlers():
    setup_logging(level="INFO", fmt="json")
    root = logging.getLogger()
    handlers_after = len(root.handlers)
    setup_logging(level="INFO", fmt="json")
    assert len(logging.getLogger().handlers) == handlers_after  # idempotent
