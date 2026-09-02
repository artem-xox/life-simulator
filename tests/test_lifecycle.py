"""Tests for the lifecycle: growing up, breeding limits, and dying.

The rules here are what turn the phenotype's trade-offs into real selective
pressure. Without a cap on offspring, fitness is just breeding speed and every
other trait is noise; with one, an animal has to *survive to breed*.
"""

from __future__ import annotations

import itertools
import random

import numpy as np

from life_simulator.config.settings import (
    FERTILITY_END_FRACTION,
    FERTILITY_START_FRACTION,
    JUVENILE_FRACTION,
    LIFESPAN_BASE,
    MAX_OFFSPRING,
    NEWBORN_SIZE_FRACTION,
    Surface,
)
from life_simulator.simulation.ecosystem import Ecosystem, SpeciesConfig
from life_simulator.simulation.entity import DeathCause, Diet, Entity, LifeStage
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.spatial import SpatialGrid
from life_simulator.simulation.world import World
from life_simulator.simulation.worldgen import WorldConfig


def _meadow() -> World:
    return World(np.full((32, 32), int(Surface.FOREST), dtype=np.int8))


#: Deterministic per-animal RNG, distinct across calls. Without this, an
#: animal's lifespan (which is itself randomised, see Entity.__init__) varies
#: from run to run, and a test that places age exactly at a fractional
#: boundary can land on either side of it depending on rounding.
_rng_seeds = itertools.count(1)


def _animal(**genes: float) -> Entity:
    return Entity(16.0, 16.0, Diet.HERBIVORE, Genome(**genes), rng=random.Random(next(_rng_seeds)))


def _step(entity: Entity, world: World) -> Entity | None:
    grid = SpatialGrid()
    grid.rebuild([entity])
    return entity.step(world, grid)


# --- Growing up ------------------------------------------------------------


def test_an_animal_is_born_a_juvenile_and_grows_into_an_adult() -> None:
    animal = _animal()
    assert animal.stage is LifeStage.JUVENILE

    animal.age = round(JUVENILE_FRACTION * animal.lifespan) + 1
    assert animal.stage is LifeStage.ADULT


def test_a_newborn_is_a_fraction_of_its_genetic_size() -> None:
    animal = _animal(size=2.0)
    assert animal.body.body_size == 2.0 * NEWBORN_SIZE_FRACTION


def test_a_juvenile_grows_as_it_is_stepped() -> None:
    world = _meadow()
    animal = _animal(size=2.0)
    sizes = []
    for _ in range(3):
        for _ in range(20):
            _step(animal, world)
        sizes.append(animal.body.body_size)

    assert sizes == sorted(sizes)
    assert sizes[0] < sizes[-1]


def test_growth_stops_at_adulthood() -> None:
    world = _meadow()
    animal = _animal()
    animal.age = round(JUVENILE_FRACTION * animal.lifespan) + 1
    _step(animal, world)
    grown = animal.body.body_size

    for _ in range(50):
        _step(animal, world)

    assert animal.body.body_size == grown


def test_lifespans_vary_between_individuals() -> None:
    random.seed(2)
    spans = {_animal().lifespan for _ in range(40)}
    assert len(spans) > 1
    assert all(0.8 * LIFESPAN_BASE < s < 1.2 * LIFESPAN_BASE for s in spans)


# --- Breeding limits -------------------------------------------------------
#
# Whether *finding* a mate succeeds is a mating concern (tests/test_mating.py).
# What belongs here is the age/count gate itself: ``_can_breed()`` is a pure
# function of an animal's own state, so it is tested directly rather than by
# running a whole courtship to observe a side effect.


def test_a_juvenile_cannot_breed() -> None:
    animal = _animal()
    assert animal.stage is LifeStage.JUVENILE
    assert not animal._can_breed()


def test_a_freshly_grown_adult_can_breed() -> None:
    animal = _animal()
    # +1: FERTILITY_START_FRACTION equals JUVENILE_FRACTION, so the unrounded
    # boundary and this rounded age can land a tick apart; nudging past it is
    # what actually asks "is a freshly grown adult eligible," not "am I
    # exactly at the boundary, whichever side that rounds to."
    animal.age = round(FERTILITY_START_FRACTION * animal.lifespan) + 1
    assert animal.stage is LifeStage.ADULT
    assert animal._can_breed()


