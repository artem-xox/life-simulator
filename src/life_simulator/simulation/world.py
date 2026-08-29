"""The World: a grid of surfaces plus a regenerating food layer.

The world is pure data and vectorised numpy logic. It knows nothing about
rendering. Arrays are indexed as ``[y, x]`` (row-major), matching numpy
conventions; callers that think in ``(x, y)`` must transpose accordingly.
"""

from __future__ import annotations

import numpy as np

from life_simulator.config.settings import (
    SURFACE_FOOD_MAX,
    SURFACE_MOVE_COST,
    SURFACE_REGROW_RATE,
    SURFACE_WALKABLE,
    Surface,
)


def _per_surface_lookup(mapping: dict[Surface, float]) -> np.ndarray:
    """Build a float array indexed by surface value from a ``{Surface: value}`` dict."""
    size = max(int(s) for s in Surface) + 1
    table = np.zeros(size, dtype=np.float32)
    for surface, value in mapping.items():
        table[int(surface)] = value
    return table


_FOOD_MAX_TABLE = _per_surface_lookup(SURFACE_FOOD_MAX)
_REGROW_TABLE = _per_surface_lookup(SURFACE_REGROW_RATE)
_MOVE_COST_TABLE = _per_surface_lookup(SURFACE_MOVE_COST)
_WALKABLE_TABLE = _per_surface_lookup({s: float(SURFACE_WALKABLE[s]) for s in Surface})


class World:
    """A rectangular grid holding terrain and a renewable food resource.

    Attributes:
        surface: int8 array of :class:`Surface` values, shape ``(height, width)``.
        elevation: float32 array of normalised terrain height in [0, 1]. Kept
            after generation because the renderer shades the map by it.
        food: float32 array of current food per cell.
        food_max: float32 array of per-cell food capacity (derived from surface).
    """

    def __init__(self, surface: np.ndarray, elevation: np.ndarray | None = None) -> None:
        if surface.ndim != 2:
            raise ValueError("surface array must be 2-dimensional (height, width)")
        self.surface: np.ndarray = surface.astype(np.int8, copy=False)
        self.height, self.width = self.surface.shape

        if elevation is None:
            elevation = np.zeros(self.surface.shape, dtype=np.float32)
        elif elevation.shape != self.surface.shape:
            raise ValueError("elevation array must match the surface shape")
        self.elevation: np.ndarray = elevation.astype(np.float32, copy=False)

        self.food_max: np.ndarray = _FOOD_MAX_TABLE[self.surface]
        self._regrow: np.ndarray = _REGROW_TABLE[self.surface]

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
        return bool(_WALKABLE_TABLE[self.surface[y, x]])

    def move_cost(self, x: int, y: int) -> float:
        return float(_MOVE_COST_TABLE[self.surface[y, x]])

    def walkable_mask(self) -> np.ndarray:
        """Return a ``(height, width)`` bool array of cells entities may occupy.

        Vectorised alternative to calling :meth:`is_walkable` per cell.
        """
        return _WALKABLE_TABLE[self.surface] > 0
