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


# --- Biomes ----------------------------------------------------------------


class Biome(IntEnum):
    """Terrain types stored as small integers in the world's biome array.

    The integer values double as indices into the lookup tables below, so the
    order here must stay in sync with those tables.
    """

    DEEP_WATER = 0
    WATER = 1
    SAND = 2
    GRASS = 3
    FOREST = 4
    MOUNTAIN = 5
    SNOW = 6


# RGB colour used to draw each biome on the map.
BIOME_COLORS: dict[Biome, tuple[int, int, int]] = {
    Biome.DEEP_WATER: (28, 56, 102),
    Biome.WATER: (48, 92, 158),
    Biome.SAND: (214, 197, 138),
    Biome.GRASS: (104, 168, 84),
    Biome.FOREST: (54, 110, 60),
    Biome.MOUNTAIN: (122, 116, 110),
    Biome.SNOW: (236, 238, 242),
}

# Maximum amount of food a single cell of each biome can hold. Zero means the
# biome never grows food (water, rock, snow).
BIOME_FOOD_MAX: dict[Biome, float] = {
    Biome.DEEP_WATER: 0.0,
    Biome.WATER: 0.0,
    Biome.SAND: 2.0,
    Biome.GRASS: 10.0,
    Biome.FOREST: 6.0,
    Biome.MOUNTAIN: 0.0,
    Biome.SNOW: 0.0,
}

# Per-tick food regrowth multiplier (fraction of food_max regained per tick).
BIOME_REGROW_RATE: dict[Biome, float] = {
    Biome.DEEP_WATER: 0.0,
    Biome.WATER: 0.0,
    Biome.SAND: 0.01,
    Biome.GRASS: 0.05,
    Biome.FOREST: 0.03,
    Biome.MOUNTAIN: 0.0,
    Biome.SNOW: 0.0,
}

# Whether entities can enter a biome at all.
BIOME_WALKABLE: dict[Biome, bool] = {
    Biome.DEEP_WATER: False,
    Biome.WATER: False,
    Biome.SAND: True,
    Biome.GRASS: True,
    Biome.FOREST: True,
    Biome.MOUNTAIN: True,
    Biome.SNOW: True,
}

# Movement cost multiplier per biome (higher = slower to cross). Only relevant
# for walkable biomes.
BIOME_MOVE_COST: dict[Biome, float] = {
    Biome.DEEP_WATER: float("inf"),
    Biome.WATER: float("inf"),
    Biome.SAND: 1.2,
    Biome.GRASS: 1.0,
    Biome.FOREST: 1.4,
    Biome.MOUNTAIN: 2.5,
    Biome.SNOW: 2.0,
}


# --- Entity rendering -------------------------------------------------------

# RGB colours for each diet type (used by the renderer; kept here so all
# visual constants live in one place rather than scattered across UI files).
HERBIVORE_COLOR: tuple[int, int, int] = (110, 210, 80)
CARNIVORE_COLOR: tuple[int, int, int] = (220, 55, 35)

# Size (in world cells) of one cell displayed in the sim-speed HUD bar.
SIM_SPEED_OPTIONS: tuple[int, ...] = (1, 5, 20, 60, 200)  # ticks per second
