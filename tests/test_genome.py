"""Tests for Genome mutation and copy."""

from __future__ import annotations

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
