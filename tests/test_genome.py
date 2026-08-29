"""Tests for Genome mutation, copy and crossover."""

from __future__ import annotations

import random
from dataclasses import fields

from life_simulator.simulation.genome import Genome


def test_copy_is_equal_and_independent() -> None:
    g = Genome(speed=1.5, vision=7.0)
    c = g.copy()
    assert c.speed == g.speed
    assert c.vision == g.vision
    # Modifying the copy should not affect the original.
    c.speed = 99.0
    assert g.speed == 1.5


def test_mutate_returns_new_instance() -> None:
    g = Genome()
    m = g.mutate()
    assert m is not g


def test_mutate_stays_within_bounds() -> None:
    g = Genome(mutation_rate=0.30)  # max mutation pressure
    for _ in range(200):
        g = g.mutate()
    for f in fields(g):
        if f.name in Genome._BOUNDS:
            lo, hi = Genome._BOUNDS[f.name]
            v = getattr(g, f.name)
            assert lo <= v <= hi, f"{f.name}={v} out of [{lo}, {hi}]"


def test_mutate_changes_at_least_one_gene() -> None:
    # With a reasonable mutation rate some genes should drift.
    g = Genome(mutation_rate=0.15)
    children = [g.mutate() for _ in range(20)]
    speeds = {c.speed for c in children}
    assert len(speeds) > 1, "mutation produced no variation in speed"


def test_zero_mutation_rate_is_clamped_to_minimum() -> None:
    # mutation_rate has a lower bound of 0.005; passing 0 should be clamped.
    g = Genome(mutation_rate=0.0)
    m = g.mutate()
    assert m.mutation_rate >= Genome._BOUNDS["mutation_rate"][0]


# --- Crossover -------------------------------------------------------------


def _parents() -> tuple[Genome, Genome]:
    """Two parents with no overlap in any gene, so a child's origin is legible."""
    low = Genome(size=0.5, speed=0.5, stealth=0.0, vision=3.0, sociality=0.0, mutation_rate=0.005)
    high = Genome(size=2.5, speed=2.0, stealth=1.0, vision=14.0, sociality=1.0, mutation_rate=0.005)
    return low, high


def test_crossover_takes_each_gene_from_one_parent() -> None:
    """With the smallest possible mutation, every gene lands near a parent's."""
    low, high = _parents()
    for _ in range(20):
        child = low.crossover(high)
        for name, (bound_low, bound_high) in Genome._BOUNDS.items():
            value = getattr(child, name)
            span = bound_high - bound_low
            near_low = abs(value - getattr(low, name)) < 0.1 * span
            near_high = abs(value - getattr(high, name)) < 0.1 * span
            assert near_low or near_high, f"{name}={value} came from neither parent"


def test_crossover_mixes_rather_than_averaging() -> None:
    """Averaging parents would collapse variation; crossover must preserve it."""
    low, high = _parents()
    random.seed(4)
    children = [low.crossover(high) for _ in range(60)]

    midpoint = (low.size + high.size) / 2
    assert any(c.size < midpoint for c in children)
    assert any(c.size > midpoint for c in children)


def test_crossover_draws_genes_independently() -> None:
    """A child is a mosaic of both parents, not a clone of whichever won."""
    low, high = _parents()
    random.seed(7)
    mosaics = 0
    for _ in range(40):
        child = low.crossover(high)
        from_low = child.size < 1.5
        vision_from_low = child.vision < 8.5
        if from_low != vision_from_low:
            mosaics += 1
    assert mosaics > 0


def test_crossover_stays_within_bounds() -> None:
    low, high = _parents()
    child = Genome(mutation_rate=0.25)
    for _ in range(100):
        child = child.crossover(low if child.size > 1.5 else high)
    for name, (bound_low, bound_high) in Genome._BOUNDS.items():
        value = getattr(child, name)
        assert bound_low <= value <= bound_high, f"{name}={value}"
