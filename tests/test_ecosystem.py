"""Integration tests for the ecosystem simulation loop."""

from __future__ import annotations

import numpy as np

from life_simulator.config.settings import ATTACK_RANGE, Surface
from life_simulator.simulation.ecosystem import Ecosystem, SpeciesConfig
from life_simulator.simulation.entity import Diet, Entity
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.spatial import SpatialGrid
from life_simulator.simulation.world import World
from life_simulator.simulation.worldgen import WorldConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _small_world() -> World:
    """A uniform forest, so entity tests don't depend on where the noise put land."""
    return World(np.full((32, 32), Surface.FOREST, dtype=np.int8))


def _herb(world: World, energy: float | None = None) -> Entity:
    return Entity(16.0, 16.0, Diet.HERBIVORE, Genome(), energy)


def _carn(world: World, x: float = 16.0, energy: float | None = None) -> Entity:
    return Entity(x, 16.0, Diet.CARNIVORE, Genome(vision=10.0), energy)


# ---------------------------------------------------------------------------
# Entity-level unit tests
# ---------------------------------------------------------------------------


def test_herbivore_gains_energy_from_grass() -> None:
    world = _small_world()
    world.grass[:] = world.grass_max  # fill grass
    herb = _herb(world, energy=5.0)
    spatial = SpatialGrid()
    spatial.rebuild([herb])

    before = herb.energy
    herb.step(world, spatial)
    # It paid its upkeep but should have eaten; the net change beats upkeep alone.
    assert herb.energy > before - herb.body.tick_cost


def test_starving_herbivore_dies() -> None:
    world = _small_world()
    world.grass[:] = 0.0  # no grass anywhere
    herb = Entity(16.0, 16.0, Diet.HERBIVORE, Genome(size=2.0), energy=0.01)
    spatial = SpatialGrid()
    spatial.rebuild([herb])
    herb.step(world, spatial)
    assert not herb.alive


def test_old_entity_dies() -> None:
    world = _small_world()
    world.grass[:] = world.grass_max
    herb = _herb(world, energy=20.0)
    herb.age = herb.lifespan - 1  # one more tick will tip it over
    spatial = SpatialGrid()
    spatial.rebuild([herb])
    herb.step(world, spatial)
    assert not herb.alive


def test_reproduction_spawns_child() -> None:
    world = _small_world()
    world.grass[:] = world.grass_max
    # Give the entity energy just above its reproduction threshold.
    herb = _herb(world)
    herb.age = round(0.5 * herb.lifespan)  # grown, and inside its fertile window
    spatial = SpatialGrid()
    spatial.rebuild([herb])
    herb.step(world, spatial)  # lets its grown body settle before energy is set
    herb.energy = herb.body.max_energy  # definitely above threshold
    child = herb.step(world, spatial)
    assert child is not None
    assert child.diet == Diet.HERBIVORE
    assert child.energy > 0.0


def test_reproduction_reduces_parent_energy() -> None:
    world = _small_world()
    world.grass[:] = 0.0
    herb = _herb(world)
    herb.age = round(0.5 * herb.lifespan)
    spatial = SpatialGrid()
    spatial.rebuild([herb])
    herb.step(world, spatial)  # lets its grown body settle before energy is set
    herb.energy = herb.body.max_energy
    before = herb.energy
    herb.step(world, spatial)
    assert herb.energy < before


def test_carnivore_attack_drains_prey_energy() -> None:
    world = _small_world()
    herb = Entity(16.0, 16.0, Diet.HERBIVORE, Genome(), energy=15.0)
    carn = Entity(16.0 + ATTACK_RANGE * 0.5, 16.0, Diet.CARNIVORE, Genome(vision=10.0), energy=5.0)
    spatial = SpatialGrid()
    spatial.rebuild([herb, carn])

    before_prey = herb.energy
    carn.step(world, spatial)
    assert herb.energy < before_prey


