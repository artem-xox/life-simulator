"""Tests for Stage 11: sexual selection, courtship, families, and herds.

Groups are not objects the simulation tracks — they emerge from steering
nudges layered onto ordinary movement. These tests check the nudges
themselves (direction, mutuality, gating) directly wherever that is precise
enough, and fall back to running a small population and measuring an outcome
only where the claim is genuinely about emergent behaviour (herd clustering,
a family staying together).
"""

from __future__ import annotations

import itertools
import random

import numpy as np

from life_simulator.config.settings import (
    ALERT_RADIUS,
    COURTSHIP_RANGE,
    LIFESPAN_BASE,
    MAX_OFFSPRING,
    Surface,
)
from life_simulator.simulation.ecosystem import Ecosystem, SpeciesConfig
from life_simulator.simulation.entity import Diet, Entity, EntityState, LifeStage
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.spatial import SpatialGrid
from life_simulator.simulation.world import World
from life_simulator.simulation.worldgen import WorldConfig


def _meadow(size: int = 48) -> World:
    return World(np.full((size, size), int(Surface.FOREST), dtype=np.int8))


#: Old enough to be grown regardless of individual lifespan variation, and
#: comfortably inside the fertile window.
_ADULT_AGE = LIFESPAN_BASE // 2

#: Deterministic per-animal RNG, distinct across calls — see test_behaviour.py
#: for why an unseeded default makes a many-tick scenario flaky.
_rng_seeds = itertools.count(1)


def _ready_adult(x: float, y: float, diet: Diet = Diet.HERBIVORE, **genes: float) -> Entity:
    """A grown, well-fed adult: eligible to breed the moment one is nearby."""
    animal = Entity(
        x, y, diet, Genome(**genes), age=_ADULT_AGE, rng=random.Random(next(_rng_seeds))
    )
    animal.energy = animal.body.max_energy
    return animal


def _step_all(animals: list[Entity], world: World) -> list[Entity]:
    """Advance every living animal one tick; return any children born."""
    grid = SpatialGrid()
    grid.rebuild(animals)
    children = []
    for animal in animals:
        if animal.alive:
            child = animal.step(world, grid)
            if child is not None:
                children.append(child)
    return children


# ===========================================================================
# 11.1 — Sexual selection: scoring and mutual acceptance
# ===========================================================================


def test_mate_score_prefers_higher_condition() -> None:
    watcher = _ready_adult(0.0, 0.0)
    weak = _ready_adult(1.0, 0.0, size=1.0)
    weak.energy = 0.3 * weak.body.max_energy
    strong = _ready_adult(1.0, 0.0, size=1.0)
    strong.energy = 0.9 * strong.body.max_energy

    assert watcher._mate_score(strong) > watcher._mate_score(weak)


def test_mate_score_prefers_larger_size() -> None:
    watcher = _ready_adult(0.0, 0.0)
    small = _ready_adult(1.0, 0.0, size=0.6)
    large = _ready_adult(1.0, 0.0, size=2.2)

    assert watcher._mate_score(large) > watcher._mate_score(small)


def test_a_lone_eligible_adult_keeps_foraging() -> None:
    """No one to pair with — the acceptance criterion is literally this."""
    world = _meadow()
    lone = _ready_adult(20.0, 20.0)

    states = set()
    for _ in range(60):
        _step_all([lone], world)
        states.add(lone.state)

    assert states <= {EntityState.FORAGE, EntityState.REST}
    assert lone.offspring == 0
    assert lone._mate is None


def test_mutual_best_candidates_pair_up() -> None:
    world = _meadow()
    a = _ready_adult(20.0, 20.0, size=1.0)
    b = _ready_adult(21.0, 20.0, size=1.0)  # identical, so each other is the obvious pick

    _step_all([a, b], world)

    assert a._mate is b
    assert b._mate is a
    assert a.state in (EntityState.SEEK_MATE, EntityState.COURT)


def test_juveniles_are_not_eligible_candidates() -> None:
    world = _meadow()
    adult = _ready_adult(20.0, 20.0)
    juvenile = Entity(
        21.0, 20.0, Diet.HERBIVORE, Genome(), age=0, rng=random.Random(next(_rng_seeds))
    )
    juvenile.energy = juvenile.body.max_energy

    _step_all([adult, juvenile], world)

    assert adult._mate is None
    assert adult.state in (EntityState.FORAGE, EntityState.REST)


def test_carnivores_do_not_pair_with_herbivores() -> None:
    world = _meadow()
    herb = _ready_adult(20.0, 20.0, Diet.HERBIVORE)
    carn = _ready_adult(21.0, 20.0, Diet.CARNIVORE, vision=10.0)
    carn.energy = 0.9 * carn.body.max_energy  # fed, so it is in the REST branch

    _step_all([herb, carn], world)

    assert herb._mate is None
    assert carn._mate is None


