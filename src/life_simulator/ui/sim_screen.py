"""SimScreen: the main simulation view.

Combines the world map, entity rendering, a HUD overlay, an inspector panel,
a live population graph, and interactive camera controls into one screen. The
simulation loop is decoupled from the render rate: ``ticks_per_second`` ticks
are accumulated per real second, with a per-frame cap to avoid spiral-of-death
when the simulation is slow.

Controls:
    * left-drag ................. pan
    * left-click (no drag) ...... select / inspect an entity
    * mouse wheel ............... zoom toward cursor
    * Space ..................... pause / resume
    * ] / [ .................... speed up / slow down
    * F ......................... fit world to screen
    * R ......................... restart with a new random seed (same species)
    * S / L ..................... save / load the simulation
    * G ......................... toggle the population graph
    * ESC ....................... return to the setup menu
"""

from __future__ import annotations

import logging
import random

import pygame

from life_simulator.config.settings import BACKGROUND_COLOR, SIM_SPEED_OPTIONS
from life_simulator.persistence.save_load import DEFAULT_SAVE_PATH, load_game, save_game
from life_simulator.simulation.ecosystem import Ecosystem, SpeciesConfig
from life_simulator.simulation.entity import MAX_AGE, Diet, Entity
from life_simulator.simulation.worldgen import WorldConfig
from life_simulator.ui.camera import Camera
from life_simulator.ui.render import WorldRenderer, draw_entities, draw_selection, find_entity_at
from life_simulator.ui.screen import Screen

log = logging.getLogger(__name__)

# Maximum simulation ticks processed in a single rendered frame.  Prevents
# the loop from freezing the window when the sim runs faster than real-time.
_MAX_STEPS_PER_FRAME = 40

# Distance (in pixels) the mouse may move between press and release while still
# counting as a click rather than a drag.
_CLICK_TOLERANCE = 4

# Seconds a transient status message (e.g. "Saved") stays on screen.
_MESSAGE_DURATION = 2.5

# Colours used in the HUD / panels.
_HUD_TEXT = (230, 230, 230)
_HUD_SHADOW = (0, 0, 0)
_HUD_HERB = (110, 210, 80)
_HUD_CARN = (220, 55, 35)
_HUD_PAUSED = (240, 200, 60)
_PANEL_BG = (10, 10, 10, 180)


