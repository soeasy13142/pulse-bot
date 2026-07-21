"""Bot lifecycle primitives: graceful shutdown + signal handlers."""
from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ShutdownInProgress(Exception):
    """Raised when a new task is submitted after shutdown was requested."""


class ShutdownCoordinator:
    """Tracks in-flight coroutines and provides drain semantics.

    Usage in bot.py:
        async with coordinator.track():
            await handle_message(update, context)

    On SIGTERM, call request_shutdown(); the main loop then awaits wait_drain()
    before exiting cleanly.
    """

    def __init__(self, drain_timeout: float = 30.0) -> None:
        self._inflight = 0
        self._event = asyncio.Event()
        self._drain_timeout = drain_timeout
        self._shutting_down = False
        self._event.set()  # idle → event is "set" so wait_drain returns immediately

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    def request_shutdown(self) -> None:
        if not self._shutting_down:
            logger.info("shutdown requested")
        self._shutting_down = True

    @asynccontextmanager
    async def track(self):
        if self._shutting_down:
            raise ShutdownInProgress("bot is shutting down")
        self._inflight += 1
        self._event.clear()
        try:
            yield
        finally:
            self._inflight -= 1
            if self._inflight == 0:
                self._event.set()

    async def wait_drain(self) -> bool:
        if self._inflight == 0:
            return True
        try:
            await asyncio.wait_for(self._event.wait(), timeout=self._drain_timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning("drain timeout reached; %d tasks still in-flight", self._inflight)
            return False


def register_signal_handlers(
    loop: asyncio.AbstractEventLoop, coord: ShutdownCoordinator
) -> None:
    """Install asyncio-native SIGTERM/SIGINT handlers that request shutdown.

    No-op on platforms that don't support add_signal_handler (e.g., Windows).
    """
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, coord.request_shutdown)
        except NotImplementedError:
            logger.warning("signal handling not supported on this platform")
            return  # one failure -> all will fail; stop early
