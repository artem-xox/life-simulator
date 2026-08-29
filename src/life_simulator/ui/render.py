"""Rendering helpers: terrain surface and entity sprites.

The map is drawn one pixel per cell into a cached surface, a slice of which is
scaled to the viewport each frame — so pan and zoom cost one blit. Because a
cell is a single pixel, colour carries all of the terrain's information:
elevation shades the land, depth tints the water, and the forest fades from
lush green to bare soil as its grass is grazed away.

Colours split into two layers. The static layer (elevation, depth, surf,
canopy texture) is computed once per world; the grass layer is re-blended by
:meth:`WorldRenderer.refresh` as the simulation eats its way across the map.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pygame

from life_simulator.config.settings import (
    CANOPY_TEXTURE,
    CARNIVORE_COLOR,
    ELEVATION_SHADE,
    FRESH_DEEP_COLOR,
    FRESH_SHALLOW_COLOR,
    GRASS_ALTITUDE_CURVE,
    GRASS_BARE_COLOR,
    GRASS_HIGHLAND_COLOR,
    GRASS_LOWLAND_COLOR,
    HERBIVORE_COLOR,
    HILLSHADE_LIGHT,
    HILLSHADE_STRENGTH,
    MOUNTAIN_PEAK_COLOR,
    MOUNTAIN_SNOW_EXPONENT,
    OCEAN_DEEP_COLOR,
    OCEAN_SHALLOW_COLOR,
    SHADE_FACTOR_RANGE,
    SURF_BLEND,
    SURF_COLOR,
    SURFACE_COLORS,
    Surface,
)
from life_simulator.simulation.entity import Diet
from life_simulator.simulation.world import World
from life_simulator.ui.camera import Camera

if TYPE_CHECKING:
    from life_simulator.simulation.entity import Entity

#: Below this zoom a cell is smaller than a pixel, so the terrain is downscaled
#: smoothly; above it, nearest-neighbour keeps cell edges crisp.
_SMOOTH_SCALE_BELOW: float = 1.5

#: Seeds the canopy speckle. Fixed, so a given map always looks the same.
_TEXTURE_SEED: int = 20260829


def _surface_color_table() -> np.ndarray:
    """Return an (n_surfaces, 3) float array of RGB colours indexed by surface."""
    size = max(int(s) for s in Surface) + 1
    table = np.zeros((size, 3), dtype=np.float32)
    for surface, color in SURFACE_COLORS.items():
        table[int(surface)] = color
    return table


_COLOR_TABLE = _surface_color_table()


def _normalise(values: np.ndarray, low: float, high: float) -> np.ndarray:
    """Map ``[low, high]`` onto ``[0, 1]``, tolerating a degenerate range."""
    if high <= low:
        return np.zeros_like(values)
    return np.clip((values - low) / (high - low), 0.0, 1.0)


def _lerp(low: tuple[int, int, int], high: tuple[int, int, int], t: np.ndarray) -> np.ndarray:
    """Blend between two colours per element of ``t`` (shape ``(n,)`` → ``(n, 3)``)."""
    start = np.asarray(low, dtype=np.float32)
    end = np.asarray(high, dtype=np.float32)
    return start + (end - start) * t[:, None]


def _touching(mask: np.ndarray, other: np.ndarray) -> np.ndarray:
    """Return the cells of ``mask`` that share an edge with a cell of ``other``."""
    near = np.zeros(other.shape, dtype=bool)
    near[1:, :] |= other[:-1, :]
    near[:-1, :] |= other[1:, :]
    near[:, 1:] |= other[:, :-1]
    near[:, :-1] |= other[:, 1:]
    return mask & near


def _hillshade(elevation: np.ndarray) -> np.ndarray:
    """Return a brightness multiplier that lights slopes from the north-west.

    Slopes tilted towards the light are brightened and those tilted away are
    darkened, which is what makes a range read as a ridge with valleys rather
    than a flat patch of grey. The gradient is divided by its own spread so the
    effect is comparable whether a map is smooth or craggy.
    """
    grad_y, grad_x = np.gradient(elevation.astype(np.float32))
    light_x, light_y = HILLSHADE_LIGHT
    illumination = -(grad_x * light_x + grad_y * light_y)

    spread = float(illumination.std())
    if spread <= 0.0:
        return np.ones_like(illumination)
    return 1.0 + HILLSHADE_STRENGTH * np.clip(illumination / spread, -2.0, 2.0)


def _canopy_texture(shape: tuple[int, int]) -> np.ndarray:
    """Return a gently clumped per-cell brightness multiplier around 1.0.

    Plain white noise looks like static; averaging it with its neighbours
    clusters it into patches that read as canopy rather than as grain.
    """
    rng = np.random.default_rng(_TEXTURE_SEED)
    noise = rng.random(shape, dtype=np.float32)
    clumped = noise.copy()
    clumped[1:, :] += noise[:-1, :]
    clumped[:-1, :] += noise[1:, :]
    clumped[:, 1:] += noise[:, :-1]
    clumped[:, :-1] += noise[:, 1:]
    clumped /= 5.0
    return 1.0 + CANOPY_TEXTURE * (clumped - clumped.mean()) * 4.0


def _static_layers(world: World) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Shade everything that does not change while the simulation runs.

    Returns:
        The colour array with every non-forest cell resolved, the forest mask,
        the fully-grassed colour of each forest cell, and its brightness
        multiplier. The forest's own colour also depends on how much grass is
        standing on it, which changes every tick and is applied later.
    """
    surface = world.surface
    elevation = world.elevation
    rgb = _COLOR_TABLE[surface].copy()

    ocean = surface == Surface.OCEAN
    fresh = surface == Surface.FRESH_WATER
    water = ocean | fresh
    land = ~water

    # Water is shaded from the surface down, so the shelf around the island
    # reads as shallow and the open sea as deep.
    sea_level = float(elevation[water].max()) if water.any() else 0.0
    depth = _normalise(elevation, 0.0, sea_level)
    if ocean.any():
        rgb[ocean] = _lerp(OCEAN_DEEP_COLOR, OCEAN_SHALLOW_COLOR, depth[ocean])
    if fresh.any():
        rgb[fresh] = _lerp(FRESH_DEEP_COLOR, FRESH_SHALLOW_COLOR, depth[fresh])

    # Land brightens as it rises, which is what gives the map its relief.
    peak = float(elevation[land].max()) if land.any() else 1.0
    altitude = _normalise(elevation, sea_level, peak)
    factor = 1.0 + ELEVATION_SHADE * (altitude - 0.5)
    factor *= _canopy_texture(surface.shape)
    factor *= _hillshade(elevation)
    factor = np.clip(factor, *SHADE_FACTOR_RANGE)

    mountain = surface == Surface.MOUNTAIN
    if mountain.any():
        snow = _normalise(
            elevation, float(elevation[mountain].min()), float(elevation[mountain].max())
        )
        rock = SURFACE_COLORS[Surface.MOUNTAIN]
        rgb[mountain] = _lerp(rock, MOUNTAIN_PEAK_COLOR, snow[mountain] ** MOUNTAIN_SNOW_EXPONENT)
        rgb[mountain] *= factor[mountain][:, None]

    sand = surface == Surface.SAND
    rgb[sand] *= factor[sand][:, None]

    surf = _touching(water, land)
    if surf.any():
        rgb[surf] += (np.asarray(SURF_COLOR, dtype=np.float32) - rgb[surf]) * SURF_BLEND

    # Grass runs from deep lowland green to pale, dry highland green, so the
    # island shows altitude bands rather than a single flat field of colour.
    forest = surface == Surface.FOREST
    banding = altitude[forest] ** GRASS_ALTITUDE_CURVE
    lush = _lerp(GRASS_LOWLAND_COLOR, GRASS_HIGHLAND_COLOR, banding)
    return rgb, forest, lush, factor[forest]


