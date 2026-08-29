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
    MOUNTAIN = 4


# RGB colour used to draw each surface on the map.
SURFACE_COLORS: dict[Surface, tuple[int, int, int]] = {
    Surface.OCEAN: (26, 54, 96),
    Surface.FRESH_WATER: (58, 116, 178),
    Surface.SAND: (216, 200, 146),
    Surface.FOREST: (58, 118, 62),
    Surface.MOUNTAIN: (122, 116, 110),
}

# Maximum amount of food a single cell of each surface can hold. Grass grows in
# the forest and nowhere else — sand, rock and water feed nobody.
SURFACE_FOOD_MAX: dict[Surface, float] = {
    Surface.OCEAN: 0.0,
    Surface.FRESH_WATER: 0.0,
    Surface.SAND: 0.0,
    Surface.FOREST: 10.0,
    Surface.MOUNTAIN: 0.0,
}

# Per-tick food regrowth multiplier (fraction of food_max regained per tick).
SURFACE_REGROW_RATE: dict[Surface, float] = {
    Surface.OCEAN: 0.0,
    Surface.FRESH_WATER: 0.0,
    Surface.SAND: 0.0,
    Surface.FOREST: 0.05,
    Surface.MOUNTAIN: 0.0,
}

# Whether entities can enter a surface at all. Animals can neither swim nor
# climb, so water and rock are both hard obstacles they must route around.
SURFACE_WALKABLE: dict[Surface, bool] = {
    Surface.OCEAN: False,
    Surface.FRESH_WATER: False,
    Surface.SAND: True,
    Surface.FOREST: True,
    Surface.MOUNTAIN: False,
}

# Movement cost multiplier per surface (higher = slower to cross). Only
# relevant for walkable surfaces.
SURFACE_MOVE_COST: dict[Surface, float] = {
    Surface.OCEAN: float("inf"),
    Surface.FRESH_WATER: float("inf"),
    Surface.SAND: 1.2,
    Surface.FOREST: 1.0,
    Surface.MOUNTAIN: float("inf"),
}


# --- Terrain shading --------------------------------------------------------
# The map is drawn one pixel per cell, so colour is the only channel terrain
# has. These endpoints are interpolated across elevation, depth and how much
# grass is left, which is what turns flat colour blocks into readable land.

# Forest fades from lush to bare soil as its grass is grazed away, so grazing
# pressure is visible on the map without any overlay. The lush end itself
# shifts with altitude — deep green in the lowlands, pale and dry on the slopes
# — which is what gives the island visible bands instead of one flat wash.
GRASS_LOWLAND_COLOR: tuple[int, int, int] = (42, 108, 44)
GRASS_HIGHLAND_COLOR: tuple[int, int, int] = (122, 146, 84)
GRASS_BARE_COLOR: tuple[int, int, int] = (104, 86, 54)

# Water is tinted by depth: shallows near the shore, dark in the deep.
OCEAN_DEEP_COLOR: tuple[int, int, int] = (16, 36, 72)
OCEAN_SHALLOW_COLOR: tuple[int, int, int] = (44, 100, 156)
FRESH_DEEP_COLOR: tuple[int, int, int] = (38, 92, 142)
FRESH_SHALLOW_COLOR: tuple[int, int, int] = (86, 152, 200)

# Surf line drawn on water cells that touch land.
SURF_COLOR: tuple[int, int, int] = (154, 194, 216)
SURF_BLEND: float = 0.35

# Rock pales towards bare, snowy summits. The exponent keeps snow on the peaks
# themselves rather than washing whole ranges white.
MOUNTAIN_PEAK_COLOR: tuple[int, int, int] = (226, 228, 233)
MOUNTAIN_SNOW_EXPONENT: float = 3.0

# How far elevation brightens or darkens land, as a fraction of its colour.
ELEVATION_SHADE: float = 0.30

# Hillshading: slopes facing the light are brightened and slopes facing away
# are darkened, which is what makes ranges read as ridges and valleys instead
# of flat grey patches. The light comes from the north-west, as on a map.
HILLSHADE_STRENGTH: float = 0.22
HILLSHADE_LIGHT: tuple[float, float] = (-0.707, -0.707)

# Elevation, texture and hillshade all multiply the same colour, so their
# product is clamped: without a ceiling, a lit slope of pale sand blows out to
# white and the beach loses its shape.
SHADE_FACTOR_RANGE: tuple[float, float] = (0.55, 1.30)

# Altitude is raised to this power before tinting grass. Below 1 it pulls the
# pale highland tone down the slopes, so the whole island shows altitude bands
# rather than only the ground right below the peaks.
GRASS_ALTITUDE_CURVE: float = 0.55

# Strength of the per-cell canopy speckle that keeps large areas from reading
# as one flat wash of colour.
CANOPY_TEXTURE: float = 0.07


# --- Entity rendering -------------------------------------------------------

# RGB colours for each diet type (used by the renderer; kept here so all
# visual constants live in one place rather than scattered across UI files).
HERBIVORE_COLOR: tuple[int, int, int] = (110, 210, 80)
CARNIVORE_COLOR: tuple[int, int, int] = (220, 55, 35)

# Size (in world cells) of one cell displayed in the sim-speed HUD bar.
SIM_SPEED_OPTIONS: tuple[int, ...] = (1, 5, 20, 60, 200)  # ticks per second