class SimScreen(Screen):
    """Main simulation screen: world + entities + HUD + inspector + graph."""

    def __init__(
        self,
        width: int,
        height: int,
        world_cfg: WorldConfig,
        species: list[SpeciesConfig],
        ecosystem: Ecosystem | None = None,
    ) -> None:
        self._width = width
        self._height = height
        self._world_cfg = world_cfg
        self._species = species

        log.info("SimScreen init  %dx%d px", width, height)
        if ecosystem is None:
            log.info("creating ecosystem (pump_events=True to keep window alive)...")
            self.ecosystem = Ecosystem.create(world_cfg, species, pump_events=True)
        else:
            log.info("using preloaded ecosystem  tick=%d", ecosystem.tick_count)
            self.ecosystem = ecosystem

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
        self._mouse_down_pos: tuple[int, int] | None = None
        self._drag_moved = False
        self._selected: Entity | None = None
        self._show_graph = True
        self._message: str = ""
        self._message_timer: float = 0.0
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
            self._drag_moved = False
            self._mouse_down_pos = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if not self._drag_moved and self._mouse_down_pos is not None:
                self._select_at(*self._mouse_down_pos)
            self._dragging = False
            self._mouse_down_pos = None
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            dx, dy = event.rel
            if abs(dx) > _CLICK_TOLERANCE or abs(dy) > _CLICK_TOLERANCE:
                self._drag_moved = True
            self._camera.pan_pixels(dx, dy)
        elif event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            self._camera.zoom_at(1.15**event.y, mx, my)
        elif event.type == pygame.KEYDOWN:
            self._handle_key(event.key)

    def _select_at(self, sx: int, sy: int) -> None:
        self._selected = find_entity_at(self.ecosystem.entities, self._camera, sx, sy)

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
        elif key == pygame.K_g:
            self._show_graph = not self._show_graph
        elif key == pygame.K_r:
            self._restart()
        elif key == pygame.K_s:
            self._save()
        elif key == pygame.K_l:
            self._load()

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
        self._selected = None

    def _save(self) -> None:
        try:
            save_game(DEFAULT_SAVE_PATH, self.ecosystem, self._world_cfg, self._species)
            self._flash(f"Saved → {DEFAULT_SAVE_PATH}")
        except Exception as exc:
            log.exception("save failed")
            self._flash(f"Save failed: {exc}")

    def _load(self) -> None:
        try:
            eco, world_cfg, species = load_game(DEFAULT_SAVE_PATH)
        except FileNotFoundError:
            self._flash(f"No save at {DEFAULT_SAVE_PATH}")
            return
        except Exception as exc:
            log.exception("load failed")
            self._flash(f"Load failed: {exc}")
            return
        self.ecosystem = eco
        self._world_cfg = world_cfg
        self._species = species
        self._renderer.set_world(eco.world)
        self._camera = Camera(
            world_w=eco.world.width,
            world_h=eco.world.height,
            screen_w=self._width,
            screen_h=self._height,
        )
        self._accumulator = 0.0
        self._selected = None
        self._flash(f"Loaded ← {DEFAULT_SAVE_PATH}")

    def _flash(self, text: str) -> None:
        self._message = text
        self._message_timer = _MESSAGE_DURATION

    def update(self, dt: float) -> Screen | None:
        if self._next_screen is not None:
            return self._next_screen
        if self._message_timer > 0.0:
            self._message_timer = max(0.0, self._message_timer - dt)
        if self._selected is not None and not self._selected.alive:
            self._selected = None
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
        if self._selected is not None:
            draw_selection(surface, self._selected, self._camera)
        self._draw_hud(surface)
        if self._selected is not None:
            self._draw_inspector(surface)
        if self._show_graph:
            self._draw_graph(surface)
        if self._message_timer > 0.0:
            self._draw_message(surface)

    def resize(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self._camera.resize(width, height)

    # --- Text helpers ------------------------------------------------------ #

    def _blit_text(
        self,
        surface: pygame.Surface,
        text: str,
        x: int,
        y: int,
        color: tuple[int, int, int],
    ) -> None:
        shadow = self._font.render(text, True, _HUD_SHADOW)
        label = self._font.render(text, True, color)
        surface.blit(shadow, (x + 1, y + 1))
        surface.blit(label, (x, y))

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
        panel.fill(_PANEL_BG)
        surface.blit(panel, (8, 8))

        y = 14
        for text, color in lines:
            self._blit_text(surface, text, 16, y, color)
            y += 22

        hint = "Space=pause ]/[=speed F=fit R=restart S/L=save G=graph ESC=menu"
        hint_surf = self._font.render(hint, True, (160, 160, 160))
        surface.blit(hint_surf, (10, surface.get_height() - 24))

    # --- Inspector panel --------------------------------------------------- #

    def _draw_inspector(self, surface: pygame.Surface) -> None:
        e = self._selected
        assert e is not None
        g = e.genome
        is_herb = e.diet == Diet.HERBIVORE
        accent = _HUD_HERB if is_herb else _HUD_CARN

        rows = [
            ("age", f"{e.age} / {MAX_AGE}"),
            ("speed", f"{g.speed:.2f}"),
            ("vision", f"{g.vision:.1f}"),
            ("metabolism", f"{g.metabolism:.2f}"),
            ("size", f"{g.size:.2f}"),
            ("repro thr", f"{g.repro_threshold:.2f}"),
            ("mutation", f"{g.mutation_rate:.3f}"),
        ]

        panel_w = 210
        # title + energy bar + rows
        panel_h = 30 + 30 + len(rows) * 22 + 12
        x = self._width - panel_w - 10
        y = 10

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill(_PANEL_BG)
        surface.blit(panel, (x, y))

        cy = y + 8
        title = e.diet.name
        self._blit_text(surface, title, x + 12, cy, accent)
        cy += 28

        # Energy bar.
        frac = max(0.0, min(1.0, e.energy / e.max_energy))
        bar_x, bar_w, bar_h = x + 12, panel_w - 24, 14
        pygame.draw.rect(surface, (60, 60, 70), (bar_x, cy, bar_w, bar_h))
        pygame.draw.rect(surface, accent, (bar_x, cy, int(bar_w * frac), bar_h))
        self._blit_text(
            surface,
            f"energy {e.energy:.1f}/{e.max_energy:.0f}",
            bar_x + 4,
            cy - 1,
            _HUD_TEXT,
        )
        cy += 26

        for name, value in rows:
            self._blit_text(surface, f"{name:<11}{value}", x + 12, cy, _HUD_TEXT)
            cy += 22

    # --- Population graph -------------------------------------------------- #

    def _draw_graph(self, surface: pygame.Surface) -> None:
        samples = self.ecosystem.stats.samples
        if len(samples) < 2:
            return

        gw, gh = 280, 110
        pad = 6
        gx = self._width - gw - 10
        gy = self._height - gh - 36

        panel = pygame.Surface((gw, gh), pygame.SRCALPHA)
        panel.fill(_PANEL_BG)
        surface.blit(panel, (gx, gy))

        peak = max(max(s.herbivores, s.carnivores) for s in samples)
        peak = max(peak, 1)
        plot_w = gw - 2 * pad
        plot_h = gh - 2 * pad - 14
        x0 = gx + pad
        y_base = gy + pad + plot_h

        n = len(samples)

        def points(getter) -> list[tuple[int, int]]:
            pts = []
            for i, s in enumerate(samples):
                px = x0 + round(i / (n - 1) * plot_w)
                py = y_base - round(getter(s) / peak * plot_h)
                pts.append((px, py))
            return pts

        pygame.draw.lines(surface, _HUD_HERB, False, points(lambda s: s.herbivores), 2)
        pygame.draw.lines(surface, _HUD_CARN, False, points(lambda s: s.carnivores), 2)

        latest = samples[-1]
        legend = f"herb {latest.herbivores}   carn {latest.carnivores}   peak {peak}"
        self._blit_text(surface, legend, x0, gy + gh - 16, _HUD_TEXT)

    # --- Transient message ------------------------------------------------- #

    def _draw_message(self, surface: pygame.Surface) -> None:
        text = self._font_large.render(self._message, True, _HUD_PAUSED)
        tw, th = text.get_size()
        x = (self._width - tw) // 2
        y = 16
        panel = pygame.Surface((tw + 24, th + 12), pygame.SRCALPHA)
        panel.fill(_PANEL_BG)
        surface.blit(panel, (x - 12, y - 6))
        surface.blit(text, (x, y))
