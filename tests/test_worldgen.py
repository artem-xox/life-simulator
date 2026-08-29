"""Tests for deterministic world generation."""

from __future__ import annotations

import numpy as np

from life_simulator.config.settings import Surface
from life_simulator.simulation.worldgen import WorldConfig, generate


def test_same_seed_is_reproducible() -> None:
    cfg = WorldConfig(seed=42, width=64, height=48)
    a = generate(cfg)
    b = generate(cfg)
    assert np.array_equal(a.surface, b.surface)


def test_different_seeds_differ() -> None:
    a = generate(WorldConfig(seed=1, width=64, height=48))
    b = generate(WorldConfig(seed=2, width=64, height=48))
    assert not np.array_equal(a.surface, b.surface)


def test_dimensions_match_config() -> None:
    cfg = WorldConfig(seed=7, width=80, height=50)
    world = generate(cfg)
    assert world.surface.shape == (cfg.height, cfg.width)
    assert world.width == cfg.width
    assert world.height == cfg.height


def test_surface_values_are_valid() -> None:
    world = generate(WorldConfig(seed=3, width=64, height=64))
    valid = {int(s) for s in Surface}
    assert set(np.unique(world.surface)).issubset(valid)


def test_higher_water_level_makes_more_ocean() -> None:
    dry = generate(WorldConfig(seed=5, width=96, height=96, water_level=0.2))
    wet = generate(WorldConfig(seed=5, width=96, height=96, water_level=0.7))

    def ocean_fraction(world) -> float:
        return float((world.surface == Surface.OCEAN).mean())

    assert ocean_fraction(wet) > ocean_fraction(dry)


def test_shore_separates_ocean_from_forest() -> None:
    world = generate(WorldConfig(seed=11, width=96, height=96))
    assert np.any(world.surface == Surface.SAND)
    assert np.any(world.surface == Surface.FOREST)


def test_food_grows_only_in_forest() -> None:
    world = generate(WorldConfig(seed=9, width=48, height=48))
    assert np.all(world.food_max[world.surface != Surface.FOREST] == 0.0)
    assert np.all(world.food_max[world.surface == Surface.FOREST] > 0.0)


def test_food_starts_below_capacity() -> None:
    world = generate(WorldConfig(seed=9, width=48, height=48))
    # World starts at 60 % of capacity to slow the initial population burst.
    assert np.all(world.food <= world.food_max)
    assert np.any(world.food > 0)


def test_water_is_not_walkable() -> None:
    world = generate(WorldConfig(seed=13, width=64, height=64))
    walkable = world.walkable_mask()
    assert not walkable[world.surface == Surface.OCEAN].any()
    assert walkable[world.surface == Surface.FOREST].all()
    assert walkable[world.surface == Surface.SAND].all()
