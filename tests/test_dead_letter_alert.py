"""Tests for AlertTrigger (B4: DLQ auto-alert)."""
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pulse_bot.bot import AlertTrigger
from pulse_bot.dead_letter import DeadLetterQueue


def _make_dlq(tmp_path: Path, count: int) -> DeadLetterQueue:
    q = DeadLetterQueue(path=tmp_path / "dlq.jsonl")
    for i in range(count):
        q.append(card_path=tmp_path / f"x{i}.md", error=f"err{i}", payload={})
    return q


async def test_alert_trigger_fires_when_over_threshold(tmp_path):
    sent: list[str] = []
    dlq = _make_dlq(tmp_path, count=6)
    trigger = AlertTrigger(
        dlq=dlq, send_message=AsyncMock(side_effect=lambda m: sent.append(m)),
        threshold=5, cooldown=3600,
    )
    await trigger.check()
    assert len(sent) == 1
    assert "Dead-letter" in sent[0]
    assert "6" in sent[0]


async def test_alert_trigger_silent_when_under_threshold(tmp_path):
    sent: list[str] = []
    dlq = _make_dlq(tmp_path, count=3)
    trigger = AlertTrigger(
        dlq=dlq, send_message=AsyncMock(side_effect=lambda m: sent.append(m)),
        threshold=5, cooldown=3600,
    )
    await trigger.check()
    assert sent == []


async def test_alert_trigger_respects_cooldown(tmp_path, monkeypatch):
    sent: list[str] = []
    dlq = _make_dlq(tmp_path, count=6)
    trigger = AlertTrigger(
        dlq=dlq, send_message=AsyncMock(side_effect=lambda m: sent.append(m)),
        threshold=5, cooldown=60,
    )
    fake_time = [1000.0]
    monkeypatch.setattr("pulse_bot.bot.time.time", lambda: fake_time[0])

    await trigger.check()
    assert len(sent) == 1

    fake_time[0] += 30
    await trigger.check()
    assert len(sent) == 1

    fake_time[0] += 60
    await trigger.check()
    assert len(sent) == 2


async def test_alert_trigger_includes_recent_errors(tmp_path):
    sent: list[str] = []
    dlq = _make_dlq(tmp_path, count=6)
    dlq.append(card_path=tmp_path / "special.md", error="CRITICAL: SSH key", payload={})
    trigger = AlertTrigger(
        dlq=dlq, send_message=AsyncMock(side_effect=lambda m: sent.append(m)),
        threshold=5, cooldown=3600,
    )
    await trigger.check()
    assert any("SSH key" in m for m in sent)
