"""Tests for terrain shading.

These exercise the colour maths only — no display is opened, so they run
headless in CI alongside the simulation tests.
"""

from __future__ import annotations

import numpy as np

from life_simulator.config.settings import Surface
from life_simulator.simulation.world import World
from life_simulator.ui.render import _blend_grass, _static_layers


def _flat_world(surface_type: Surface, elevation: float = 0.5) -> World:
    surface = np.full((8, 8), int(surface_type), dtype=np.int8)
    return World(surface, np.full((8, 8), elevation, dtype=np.float32))


def _shade(world: World) -> np.ndarray:
    return _blend_grass(world, *_static_layers(world))


def test_grazed_forest_looks_drier_than_lush_forest() -> None:
    """The map has to show where the herds have been eating, at any altitude."""
    for elevation in (0.1, 0.5, 0.95):
        world = _flat_world(Surface.FOREST, elevation)

        world.grass[:] = world.grass_max
        lush = _shade(world).mean(axis=(0, 1))

        world.grass[:] = 0.0
        bare = _shade(world).mean(axis=(0, 1))

        # "Greenness" is how far green runs ahead of red; grazing must drop it
        # whether the cell is a coastal meadow or a pale highland slope.
        assert lush[1] - lush[0] > bare[1] - bare[0]


def test_deep_water_is_darker_than_the_shallows() -> None:
    surface = np.full((4, 4), int(Surface.OCEAN), dtype=np.int8)
    elevation = np.tile(np.array([0.05, 0.1, 0.2, 0.3], dtype=np.float32), (4, 1))
    rgb = _shade(World(surface, elevation))

    assert rgb[:, 0].sum() < rgb[:, -1].sum()


def test_shading_stays_inside_the_colour_range() -> None:
    """Hillshade and elevation multiply the base colours; they must not overflow."""
    for surface_type in Surface:
        world = _flat_world(surface_type, elevation=0.9)
        rgb = _shade(world)
        assert rgb.min() >= 0.0
        assert rgb.max() <= 255.0


def test_a_world_without_elevation_still_renders() -> None:
    """Worlds built straight from a surface array carry no terrain height."""
    world = World(np.full((6, 6), int(Surface.FOREST), dtype=np.int8))
    assert _shade(world).shape == (6, 6, 3)
