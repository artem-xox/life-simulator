"""Time-series statistics collected as the simulation runs.

A bounded ring buffer of per-sample snapshots: population counts per diet plus
average genome values across the whole population. The UI reads these samples
to draw the live population graph and evolution trends.

Sampling is decoupled from ticks: the ecosystem calls :meth:`record` on a fixed
tick interval so the buffer covers a useful time window regardless of speed.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from life_simulator.simulation.entity import Diet, Entity


@dataclass(frozen=True)
class StatSample:
    """One snapshot of population and average genome values at a given tick."""

    tick: int
    herbivores: int
    carnivores: int
    avg_speed: float
    avg_vision: float
    avg_size: float


class Stats:
    """Bounded ring buffer of :class:`StatSample` snapshots.

    Args:
        capacity: maximum number of samples retained; oldest are dropped.
    """

    def __init__(self, capacity: int = 600) -> None:
        self._samples: deque[StatSample] = deque(maxlen=capacity)

    def record(self, tick: int, entities: Iterable[Entity]) -> None:
        """Append a snapshot computed from the current entity list in one pass."""
        herb = carn = 0
        sum_speed = sum_vision = sum_size = 0.0
        total = 0
        for e in entities:
            total += 1
            if e.diet == Diet.HERBIVORE:
                herb += 1
            else:
                carn += 1
            g = e.genome
            sum_speed += g.speed
            sum_vision += g.vision
            sum_size += g.size

        n = total or 1
        self._samples.append(
            StatSample(
                tick=tick,
                herbivores=herb,
                carnivores=carn,
                avg_speed=sum_speed / n,
                avg_vision=sum_vision / n,
                avg_size=sum_size / n,
            )
        )

    def clear(self) -> None:
        self._samples.clear()

    @property
    def samples(self) -> list[StatSample]:
        return list(self._samples)

    @property
    def latest(self) -> StatSample | None:
        return self._samples[-1] if self._samples else None

    def __len__(self) -> int:
        return len(self._samples)