def test_an_already_paired_candidate_cannot_be_poached() -> None:
    """Once mutual, a pair stops searching entirely — poaching cannot happen."""
    world = _meadow()
    a = _ready_adult(20.0, 20.0, size=1.0)
    b = _ready_adult(20.3, 20.0, size=1.0)
    for _ in range(3):
        _step_all([a, b], world)
    assert a._mate is b and b._mate is a  # committed before the newcomer shows up

    suitor = _ready_adult(20.4, 20.1, size=2.5)  # scores far higher than A ever could
    for _ in range(5):
        _step_all([a, b, suitor], world)
        assert b._mate is a
        assert suitor._mate is not b


# ===========================================================================
# 11.2 — Courtship and conception
# ===========================================================================


def test_pair_transitions_to_court_once_within_range() -> None:
    world = _meadow()
    a = _ready_adult(20.0, 20.0)
    b = _ready_adult(20.0 + COURTSHIP_RANGE - 0.1, 20.0)

    _step_all([a, b], world)

    assert a.state is EntityState.COURT
    assert b.state is EntityState.COURT


def test_courting_pair_produces_a_child() -> None:
    world = _meadow()
    a = _ready_adult(20.0, 20.0)
    b = _ready_adult(20.3, 20.0)

    child = None
    for _ in range(60):
        children = _step_all([a, b], world)
        if children:
            child = children[0]
            break

    assert child is not None
    assert child.diet == Diet.HERBIVORE
    assert child.stage is LifeStage.JUVENILE
    assert a.offspring == 1
    assert b.offspring == 1


def test_child_genes_come_from_a_crossover_of_both_parents() -> None:
    """Each gene lands near one parent or the other, per Genome.crossover."""
    world = _meadow()
    low = _ready_adult(
        20.0, 20.0, size=0.5, speed=0.5, stealth=0.0, vision=3.0, sociality=0.0, mutation_rate=0.005
    )
    high = _ready_adult(
        20.3,
        20.0,
        size=2.5,
        speed=2.0,
        stealth=1.0,
        vision=14.0,
        sociality=1.0,
        mutation_rate=0.005,
    )

    child = low._conceive_with(high, world)

    for name, (lo, hi) in Genome._BOUNDS.items():
        value = getattr(child.genome, name)
        span = hi - lo
        near_low = abs(value - getattr(low.genome, name)) < 0.1 * span
        near_high = abs(value - getattr(high.genome, name)) < 0.1 * span
        assert near_low or near_high, f"{name}={value} came from neither parent"


def test_a_newborn_never_starts_over_its_own_capacity() -> None:
    """A parent-sized share of energy does not fit in a newborn-sized body."""
    world = _meadow()
    a = _ready_adult(20.0, 20.0)
    b = _ready_adult(20.3, 20.0)

    child = a._conceive_with(b, world)

    assert 0.0 < child.energy <= child.body.max_energy


def test_parents_together_pay_exactly_what_the_child_receives() -> None:
    """Nothing is burned in the handover — conception is a pure transfer."""
    world = _meadow()
    a = _ready_adult(20.0, 20.0)
    b = _ready_adult(20.3, 20.0)
    before = a.energy + b.energy

    child = a._conceive_with(b, world)

    spent = before - (a.energy + b.energy)
    assert abs(spent - child.energy) < 1e-9


def test_both_parents_are_charged_the_same_share() -> None:
    world = _meadow()
    a = _ready_adult(20.0, 20.0)
    b = _ready_adult(20.3, 20.0)
    before_a, before_b = a.energy, b.energy

    a._conceive_with(b, world)

    assert abs((before_a - a.energy) - (before_b - b.energy)) < 1e-9


def test_conception_clears_courtship_state_on_both_parents() -> None:
    world = _meadow()
    a = _ready_adult(20.0, 20.0)
    b = _ready_adult(20.3, 20.0)
    a._mate, b._mate = b, a

    a._conceive_with(b, world)

    assert a._mate is None
    assert b._mate is None
    assert a._court_ticks == 0
    assert b._court_ticks == 0


def test_a_freshly_bred_pair_cannot_conceive_again_immediately() -> None:
    world = _meadow()
    a = _ready_adult(20.0, 20.0)
    b = _ready_adult(20.3, 20.0)
    a._conceive_with(b, world)

    assert not a._can_breed()
    assert not b._can_breed()


