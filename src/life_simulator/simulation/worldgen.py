"""Deterministic world generation from layered OpenSimplex noise.

Two noise fields are combined into a biome map:

* **elevation** decides water vs. land and, on land, lowlands vs. mountains;
* **moisture** decides how wet the land is (desert -> grass -> forest).

A single integer ``seed`` makes generation fully reproducible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from opensimplex import OpenSimplex

from life_simulator.config.settings import Biome
from life_simulator.simulation.world import World

log = logging.getLogger(__name__)


@dataclass
class WorldConfig:
    """Parameters that shape a generated world.

    Attributes:
        seed: master seed; identical seeds + params produce identical worlds.
        width: map width in cells.
        height: map height in cells.
        water_level: fraction of the map (0..1) below sea level.
        climate: moisture bias in [-1, 1]; negative = drier, positive = wetter.
        elevation_scale: feature size of the elevation noise (larger = bigger
            continents).
        moisture_scale: feature size of the moisture noise.
        octaves: number of noise octaves summed for fractal detail.
    """

    seed: int = 1
    width: int = 256
    height: int = 192
    water_level: float = 0.42
    climate: float = 0.0
    elevation_scale: float = 90.0
    moisture_scale: float = 120.0
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


def _classify(elevation: np.ndarray, moisture: np.ndarray, cfg: WorldConfig) -> np.ndarray:
    """Turn elevation/moisture fields into a biome index array."""
    biome = np.empty(elevation.shape, dtype=np.int8)

    sea = cfg.water_level
    moist = np.clip(moisture + cfg.climate * 0.3, 0.0, 1.0)

    biome[:] = Biome.GRASS

    deep = elevation < sea * 0.6
    water = (elevation >= sea * 0.6) & (elevation < sea)
    beach = (elevation >= sea) & (elevation < sea + 0.05)
    mountain = elevation > 0.82
    snow = elevation > 0.92

    land = elevation >= sea
    desert_like = land & (moist < 0.35)
    forest_like = land & (moist > 0.6)

    biome[desert_like] = Biome.SAND
    biome[forest_like] = Biome.FOREST
    biome[beach] = Biome.SAND
    biome[mountain] = Biome.MOUNTAIN
    biome[snow] = Biome.SNOW
    biome[water] = Biome.WATER
    biome[deep] = Biome.DEEP_WATER

    return biome


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

    log.debug("computing moisture noise...")
    moist_gen = OpenSimplex(seed=cfg.seed + 1_000_003)
    moisture = _fractal_noise(moist_gen, cfg.width, cfg.height, cfg.moisture_scale, cfg.octaves)

    log.debug("classifying biomes...")
    biome = _classify(elevation, moisture, cfg)

    unique, counts = np.unique(biome, return_counts=True)
    total = biome.size
    biome_summary = "  ".join(
        f"{Biome(b).name}={c / total * 100:.0f}%" for b, c in zip(unique, counts, strict=True)
    )
    log.info("biome distribution: %s", biome_summary)

    world = World(biome)
    log.info("world ready  walkable cells: %d / %d", int((world.food_max > 0).sum()), total)
    return world
