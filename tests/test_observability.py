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


def test_watchdog_noop_without_notify_socket(monkeypatch, caplog):
    from pulse_bot.observability import WatchdogPinger

    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    pinger = WatchdogPinger()
    pinger.start()
    pinger.stop()
    assert "watchdog disabled" in caplog.text


def test_watchdog_pings_when_notify_socket_set(monkeypatch):
    from pulse_bot import observability as obs_mod
    from pulse_bot.observability import WatchdogPinger

    fake_notifications: list[str] = []

    class FakeNotifier:
        def notify(self, msg: str) -> None:
            fake_notifications.append(msg)

    monkeypatch.setattr(obs_mod.sdnotify, "SystemdNotifier", FakeNotifier)
    monkeypatch.setenv("NOTIFY_SOCKET", "/tmp/fake.sock")

    pinger = WatchdogPinger(interval=0.05)
    pinger.start()
    import time as time_mod

    time_mod.sleep(0.15)
    pinger.stop()

    assert any("WATCHDOG=1" in n for n in fake_notifications)


def test_watchdog_noop_without_sdnotify(monkeypatch):
    """WatchdogPinger.start() is a no-op when _HAS_SDNOTIFY is False."""
    from pulse_bot import observability as obs_mod
    from pulse_bot.observability import WatchdogPinger

    monkeypatch.setattr(obs_mod, "_HAS_SDNOTIFY", False)
    monkeypatch.setenv("NOTIFY_SOCKET", "/tmp/fake.sock")
    pinger = WatchdogPinger(interval=0.05)
    pinger.start()
    # Should not raise; thread should not be created
    assert pinger._thread is None or not pinger._thread.is_alive()
    pinger.stop()


def test_watchdog_uses_sdnotify_when_available(monkeypatch):
    """WatchdogPinger notifies systemd when both NOTIFY_SOCKET and sdnotify are available."""
    from pulse_bot import observability as obs_mod
    from pulse_bot.observability import WatchdogPinger

    monkeypatch.setattr(obs_mod, "_HAS_SDNOTIFY", True)
    fake_notifications: list[str] = []

    class FakeNotifier:
        def notify(self, msg: str) -> None:
            fake_notifications.append(msg)

    monkeypatch.setattr(obs_mod.sdnotify, "SystemdNotifier", lambda: FakeNotifier())
    monkeypatch.setenv("NOTIFY_SOCKET", "/tmp/fake.sock")

    pinger = WatchdogPinger(interval=0.05)
    pinger.start()
    import time

    time.sleep(0.15)
    pinger.stop()

    assert any("WATCHDOG=1" in n for n in fake_notifications)


def test_watchdog_stop_is_idempotent(monkeypatch):
    from pulse_bot import observability as obs_mod
    from pulse_bot.observability import WatchdogPinger

    class FakeNotifier:
        def notify(self, msg: str) -> None:
            pass

    monkeypatch.setattr(obs_mod.sdnotify, "SystemdNotifier", FakeNotifier)
    monkeypatch.setenv("NOTIFY_SOCKET", "/tmp/fake.sock")

    pinger = WatchdogPinger(interval=0.05)
    pinger.start()
    pinger.stop()
    pinger.stop()  # second stop must not raise
