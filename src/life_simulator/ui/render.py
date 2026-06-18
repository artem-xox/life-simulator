"""Rendering helpers: terrain surface and entity sprites.

WorldRenderer caches a 1px-per-cell terrain surface and blits a scaled slice
each frame for cheap pan/zoom. draw_entities iterates the visible entity list
and draws coloured circles scaled to the current zoom.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pygame

from life_simulator.config.settings import (
    BIOME_COLORS,
    CARNIVORE_COLOR,
    HERBIVORE_COLOR,
    Biome,
)
from life_simulator.simulation.entity import Diet
from life_simulator.simulation.world import World
from life_simulator.ui.camera import Camera

if TYPE_CHECKING:
    from life_simulator.simulation.entity import Entity


def _biome_color_table() -> np.ndarray:
    """Return an (n_biomes, 3) uint8 array of RGB colours indexed by biome."""
    size = max(int(b) for b in Biome) + 1
    table = np.zeros((size, 3), dtype=np.uint8)
    for biome, color in BIOME_COLORS.items():
        table[int(biome)] = color
    return table


_COLOR_TABLE = _biome_color_table()


def build_terrain_surface(world: World) -> pygame.Surface:
    """Build a 1px-per-cell surface coloured by biome.

    Returned surface has shape ``(width, height)`` in pixels, matching pygame's
    ``(x, y)`` surface convention.
    """
    # world.biome is (height, width); colour-map then transpose to (width, height, 3).
    rgb = _COLOR_TABLE[world.biome]  # (h, w, 3)
    rgb = np.transpose(rgb, (1, 0, 2))  # (w, h, 3) for make_surface
    return pygame.surfarray.make_surface(rgb)


class WorldRenderer:
    """Caches the terrain surface and draws the visible region each frame."""

    def __init__(self, world: World) -> None:
        self.set_world(world)

    def set_world(self, world: World) -> None:
        self.world = world
        self._terrain = build_terrain_surface(world)

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        x0, y0, x1, y1 = camera.visible_cell_rect()
        if x1 <= x0 or y1 <= y0:
            return

        region = self._terrain.subsurface(pygame.Rect(x0, y0, x1 - x0, y1 - y0))
        dest_w = max(1, round((x1 - x0) * camera.zoom))
        dest_h = max(1, round((y1 - y0) * camera.zoom))
        scaled = pygame.transform.scale(region, (dest_w, dest_h))

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
