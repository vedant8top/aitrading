"""Graceful shutdown: handles CTRL+C, KeyboardInterrupt, SIGTERM."""

from __future__ import annotations

import logging
import os
import signal
import sys
from typing import Any, Callable, Optional

logger = logging.getLogger("runtime.graceful_shutdown")


class GracefulShutdown:
    """Handles graceful shutdown signals and persists final state.

    Handles:
    - CTRL+C (KeyboardInterrupt)
    - SIGTERM
    - Custom shutdown callbacks
    """

    def __init__(self) -> None:
        self._shutdown_requested = False
        self._callbacks: list[Callable[[], Any]] = []
        self._original_sigint: Any = None
        self._original_sigterm: Any = None

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def register(self, callback: Callable[[], Any]) -> None:
        """Register a shutdown callback."""
        self._callbacks.append(callback)
        logger.debug("Shutdown callback registered: %s", callback.__name__)

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle shutdown signal."""
        if self._shutdown_requested:
            logger.warning("Second shutdown signal received, forcing exit")
            sys.exit(1)

        self._shutdown_requested = True
        signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        logger.info("Received %s, initiating graceful shutdown...", signal_name)

        for callback in self._callbacks:
            try:
                callback()
                logger.info("Shutdown callback executed: %s", callback.__name__)
            except Exception as e:
                logger.error("Shutdown callback failed: %s", e)

        logger.info("Graceful shutdown complete")

    def install(self) -> None:
        """Install signal handlers."""
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)

        signal.signal(signal.SIGINT, self._handle_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._handle_signal)

        logger.info("Shutdown signal handlers installed")

    def uninstall(self) -> None:
        """Restore original signal handlers."""
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)
        logger.info("Shutdown signal handlers restored")