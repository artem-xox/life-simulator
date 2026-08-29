"""Tests for the grass layer: logistic regrowth and neighbour reseeding."""

from __future__ import annotations

import numpy as np

from life_simulator.config.settings import Surface
from life_simulator.simulation.world import World


def _meadow(width: int = 9, height: int = 9) -> World:
    return World(np.full((height, width), int(Surface.FOREST), dtype=np.int8))


def _regrow(world: World, ticks: int) -> None:
    for _ in range(ticks):
        world.regrow()


# --- Logistic growth -------------------------------------------------------


def test_grass_grows_back_towards_capacity() -> None:
    world = _meadow()
    world.grass[:] = world.grass_max * 0.5
    before = world.grass.copy()

    _regrow(world, 10)

    assert np.all(world.grass > before)
    assert np.all(world.grass <= world.grass_max)


def test_grass_never_exceeds_capacity() -> None:
    world = _meadow()
    world.grass[:] = world.grass_max
    _regrow(world, 50)
    assert np.all(world.grass <= world.grass_max)


def test_growth_is_fastest_at_middling_density() -> None:
    """The signature of logistic growth: slow when sparse, slow when crowded."""

    def gain(fraction: float) -> float:
        world = _meadow()
        world.grass[:] = world.grass_max * fraction
        before = float(world.grass[4, 4])
        world.regrow()
        return float(world.grass[4, 4]) - before

    assert gain(0.5) > gain(0.1)
    assert gain(0.5) > gain(0.95)


# --- Overgrazing and recovery ----------------------------------------------


def test_bare_ground_surrounded_by_bare_ground_stays_bare() -> None:
    """Nothing is left to grow from, so an overgrazed patch does not spring back."""
    world = _meadow()
    world.grass[:] = 0.0
    _regrow(world, 200)
    assert float(world.grass.max()) == 0.0


def test_bare_ground_recovers_from_its_neighbours() -> None:
    world = _meadow()
    world.grass[:] = world.grass_max
    world.grass[4, 4] = 0.0

    _regrow(world, 30)

    assert world.grass[4, 4] > 0.0


def test_an_overgrazed_patch_heals_from_its_edges_inwards() -> None:
    """A scar shrinks from the outside, so the middle is the last to come back."""
    world = _meadow(11, 11)
    world.grass[:] = world.grass_max
    world.grass[3:8, 3:8] = 0.0

    _regrow(world, 15)

    capacity = float(world.grass_max[5, 5])
    edge = float(world.grass[3, 5])
    ring = float(world.grass[4, 5])
    middle = float(world.grass[5, 5])

    assert edge > ring > middle
    assert middle < 0.01 * capacity  # the centre is still bare earth


def test_recovery_is_slower_than_regrowth_of_thinned_grass() -> None:
    """Grazing a cell bare costs far more time than merely thinning it."""
    thinned = _meadow()
    thinned.grass[:] = thinned.grass_max
    thinned.grass[4, 4] = thinned.grass_max[4, 4] * 0.5

    bare = _meadow()
    bare.grass[:] = bare.grass_max
    bare.grass[4, 4] = 0.0

    _regrow(thinned, 20)
    _regrow(bare, 20)

    assert thinned.grass[4, 4] > bare.grass[4, 4]


# --- Where grass may not go ------------------------------------------------


def test_grass_never_spreads_onto_barren_ground() -> None:
    """Sand beside a lush forest stays sand, however long the world runs."""
    surface = np.full((5, 5), int(Surface.FOREST), dtype=np.int8)
    surface[:, 3:] = int(Surface.SAND)
    surface[0, :] = int(Surface.MOUNTAIN)
    world = World(surface)
    world.grass[:] = world.grass_max

    _regrow(world, 100)

    assert np.all(world.grass[surface != int(Surface.FOREST)] == 0.0)


# --- Grazing ---------------------------------------------------------------


def test_grazing_returns_what_it_removes() -> None:
    world = _meadow()
    world.grass[2, 2] = 5.0

    assert world.graze_at(2, 2, 2.0) == 2.0
    assert world.grass[2, 2] == 3.0


def test_grazing_cannot_take_more_than_is_there() -> None:
    world = _meadow()
    world.grass[2, 2] = 1.5

    assert world.graze_at(2, 2, 10.0) == 1.5
    assert world.grass[2, 2] == 0.0
