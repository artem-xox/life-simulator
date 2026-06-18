"""Tests for the time-series statistics buffer."""

from __future__ import annotations

from life_simulator.simulation.entity import Diet, Entity
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.stats import Stats


def _entities() -> list[Entity]:
    return [
        Entity(0.0, 0.0, Diet.HERBIVORE, Genome(speed=1.0, vision=4.0, size=1.0)),
        Entity(1.0, 1.0, Diet.HERBIVORE, Genome(speed=2.0, vision=6.0, size=2.0)),
        Entity(2.0, 2.0, Diet.CARNIVORE, Genome(speed=3.0, vision=8.0, size=3.0)),
    ]


def test_record_counts_per_diet() -> None:
    stats = Stats()
    stats.record(0, _entities())
    sample = stats.latest
    assert sample is not None
    assert sample.herbivores == 2
    assert sample.carnivores == 1


def test_record_computes_population_averages() -> None:
    stats = Stats()
    stats.record(10, _entities())
    sample = stats.latest
    assert sample is not None
    assert sample.tick == 10
    assert sample.avg_speed == (1.0 + 2.0 + 3.0) / 3
    assert sample.avg_vision == (4.0 + 6.0 + 8.0) / 3
    assert sample.avg_size == (1.0 + 2.0 + 3.0) / 3


def test_empty_population_does_not_divide_by_zero() -> None:
    stats = Stats()
    stats.record(0, [])
    sample = stats.latest
    assert sample is not None
    assert sample.herbivores == 0
    assert sample.carnivores == 0
    assert sample.avg_speed == 0.0


def test_ring_buffer_drops_oldest() -> None:
    stats = Stats(capacity=3)
    for tick in range(5):
        stats.record(tick, _entities())
    assert len(stats) == 3
    assert [s.tick for s in stats.samples] == [2, 3, 4]


def test_clear_empties_buffer() -> None:
    stats = Stats()
    stats.record(0, _entities())
    stats.clear()
    assert len(stats) == 0
    assert stats.latest is None
