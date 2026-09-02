"""Heritable genome: the traits passed from parent to offspring.

Design principle: genes are floating-point values with explicit (min, max)
bounds. Mutation adds Gaussian noise scaled by ``mutation_rate * gene_range``
and clips to bounds. This keeps every gene in a biologically meaningful range
regardless of how many generations of mutation accumulate.

Genes here are *independent* — a mutation to size does not touch speed. The
correlations between traits live one layer up, in
:mod:`life_simulator.simulation.phenotype`, where a body's actual abilities are
derived from its genes with physical trade-offs. That is how the relationships
work in nature: nothing couples the genes for mass and pace, but a heavier
animal really is slower.

New genes can be added by:
  1. Adding a field with a default.
  2. Adding the bounds entry to ``_BOUNDS``.
  3. Done — ``mutate()``, ``copy()`` and ``crossover()`` pick them up
     automatically via ``dataclasses.fields()``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, fields
from typing import ClassVar


@dataclass
class Genome:
    """Heritable traits of a single entity.

    Attributes:
        size: body mass scale. Drives almost every trade-off in the phenotype.
        speed: raw locomotive ability, before the drag of carrying a body.
        stealth: camouflage and quietness; how close it gets before being seen.
        vision: sight radius in cells; the range at which it sees others.
        sociality: how strongly it is drawn to its own kind.
        mutation_rate: Gaussian std-dev per gene expressed as a fraction of the
            gene's own range, so it stays meaningful across all scales. Being a
            gene itself, how fast a lineage evolves can itself evolve.
    """

    size: float = 1.0
    speed: float = 1.0
    stealth: float = 0.3
    vision: float = 6.0
    sociality: float = 0.5
    mutation_rate: float = 0.05

    # (min, max) for each mutable gene. ClassVar is ignored by @dataclass.
    _BOUNDS: ClassVar[dict[str, tuple[float, float]]] = {
        "size": (0.5, 2.5),
        "speed": (0.5, 2.0),
        "stealth": (0.0, 1.0),
        "vision": (3.0, 14.0),
        "sociality": (0.0, 1.0),
        "mutation_rate": (0.005, 0.25),
    }

    def mutate(self, rng: random.Random | None = None) -> Genome:
        """Return a new Genome with Gaussian noise applied to every bounded gene.

        Args:
            rng: generator to draw from. The simulation passes its own seeded
                one so a run reproduces; callers with no stake in determinism
                may omit it.
        """
        draw = rng if rng is not None else random
        kwargs: dict[str, float] = {}
        for f in fields(self):
            value: float = getattr(self, f.name)
            if f.name in self._BOUNDS:
                low, high = self._BOUNDS[f.name]
                value += draw.gauss(0.0, self.mutation_rate * (high - low))
                value = max(low, min(high, value))
            kwargs[f.name] = value
        return Genome(**kwargs)

    def crossover(self, other: Genome, rng: random.Random | None = None) -> Genome:
        """Return a child genome: each gene from one parent, then mutated once.

        Uniform crossover — an independent coin flip per gene — rather than
        averaging the parents. Averaging would pull every offspring towards the
        population mean and bleed away the variation selection needs; picking
        whole genes keeps the extremes in circulation.

        The child mutates at the rate it inherited, not its parents'.
        """
        draw = rng if rng is not None else random
        inherited = Genome(
            **{f.name: getattr(draw.choice((self, other)), f.name) for f in fields(self)}
        )
        return inherited.mutate(rng)

    def copy(self) -> Genome:
        """Return a shallow copy with identical gene values."""
        return Genome(**{f.name: getattr(self, f.name) for f in fields(self)})
