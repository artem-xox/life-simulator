"""SetupScreen: pre-game configuration menu built with pygame_gui.

Three columns let the player tune world generation, herbivore traits, and
carnivore traits before pressing Start.  Values persist across resize events
so the player doesn't lose their tweaks when dragging the window edge.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass

import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UIHorizontalSlider, UILabel, UITextEntryLine

from life_simulator.config.settings import BACKGROUND_COLOR, CARNIVORE_COLOR, HERBIVORE_COLOR
from life_simulator.simulation.ecosystem import SpeciesConfig
from life_simulator.simulation.entity import Diet
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.worldgen import WorldConfig
from life_simulator.ui.screen import Screen

log = logging.getLogger(__name__)

# ---- visual constants -------------------------------------------------------

_TITLE_COLOR: tuple[int, int, int] = (228, 228, 235)
_WORLD_COLOR: tuple[int, int, int] = (185, 160, 255)
_HINT_COLOR: tuple[int, int, int] = (110, 110, 125)


# ---- value snapshot ---------------------------------------------------------


@dataclass
class _Vals:
    """Mutable snapshot of every configurable field.

    Kept separate so that resize rebuilds the UI from saved values rather than
    defaults.
    """

    seed: int = 2026
    water: float = 0.40
    climate: float = 0.10
    map_w: int = 160
    map_h: int = 120
    h_count: int = 150
    h_speed: float = 1.0
    h_vision: float = 5.0
    h_meta: float = 0.9
    h_repro: float = 0.78
    c_count: int = 15
    c_speed: float = 1.5
    c_vision: float = 9.0
    c_meta: float = 1.1
    c_repro: float = 0.80


# ---- screen -----------------------------------------------------------------


class SetupScreen(Screen):
    """Configuration menu: world params, species traits, and a Start button."""

    # Pixels between the top of two consecutive parameter rows.
    _ROW_H = 60
    # Y-coordinate where parameter rows begin (below title + column headers).
    _Y0 = 118

    def __init__(self, width: int, height: int) -> None:
        self._w = width
        self._h = height
        self._vals = _Vals()
        self._start_requested = False

        self._mgr = pygame_gui.UIManager((width, height))
        self._font_lg = pygame.font.SysFont("menlo,consolas,monospace", 28, bold=True)
        self._font_hd = pygame.font.SysFont("menlo,consolas,monospace", 16, bold=True)

        # Populated by _build_ui; each entry: (label_el, slider_el, name, fmt).
        self._param_rows: list[tuple[UILabel, UIHorizontalSlider, str, Callable]] = []

        # Individual widget references set by _build_ui.
        self._seed_entry: UITextEntryLine
        self._rnd_btn: UIButton
        self._start_btn: UIButton
        self._s_water: UIHorizontalSlider
        self._s_climate: UIHorizontalSlider
        self._s_map_w: UIHorizontalSlider
        self._s_map_h: UIHorizontalSlider
        self._s_h_count: UIHorizontalSlider
        self._s_h_speed: UIHorizontalSlider
        self._s_h_vision: UIHorizontalSlider
        self._s_h_meta: UIHorizontalSlider
        self._s_h_repro: UIHorizontalSlider
        self._s_c_count: UIHorizontalSlider
        self._s_c_speed: UIHorizontalSlider
        self._s_c_vision: UIHorizontalSlider
        self._s_c_meta: UIHorizontalSlider
        self._s_c_repro: UIHorizontalSlider

        self._build_ui()

    # ---- layout helpers -----------------------------------------------------

    def _col_layout(self) -> tuple[int, list[int]]:
        """Return (col_width, [left_x_col0, left_x_col1, left_x_col2])."""
        col_w = max(260, (self._w - 80) // 3)
        gap = max(10, (self._w - 3 * col_w) // 4)
        cols = [gap, gap * 2 + col_w, gap * 3 + col_w * 2]
        return col_w, cols

    def _build_ui(self) -> None:
        v = self._vals
        mgr = self._mgr
        col_w, cols = self._col_layout()
        Y0, ROW = self._Y0, self._ROW_H
        self._param_rows.clear()

        def r(x: int, y: int, w: int = col_w, h: int = 26) -> pygame.Rect:
            return pygame.Rect(x, y, w, h)

        def add_slider(
            col: int,
            row: int,
            name: str,
            val: float,
            lo: float,
            hi: float,
            step: float,
            fmt: Callable,
        ) -> UIHorizontalSlider:
            x = cols[col]
            y = Y0 + row * ROW
            lbl = UILabel(r(x, y, col_w, 20), f"{name}: {fmt(val)}", mgr)
            sld = UIHorizontalSlider(
                r(x, y + 22, col_w, 28), val, (lo, hi), mgr, click_increment=step
            )
            self._param_rows.append((lbl, sld, name, fmt))
            return sld

        # ---- seed row (spans column 0) --------------------------------------
        UILabel(r(cols[0], Y0, 70, 22), "Seed:", mgr)
        self._seed_entry = UITextEntryLine(r(cols[0] + 75, Y0, col_w - 145, 28), mgr)
        self._seed_entry.set_text(str(v.seed))
        self._rnd_btn = UIButton(r(cols[0] + col_w - 65, Y0, 65, 28), "Random", mgr)

        # ---- world column (col 0, rows 1-4) ---------------------------------
        self._s_water = add_slider(
            0, 1, "Water level", v.water, 0.20, 0.70, 0.01, lambda x: f"{x:.2f}"
        )
        self._s_climate = add_slider(
            0, 2, "Climate (dry/wet)", v.climate, -1.0, 1.0, 0.05, lambda x: f"{x:+.2f}"
        )
        self._s_map_w = add_slider(
            0, 3, "Map width (cells)", float(v.map_w), 80, 320, 16, lambda x: f"{round(x)}"
        )
        self._s_map_h = add_slider(
            0, 4, "Map height (cells)", float(v.map_h), 60, 240, 12, lambda x: f"{round(x)}"
        )

        # ---- herbivore column (col 1, rows 0-4) -----------------------------
        self._s_h_count = add_slider(
            1, 0, "Count", float(v.h_count), 10, 400, 10, lambda x: f"{round(x)}"
        )
        self._s_h_speed = add_slider(1, 1, "Speed", v.h_speed, 0.3, 3.0, 0.1, lambda x: f"{x:.1f}")
        self._s_h_vision = add_slider(
            1, 2, "Vision (cells)", v.h_vision, 2.0, 15.0, 0.5, lambda x: f"{x:.1f}"
        )
        self._s_h_meta = add_slider(
            1, 3, "Metabolism", v.h_meta, 0.5, 2.0, 0.05, lambda x: f"{x:.2f}"
        )
        self._s_h_repro = add_slider(
            1, 4, "Repro threshold", v.h_repro, 0.40, 0.90, 0.01, lambda x: f"{x:.2f}"
        )

        # ---- carnivore column (col 2, rows 0-4) -----------------------------
        self._s_c_count = add_slider(
            2, 0, "Count", float(v.c_count), 1, 100, 1, lambda x: f"{round(x)}"
        )
        self._s_c_speed = add_slider(2, 1, "Speed", v.c_speed, 0.3, 3.0, 0.1, lambda x: f"{x:.1f}")
        self._s_c_vision = add_slider(
            2, 2, "Vision (cells)", v.c_vision, 2.0, 15.0, 0.5, lambda x: f"{x:.1f}"
        )
        self._s_c_meta = add_slider(
            2, 3, "Metabolism", v.c_meta, 0.5, 2.0, 0.05, lambda x: f"{x:.2f}"
        )
        self._s_c_repro = add_slider(
            2, 4, "Repro threshold", v.c_repro, 0.40, 0.90, 0.01, lambda x: f"{x:.2f}"
        )

        # ---- start button ---------------------------------------------------
        btn_y = Y0 + 5 * ROW + 16
        btn_w, btn_h = 240, 48
        self._start_btn = UIButton(
            r(self._w // 2 - btn_w // 2, btn_y, btn_w, btn_h),
            "Start Simulation",
            mgr,
        )

    # ---- value persistence --------------------------------------------------

    def _snapshot_values(self) -> None:
        """Copy widget states into self._vals so resize/relaunch can restore them."""
        v = self._vals
        try:
            v.seed = int(self._seed_entry.get_text())
        except (ValueError, AttributeError):
            pass
        v.water = self._s_water.get_current_value()
        v.climate = self._s_climate.get_current_value()
        v.map_w = round(self._s_map_w.get_current_value())
        v.map_h = round(self._s_map_h.get_current_value())
        v.h_count = round(self._s_h_count.get_current_value())
        v.h_speed = self._s_h_speed.get_current_value()
        v.h_vision = self._s_h_vision.get_current_value()
        v.h_meta = self._s_h_meta.get_current_value()
        v.h_repro = self._s_h_repro.get_current_value()
        v.c_count = round(self._s_c_count.get_current_value())
        v.c_speed = self._s_c_speed.get_current_value()
        v.c_vision = self._s_c_vision.get_current_value()
        v.c_meta = self._s_c_meta.get_current_value()
        v.c_repro = self._s_c_repro.get_current_value()

    # ---- Screen protocol ----------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        self._mgr.process_events(event)
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element is self._start_btn:
                self._start_requested = True
            elif event.ui_element is self._rnd_btn:
                self._seed_entry.set_text(str(random.randint(0, 99_999)))

    def update(self, dt: float) -> Screen | None:
        self._mgr.update(dt)
        # Keep slider label text in sync with the dragged handle position.
        for lbl, sld, name, fmt in self._param_rows:
            lbl.set_text(f"{name}: {fmt(sld.get_current_value())}")
        if self._start_requested:
            self._start_requested = False
            return self._launch_sim()
        return None

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BACKGROUND_COLOR)
        w = self._w
        _, cols = self._col_layout()

        # Title
        title = self._font_lg.render("Life Simulator  —  Setup", True, _TITLE_COLOR)
        surface.blit(title, (w // 2 - title.get_width() // 2, 20))

        # Column headers
        for text, x, color in [
            ("WORLD", cols[0], _WORLD_COLOR),
            ("HERBIVORES", cols[1], HERBIVORE_COLOR),
            ("CARNIVORES", cols[2], CARNIVORE_COLOR),
        ]:
            surf = self._font_hd.render(text, True, color)
            surface.blit(surf, (x, 88))

        # Bottom hint
        hint = self._font_hd.render(
            "Drag sliders to tune parameters, then click  Start Simulation",
            True,
            _HINT_COLOR,
        )
        surface.blit(hint, (w // 2 - hint.get_width() // 2, self._h - 28))

        self._mgr.draw_ui(surface)

    def resize(self, width: int, height: int) -> None:
        self._snapshot_values()
        self._w = width
        self._h = height
        self._mgr = pygame_gui.UIManager((width, height))
        self._param_rows.clear()
        self._build_ui()

    # ---- launch -------------------------------------------------------------

    def _launch_sim(self) -> Screen:
        from life_simulator.ui.sim_screen import SimScreen

        self._snapshot_values()
        v = self._vals

        world_cfg = WorldConfig(
            seed=v.seed,
            width=v.map_w,
            height=v.map_h,
            water_level=round(v.water, 2),
            climate=round(v.climate, 2),
        )
        species: list[SpeciesConfig] = [
            SpeciesConfig(
                diet=Diet.HERBIVORE,
                count=v.h_count,
                genome=Genome(
                    speed=round(v.h_speed, 2),
                    vision=round(v.h_vision, 1),
                    metabolism=round(v.h_meta, 2),
                    repro_threshold=round(v.h_repro, 2),
                ),
            ),
            SpeciesConfig(
                diet=Diet.CARNIVORE,
                count=v.c_count,
                genome=Genome(
                    speed=round(v.c_speed, 2),
                    vision=round(v.c_vision, 1),
                    metabolism=round(v.c_meta, 2),
                    repro_threshold=round(v.c_repro, 2),
                ),
            ),
        ]
        log.info(
            "launching sim  seed=%d  world=%dx%d  herb=%d  carn=%d",
            v.seed,
            v.map_w,
            v.map_h,
            v.h_count,
            v.c_count,
        )
        return SimScreen(self._w, self._h, world_cfg, species)