def _blend_grass(
    world: World,
    static: np.ndarray,
    forest: np.ndarray,
    forest_lush: np.ndarray,
    forest_factor: np.ndarray,
) -> np.ndarray:
    """Colour the forest by how much grass is left standing on it."""
    rgb = static.copy()
    if forest.any():
        capacity = np.maximum(world.grass_max[forest], 1e-6)
        density = np.clip(world.grass[forest] / capacity, 0.0, 1.0)[:, None]
        bare = np.asarray(GRASS_BARE_COLOR, dtype=np.float32)
        rgb[forest] = (bare + (forest_lush - bare) * density) * forest_factor[:, None]
    return np.clip(rgb, 0.0, 255.0)


def _to_surface(rgb: np.ndarray) -> pygame.Surface:
    """Convert a ``(height, width, 3)`` colour array into a pygame surface."""
    clipped = rgb.astype(np.uint8)
    # make_surface expects (width, height, 3), the transpose of the world grid.
    return pygame.surfarray.make_surface(np.transpose(clipped, (1, 0, 2)))


class WorldRenderer:
    """Caches the terrain surface and draws the visible region each frame."""

    def __init__(self, world: World) -> None:
        # Both are filled in by set_world; declared here so the attributes are
        # visible on the class rather than appearing mid-flight.
        self._layers: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
        self._terrain: pygame.Surface
        self.set_world(world)

    def set_world(self, world: World) -> None:
        self.world = world
        self._layers = _static_layers(world)
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the cached surface from the world's current grass levels."""
        self._terrain = _to_surface(_blend_grass(self.world, *self._layers))

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        x0, y0, x1, y1 = camera.visible_cell_rect()
        if x1 <= x0 or y1 <= y0:
            return

        region = self._terrain.subsurface(pygame.Rect(x0, y0, x1 - x0, y1 - y0))
        dest_w = max(1, round((x1 - x0) * camera.zoom))
        dest_h = max(1, round((y1 - y0) * camera.zoom))
        resize = (
            pygame.transform.smoothscale
            if camera.zoom < _SMOOTH_SCALE_BELOW
            else pygame.transform.scale
        )
        scaled = resize(region, (dest_w, dest_h))

        sx, sy = camera.world_to_screen(x0, y0)
        surface.blit(scaled, (round(sx), round(sy)))


