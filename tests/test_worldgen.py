"""Tests for deterministic world generation."""

from __future__ import annotations

import numpy as np

from life_simulator.config.settings import Surface
from life_simulator.simulation.world import World
from life_simulator.simulation.worldgen import MIN_ISLAND_FRACTION, WorldConfig, generate


def _component_from(mask: np.ndarray, start: tuple[int, int]) -> np.ndarray:
    """Flood-fill ``mask`` from ``start`` and return the cells reached.

    Deliberately independent of the generator's own flood fill so the tests
    check the shape of the result rather than mirroring its implementation.
    """
    reached = np.zeros(mask.shape, dtype=bool)
    reached[start] = True
    while True:
        grown = reached.copy()
        grown[1:, :] |= reached[:-1, :]
        grown[:-1, :] |= reached[1:, :]
        grown[:, 1:] |= reached[:, :-1]
        grown[:, :-1] |= reached[:, 1:]
        grown &= mask
        if np.array_equal(grown, reached):
            return reached
        reached = grown


def _components(mask: np.ndarray) -> list[np.ndarray]:
    """Split ``mask`` into its connected components."""
    remaining = mask.copy()
    found: list[np.ndarray] = []
    while remaining.any():
        ys, xs = np.nonzero(remaining)
        component = _component_from(mask, (ys[0], xs[0]))
        found.append(component)
        remaining &= ~component
    return found


def _island(seed: int, width: int = 160, height: int = 120) -> World:
    return generate(WorldConfig(seed=seed, width=width, height=height))


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


# --- Island shape ----------------------------------------------------------


def test_map_border_is_ocean() -> None:
    for seed in (1, 2, 3, 2026):
        surface = _island(seed).surface
        assert np.all(surface[0, :] == Surface.OCEAN)
        assert np.all(surface[-1, :] == Surface.OCEAN)
        assert np.all(surface[:, 0] == Surface.OCEAN)
        assert np.all(surface[:, -1] == Surface.OCEAN)


def test_one_landmass_dominates() -> None:
    """A map may be an archipelago, but most of its land is one main island."""
    for seed in (1, 2, 3, 2026):
        land = _island(seed).surface != Surface.OCEAN
        biggest = max(c.sum() for c in _components(land))
        assert biggest >= 0.5 * land.sum()


def test_no_speck_islands() -> None:
    """Islands too small to sustain a population are drowned during generation."""
    for seed in (1, 2, 3, 2026):
        world = _island(seed)
        land = world.surface != Surface.OCEAN
        smallest = min(int(c.sum()) for c in _components(land))
        assert smallest >= MIN_ISLAND_FRACTION * world.surface.size


def test_map_has_a_meaningful_amount_of_land() -> None:
    for seed in (1, 2, 3, 2026):
        world = _island(seed)
        assert 0.2 < float(world.walkable_mask().mean()) < 0.8


def test_small_maps_still_produce_a_living_island() -> None:
    """The setup screen allows maps well below the default size."""
    world = _island(5, width=80, height=60)
    assert float(world.walkable_mask().mean()) > 0.15


def test_raising_the_resolution_keeps_the_same_kind_of_island() -> None:
    """A finer map is the same world in more detail, not a different one.

    Terrain features are measured in cells, so without scaling them against the
    map size a bigger map would simply fit more, smaller islands into the same
    frame. Composition holding steady is what says the scaling works.
    """

    def composition(width: int, height: int) -> dict[Surface, float]:
        surface = generate(WorldConfig(seed=2026, width=width, height=height)).surface
        return {s: float((surface == s).mean()) for s in Surface}

    coarse = composition(200, 150)
    fine = composition(600, 450)

    for kind, share in coarse.items():
        assert abs(share - fine[kind]) < 0.05, kind


# --- Mountains -------------------------------------------------------------


def test_mountains_exist_and_block_movement() -> None:
    world = _island(2026)
    mountains = world.surface == Surface.MOUNTAIN
    assert mountains.any()
    assert not world.walkable_mask()[mountains].any()


