"""Tests for the phenotype: the trade-offs that turn genes into abilities.

These assert *directions*, not numbers. The exact constants are for the balance
pass to settle; what must never change is that growing large is a bargain with
costs on both sides, so no gene is simply better than its alternatives.
"""

from __future__ import annotations

import pytest

from life_simulator.config.settings import MAX_STEALTH
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.phenotype import Phenotype

SIZES = (0.5, 1.0, 1.5, 2.0, 2.5)


def _by_size(size: float, **genes: float) -> Phenotype:
    return Phenotype.of(Genome(size=size, **genes))


def _ordered(values: list[float]) -> bool:
    """True if ``values`` strictly increases."""
    return all(a < b for a, b in zip(values[:-1], values[1:], strict=True))


# --- What size buys --------------------------------------------------------


def test_bigger_bodies_hold_more_energy() -> None:
    assert _ordered([_by_size(s).max_energy for s in SIZES])


def test_energy_storage_outgrows_mass() -> None:
    """Doubling the body more than doubles the reserve — big animals endure."""
    small, large = _by_size(1.0), _by_size(2.0)
    assert large.max_energy > 2 * small.max_energy


def test_bigger_bodies_survive_longer_between_meals() -> None:
    """Kleiber's law: upkeep grows slower than mass, so reserves last longer."""
    endurance = [_by_size(s).max_energy / _by_size(s).tick_cost for s in SIZES]
    assert _ordered(endurance)


def test_bigger_bodies_have_more_leverage_to_escape() -> None:
    assert _ordered([_by_size(s).escape_power for s in SIZES])


# --- What size costs -------------------------------------------------------


def test_bigger_bodies_cost_more_to_run() -> None:
    assert _ordered([_by_size(s).tick_cost for s in SIZES])


def test_upkeep_grows_slower_than_mass() -> None:
    """The other half of Kleiber: a doubled body costs less than double."""
    small, large = _by_size(1.0), _by_size(2.0)
    assert small.tick_cost < large.tick_cost < 2 * small.tick_cost


def test_bigger_bodies_are_slower() -> None:
    assert _ordered([_by_size(s).speed for s in reversed(SIZES)])


def test_bigger_bodies_are_easier_to_spot() -> None:
    stealth = [_by_size(s, stealth=0.8).stealth for s in SIZES]
    assert _ordered(list(reversed(stealth)))


# --- Bounds and other genes ------------------------------------------------


def test_stealth_stays_in_range() -> None:
    for size in SIZES:
        for gene in (0.0, 0.5, 1.0):
            assert 0.0 <= _by_size(size, stealth=gene).stealth <= MAX_STEALTH


def test_a_perfectly_hidden_animal_is_still_not_invisible() -> None:
    assert _by_size(0.5, stealth=1.0).stealth <= MAX_STEALTH


def test_the_speed_gene_still_makes_an_animal_faster() -> None:
    slow = Phenotype.of(Genome(size=1.0, speed=0.5))
    fast = Phenotype.of(Genome(size=1.0, speed=2.0))
    assert fast.speed > slow.speed


def test_sprinting_is_punishingly_expensive_for_fast_animals() -> None:
    """Cost is quadratic in pace, so speed is not free once it is used."""
    slow = Phenotype.of(Genome(size=1.0, speed=0.5))
    fast = Phenotype.of(Genome(size=1.0, speed=2.0))
    assert fast.sprint_cost > 4 * slow.sprint_cost


def test_sprinting_costs_more_than_standing_still() -> None:
    body = _by_size(1.0)
    assert body.sprint_cost > body.tick_cost


# --- Growth ----------------------------------------------------------------


def test_a_juvenile_is_a_smaller_version_of_its_genes() -> None:
    """Half-grown means half the body, with every consequence that follows."""
    grown = Phenotype.of(Genome(size=2.0), growth=1.0)
    young = Phenotype.of(Genome(size=2.0), growth=0.5)

    assert young.body_size == pytest.approx(grown.body_size / 2)
    assert young.max_energy < grown.max_energy
    assert young.tick_cost < grown.tick_cost
    assert young.escape_power < grown.escape_power
    assert young.speed > grown.speed  # a lighter body is quicker for its genes


def test_growth_does_not_change_the_genes() -> None:
    genome = Genome(size=2.0)
    Phenotype.of(genome, growth=0.4)
    assert genome.size == 2.0
