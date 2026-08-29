"""Global constants: window defaults, biome definitions and balance values.

This module holds only data (no behaviour) so it can be imported by both the
simulation and the UI layers without creating dependencies between them.
"""

from __future__ import annotations

from enum import IntEnum

# --- Window / rendering defaults -------------------------------------------

WINDOW_TITLE = "Life Simulator"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
TARGET_FPS = 60

# Background colour used to clear the screen each frame.
BACKGROUND_COLOR = (18, 18, 22)


# --- Surfaces ---------------------------------------------------------------


class Surface(IntEnum):
    """Ground types stored as small integers in the world's surface array.

    The world is a single temperate biome; what varies across it is the surface
    underfoot. The integer values double as indices into the lookup tables
    below, so the order here must stay in sync with those tables.
    """

    OCEAN = 0
    FRESH_WATER = 1
    SAND = 2
    FOREST = 3


# RGB colour used to draw each surface on the map.
SURFACE_COLORS: dict[Surface, tuple[int, int, int]] = {
    Surface.OCEAN: (26, 54, 96),
    Surface.FRESH_WATER: (58, 116, 178),
    Surface.SAND: (216, 200, 146),
    Surface.FOREST: (58, 118, 62),
}

# Maximum amount of food a single cell of each surface can hold. Grass grows in
# the forest and nowhere else — sand and water feed nobody.
SURFACE_FOOD_MAX: dict[Surface, float] = {
    Surface.OCEAN: 0.0,
    Surface.FRESH_WATER: 0.0,
    Surface.SAND: 0.0,
    Surface.FOREST: 10.0,
}

# Per-tick food regrowth multiplier (fraction of food_max regained per tick).
SURFACE_REGROW_RATE: dict[Surface, float] = {
    Surface.OCEAN: 0.0,
    Surface.FRESH_WATER: 0.0,
    Surface.SAND: 0.0,
    Surface.FOREST: 0.05,
}

# Whether entities can enter a surface at all. Animals cannot swim.
SURFACE_WALKABLE: dict[Surface, bool] = {
    Surface.OCEAN: False,
    Surface.FRESH_WATER: False,
    Surface.SAND: True,
    Surface.FOREST: True,
}

# Movement cost multiplier per surface (higher = slower to cross). Only
# relevant for walkable surfaces.
SURFACE_MOVE_COST: dict[Surface, float] = {
    Surface.OCEAN: float("inf"),
    Surface.FRESH_WATER: float("inf"),
    Surface.SAND: 1.2,
    Surface.FOREST: 1.0,
}


# --- Entity rendering -------------------------------------------------------

# RGB colours for each diet type (used by the renderer; kept here so all
# visual constants live in one place rather than scattered across UI files).
HERBIVORE_COLOR: tuple[int, int, int] = (110, 210, 80)
CARNIVORE_COLOR: tuple[int, int, int] = (220, 55, 35)

# Size (in world cells) of one cell displayed in the sim-speed HUD bar.
SIM_SPEED_OPTIONS: tuple[int, ...] = (1, 5, 20, 60, 200)  # ticks per second
