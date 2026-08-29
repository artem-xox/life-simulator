"""Vectorised helpers for reasoning about a 2D cell grid.

Terrain generation, grass growth and terrain shading all need the same handful
of neighbourhood operations. They live here so there is one implementation of
each rather than a copy per caller.

Every function treats cells beyond the map edge as absent — a mask does not
grow past the border and a blur averages against nothing there — so features
stop at the coastline instead of wrapping around it. Arrays are indexed
``[y, x]``, matching the rest of the simulation.
"""

from __future__ import annotations

import numpy as np


def neighbour_sum(field: np.ndarray) -> np.ndarray:
    """Return the sum of each cell's four orthogonal neighbours."""
    total = np.zeros_like(field)
    total[1:, :] += field[:-1, :]
    total[:-1, :] += field[1:, :]
    total[:, 1:] += field[:, :-1]
    total[:, :-1] += field[:, 1:]
    return total


def neighbour_mean(field: np.ndarray) -> np.ndarray:
    """Return the mean of each cell's four orthogonal neighbours."""
    return neighbour_sum(field) * 0.25


def box_blur(field: np.ndarray, passes: int = 1) -> np.ndarray:
    """Average each cell with its four orthogonal neighbours, ``passes`` times."""
    for _ in range(passes):
        field = (field + neighbour_sum(field)) / 5.0
    return field


def dilate(mask: np.ndarray) -> np.ndarray:
    """Grow a boolean mask by one cell in the four cardinal directions."""
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def touching(mask: np.ndarray, other: np.ndarray) -> np.ndarray:
    """Return the cells of ``mask`` that share an edge with a cell of ``other``."""
    return mask & dilate(other)
