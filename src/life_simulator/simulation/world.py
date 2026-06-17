"""The World: a grid of biomes plus a regenerating food layer.

The world is pure data and vectorised numpy logic. It knows nothing about
rendering. Arrays are indexed as ``[y, x]`` (row-major), matching numpy
conventions; callers that think in ``(x, y)`` must transpose accordingly.
"""

from __future__ import annotations

import numpy as np

from life_simulator.config.settings import (
    BIOME_FOOD_MAX,
    BIOME_MOVE_COST,
    BIOME_REGROW_RATE,
    BIOME_WALKABLE,
    Biome,
)


def _per_biome_lookup(mapping: dict[Biome, float]) -> np.ndarray:
    """Build a float array indexed by biome value from a ``{Biome: value}`` dict."""
    size = max(int(b) for b in Biome) + 1
    table = np.zeros(size, dtype=np.float32)
    for biome, value in mapping.items():
        table[int(biome)] = value
    return table


_FOOD_MAX_TABLE = _per_biome_lookup(BIOME_FOOD_MAX)
_REGROW_TABLE = _per_biome_lookup(BIOME_REGROW_RATE)
_MOVE_COST_TABLE = _per_biome_lookup(BIOME_MOVE_COST)
_WALKABLE_TABLE = _per_biome_lookup({b: float(BIOME_WALKABLE[b]) for b in Biome})


class World:
    """A rectangular grid holding terrain and a renewable food resource.

    Attributes:
        biome: int8 array of :class:`Biome` values, shape ``(height, width)``.
        food: float32 array of current food per cell.
        food_max: float32 array of per-cell food capacity (derived from biome).
    """

    def __init__(self, biome: np.ndarray) -> None:
        if biome.ndim != 2:
            raise ValueError("biome array must be 2-dimensional (height, width)")
        self.biome: np.ndarray = biome.astype(np.int8, copy=False)
        self.height, self.width = self.biome.shape

        self.food_max: np.ndarray = _FOOD_MAX_TABLE[self.biome]
        self._regrow: np.ndarray = _REGROW_TABLE[self.biome]

        # Start at 60 % of capacity so food isn't trivially abundant on tick 1.
        # This slows the initial herbivore population burst.
        self.food: np.ndarray = self.food_max * 0.6

    # --- Resource dynamics -------------------------------------------------

    def regrow_food(self, dt_ticks: float = 1.0) -> None:
        """Regrow food towards each cell's capacity.

        Args:
            dt_ticks: number of simulation ticks worth of growth to apply.
        """
        self.food += self._regrow * self.food_max * dt_ticks
        np.clip(self.food, 0.0, self.food_max, out=self.food)

    def eat_at(self, x: int, y: int, amount: float) -> float:
        """Consume up to ``amount`` food at a cell; return the amount eaten."""
        available = float(self.food[y, x])
        eaten = min(available, amount)
        self.food[y, x] = available - eaten
        return eaten

    # --- Terrain queries ---------------------------------------------------

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return bool(_WALKABLE_TABLE[self.biome[y, x]])

    def move_cost(self, x: int, y: int) -> float:
        return float(_MOVE_COST_TABLE[self.biome[y, x]])
