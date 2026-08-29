"""The World: a grid of surfaces plus a living grass layer.

The world is pure data and vectorised numpy logic. It knows nothing about
rendering. Arrays are indexed as ``[y, x]`` (row-major), matching numpy
conventions; callers that think in ``(x, y)`` must transpose accordingly.

Grass is the ecosystem's only energy inflow, so how it regrows decides whether
herds can stay put or have to keep moving. It grows logistically — from what is
still standing, fastest at middling density — which means a cell grazed to bare
earth has nothing left to grow from and can only recover by seeding in from its
neighbours.
"""

from __future__ import annotations

import numpy as np

from life_simulator.config.settings import (
    GRASS_REGROW_RATE,
    GRASS_SPREAD_RATE,
    INITIAL_GRASS_FRACTION,
    SURFACE_GRASS_MAX,
    SURFACE_MOVE_COST,
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


_GRASS_MAX_TABLE = _per_surface_lookup(SURFACE_GRASS_MAX)
_MOVE_COST_TABLE = _per_surface_lookup(SURFACE_MOVE_COST)
_WALKABLE_TABLE = _per_surface_lookup({s: float(SURFACE_WALKABLE[s]) for s in Surface})


class World:
    """A rectangular grid holding terrain and the grass growing on it.

    Attributes:
        surface: int8 array of :class:`Surface` values, shape ``(height, width)``.
        elevation: float32 array of normalised terrain height in [0, 1]. Kept
            after generation because the renderer shades the map by it.
        grass: float32 array of grass currently standing on each cell.
        grass_max: float32 array of per-cell capacity (derived from surface).
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

        self.grass_max: np.ndarray = _GRASS_MAX_TABLE[self.surface]
        self._fertile: np.ndarray = self.grass_max > 0.0
        self.grass: np.ndarray = self.grass_max * INITIAL_GRASS_FRACTION

    # --- Grass dynamics ----------------------------------------------------

    def regrow(self, dt_ticks: float = 1.0) -> None:
        """Grow the grass by one step of logistic growth plus neighbour seeding.

        Args:
            dt_ticks: number of simulation ticks worth of growth to apply.
        """
        headroom = self._headroom()
        seeded = _neighbour_mean(self.grass)

        growth = GRASS_REGROW_RATE * self.grass + GRASS_SPREAD_RATE * seeded
        growth *= headroom * dt_ticks
        growth *= self._fertile  # nothing takes root on sand, rock or water

        self.grass += growth
        np.clip(self.grass, 0.0, self.grass_max, out=self.grass)

    def _headroom(self) -> np.ndarray:
        """Return how much of each cell's capacity is still free, in [0, 1].

        Growth slows to nothing as a cell fills up — the crowding term that
        makes the curve logistic rather than exponential.
        """
        filled = np.zeros(self.grass.shape, dtype=np.float32)
        np.divide(self.grass, self.grass_max, out=filled, where=self._fertile)
        return np.clip(1.0 - filled, 0.0, 1.0)

    def graze_at(self, x: int, y: int, amount: float) -> float:
        """Eat up to ``amount`` grass from a cell; return how much was eaten."""
        available = float(self.grass[y, x])
        eaten = min(available, amount)
        self.grass[y, x] = available - eaten
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


def _neighbour_mean(field: np.ndarray) -> np.ndarray:
    """Return the mean of each cell's four orthogonal neighbours.

    Cells off the edge of the map count as zero, so grass spreads inwards from
    a coastline rather than wrapping around it.
    """
    total = np.zeros_like(field)
    total[1:, :] += field[:-1, :]
    total[:-1, :] += field[1:, :]
    total[:, 1:] += field[:, :-1]
    total[:, :-1] += field[:, 1:]
    return total * 0.25
