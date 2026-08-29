"""Deterministic world generation from layered OpenSimplex noise.

A single fractal **elevation** field is classified into surfaces:

* everything below sea level becomes ocean;
* a narrow band just above sea level becomes the sandy shore;
* the remaining land is forest, the only surface where grass grows.

A single integer ``seed`` makes generation fully reproducible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from opensimplex import OpenSimplex

from life_simulator.config.settings import Surface
from life_simulator.simulation.world import World

log = logging.getLogger(__name__)

#: Elevation band above sea level that becomes sand, as a fraction of the
#: normalised [0, 1] elevation range. Wider = broader beaches.
BEACH_BAND: float = 0.035


@dataclass
class WorldConfig:
    """Parameters that shape a generated world.

    Attributes:
        seed: master seed; identical seeds + params produce identical worlds.
        width: map width in cells.
        height: map height in cells.
        water_level: fraction of the map (0..1) below sea level.
        elevation_scale: feature size of the elevation noise (larger = bigger
            landmasses).
        octaves: number of noise octaves summed for fractal detail.
    """

    seed: int = 1
    width: int = 256
    height: int = 192
    water_level: float = 0.42
    elevation_scale: float = 90.0
    octaves: int = 4


def _fractal_noise(
    gen: OpenSimplex, width: int, height: int, scale: float, octaves: int
) -> np.ndarray:
    """Generate a fractal-Brownian-motion noise field normalised to [0, 1]."""
    field = np.zeros((height, width), dtype=np.float64)
    amplitude = 1.0
    frequency = 1.0 / scale
    total_amplitude = 0.0

    for _ in range(octaves):
        xs = np.arange(width) * frequency
        ys = np.arange(height) * frequency
        layer = gen.noise2array(xs, ys)
        field += amplitude * layer
        total_amplitude += amplitude
        amplitude *= 0.5
        frequency *= 2.0

    field /= total_amplitude
    # noise2array returns values in [-1, 1]; remap to [0, 1].
    return (field + 1.0) * 0.5


def _classify(elevation: np.ndarray, cfg: WorldConfig) -> np.ndarray:
    """Turn an elevation field into a surface index array."""
    surface = np.empty(elevation.shape, dtype=np.int8)
    sea = cfg.water_level

    surface[:] = Surface.FOREST
    surface[elevation < sea + BEACH_BAND] = Surface.SAND
    surface[elevation < sea] = Surface.OCEAN

    return surface


def generate(cfg: WorldConfig) -> World:
    """Generate a :class:`World` deterministically from ``cfg``."""
    log.info(
        "generating world  seed=%d  size=%dx%d  water_level=%.2f",
        cfg.seed,
        cfg.width,
        cfg.height,
        cfg.water_level,
    )

    log.debug("computing elevation noise (%d octaves)...", cfg.octaves)
    elev_gen = OpenSimplex(seed=cfg.seed)
    elevation = _fractal_noise(elev_gen, cfg.width, cfg.height, cfg.elevation_scale, cfg.octaves)

    log.debug("classifying surfaces...")
    surface = _classify(elevation, cfg)

    unique, counts = np.unique(surface, return_counts=True)
    total = surface.size
    summary = "  ".join(
        f"{Surface(s).name}={c / total * 100:.0f}%" for s, c in zip(unique, counts, strict=True)
    )
    log.info("surface distribution: %s", summary)

    world = World(surface)
    log.info("world ready  walkable cells: %d / %d", int(world.walkable_mask().sum()), total)
    return world
