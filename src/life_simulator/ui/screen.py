"""Screen base class and a tiny stack-free screen manager.

A :class:`Screen` owns its own event handling, update and draw logic. The
:class:`ScreenManager` keeps one active screen and lets screens request a
transition by returning a new screen from :meth:`Screen.update`.
"""

from __future__ import annotations

from collections.abc import Sequence

import pygame


class Screen:
    """Abstract base for a full-window UI state."""

    def handle_event(self, event: pygame.event.Event) -> None:
        """React to a single pygame event."""

    def update(self, dt: float) -> Screen | None:
        """Advance state by ``dt`` seconds.

        Returns a new :class:`Screen` to switch to, or ``None`` to stay.
        """
        return None

    def draw(self, surface: pygame.Surface) -> None:
        """Render the screen onto ``surface``."""

    def resize(self, width: int, height: int) -> None:
        """Handle a change in window size."""


class ScreenManager:
    """Drives the currently active screen and performs transitions."""

    def __init__(self, initial: Screen) -> None:
        self._current = initial

    @property
    def current(self) -> Screen:
        return self._current

    def handle_events(self, events: Sequence[pygame.event.Event]) -> None:
        for event in events:
            self._current.handle_event(event)

    def update(self, dt: float) -> None:
        next_screen = self._current.update(dt)
        if next_screen is not None and next_screen is not self._current:
            self._current = next_screen

    def draw(self, surface: pygame.Surface) -> None:
        self._current.draw(surface)

    def resize(self, width: int, height: int) -> None:
        self._current.resize(width, height)
