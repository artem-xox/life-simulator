"""Entry point: window, main loop and the screen manager.

Run with ``uv run python -m life_simulator`` or via the ``life-sim`` script.

Default world and species configurations live here for now; a setup screen
(stage 4) will let the player configure them interactively.
"""

from __future__ import annotations

# Logging must be configured before any other local import so that modules
# which create module-level loggers pick up the right handler.
from life_simulator.config.log import setup as _setup_logging

_setup_logging()

import logging  # noqa: E402  (after log setup)

import pygame  # noqa: E402

from life_simulator.config.settings import (  # noqa: E402
    START_FULLSCREEN,
    TARGET_FPS,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from life_simulator.ui.screen import ScreenManager  # noqa: E402
from life_simulator.ui.setup_screen import SetupScreen  # noqa: E402

log = logging.getLogger(__name__)


def _open_display(fullscreen: bool) -> pygame.Surface:
    """Open (or reopen) the window, either fullscreen or windowed.

    Fullscreen asks for size ``(0, 0)``, which hands SDL the desktop and gets a
    borderless window the size of the usable screen. On macOS that means the
    menu bar is hidden and the app gets its own Space — a borderless window at
    the raw desktop size would instead be overlapped by the menu bar, hiding
    the top of the HUD.
    """
    if fullscreen:
        surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)

    log.info("opening display  %dx%d  fullscreen=%s", *surface.get_size(), fullscreen)
    return surface


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    log.info("=== life-simulator starting ===")

    log.info("pygame.init()...")
    result = pygame.init()
    log.info("pygame.init() done  success=%d  failed=%d", result[0], result[1])

    pygame.display.set_caption(WINDOW_TITLE)
    fullscreen = START_FULLSCREEN
    surface = _open_display(fullscreen)
    log.info("display created  driver=%s", pygame.display.get_driver())

    clock = pygame.time.Clock()

    log.info("building SetupScreen...")
    manager = ScreenManager(SetupScreen(*surface.get_size()))
    log.info("entering main loop  target_fps=%d", TARGET_FPS)

    frame = 0
    running = True
    while running:
        dt = clock.tick(TARGET_FPS) / 1000.0

        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                log.info("QUIT event received")
                running = False
            elif event.type == pygame.VIDEORESIZE and not fullscreen:
                log.info("window resized to %dx%d", event.w, event.h)
                surface = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                manager.resize(event.w, event.h)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                fullscreen = not fullscreen
                surface = _open_display(fullscreen)
                manager.resize(*surface.get_size())

        manager.handle_events(events)
        manager.update(dt)
        manager.draw(surface)
        pygame.display.flip()

        frame += 1
        if frame == 1:
            fps = clock.get_fps()
            log.info("first frame rendered  fps=%.1f", fps)
        elif frame % 300 == 0:
            fps = clock.get_fps()
            eco = getattr(manager.current, "ecosystem", None)
            if eco is not None:
                log.info(
                    "frame=%d  fps=%.1f  tick=%d  herb=%d  carn=%d",
                    frame,
                    fps,
                    eco.tick_count,
                    eco.herbivore_count,
                    eco.carnivore_count,
                )
            else:
                log.info("frame=%d  fps=%.1f  (setup screen)", frame, fps)

    log.info("pygame.quit()")
    pygame.quit()
    log.info("=== life-simulator stopped ===")


if __name__ == "__main__":
    main()
