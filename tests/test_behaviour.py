"""Tests for behaviour: detection, states, chases and captures.

The detection rule and the capture roll are where two of the genome's genes
finally bite. These tests build animals by hand so each rule can be checked on
its own, then a whole-population run checks the rules hold together.
"""

from __future__ import annotations

import numpy as np

from life_simulator.config.settings import (
    HUNGER_THRESHOLD,
    LIFESPAN_BASE,
    MAX_ESCAPE_CHANCE,
    MIN_ESCAPE_CHANCE,
    Surface,
)
from life_simulator.simulation.ecosystem import Ecosystem, SpeciesConfig
from life_simulator.simulation.entity import (
    DeathCause,
    Diet,
    Entity,
    EntityState,
    LifeStage,
)
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.phenotype import Phenotype
from life_simulator.simulation.spatial import SpatialGrid
from life_simulator.simulation.world import World
from life_simulator.simulation.worldgen import WorldConfig


def _meadow(size: int = 64) -> World:
    return World(np.full((size, size), int(Surface.FOREST), dtype=np.int8))


#: Old enough to be grown whatever the individual lifespan turns out to be, so
#: the body an animal is built with is the body the tests measure.
_ADULT_AGE = LIFESPAN_BASE // 2


def _grazer(x: float = 32.0, y: float = 32.0, **genes: float) -> Entity:
    return Entity(x, y, Diet.HERBIVORE, Genome(**genes), age=_ADULT_AGE)


def _hunter(x: float = 32.0, y: float = 32.0, **genes: float) -> Entity:
    genes.setdefault("vision", 10.0)
    return Entity(x, y, Diet.CARNIVORE, Genome(**genes), age=_ADULT_AGE)


def _step_all(animals: list[Entity], world: World) -> None:
    grid = SpatialGrid()
    grid.rebuild(animals)
    for animal in animals:
        if animal.alive:
            animal.step(world, grid)


# --- Detection -------------------------------------------------------------


def test_stealth_shortens_the_range_at_which_an_animal_is_seen() -> None:
    watcher = _hunter(vision=10.0)
    obvious = _grazer(stealth=0.0)
    hidden = _grazer(stealth=0.8)

    assert watcher.detection_range(hidden) < watcher.detection_range(obvious)


def test_sharper_eyes_see_further() -> None:
    keen = _hunter(vision=12.0)
    dim = _hunter(vision=4.0)
    prey = _grazer(stealth=0.2)

    assert keen.detection_range(prey) > dim.detection_range(prey)


def test_detection_is_not_mutual() -> None:
    """A stealthy hunter can be inside a grazer's range without being noticed."""
    hunter = _hunter(x=32.0, vision=12.0, stealth=0.9)
    grazer = _grazer(x=38.0, vision=12.0, stealth=0.0)

    assert hunter.can_see(grazer)
    assert not grazer.can_see(hunter)


def test_size_undermines_the_stealth_gene() -> None:
    """Bulk is conspicuous, so the same gene hides a big animal less well."""
    watcher = _hunter(vision=12.0)
    small = _grazer(size=0.6, stealth=0.8)
    large = _grazer(size=2.2, stealth=0.8)

    assert watcher.detection_range(small) < watcher.detection_range(large)


# --- Herbivore states ------------------------------------------------------


def test_a_grazer_forages_when_hungry_and_unthreatened() -> None:
    world = _meadow()
    grazer = _grazer()
    grazer.energy = 0.3 * grazer.body.max_energy
    _step_all([grazer], world)

    assert grazer.state is EntityState.FORAGE


def test_a_full_grazer_rests() -> None:
    world = _meadow()
    grazer = _grazer()
    grazer.energy = grazer.body.max_energy
    _step_all([grazer], world)

    assert grazer.state is EntityState.REST


def test_a_grazer_flees_a_predator_it_can_see() -> None:
    world = _meadow()
    grazer = _grazer(x=32.0, vision=12.0)
    hunter = _hunter(x=35.0, stealth=0.0)
    grazer.energy = 0.5 * grazer.body.max_energy

    _step_all([grazer, hunter], world)

    assert grazer.state is EntityState.FLEE
    assert grazer.x < 32.0  # it moved away from the danger