def draw_entities(
    surface: pygame.Surface,
    entities: list[Entity],
    camera: Camera,
) -> None:
    """Draw every entity as a filled circle, culled to the visible screen area."""
    sw, sh = camera.screen_w, camera.screen_h
    margin = 20  # pixels — entities just off-screen are still drawn to avoid pop-in

    for entity in entities:
        sx, sy = camera.world_to_screen(entity.x, entity.y)
        if sx < -margin or sx > sw + margin or sy < -margin or sy > sh + margin:
            continue
        radius = max(2, round(entity.genome.size * camera.zoom * 0.38))
        color = HERBIVORE_COLOR if entity.diet == Diet.HERBIVORE else CARNIVORE_COLOR
        pygame.draw.circle(surface, color, (round(sx), round(sy)), radius)


def find_entity_at(
    entities: list[Entity],
    camera: Camera,
    sx: float,
    sy: float,
    pixel_radius: float = 12.0,
) -> Entity | None:
    """Return the living entity nearest to screen point ``(sx, sy)`` within range.

    ``pixel_radius`` is the maximum screen-space distance (in pixels) at which a
    click counts as selecting an entity.
    """
    best: Entity | None = None
    best_dist = pixel_radius
    for entity in entities:
        if not entity.alive:
            continue
        ex, ey = camera.world_to_screen(entity.x, entity.y)
        dist = ((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5
        if dist <= best_dist:
            best_dist = dist
            best = entity
    return best


def draw_selection(surface: pygame.Surface, entity: Entity, camera: Camera) -> None:
    """Draw a highlight ring around the selected entity."""
    sx, sy = camera.world_to_screen(entity.x, entity.y)
    radius = max(4, round(entity.genome.size * camera.zoom * 0.38)) + 4
    pygame.draw.circle(surface, (255, 230, 90), (round(sx), round(sy)), radius, 2)
