"""Logging and watchdog primitives."""
from __future__ import annotations

import logging
import os
import threading
import sys
from typing import Optional

try:
    import sdnotify
    _HAS_SDNOTIFY: bool = True
except ImportError:
    _HAS_SDNOTIFY: bool = False


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure root logger to write JSON or text records to stderr.

    Idempotent: removes previously installed handlers before adding the new one,
    preserving third-party root-level handlers.
    """
    handler = logging.StreamHandler(sys.stderr)
    if fmt == "json":
        from pythonjsonlogger import jsonlogger

        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Remove only handlers previously installed by this function (tagged).
    # Do NOT clear all handlers — that would break pytest's caplog fixture
    # and any other tool that attaches its own root-level handlers.
    for h in list(root.handlers):
        if getattr(h, "_pulse_bot_ours", False):
            root.removeHandler(h)
    handler._pulse_bot_ours = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


class WatchdogPinger:
    """Periodically sends WATCHDOG=1 to systemd via sd_notify.

    No-op when NOTIFY_SOCKET is not set (e.g., local dev without systemd).
    """

    def __init__(self, interval: float = 10.0) -> None:
        self._interval = interval
        self._stop = threading.Event()
        self._enabled = "NOTIFY_SOCKET" in os.environ
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self._enabled or not _HAS_SDNOTIFY:
            if not _HAS_SDNOTIFY:
                logging.getLogger(__name__).info("watchdog disabled (sdnotify not available)")
            elif not self._enabled:
                logging.getLogger(__name__).info("watchdog disabled (NOTIFY_SOCKET not set)")
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="watchdog-pinger")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        notifier = sdnotify.SystemdNotifier()
        while not self._stop.wait(self._interval):
            notifier.notify("WATCHDOG=1")