def test_no_animal_exceeds_the_lifetime_offspring_cap() -> None:
    """A small pool of ready adults, run long enough to try repeatedly."""
    world = _meadow()
    world.grass[:] = world.grass_max
    animals = [_ready_adult(20.0 + i * 0.4, 20.0) for i in range(6)]

    for _ in range(4000):
        for animal in animals:
            if animal.alive and animal.stage is LifeStage.ADULT:
                animal.energy = animal.body.max_energy
        _step_all(animals, world)

    assert all(a.offspring <= MAX_OFFSPRING for a in animals)


# ===========================================================================
# 11.3 — Family bonds
# ===========================================================================


def test_juvenile_social_target_points_toward_its_parent() -> None:
    parent = _ready_adult(20.0, 20.0)
    juvenile = Entity(
        25.0,
        20.0,
        Diet.HERBIVORE,
        Genome(),
        age=0,
        rng=random.Random(next(_rng_seeds)),
        parents=(parent, parent),
    )
    grid = SpatialGrid()
    grid.rebuild([parent, juvenile])

    target = juvenile._social_target(grid)

    assert target is not None
    tx, _ty = target
    assert tx < 25.0  # pulled back towards the parent at x=20


def test_parent_social_target_points_toward_juvenile_offspring() -> None:
    parent = _ready_adult(20.0, 20.0)
    juvenile = Entity(
        25.0, 20.0, Diet.HERBIVORE, Genome(), age=0, rng=random.Random(next(_rng_seeds))
    )
    parent._children.append(juvenile)
    grid = SpatialGrid()
    grid.rebuild([parent, juvenile])

    target = parent._social_target(grid)

    assert target is not None
    tx, _ty = target
    assert tx > 20.0  # pulled towards the juvenile at x=25


def test_family_pull_ends_once_the_juvenile_is_grown() -> None:
    """Sociality=0 isolates the claim: with no herd pull either, nothing is left."""
    parent = _ready_adult(20.0, 20.0, sociality=0.0)
    grown_child = _ready_adult(25.0, 20.0, sociality=0.0)  # already adult
    parent._children.append(grown_child)
    grid = SpatialGrid()
    grid.rebuild([parent, grown_child])

    assert parent._social_target(grid) is None


def test_a_juvenile_stays_near_its_parent_over_time() -> None:
    """Bounded, and much tighter than an unrelated pair drifting independently."""
    world = _meadow()
    parent = _ready_adult(30.0, 30.0)
    juvenile = Entity(
        35.0,
        30.0,
        Diet.HERBIVORE,
        Genome(),
        age=0,
        rng=random.Random(next(_rng_seeds)),
        parents=(parent, parent),
    )
    parent._children.append(juvenile)

    max_distance = 0.0
    for _ in range(120):
        _step_all([parent, juvenile], world)
        max_distance = max(max_distance, parent.distance_to(juvenile))
        if juvenile.stage is LifeStage.ADULT:
            break

    # Two unrelated animals left to wander independently in the same setup
    # range past 15 cells apart; a bonded family stays under half that.
    assert max_distance < 10.0


# ===========================================================================
# 11.4 — Herd steering
# ===========================================================================


def test_herd_cohesion_pulls_toward_the_group_centre() -> None:
    watcher = _ready_adult(20.0, 20.0, sociality=1.0)
    neighbours = [_ready_adult(30.0, 20.0), _ready_adult(20.0, 30.0)]
    grid = SpatialGrid()
    grid.rebuild([watcher, *neighbours])

    target = watcher._social_target(grid)

    assert target is not None
    tx, ty = target
    assert tx > 20.0
    assert ty > 20.0


def test_zero_sociality_feels_no_cohesion() -> None:
    watcher = _ready_adult(20.0, 20.0, sociality=0.0)
    neighbour = _ready_adult(25.0, 20.0)
    grid = SpatialGrid()
    grid.rebuild([watcher, neighbour])

    # Distant enough that separation cannot be the one contributing force.
    assert watcher._social_target(grid) is None


def test_a_crowded_animal_is_pushed_apart_rather_than_stacked() -> None:
    watcher = _ready_adult(20.0, 20.0, sociality=0.0)
    crowder = _ready_adult(20.5, 20.0)  # well inside HERD_SEPARATION_RADIUS
    grid = SpatialGrid()
    grid.rebuild([watcher, crowder])

    target = watcher._social_target(grid)

    assert target is not None
    tx, _ty = target
    assert tx < 20.0  # pushed away from the crowder at x=20.5


