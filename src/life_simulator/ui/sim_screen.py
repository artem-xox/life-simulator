"""SimScreen: the main simulation view.

Combines the world map, entity rendering, a HUD overlay, and interactive
camera controls into one screen. The simulation loop is decoupled from the
render rate: ``ticks_per_second`` ticks are accumulated per real second,
with a per-frame cap to avoid spiral-of-death when the simulation is slow.

Controls:
    * left-drag / arrow keys .... pan
    * mouse wheel ............... zoom toward cursor
    * Space ..................... pause / resume
    * ] / [ .................... speed up / slow down
    * F ......................... fit world to screen
    * R ......................... restart with a new random seed (same species)
"""

from __future__ import annotations

import logging
import random

import pygame

from life_simulator.config.settings import BACKGROUND_COLOR, SIM_SPEED_OPTIONS
from life_simulator.simulation.ecosystem import Ecosystem, SpeciesConfig
from life_simulator.simulation.worldgen import WorldConfig
from life_simulator.ui.camera import Camera
from life_simulator.ui.render import WorldRenderer, draw_entities
from life_simulator.ui.screen import Screen

log = logging.getLogger(__name__)

# Maximum simulation ticks processed in a single rendered frame.  Prevents
# the loop from freezing the window when the sim runs faster than real-time.
_MAX_STEPS_PER_FRAME = 40

# Colours used in the HUD.
_HUD_TEXT = (230, 230, 230)
_HUD_SHADOW = (0, 0, 0)
_HUD_HERB = (110, 210, 80)
_HUD_CARN = (220, 55, 35)
_HUD_PAUSED = (240, 200, 60)


class SimScreen(Screen):
    """Main simulation screen: world + entities + HUD + camera."""

    def __init__(
        self,
        width: int,
        height: int,
        world_cfg: WorldConfig,
        species: list[SpeciesConfig],
    ) -> None:
        self._width = width
        self._height = height
        self._world_cfg = world_cfg
        self._species = species

        log.info("SimScreen init  %dx%d px", width, height)
        log.info("creating ecosystem (pump_events=True to keep window alive)...")
        self.ecosystem = Ecosystem.create(world_cfg, species, pump_events=True)

        log.info("building terrain render surface...")
        self._renderer = WorldRenderer(self.ecosystem.world)

        log.info("setting up camera...")
        self._camera = Camera(
            world_w=self.ecosystem.world.width,
            world_h=self.ecosystem.world.height,
            screen_w=width,
            screen_h=height,
        )

        self._paused = False
        self._speed_idx: int = 1  # index into SIM_SPEED_OPTIONS
        self._accumulator: float = 0.0
        self._dragging = False
        self._next_screen: Screen | None = None
        self._font = pygame.font.SysFont("menlo,consolas,monospace", 16)
        self._font_large = pygame.font.SysFont("menlo,consolas,monospace", 20)
        log.info("SimScreen ready — entering main loop")

    @property
    def _tps(self) -> int:
        return SIM_SPEED_OPTIONS[self._speed_idx]

    # --- Screen protocol --------------------------------------------------- #

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._dragging = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            dx, dy = event.rel
            self._camera.pan_pixels(dx, dy)
        elif event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            self._camera.zoom_at(1.15**event.y, mx, my)
        elif event.type == pygame.KEYDOWN:
            self._handle_key(event.key)

    def _handle_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            from life_simulator.ui.setup_screen import SetupScreen

            log.info("ESC pressed — returning to setup menu")
            self._next_screen = SetupScreen(self._width, self._height)
        elif key == pygame.K_SPACE:
            self._paused = not self._paused
        elif key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_PLUS):
            self._speed_idx = min(self._speed_idx + 1, len(SIM_SPEED_OPTIONS) - 1)
        elif key in (pygame.K_LEFTBRACKET, pygame.K_MINUS):
            self._speed_idx = max(self._speed_idx - 1, 0)
        elif key == pygame.K_f:
            self._camera.fit_to_screen()
        elif key == pygame.K_r:
            self._restart()

    def _restart(self) -> None:
        self._world_cfg.seed = random.randint(0, 2**31 - 1)
        self.ecosystem = Ecosystem.create(self._world_cfg, self._species)
        self._renderer.set_world(self.ecosystem.world)
        self._camera = Camera(
            world_w=self.ecosystem.world.width,
            world_h=self.ecosystem.world.height,
            screen_w=self._width,
            screen_h=self._height,
        )
        self._accumulator = 0.0

    def update(self, dt: float) -> Screen | None:
        if self._next_screen is not None:
            return self._next_screen
        if not self._paused:
            self._accumulator += dt
            step = 1.0 / self._tps
            steps = 0
            while self._accumulator >= step and steps < _MAX_STEPS_PER_FRAME:
                self.ecosystem.tick()
                self._accumulator -= step
                steps += 1
        return None

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BACKGROUND_COLOR)
        self._renderer.draw(surface, self._camera)
        draw_entities(surface, self.ecosystem.entities, self._camera)
        self._draw_hud(surface)

    def resize(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self._camera.resize(width, height)

    # --- HUD --------------------------------------------------------------- #

    def _draw_hud(self, surface: pygame.Surface) -> None:
        eco = self.ecosystem
        h_count = eco.herbivore_count
        c_count = eco.carnivore_count
        speed_str = "PAUSED" if self._paused else f"{self._tps} tps"

        lines: list[tuple[str, tuple[int, int, int]]] = [
            (f"tick  {eco.tick_count:>7}", _HUD_TEXT),
            (f"herb  {h_count:>7}", _HUD_HERB),
            (f"carn  {c_count:>7}", _HUD_CARN),
            (f"speed {speed_str:>7}", _HUD_PAUSED if self._paused else _HUD_TEXT),
            (f"zoom  {self._camera.zoom:>6.1f}x", _HUD_TEXT),
        ]

        panel_w, panel_h = 190, len(lines) * 22 + 12
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((10, 10, 10, 160))
        surface.blit(panel, (8, 8))

        y = 14
        for text, color in lines:
            shadow = self._font.render(text, True, _HUD_SHADOW)
            label = self._font.render(text, True, color)
            surface.blit(shadow, (17, y + 1))
            surface.blit(label, (16, y))
            y += 22

        # Controls hint at the bottom.
        hint = "Space=pause  ]/[=speed  F=fit  R=restart  ESC=menu"
        hint_surf = self._font.render(hint, True, (160, 160, 160))
        surface.blit(hint_surf, (10, surface.get_height() - 24))
