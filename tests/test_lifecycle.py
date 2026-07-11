import asyncio
import signal

import pytest

from pulse_bot.lifecycle import (
    ShutdownCoordinator,
    ShutdownInProgress,
    register_signal_handlers,
)


async def test_track_yields_when_not_shutting_down():
    coord = ShutdownCoordinator()
    async with coord.track():
        pass  # no exception


async def test_track_rejects_after_request_shutdown():
    coord = ShutdownCoordinator()
    coord.request_shutdown()
    with pytest.raises(ShutdownInProgress):
        async with coord.track():
            pass


async def test_wait_drain_returns_true_when_idle():
    coord = ShutdownCoordinator()
    assert await coord.wait_drain() is True


async def test_wait_drain_waits_for_inflight_to_finish():
    coord = ShutdownCoordinator()
    finished = asyncio.Event()

    async def worker():
        async with coord.track():
            await asyncio.sleep(0.05)
            finished.set()

    asyncio.create_task(worker())
    await asyncio.sleep(0.01)
    drained = await coord.wait_drain()
    assert drained is True
    assert finished.is_set()


async def test_wait_drain_returns_false_on_timeout():
    coord = ShutdownCoordinator(drain_timeout=0.05)

    async def slow():
        async with coord.track():
            await asyncio.sleep(1.0)

    asyncio.create_task(slow())
    await asyncio.sleep(0.01)
    drained = await coord.wait_drain()
    assert drained is False


async def test_is_shutting_down_flips_after_request():
    coord = ShutdownCoordinator()
    assert coord.is_shutting_down is False
    coord.request_shutdown()
    assert coord.is_shutting_down is True


def test_register_signal_handlers_invokes_request_shutdown(monkeypatch):
    coord = ShutdownCoordinator()
    loop = asyncio.new_event_loop()
    captured: dict[int, object] = {}

    def fake_add_signal_handler(sig, handler):
        captured[sig] = handler

    monkeypatch.setattr(loop, "add_signal_handler", fake_add_signal_handler)
    register_signal_handlers(loop, coord)

    assert signal.SIGTERM in captured
    assert signal.SIGINT in captured

    captured[signal.SIGTERM]()  # simulate signal
    assert coord.is_shutting_down is True
    loop.close()
