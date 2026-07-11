"""Logging and watchdog primitives."""
from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure root logger to write JSON or text records to stderr.

    Idempotent: clears existing handlers before installing new ones.
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
