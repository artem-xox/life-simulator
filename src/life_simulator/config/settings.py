"""Global constants: window defaults, biome definitions and balance values.

This module holds only data (no behaviour) so it can be imported by both the
simulation and the UI layers without creating dependencies between them.
"""

from __future__ import annotations

from enum import IntEnum

# --- Window / rendering defaults -------------------------------------------

WINDOW_TITLE = "Life Simulator"
TARGET_FPS = 60

# The map is the point, so the simulator opens borderless at desktop size.
# F11 drops it back to a plain resizable window of WINDOW_WIDTH x WINDOW_HEIGHT.
START_FULLSCREEN = True
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800

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

# How much grass a single cell of each surface can hold. Grass grows in the
# forest and nowhere else — sand, rock and water feed nobody.
SURFACE_GRASS_MAX: dict[Surface, float] = {
    Surface.OCEAN: 0.0,
    Surface.FRESH_WATER: 0.0,
    Surface.SAND: 0.0,
    Surface.FOREST: 10.0,
    Surface.MOUNTAIN: 0.0,
}


# --- Grass dynamics ---------------------------------------------------------
# Grass is the ecosystem's only energy inflow, and it grows logistically: a
# patch regrows from what is still standing on it, fastest at middling density
# and not at all once the cell has been grazed to bare earth.

# Fraction of the standing grass added back per tick, before the crowding term.
GRASS_REGROW_RATE: float = 0.06

# A bare cell has nothing left to grow from, so it can only recover by seeding
# in from its neighbours — which is why an overgrazed patch heals slowly from
# its edges inwards and leaves a visible scar in the meantime.
GRASS_SPREAD_RATE: float = 0.02

# Grass starts below capacity so the map is not trivially abundant on tick one.
INITIAL_GRASS_FRACTION: float = 0.6

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


# --- Creature energy budget -------------------------------------------------

#: Energy a size-1 body burns per tick simply staying alive.
BASE_ENERGY_COST: float = 0.30

#: Energy a size-1 body can hold.
MAX_ENERGY_BASE: float = 20.0

#: Grass consumed from the cell per grazing action (herbivores).
GRAZE_AMOUNT: float = 2.0

#: Energy gained per unit of grass eaten. Deliberately low: with abundant grass
#: an herbivore net-gains ~0.5 energy/tick, making reproduction take ~25 ticks
#: rather than every 2-3 ticks.
GRAZE_ENERGY_GAIN: float = 0.40

#: Energy stolen from prey per tick while within ATTACK_RANGE (carnivores).
#: Low value forces several ticks of sustained contact to drain a prey's energy.
ATTACK_DAMAGE: float = 1.8

#: Distance in cells within which a carnivore can attack.
ATTACK_RANGE: float = 1.5

#: Fraction of energy stolen from prey that the attacker keeps.
ATTACK_EFFICIENCY: float = 0.40

#: Energy given to the newborn as a fraction of parent max_energy.
#: High value (> 0.5) makes reproduction expensive to slow population growth.
CHILD_ENERGY_FRACTION: float = 0.65

#: Fraction of its maximum energy an animal must hold before it will breed.
#: A placeholder for the fertility rules of the lifecycle stage.
REPRODUCTION_THRESHOLD: float = 0.78

#: Ticks between choosing a new random wander target.
WANDER_INTERVAL: int = 10


# --- Lifecycle --------------------------------------------------------------
# An animal is born small and helpless, grows into an adult, breeds once or
# twice inside a window in the middle of its life, and dies of old age if
# nothing eats it first.

#: Typical lifespan in ticks, before individual variation.
LIFESPAN_BASE: int = 700

#: Individual lifespan varies by up to this fraction either way, so a cohort
#: born together does not die together.
LIFESPAN_VARIATION: float = 0.10

#: Fraction of a life spent growing up. Until then the animal is a juvenile:
#: small, clumsy, barred from breeding, and easy prey.
JUVENILE_FRACTION: float = 0.20

#: A newborn's body as a fraction of the size its genes call for.
NEWBORN_SIZE_FRACTION: float = 0.40

#: A newborn's pace as a fraction of what its body would otherwise manage.
#: Being light makes a juvenile quick in principle; being uncoordinated is what
#: actually makes it catchable.
NEWBORN_COORDINATION: float = 0.55

#: Energy a predator gets from a juvenile, relative to a grown animal of the
#: same body — there is simply less on it.
JUVENILE_PREY_VALUE: float = 0.6

#: Most offspring an animal can ever have.
MAX_OFFSPRING: int = 2

#: Fertility window as fractions of a lifetime. Breeding starts at adulthood
#: and stops well before old age.
FERTILITY_START_FRACTION: float = 0.20
FERTILITY_END_FRACTION: float = 0.80

#: Rest between births, as a fraction of a lifetime. With the window above,
#: this is what holds a life to one or two offspring rather than a burst.
BREEDING_COOLDOWN_FRACTION: float = 0.25


# --- Phenotype: how genes become abilities ----------------------------------
# Exponents that turn body size into real-world consequences. Every one of them
# is a trade-off, which is what stops any single gene from being simply better
# than its alternatives.

#: Energy storage grows faster than mass — big animals bank a deep reserve.
ENERGY_SIZE_EXPONENT: float = 1.2

#: Kleiber's law. Upkeep grows *slower* than mass, so a large body is more
#: efficient per unit of itself while still costing more in absolute terms.
METABOLIC_SIZE_EXPONENT: float = 0.75

#: Mass drags: pace falls off as size rises.
SPEED_SIZE_EXPONENT: float = 0.4

#: Energy a size-1 body spends per cell it travels. Locomotion is charged by
#: distance, not by time: a fast animal reaches food sooner but burns more
#: getting there, which is what stops speed from being a free gene.
TRAVEL_ENERGY_FACTOR: float = 0.12

#: Sprinting costs this multiple of upkeep, times the square of speed — running
#: fast is punishingly expensive, and running fast while heavy more so.
SPRINT_COST_FACTOR: float = 3.0

#: Concealment lost per unit of size above 1. Bulk is hard to hide.
STEALTH_SIZE_PENALTY: float = 0.35

#: Nothing is ever wholly invisible.
MAX_STEALTH: float = 0.95


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

# Smoothing passes applied to elevation before the gradient is taken. The raw
# terrain's finest noise octave would otherwise dominate the shading and make a
# high-resolution map look like brushed metal instead of hills.
HILLSHADE_SMOOTHING: int = 3
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
