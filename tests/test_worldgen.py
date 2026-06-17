"""Tests for deterministic world generation."""

from __future__ import annotations

import numpy as np

from life_simulator.config.settings import Biome
from life_simulator.simulation.worldgen import WorldConfig, generate


def test_same_seed_is_reproducible() -> None:
    cfg = WorldConfig(seed=42, width=64, height=48)
    a = generate(cfg)
    b = generate(cfg)
    assert np.array_equal(a.biome, b.biome)


def test_different_seeds_differ() -> None:
    a = generate(WorldConfig(seed=1, width=64, height=48))
    b = generate(WorldConfig(seed=2, width=64, height=48))
    assert not np.array_equal(a.biome, b.biome)


def test_dimensions_match_config() -> None:
    cfg = WorldConfig(seed=7, width=80, height=50)
    world = generate(cfg)
    assert world.biome.shape == (cfg.height, cfg.width)
    assert world.width == cfg.width
    assert world.height == cfg.height


def test_biome_values_are_valid() -> None:
    world = generate(WorldConfig(seed=3, width=64, height=64))
    valid = {int(b) for b in Biome}
    assert set(np.unique(world.biome)).issubset(valid)


def test_higher_water_level_makes_more_water() -> None:
    dry = generate(WorldConfig(seed=5, width=96, height=96, water_level=0.2))
    wet = generate(WorldConfig(seed=5, width=96, height=96, water_level=0.7))

    def water_fraction(world) -> float:
        mask = (world.biome == Biome.WATER) | (world.biome == Biome.DEEP_WATER)
        return float(mask.mean())

    assert water_fraction(wet) > water_fraction(dry)


def test_food_starts_below_capacity() -> None:
    world = generate(WorldConfig(seed=9, width=48, height=48))
    # World starts at 60 % of capacity to slow the initial population burst.
    assert np.all(world.food <= world.food_max)
    assert np.any(world.food > 0)
