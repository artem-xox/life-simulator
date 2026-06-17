"""Centralised logging configuration.

Call ``setup()`` once at process startup (before any other imports that might
log). After that, every module can do::

    import logging
    log = logging.getLogger(__name__)
    log.info("...")

Log output goes to stderr with millisecond timestamps so you can see exactly
which step is slow or missing when the app hangs.
"""

from __future__ import annotations

import logging
import sys


def setup(level: int = logging.DEBUG) -> None:
    """Configure the root logger with a timestamp+module format."""
    fmt = "%(asctime)s.%(msecs)03d  %(levelname)-7s  %(name)s  %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format=fmt,
        datefmt=datefmt,
        force=True,
    )
    # Quiet down noisy third-party libraries.
    logging.getLogger("pygame").setLevel(logging.WARNING)
