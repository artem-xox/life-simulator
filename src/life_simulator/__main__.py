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
    TARGET_FPS,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from life_simulator.ui.screen import ScreenManager  # noqa: E402
from life_simulator.ui.setup_screen import SetupScreen  # noqa: E402

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    log.info("=== life-simulator starting ===")

    log.info("pygame.init()...")
    result = pygame.init()
    log.info("pygame.init() done  success=%d  failed=%d", result[0], result[1])

    log.info("creating display  %dx%d...", WINDOW_WIDTH, WINDOW_HEIGHT)
    pygame.display.set_caption(WINDOW_TITLE)
    surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
    log.info("display created  driver=%s", pygame.display.get_driver())

    clock = pygame.time.Clock()

    log.info("building SetupScreen...")
    manager = ScreenManager(SetupScreen(WINDOW_WIDTH, WINDOW_HEIGHT))
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
            elif event.type == pygame.VIDEORESIZE:
                log.info("window resized to %dx%d", event.w, event.h)
                surface = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                manager.resize(event.w, event.h)

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
