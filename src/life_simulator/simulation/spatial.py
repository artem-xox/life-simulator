"""SpatialGrid: O(k) neighbour lookup via hash-bucket partitioning.

The world is divided into square buckets of ``bucket_size`` cells. Each entity
is registered in the bucket that contains its centre. A radius query collects
all buckets whose bounding box overlaps the query circle, so the result may
include entities outside the exact radius — callers should do a precise distance
check when needed.

Rebuild cost is O(N) per tick; query cost is O(k) where k is the average number
of entities in the expanded bucket neighbourhood (~constant for realistic
population densities).
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from life_simulator.simulation.entity import Entity


class SpatialGrid:
    """Hash-bucket spatial index rebuilt from scratch each simulation tick."""

    def __init__(self, bucket_size: int = 8) -> None:
        self.bucket_size = bucket_size
        self._buckets: dict[tuple[int, int], list[Entity]] = defaultdict(list)

    def _key(self, x: float, y: float) -> tuple[int, int]:
        return int(x) // self.bucket_size, int(y) // self.bucket_size

    def rebuild(self, entities: list[Entity]) -> None:
        """Rebuild the index from the current entity list. Call once per tick."""
        self._buckets.clear()
        for e in entities:
            if e.alive:
                self._buckets[self._key(e.x, e.y)].append(e)

    def nearby(self, x: float, y: float, radius: float) -> list[Entity]:
        """Return all entities in buckets overlapping the bounding box of ``radius``."""
        result: list[Entity] = []
        r_buckets = int(radius / self.bucket_size) + 1
        cx, cy = self._key(x, y)
        for bx in range(cx - r_buckets, cx + r_buckets + 1):
            for by in range(cy - r_buckets, cy + r_buckets + 1):
                bucket = self._buckets.get((bx, by))
                if bucket:
                    result.extend(bucket)
        return result