def test_mountains_sit_above_the_forest() -> None:
    world = _island(2026)
    mountain_floor = world.elevation[world.surface == Surface.MOUNTAIN].min()
    assert mountain_floor > world.elevation[world.surface == Surface.FOREST].mean()


# --- Inland water ----------------------------------------------------------


def test_inland_water_exists() -> None:
    assert np.any(_island(2026).surface == Surface.FRESH_WATER)


def test_rivers_reach_the_ocean() -> None:
    surface = _island(2026).surface
    fresh = surface == Surface.FRESH_WATER
    ocean = surface == Surface.OCEAN
    touching_ocean = (
        (fresh[1:, :] & ocean[:-1, :]).any()
        or (fresh[:-1, :] & ocean[1:, :]).any()
        or (fresh[:, 1:] & ocean[:, :-1]).any()
        or (fresh[:, :-1] & ocean[:, 1:]).any()
    )
    assert touching_ocean


def test_inland_water_is_never_walkable() -> None:
    world = _island(2026)
    assert not world.walkable_mask()[world.surface == Surface.FRESH_WATER].any()


# --- Beaches ---------------------------------------------------------------


def _neighbours(mask: np.ndarray) -> np.ndarray:
    """Return the cells sharing an edge with a ``True`` cell of ``mask``."""
    near = np.zeros(mask.shape, dtype=bool)
    near[1:, :] |= mask[:-1, :]
    near[:-1, :] |= mask[1:, :]
    near[:, 1:] |= mask[:, :-1]
    near[:, :-1] |= mask[:, 1:]
    return near


def test_every_ocean_coast_has_sand() -> None:
    """Land that touches the sea is beach, never bare forest."""
    surface = _island(2026).surface
    coastal_land = _neighbours(surface == Surface.OCEAN) & (surface == Surface.FOREST)
    assert not coastal_land.any()


def test_lakes_and_rivers_have_banks() -> None:
    surface = _island(2026).surface
    assert (_neighbours(surface == Surface.FRESH_WATER) & (surface == Surface.SAND)).any()


def test_sand_only_appears_near_water() -> None:
    """No stray dunes inland: every beach cell is within reach of a waterline."""
    cfg = WorldConfig(seed=2026, width=160, height=120)
    world = generate(cfg)
    water = (world.surface == Surface.OCEAN) | (world.surface == Surface.FRESH_WATER)

    reach = water.copy()
    for _ in range(int(cfg.shore_width * 2) + 1):
        reach = _neighbours(reach) | reach
    assert not ((world.surface == Surface.SAND) & ~reach).any()


def test_shore_width_controls_how_much_sand() -> None:
    def sand_fraction(width: float) -> float:
        cfg = WorldConfig(seed=2026, width=160, height=120, shore_width=width)
        return float((generate(cfg).surface == Surface.SAND).mean())

    assert sand_fraction(0.0) == 0.0
    assert sand_fraction(8.0) > sand_fraction(3.0) > 0.0


def test_grass_grows_only_in_forest() -> None:
    world = generate(WorldConfig(seed=9, width=48, height=48))
    assert np.all(world.grass_max[world.surface != Surface.FOREST] == 0.0)
    assert np.all(world.grass_max[world.surface == Surface.FOREST] > 0.0)


def test_grass_starts_below_capacity() -> None:
    world = generate(WorldConfig(seed=9, width=48, height=48))
    # World starts below capacity to slow the initial population burst.
    assert np.all(world.grass <= world.grass_max)
    assert np.any(world.grass > 0)


def test_water_is_not_walkable() -> None:
    world = generate(WorldConfig(seed=13, width=64, height=64))
    walkable = world.walkable_mask()
    assert not walkable[world.surface == Surface.OCEAN].any()
    assert walkable[world.surface == Surface.FOREST].all()
    assert walkable[world.surface == Surface.SAND].all()