def test_high_sociality_populations_cluster_more_than_low_sociality() -> None:
    """Per PLAN's acceptance: a metric test, averaged over several seeds.

    Any one seed's nearest-neighbour spread is noisy; the direction of the
    effect is what the ticket asks for, so the average is the claim.
    """

    def mean_nearest_neighbour(animals: list[Entity]) -> float:
        alive = [a for a in animals if a.alive]
        if len(alive) < 2:
            return float("nan")
        total = 0.0
        for i, a in enumerate(alive):
            total += min(a.distance_to(b) for j, b in enumerate(alive) if j != i)
        return total / len(alive)

    def run(sociality: float, seed: int) -> float:
        rng = random.Random(seed)
        world = _meadow(80)
        animals = [
            Entity(
                rng.uniform(10, 70),
                rng.uniform(10, 70),
                Diet.HERBIVORE,
                Genome(sociality=sociality, mutation_rate=0.0),
                age=_ADULT_AGE,
                rng=random.Random(seed * 1000 + i),
            )
            for i in range(24)
        ]
        for animal in animals:
            animal.energy = 0.8 * animal.body.max_energy
        for _ in range(150):
            _step_all(animals, world)
        return mean_nearest_neighbour(animals)

    lonely = [run(0.0, seed) for seed in range(1, 6)]
    social = [run(1.0, seed) for seed in range(1, 6)]

    assert sum(social) / len(social) < 0.8 * (sum(lonely) / len(lonely))


# ===========================================================================
# 11.5 — Shared vigilance
# ===========================================================================


def test_alerted_neighbour_flees_without_seeing_the_predator_itself() -> None:
    world = _meadow(60)
    sentinel = _ready_adult(30.0, 30.0, vision=12.0)
    bystander = _ready_adult(30.0 + ALERT_RADIUS - 1.0, 30.0, vision=1.0)
    predator = Entity(
        35.0,
        30.0,
        Diet.CARNIVORE,
        Genome(stealth=0.0),
        age=_ADULT_AGE,
        rng=random.Random(next(_rng_seeds)),
    )

    assert not bystander.can_see(predator)  # the premise: it could never spot this alone

    _step_all([sentinel, bystander, predator], world)

    assert bystander.state is EntityState.FLEE


def test_alert_does_not_cross_species() -> None:
    world = _meadow(60)
    fleeing_herb = _ready_adult(30.0, 30.0, vision=12.0)
    nearby_predator = Entity(
        35.0,
        30.0,
        Diet.CARNIVORE,
        Genome(stealth=0.0, vision=1.0),
        age=_ADULT_AGE,
        rng=random.Random(next(_rng_seeds)),
    )
    another_predator = Entity(
        31.0,
        30.0,
        Diet.CARNIVORE,
        Genome(vision=1.0),
        age=_ADULT_AGE,
        rng=random.Random(next(_rng_seeds)),
    )
    another_predator.energy = 0.9 * another_predator.body.max_energy  # resting, not hunting

    _step_all([fleeing_herb, nearby_predator, another_predator], world)

    assert another_predator.state is not EntityState.FLEE  # not even a herbivore state


def test_alert_does_not_reach_beyond_its_radius() -> None:
    world = _meadow(80)
    sentinel = _ready_adult(30.0, 30.0, vision=12.0)
    far_away = _ready_adult(30.0 + ALERT_RADIUS + 5.0, 30.0, vision=1.0)
    predator = Entity(
        35.0,
        30.0,
        Diet.CARNIVORE,
        Genome(stealth=0.0),
        age=_ADULT_AGE,
        rng=random.Random(next(_rng_seeds)),
    )

    _step_all([sentinel, far_away, predator], world)

    assert far_away.state is not EntityState.FLEE


# ===========================================================================
# End-to-end: a whole population
# ===========================================================================


def test_mating_and_families_occur_over_a_long_run() -> None:
    random.seed(11)
    eco = Ecosystem.create(
        WorldConfig(seed=2026, width=160, height=120),
        [SpeciesConfig(Diet.HERBIVORE, 150), SpeciesConfig(Diet.CARNIVORE, 25)],
    )

    seen_states: set[EntityState] = set()
    for _ in range(3000):
        eco.tick()
        seen_states.update(e.state for e in eco.entities)

    assert EntityState.SEEK_MATE in seen_states
    assert EntityState.COURT in seen_states
    assert any(e._parents is not None for e in eco.entities)


def test_determinism_holds_with_mating_in_play() -> None:
    """Sexual selection adds new RNG draws (tie-breaks); reproducibility must survive."""

    def run() -> list[tuple[float, float, float, int]]:
        eco = Ecosystem.create(
            WorldConfig(seed=77, width=96, height=72),
            [SpeciesConfig(Diet.HERBIVORE, 40), SpeciesConfig(Diet.CARNIVORE, 8)],
        )
        for _ in range(300):
            eco.tick()
        return [(e.x, e.y, e.energy, e.offspring) for e in eco.entities]

    assert run() == run()