def test_carnivore_gains_energy_from_attack() -> None:
    world = _small_world()
    herb = Entity(16.0, 16.0, Diet.HERBIVORE, Genome(), energy=15.0)
    carn = Entity(16.0 + ATTACK_RANGE * 0.5, 16.0, Diet.CARNIVORE, Genome(vision=10.0), energy=2.0)
    before_carn = carn.energy
    spatial = SpatialGrid()
    spatial.rebuild([herb, carn])
    carn.step(world, spatial)
    # Carnivore attacked within range — it should have gained energy.
    assert carn.energy > before_carn - carn.body.tick_cost


# ---------------------------------------------------------------------------
# Ecosystem-level tests
# ---------------------------------------------------------------------------


def test_ecosystem_tick_count_increments() -> None:
    cfg = WorldConfig(seed=1, width=32, height=32, water_level=0.1)
    eco = Ecosystem.create(cfg, [SpeciesConfig(Diet.HERBIVORE, 10)])
    eco.tick()
    eco.tick()
    assert eco.tick_count == 2


def test_population_never_negative() -> None:
    cfg = WorldConfig(seed=7, width=32, height=32, water_level=0.1)
    eco = Ecosystem.create(
        cfg,
        [
            SpeciesConfig(Diet.HERBIVORE, 20),
            SpeciesConfig(Diet.CARNIVORE, 5),
        ],
    )
    for _ in range(50):
        eco.tick()
        assert eco.herbivore_count >= 0
        assert eco.carnivore_count >= 0


def test_determinism_same_seed() -> None:
    """Two ecosystems with the same seed must produce identical tick-100 counts."""
    cfg = WorldConfig(seed=99, width=48, height=48, water_level=0.15)
    species = [
        SpeciesConfig(Diet.HERBIVORE, 30, Genome(mutation_rate=0.0)),
        SpeciesConfig(Diet.CARNIVORE, 8, Genome(mutation_rate=0.0)),
    ]

    import random

    def run() -> tuple[int, int]:
        random.seed(42)
        eco = Ecosystem.create(cfg, species)
        for _ in range(100):
            eco.tick()
        return eco.herbivore_count, eco.carnivore_count

    assert run() == run()


# ---------------------------------------------------------------------------
# Locomotion costs
# ---------------------------------------------------------------------------


def test_moving_costs_energy() -> None:
    """Travel is charged by distance, so covering ground is never free."""
    world = _small_world()
    world.grass[:] = 0.0  # nothing to eat, so only costs show up
    resting = Entity(16.0, 16.0, Diet.HERBIVORE, Genome(speed=1.0), energy=10.0)
    walking = Entity(16.0, 16.0, Diet.HERBIVORE, Genome(speed=1.0), energy=10.0)

    walking._move_toward(30.0, 16.0, world)

    assert walking.energy < resting.energy
    assert walking.x > 16.0


def test_a_faster_animal_spends_more_getting_there() -> None:
    """Speed buys arrival time, and pays for it in energy."""
    world = _small_world()
    slow = Entity(4.0, 16.0, Diet.HERBIVORE, Genome(speed=0.5), energy=10.0)
    fast = Entity(4.0, 16.0, Diet.HERBIVORE, Genome(speed=2.0), energy=10.0)

    for _ in range(5):
        slow._move_toward(28.0, 16.0, world)
        fast._move_toward(28.0, 16.0, world)

    assert fast.x > slow.x  # it got further
    assert fast.energy < slow.energy  # and it cost more


def test_an_animal_that_cannot_move_pays_nothing() -> None:
    """Blocked on every side, it holds still rather than burning energy in place."""
    surface = np.full((5, 5), int(Surface.OCEAN), dtype=np.int8)
    surface[2, 2] = int(Surface.FOREST)
    world = World(surface)
    stuck = Entity(2.5, 2.5, Diet.HERBIVORE, Genome(), energy=10.0)

    before = stuck.energy
    stuck._move_toward(4.0, 2.5, world)

    assert stuck.energy == before
    assert (stuck.x, stuck.y) == (2.5, 2.5)
