"""Smoke tests: the app opens a window and runs a few frames.

These drive the real screens through pygame's dummy video driver, so they
catch a broken window mode or a screen that cannot draw without needing a
display attached.
"""

from __future__ import annotations

import os

import pygame
import pytest

from life_simulator.config.settings import WINDOW_HEIGHT, WINDOW_WIDTH


@pytest.fixture(name="display")
def _display():
    """Initialise a headless pygame display and tear it down afterwards."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    try:
        yield
    finally:
        pygame.display.quit()


@pytest.mark.usefixtures("display")
def test_windowed_mode_uses_the_configured_size() -> None:
    from life_simulator.__main__ import _open_display

    assert _open_display(fullscreen=False).get_size() == (WINDOW_WIDTH, WINDOW_HEIGHT)


@pytest.mark.usefixtures("display")
def test_fullscreen_mode_fills_the_desktop() -> None:
    from life_simulator.__main__ import _open_display

    assert _open_display(fullscreen=True).get_size() == pygame.display.get_desktop_sizes()[0]


@pytest.mark.usefixtures("display")
def test_setup_screen_runs_and_draws() -> None:
    from life_simulator.ui.screen import ScreenManager
    from life_simulator.ui.setup_screen import SetupScreen

    surface = pygame.display.set_mode((800, 600))
    manager = ScreenManager(SetupScreen(800, 600))

    for _ in range(3):
        manager.update(1 / 60)
        manager.draw(surface)


@pytest.mark.usefixtures("display")
def test_sim_screen_ticks_and_draws() -> None:
    from life_simulator.simulation.ecosystem import SpeciesConfig
    from life_simulator.simulation.entity import Diet
    from life_simulator.simulation.worldgen import WorldConfig
    from life_simulator.ui.sim_screen import SimScreen

    surface = pygame.display.set_mode((800, 600))
    screen = SimScreen(
        800,
        600,
        WorldConfig(seed=3, width=96, height=72),
        [SpeciesConfig(Diet.HERBIVORE, 20), SpeciesConfig(Diet.CARNIVORE, 3)],
    )

    # Long enough to cross the tick interval at the default simulation speed.
    for _ in range(20):
        screen.update(0.1)
        screen.draw(surface)

    assert screen.ecosystem.tick_count > 0