def test_breeding_stops_before_old_age() -> None:
    animal = _animal()
    animal.age = round(FERTILITY_END_FRACTION * animal.lifespan) + 1
    assert not animal._can_breed()


def test_an_animal_at_its_lifetime_limit_cannot_breed_again() -> None:
    animal = _animal()
    animal.age = round(FERTILITY_START_FRACTION * animal.lifespan)
    animal.offspring = MAX_OFFSPRING
    assert not animal._can_breed()


def test_a_freshly_bred_animal_is_resting() -> None:
    animal = _animal()
    animal.age = round(FERTILITY_START_FRACTION * animal.lifespan)
    animal.offspring = 1
    animal._breeding_rest_until = animal.age + 1
    assert not animal._can_breed()


# --- Dying -----------------------------------------------------------------


def test_starvation_is_recorded() -> None:
    world = _meadow()
    world.grass[:] = 0.0
    animal = _animal()
    animal.energy = 0.01
    _step(animal, world)

    assert not animal.alive
    assert animal.death_cause is DeathCause.STARVATION


def test_old_age_is_recorded() -> None:
    world = _meadow()
    world.grass[:] = world.grass_max
    animal = _animal()
    animal.age = animal.lifespan - 1
    animal.energy = animal.body.max_energy
    _step(animal, world)

    assert not animal.alive
    assert animal.death_cause is DeathCause.OLD_AGE


def test_predation_is_recorded() -> None:
    """No capture is ever certain, so the roll is forced rather than retried."""
    world = _meadow()
    prey = Entity(16.0, 16.0, Diet.HERBIVORE, Genome(size=0.5), energy=0.5)
    hunter = Entity(16.5, 16.0, Diet.CARNIVORE, Genome(size=2.0, vision=10.0), energy=5.0)
    hunter._rng.random = lambda: 1.0  # above any escape chance: the prey is caught
    grid = SpatialGrid()
    grid.rebuild([prey, hunter])

    hunter.step(world, grid)

    assert not prey.alive
    assert prey.death_cause is DeathCause.PREDATION


def test_a_juvenile_is_worth_less_to_a_predator() -> None:
    young = _animal()
    grown = _animal()
    grown.age = round(JUVENILE_FRACTION * grown.lifespan) + 1

    assert young.prey_value < grown.prey_value


# --- A whole population ----------------------------------------------------


def test_a_long_run_shows_every_stage_and_every_cause_of_death() -> None:
    random.seed(11)
    eco = Ecosystem.create(
        WorldConfig(seed=2026, width=160, height=120),
        [SpeciesConfig(Diet.HERBIVORE, 150), SpeciesConfig(Diet.CARNIVORE, 25)],
    )

    stages: set[LifeStage] = set()
    for _ in range(3000):
        eco.tick()
        stages.update(e.stage for e in eco.entities)

    assert stages == {LifeStage.JUVENILE, LifeStage.ADULT}
    assert all(count > 0 for count in eco.deaths.values()), eco.deaths


def test_every_death_is_accounted_for() -> None:
    """No animal may leave the world without a recorded reason."""
    random.seed(3)
    eco = Ecosystem.create(
        WorldConfig(seed=7, width=96, height=72),
        [SpeciesConfig(Diet.HERBIVORE, 60), SpeciesConfig(Diet.CARNIVORE, 10)],
    )
    seeded = len(eco.entities)

    for _ in range(1500):
        eco.tick()

    assert seeded + eco.births - sum(eco.deaths.values()) == len(eco.entities)


def test_an_animal_reaches_its_full_size_on_becoming_an_adult() -> None:
    """Growth must not stop a fraction short at the moment the stage flips."""
    world = _meadow()
    animal = _animal(size=1.5)
    while animal.stage is LifeStage.JUVENILE:
        _step(animal, world)
    _step(animal, world)

    assert animal.body.body_size == animal.genome.size
