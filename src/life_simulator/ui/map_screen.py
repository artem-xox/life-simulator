"""Stage-1 map viewer: generate a world and explore it with pan/zoom.

This is a stepping stone toward the full simulation screen. It exists so the
world generation and camera can be inspected interactively before entities are
added in later stages.

Controls:
    * left-drag .......... pan
    * mouse wheel ........ zoom toward cursor
    * R .................. regenerate with a new random seed
    * F .................. fit the whole world to the screen
"""

from __future__ import annotations

import random

import pygame

from life_simulator.config.settings import BACKGROUND_COLOR
from life_simulator.simulation.worldgen import WorldConfig, generate
from life_simulator.ui.camera import Camera
from life_simulator.ui.render import WorldRenderer
from life_simulator.ui.screen import Screen


class MapScreen(Screen):
    def __init__(self, width: int, height: int, config: WorldConfig | None = None) -> None:
        self._screen_w = width
        self._screen_h = height
        self.config = config or WorldConfig(seed=random.randint(0, 2**31 - 1))

        self.world = generate(self.config)
        self.renderer = WorldRenderer(self.world)
        self.camera = Camera(
            world_w=self.world.width,
            world_h=self.world.height,
            screen_w=width,
            screen_h=height,
        )

        self._dragging = False
        self._font = pygame.font.SysFont("menlo,consolas,monospace", 16)

    # --- World lifecycle ---------------------------------------------------

    def _regenerate(self, seed: int | None = None) -> None:
        self.config.seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        self.world = generate(self.config)
        self.renderer.set_world(self.world)
        self.camera = Camera(
            world_w=self.world.width,
            world_h=self.world.height,
            screen_w=self._screen_w,
            screen_h=self._screen_h,
        )

    # --- Screen protocol ---------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._dragging = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            dx, dy = event.rel
            self.camera.pan_pixels(dx, dy)
        elif event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            factor = 1.15**event.y
            self.camera.zoom_at(factor, mx, my)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self._regenerate()
            elif event.key == pygame.K_f:
                self.camera.fit_to_screen()

    def update(self, dt: float) -> Screen | None:
        return None

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BACKGROUND_COLOR)
        self.renderer.draw(surface, self.camera)
        self._draw_hud(surface)

    def resize(self, width: int, height: int) -> None:
        self._screen_w = width
        self._screen_h = height
        self.camera.resize(width, height)

    # --- HUD ---------------------------------------------------------------

    def _draw_hud(self, surface: pygame.Surface) -> None:
        lines = [
            f"seed: {self.config.seed}",
            f"size: {self.world.width}x{self.world.height}  zoom: {self.camera.zoom:.1f}px/cell",
            "drag=pan  wheel=zoom  R=regenerate  F=fit",
        ]
        y = 8
        for line in lines:
            shadow = self._font.render(line, True, (0, 0, 0))
            text = self._font.render(line, True, (235, 235, 235))
            surface.blit(shadow, (11, y + 1))
            surface.blit(text, (10, y))
            y += 20
