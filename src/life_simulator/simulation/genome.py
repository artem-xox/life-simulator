"""Heritable genome: the traits passed from parent to offspring with mutation.

Design principle: genes are floating-point values with explicit (min, max)
bounds. Mutation adds Gaussian noise scaled by ``mutation_rate * gene_range``
and clips to bounds. This keeps every gene in a biologically meaningful range
regardless of how many generations of mutation accumulate.

New genes can be added by:
  1. Adding a field with a default.
  2. Adding the bounds entry to ``_BOUNDS``.
  3. Done — ``mutate()`` and ``copy()`` pick them up automatically via
     ``dataclasses.fields()``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, fields
from typing import ClassVar


@dataclass
class Genome:
    """Heritable traits of a single entity.

    Attributes:
        speed: movement in cells per tick.
        vision: sight radius in cells; determines search range for food/prey.
        metabolism: multiplier on the per-tick energy cost (together with size).
        size: body size; scales max energy, combat damage absorption, and cost.
        repro_threshold: fraction of max_energy required to trigger reproduction.
        mutation_rate: Gaussian std-dev per gene expressed as a fraction of the
            gene's own range — so it stays meaningful across all scales.
    """

    speed: float = 1.0
    vision: float = 6.0
    metabolism: float = 1.0
    size: float = 1.0
    repro_threshold: float = 0.7
    mutation_rate: float = 0.05

    # (min, max) for each mutable gene. ClassVar is ignored by @dataclass.
    _BOUNDS: ClassVar[dict[str, tuple[float, float]]] = {
        "speed": (0.3, 3.0),
        "vision": (2.0, 15.0),
        "metabolism": (0.5, 2.0),
        "size": (0.5, 3.0),
        "repro_threshold": (0.4, 0.9),
        "mutation_rate": (0.005, 0.30),
    }

    def mutate(self) -> Genome:
        """Return a new Genome with Gaussian noise applied to every bounded gene."""
        kwargs: dict[str, float] = {}
        for f in fields(self):
            v: float = getattr(self, f.name)
            if f.name in self._BOUNDS:
                lo, hi = self._BOUNDS[f.name]
                v = v + random.gauss(0.0, self.mutation_rate * (hi - lo))
                v = max(lo, min(hi, v))
            kwargs[f.name] = v
        return Genome(**kwargs)

    def copy(self) -> Genome:
        """Return a shallow copy with identical gene values."""
        return Genome(**{f.name: getattr(self, f.name) for f in fields(self)})