def test_fleeing_beats_being_full() -> None:
    """Danger overrides comfort: a sated animal still runs."""
    world = _meadow()
    grazer = _grazer(x=32.0, vision=12.0)
    grazer.energy = grazer.body.max_energy
    hunter = _hunter(x=35.0, stealth=0.0)

    _step_all([grazer, hunter], world)

    assert grazer.state is EntityState.FLEE


def test_a_grazer_keeps_running_after_the_danger_is_out_of_sight() -> None:
    world = _meadow()
    grazer = _grazer(x=32.0, vision=12.0)
    grazer.energy = 0.5 * grazer.body.max_energy
    hunter = _hunter(x=35.0, stealth=0.0)

    _step_all([grazer, hunter], world)
    hunter.alive = False  # the threat vanishes entirely
    _step_all([grazer], world)

    assert grazer.state is EntityState.FLEE


# --- Predator states -------------------------------------------------------


def test_a_fed_predator_rests_instead_of_hunting() -> None:
    world = _meadow()
    hunter = _hunter(x=32.0)
    hunter.energy = hunter.body.max_energy
    prey = _grazer(x=34.0)

    _step_all([hunter, prey], world)

    assert hunter.state is EntityState.REST


def test_a_hungry_predator_with_no_prey_in_sight_hunts() -> None:
    world = _meadow()
    hunter = _hunter()
    hunter.energy = 0.2 * hunter.body.max_energy

    _step_all([hunter], world)

    assert hunter.state is EntityState.HUNT


def test_a_hungry_predator_chases_prey_it_can_see() -> None:
    world = _meadow()
    hunter = _hunter(x=32.0, vision=12.0)
    hunter.energy = 0.3 * hunter.body.max_energy
    prey = _grazer(x=38.0, stealth=0.0)

    _step_all([hunter, prey], world)

    assert hunter.state is EntityState.CHASE
    assert hunter.x > 32.0  # it closed the gap


def test_a_predator_stops_resting_once_it_is_hungry_again() -> None:
    """Digestion is long, but it ends — otherwise nothing would ever hunt."""
    world = _meadow()
    hunter = _hunter()
    hunter.energy = hunter.body.max_energy

    for _ in range(400):
        _step_all([hunter], world)
        if hunter.state is not EntityState.REST:
            break

    assert hunter.state is not EntityState.REST
    assert hunter.energy < HUNGER_THRESHOLD * hunter.body.max_energy


# --- Chases ----------------------------------------------------------------


def test_sprinting_costs_more_than_walking() -> None:
    world = _meadow()
    walker = _grazer(x=10.0)
    runner = _grazer(x=10.0)
    walker.energy = runner.energy = 15.0

    walker._move_toward(60.0, 32.0, world)
    runner._sprint_toward(60.0, 32.0, world)

    assert runner.x > walker.x  # covered more ground
    assert runner.energy < walker.energy  # and paid for it


def test_a_predator_gives_up_when_the_prey_is_far_clear() -> None:
    hunter = _hunter(x=0.0, vision=8.0)
    hunter.energy = 0.5 * hunter.body.max_energy
    escaped = _grazer(x=60.0, stealth=0.0)

    assert hunter._has_given_up(escaped)


def test_an_exhausted_predator_gives_up() -> None:
    hunter = _hunter(x=32.0, vision=10.0)
    hunter.energy = 0.01 * hunter.body.max_energy
    prey = _grazer(x=33.0, stealth=0.0)

    assert hunter._has_given_up(prey)


def test_no_chase_runs_forever() -> None:
    """Every hunt must end, or a predator would starve locked onto one animal."""
    world = _meadow()
    hunter = _hunter(x=10.0, vision=10.0, speed=1.0)
    hunter.energy = 0.5 * hunter.body.max_energy
    prey = _grazer(x=16.0, speed=2.0, stealth=0.0)
    prey.energy = prey.body.max_energy

    chasing = 0
    for _ in range(600):
        _step_all([hunter, prey], world)
        if not (hunter.alive and prey.alive):
            break
        if hunter.state is EntityState.CHASE:
            chasing += 1

    assert chasing < 600


# --- Captures --------------------------------------------------------------


def test_faster_prey_escapes_more_often() -> None:
    hunter = _hunter(speed=1.0)
    quick = _grazer(speed=2.0)
    slow = _grazer(speed=0.5)

    assert hunter.escape_chance(quick) > hunter.escape_chance(slow)


