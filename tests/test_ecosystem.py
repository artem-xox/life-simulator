"""Integration tests for the ecosystem simulation loop."""

from __future__ import annotations

from life_simulator.simulation.ecosystem import Ecosystem, SpeciesConfig
from life_simulator.simulation.entity import (
    ATTACK_RANGE,
    BASE_ENERGY_COST,
    MAX_AGE,
    Diet,
    Entity,
)
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.spatial import SpatialGrid
from life_simulator.simulation.world import World
from life_simulator.simulation.worldgen import WorldConfig, generate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _small_world() -> World:
    return generate(WorldConfig(seed=42, width=32, height=32, water_level=0.1))


def _herb(world: World, energy: float | None = None) -> Entity:
    return Entity(16.0, 16.0, Diet.HERBIVORE, Genome(), energy)


def _carn(world: World, x: float = 16.0, energy: float | None = None) -> Entity:
    return Entity(x, 16.0, Diet.CARNIVORE, Genome(vision=10.0), energy)


# ---------------------------------------------------------------------------
# Entity-level unit tests
# ---------------------------------------------------------------------------


def test_herbivore_gains_energy_from_food() -> None:
    world = _small_world()
    world.food[:] = world.food_max  # fill food
    herb = _herb(world, energy=5.0)
    spatial = SpatialGrid()
    spatial.rebuild([herb])

    before = herb.energy
    herb.step(world, spatial)
    # Entity spent metabolism cost but should have eaten; net change positive.
    assert herb.energy > before - BASE_ENERGY_COST * herb.genome.metabolism * herb.genome.size


def test_starving_herbivore_dies() -> None:
    world = _small_world()
    world.food[:] = 0.0  # no food anywhere
    herb = Entity(16.0, 16.0, Diet.HERBIVORE, Genome(metabolism=2.0), energy=0.01)
    spatial = SpatialGrid()
    spatial.rebuild([herb])
    herb.step(world, spatial)
    assert not herb.alive


def test_old_entity_dies() -> None:
    world = _small_world()
    world.food[:] = world.food_max
    herb = _herb(world, energy=20.0)
    herb.age = MAX_AGE  # one more tick will tip it over
    spatial = SpatialGrid()
    spatial.rebuild([herb])
    herb.step(world, spatial)
    assert not herb.alive


def test_reproduction_spawns_child() -> None:
    world = _small_world()
    world.food[:] = world.food_max
    # Give the entity energy just above its reproduction threshold.
    herb = _herb(world)
    herb.energy = herb.max_energy  # definitely above threshold
    spatial = SpatialGrid()
    spatial.rebuild([herb])
    child = herb.step(world, spatial)
    assert child is not None
    assert child.diet == Diet.HERBIVORE
    assert child.energy > 0.0


def test_reproduction_reduces_parent_energy() -> None:
    world = _small_world()
    world.food[:] = 0.0
    herb = _herb(world)
    herb.energy = herb.max_energy
    before = herb.energy
    spatial = SpatialGrid()
    spatial.rebuild([herb])
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
    assert carn.energy > before_carn - BASE_ENERGY_COST * carn.genome.metabolism * carn.genome.size


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