def test_bigger_prey_has_more_leverage_to_tear_free() -> None:
    hunter = _hunter(size=1.5)
    heavy = _grazer(size=2.4, speed=1.0)
    light = _grazer(size=0.6, speed=1.0)

    assert hunter.escape_chance(heavy) > hunter.escape_chance(light)


def test_a_juvenile_is_easier_to_catch_than_its_grown_self() -> None:
    hunter = _hunter()
    genome = Genome()
    young = Entity(32.0, 32.0, Diet.HERBIVORE, genome, age=0)
    grown = _grazer()
    assert young.body == Phenotype.of(genome, maturity=0.0)

    assert young.stage is LifeStage.JUVENILE
    assert hunter.escape_chance(young) < hunter.escape_chance(grown)


def test_no_hunt_is_ever_certain() -> None:
    """However lopsided the pairing, both outcomes stay possible."""
    hopeless = _hunter(size=2.5, speed=2.0)
    doomed = _grazer(size=0.5, speed=0.5)
    unstoppable = _hunter(size=0.5, speed=0.5)
    nimble = _grazer(size=2.5, speed=2.0)

    for chance in (hopeless.escape_chance(doomed), unstoppable.escape_chance(nimble)):
        assert MIN_ESCAPE_CHANCE <= chance <= MAX_ESCAPE_CHANCE


def test_a_kill_feeds_the_predator_and_records_the_cause() -> None:
    world = _meadow()
    hunter = _hunter(x=32.0, size=2.0, speed=2.0)
    hunter.energy = 0.2 * hunter.body.max_energy
    prey = _grazer(x=32.5, size=0.5, speed=0.5, stealth=0.0)
    before = hunter.energy

    for _ in range(200):
        _step_all([hunter, prey], world)
        if not prey.alive:
            break

    assert not prey.alive
    assert prey.death_cause is DeathCause.PREDATION
    assert hunter.energy > before


def test_a_kill_sends_the_predator_to_rest() -> None:
    world = _meadow()
    hunter = _hunter(x=32.0, size=2.0, speed=2.0)
    hunter.energy = 0.2 * hunter.body.max_energy
    prey = _grazer(x=32.5, size=0.5, speed=0.5, stealth=0.0)

    for _ in range(200):
        _step_all([hunter, prey], world)
        if not prey.alive:
            break

    assert hunter.state is EntityState.REST


def test_prey_that_tears_free_is_wounded() -> None:
    hunter = _hunter(x=32.0)
    prey = _grazer(x=32.2)
    prey.energy = 10.0
    hunter._rng.random = lambda: 0.0  # forces the escape branch

    hunter._attempt_capture(prey)

    assert prey.alive
    assert prey.energy < 10.0


def test_a_predator_that_misses_cannot_seize_again_immediately() -> None:
    hunter = _hunter(x=32.0)
    prey = _grazer(x=32.2)
    prey.energy = 10.0
    hunter._rng.random = lambda: 0.0

    hunter._attempt_capture(prey)

    assert hunter._capture_rest_until > hunter.age


# --- Determinism and a whole population ------------------------------------


def test_two_runs_of_the_same_seed_are_identical() -> None:
    """Nothing reaches for the global RNG, so a seed reproduces a whole run."""

    def run() -> list[tuple[float, float, float]]:
        eco = Ecosystem.create(
            WorldConfig(seed=99, width=96, height=72),
            [SpeciesConfig(Diet.HERBIVORE, 40), SpeciesConfig(Diet.CARNIVORE, 8)],
        )
        for _ in range(200):
            eco.tick()
        return [(e.x, e.y, e.energy) for e in eco.entities]

    assert run() == run()


def test_hunting_actually_happens_over_a_long_run() -> None:
    eco = Ecosystem.create(
        WorldConfig(seed=2026, width=160, height=120),
        [SpeciesConfig(Diet.HERBIVORE, 150), SpeciesConfig(Diet.CARNIVORE, 25)],
    )

    seen: set[EntityState] = set()
    for _ in range(2000):
        eco.tick()
        seen.update(e.state for e in eco.entities)

    assert EntityState.CHASE in seen
    assert EntityState.FLEE in seen
    assert eco.deaths[DeathCause.PREDATION] > 0
