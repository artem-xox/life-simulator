"""Deterministic world generation: an island carved from fractal noise.

Generation runs as a series of passes over one elevation field:

1. **terrain** — fractal gradient noise, sampled through a warped coordinate
   field so the landscape twists instead of looking like smooth blobs;
2. **island** — a radial falloff pulls elevation down towards the map edges,
   guaranteeing a ring of ocean. It leaves the middle of the map untouched, so
   the coastline follows the terrain: bays, headlands and offshore islands come
   out of the noise rather than being traced onto a circle;
3. **surfaces** — elevation is cut into sea, a sand shore, forest, and bare
   rock above the mountain line;
4. **inland water** — water the border ocean cannot reach becomes a lake;
5. **rivers** — many streams run downhill from the high ground. Where they
   converge they merge into one course, so a branching network forms and the
   trunks near the sea run wider than the headwaters.

A single integer ``seed`` makes every pass reproducible.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

import numpy as np

from life_simulator.config.settings import Surface
from life_simulator.simulation.world import World

log = logging.getLogger(__name__)

#: Elevation band above sea level that becomes sand, in normalised elevation
#: units. Wider = broader beaches.
BEACH_BAND: float = 0.02

#: Normalised radius at which the island falloff starts biting, and the radius
#: at which it has pulled elevation all the way to zero. Coordinates are scaled
#: so that every border cell sits at radius >= 1.0, which is what guarantees a
#: ring of ocean around the map. Keeping ``ISLAND_INNER`` high leaves the middle
#: of the map as raw terrain, which is where lakes and mountains come from.
ISLAND_INNER: float = 0.70
ISLAND_OUTER: float = 1.0

#: Percentiles the raw noise is stretched between. Anchoring on percentiles
#: instead of min/max keeps the amount of land roughly stable from seed to seed.
NOISE_STRETCH_LOW: float = 0.02
NOISE_STRETCH_HIGH: float = 0.98

#: Domain warp: before the terrain is sampled, every coordinate is displaced by
#: up to ``WARP_STRENGTH`` cells along a second, smoother noise field. This is
#: what turns rounded blobs into a ragged coast of inlets and headlands.
WARP_SCALE: float = 60.0
WARP_STRENGTH: float = 26.0
WARP_OCTAVES: int = 3

#: Landmasses smaller than this fraction of the map are drowned. Anything that
#: survives is big enough to be worth living on, so the map ends up as one main
#: island with the occasional offshore neighbour.
MIN_ISLAND_FRACTION: float = 0.008

#: Inclusive range for how many streams are traced. They merge on the way down,
#: so the map ends up with far fewer river mouths than sources.
RIVER_SOURCE_RANGE: tuple[int, int] = (10, 16)

#: Rivers start on land above this quantile of the island's elevation.
RIVER_SOURCE_QUANTILE: float = 0.75

#: How many streams have to share a cell before the river is drawn wider.
RIVER_FLOW_FOR_WIDTH_1: int = 3
RIVER_FLOW_FOR_WIDTH_2: int = 8

_OFFSETS_8: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)


@dataclass
class WorldConfig:
    """Parameters that shape a generated world.

    Attributes:
        seed: master seed; identical seeds + params produce identical worlds.
        width: map width in cells.
        height: map height in cells.
        water_level: sea level in normalised elevation units (0..1). Higher
            floods more of the map, leaving a smaller island.
        mountain_level: elevation above which land becomes impassable rock.
            Lower values raise more mountains.
        elevation_scale: feature size of the terrain noise (larger = smoother,
            more solid island; smaller = a raggedier coastline).
        octaves: number of noise octaves summed for fractal detail.
    """

    seed: int = 1
    width: int = 256
    height: int = 192
    water_level: float = 0.28
    mountain_level: float = 0.83
    elevation_scale: float = 70.0
    octaves: int = 6


# --- Noise -----------------------------------------------------------------


def _gradient_noise(rng: np.random.Generator, lx: np.ndarray, ly: np.ndarray) -> np.ndarray:
    """Perlin gradient noise sampled at lattice coordinates ``lx``/``ly``.

    A lattice of random unit gradients is laid over the field; every sample
    interpolates the dot products of the four gradients around it. Fully
    vectorised, so a whole map costs a handful of numpy operations rather than
    one call per cell.

    Args:
        lx, ly: sample positions in lattice units. Must be non-negative.
    """
    lattice_w = int(lx.max()) + 2
    lattice_h = int(ly.max()) + 2
    angles = rng.uniform(0.0, 2.0 * np.pi, size=(lattice_h, lattice_w))
    grad_x, grad_y = np.cos(angles), np.sin(angles)

    x0 = lx.astype(np.intp)
    y0 = ly.astype(np.intp)
    tx = lx - x0
    ty = ly - y0

    # Dot product of each corner's gradient with the offset from that corner.
    n00 = grad_x[y0, x0] * tx + grad_y[y0, x0] * ty
    n10 = grad_x[y0, x0 + 1] * (tx - 1.0) + grad_y[y0, x0 + 1] * ty
    n01 = grad_x[y0 + 1, x0] * tx + grad_y[y0 + 1, x0] * (ty - 1.0)
    n11 = grad_x[y0 + 1, x0 + 1] * (tx - 1.0) + grad_y[y0 + 1, x0 + 1] * (ty - 1.0)

    # Quintic fade keeps the second derivative continuous across lattice lines,
    # which is what stops the terrain from showing a square grid.
    fade_x = tx * tx * tx * (tx * (tx * 6.0 - 15.0) + 10.0)
    fade_y = ty * ty * ty * (ty * (ty * 6.0 - 15.0) + 10.0)

    top = n00 + fade_x * (n10 - n00)
    bottom = n01 + fade_x * (n11 - n01)
    return top + fade_y * (bottom - top)


def _fractal_noise(
    rng: np.random.Generator,
    coord_x: np.ndarray,
    coord_y: np.ndarray,
    scale: float,
    octaves: int,
) -> np.ndarray:
    """Sum octaves of gradient noise, each twice as fine and half as strong."""
    field = np.zeros(coord_x.shape, dtype=np.float64)
    amplitude = 1.0

    for octave in range(octaves):
        octave_scale = max(scale / (2.0**octave), 2.0)
        field += amplitude * _gradient_noise(rng, coord_x / octave_scale, coord_y / octave_scale)
        amplitude *= 0.5

    return field


def _stretch(field: np.ndarray) -> np.ndarray:
    """Rescale a field to [0, 1] between two percentiles.

    Summed octaves cluster around the middle of their range; stretching gives
    the terrain enough contrast to survive the island falloff. Anchoring on
    percentiles rather than the extremes stops one freak peak from flattening a
    whole map and leaving a tiny island.
    """
    lo, hi = np.quantile(field, (NOISE_STRETCH_LOW, NOISE_STRETCH_HIGH))
    if hi <= lo:
        return np.full_like(field, 0.5)
    return np.clip((field - lo) / (hi - lo), 0.0, 1.0)


def _elevation_field(cfg: WorldConfig, rng: np.random.Generator) -> np.ndarray:
    """Build the warped, island-shaped elevation field for a config."""
    grid_x, grid_y = np.meshgrid(
        np.arange(cfg.width, dtype=np.float64),
        np.arange(cfg.height, dtype=np.float64),
    )

    # Sampling happens at displaced coordinates, so keep everything clear of
    # zero: the noise lattice is only defined for non-negative positions.
    margin = 2.0 * WARP_STRENGTH
    warp_x = _fractal_noise(rng, grid_x + margin, grid_y + margin, WARP_SCALE, WARP_OCTAVES)
    warp_y = _fractal_noise(rng, grid_x + margin, grid_y + margin, WARP_SCALE, WARP_OCTAVES)

    sample_x = np.clip(grid_x + margin + WARP_STRENGTH * warp_x, 0.0, None)
    sample_y = np.clip(grid_y + margin + WARP_STRENGTH * warp_y, 0.0, None)

    elevation = _stretch(_fractal_noise(rng, sample_x, sample_y, cfg.elevation_scale, cfg.octaves))
    return elevation * (1.0 - _island_falloff(cfg.width, cfg.height))


def _island_falloff(width: int, height: int) -> np.ndarray:
    """Return a 0..1 field that is 0 in the middle and 1 at the map edges.

    Axes are normalised independently, so the island fills a wide map rather
    than leaving unused ocean down the sides.
    """
    nx = np.linspace(-1.0, 1.0, width)
    ny = np.linspace(-1.0, 1.0, height)
    radius = np.hypot(nx[None, :], ny[:, None])

    t = np.clip((radius - ISLAND_INNER) / (ISLAND_OUTER - ISLAND_INNER), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)  # smoothstep


# --- Grid helpers ----------------------------------------------------------


def _dilate(mask: np.ndarray) -> np.ndarray:
    """Grow a boolean mask by one cell in the four cardinal directions."""
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def _fill(mask: np.ndarray, seed: np.ndarray) -> np.ndarray:
    """Grow ``seed`` inside ``mask`` until it stops changing."""
    reached = mask & seed
    while True:
        grown = _dilate(reached) & mask
        if np.array_equal(grown, reached):
            return reached
        reached = grown


def _reachable_from_border(mask: np.ndarray) -> np.ndarray:
    """Return the cells of ``mask`` connected to the map border within ``mask``."""
    border = np.zeros(mask.shape, dtype=bool)
    border[0, :] = border[-1, :] = True
    border[:, 0] = border[:, -1] = True
    return _fill(mask, border)


def _distance_to(mask: np.ndarray) -> np.ndarray:
    """Return the step distance from every cell to the nearest ``True`` cell.

    Distance is measured in four-connected steps. Cells that cannot reach the
    mask at all keep a distance of ``-1``.
    """
    dist = np.full(mask.shape, -1, dtype=np.int32)
    visited = mask.copy()
    dist[visited] = 0

    frontier = visited
    step = 0
    while True:
        step += 1
        frontier = _dilate(frontier) & ~visited
        if not frontier.any():
            return dist
        dist[frontier] = step
        visited |= frontier


# --- Passes ----------------------------------------------------------------


def _classify(elevation: np.ndarray, cfg: WorldConfig) -> np.ndarray:
    """Turn an elevation field into a surface index array."""
    surface = np.empty(elevation.shape, dtype=np.int8)
    surface[:] = Surface.FOREST
    surface[elevation >= cfg.mountain_level] = Surface.MOUNTAIN
    surface[elevation < cfg.water_level + BEACH_BAND] = Surface.SAND
    surface[elevation < cfg.water_level] = Surface.OCEAN
    return surface


def _drop_small_islands(surface: np.ndarray) -> int:
    """Drown landmasses too small to live on, in place. Returns how many remain."""
    land = surface != Surface.OCEAN
    minimum = max(16, int(MIN_ISLAND_FRACTION * surface.size))

    remaining = land.copy()
    keep = np.zeros(surface.shape, dtype=bool)
    islands = 0

    while remaining.any():
        ys, xs = np.nonzero(remaining)
        seed = np.zeros(surface.shape, dtype=bool)
        seed[ys[0], xs[0]] = True

        component = _fill(land, seed)
        if component.sum() >= minimum:
            keep |= component
            islands += 1
        remaining &= ~component

    surface[land & ~keep] = Surface.OCEAN
    return islands


def _mark_lakes(surface: np.ndarray) -> int:
    """Reclassify water the border ocean cannot reach as fresh water.

    Returns:
        The number of cells turned into lakes.
    """
    ocean = surface == Surface.OCEAN
    inland = ocean & ~_reachable_from_border(ocean)
    surface[inland] = Surface.FRESH_WATER
    return int(inland.sum())


def _river_sources(
    surface: np.ndarray,
    elevation: np.ndarray,
    ocean_distance: np.ndarray,
    rng: random.Random,
) -> list[tuple[int, int]]:
    """Pick high, inland cells for streams to spring from."""
    height, width = surface.shape
    inland = max(3, int(0.10 * min(width, height)))
    candidate_mask = (surface != Surface.OCEAN) & (ocean_distance >= inland)
    if not candidate_mask.any():
        return []

    threshold = float(np.quantile(elevation[candidate_mask], RIVER_SOURCE_QUANTILE))
    candidate_mask &= elevation >= threshold

    ys, xs = np.nonzero(candidate_mask)
    candidates = list(zip(xs.tolist(), ys.tolist(), strict=True))
    if not candidates:
        return []

    rng.shuffle(candidates)
    wanted = min(rng.randint(*RIVER_SOURCE_RANGE), len(candidates))
    spacing = 0.08 * min(width, height)

    sources: list[tuple[int, int]] = []
    for cx, cy in candidates:
        if len(sources) == wanted:
            break
        if all(np.hypot(cx - sx, cy - sy) >= spacing for sx, sy in sources):
            sources.append((cx, cy))
    return sources


def _trace_stream(
    surface: np.ndarray,
    elevation: np.ndarray,
    ocean_distance: np.ndarray,
    source: tuple[int, int],
) -> list[tuple[int, int]]:
    """Walk downhill from ``source`` to the sea, returning the cells crossed.

    The stream follows the steepest descent of the terrain, which is what makes
    its course meander and what makes separate streams converge onto the same
    valley floor. Where the terrain traps it in a hollow with no lower
    neighbour, it takes the step that gets it closest to the sea instead, so
    every stream reaches the coast rather than pooling inland forever.
    """
    height, width = surface.shape
    x, y = source
    path: list[tuple[int, int]] = []
    visited: set[tuple[int, int]] = set()

    for _ in range(width + height):
        if surface[y, x] == Surface.OCEAN:
            break
        path.append((x, y))
        visited.add((x, y))

        neighbours = [
            (x + dx, y + dy)
            for dx, dy in _OFFSETS_8
            if 0 <= x + dx < width and 0 <= y + dy < height and (x + dx, y + dy) not in visited
        ]
        if not neighbours:
            break

        downhill = [(nx, ny) for nx, ny in neighbours if elevation[ny, nx] < elevation[y, x]]
        if downhill:
            x, y = min(downhill, key=lambda c: elevation[c[1], c[0]])
        else:
            x, y = min(
                neighbours,
                key=lambda c: (ocean_distance[c[1], c[0]], elevation[c[1], c[0]]),
            )

    return path


def _carve_rivers(surface: np.ndarray, elevation: np.ndarray, rng: random.Random) -> int:
    """Trace streams from the high ground and cut their combined network in.

    Every stream runs the whole way to the sea and adds to a flow count per
    cell. Cells that several streams share are trunk rivers and get carved
    wider than the headwaters feeding them.

    Returns:
        The number of streams traced.
    """
    ocean_distance = _distance_to(surface == Surface.OCEAN)
    sources = _river_sources(surface, elevation, ocean_distance, rng)

    flow = np.zeros(surface.shape, dtype=np.int32)
    for source in sources:
        for x, y in _trace_stream(surface, elevation, ocean_distance, source):
            flow[y, x] += 1

    channel = flow > 0
    wide = flow >= RIVER_FLOW_FOR_WIDTH_1
    wider = flow >= RIVER_FLOW_FOR_WIDTH_2
    channel |= _dilate(wide)
    channel |= _dilate(_dilate(wider))

    surface[channel & (surface != Surface.OCEAN)] = Surface.FRESH_WATER
    return len(sources)


# --- Entry point -----------------------------------------------------------


def generate(cfg: WorldConfig) -> World:
    """Generate a :class:`World` deterministically from ``cfg``."""
    log.info(
        "generating world  seed=%d  size=%dx%d  water_level=%.2f  mountain_level=%.2f",
        cfg.seed,
        cfg.width,
        cfg.height,
        cfg.water_level,
        cfg.mountain_level,
    )

    elevation = _elevation_field(cfg, np.random.default_rng(cfg.seed))

    surface = _classify(elevation, cfg)
    islands = _drop_small_islands(surface)
    lake_cells = _mark_lakes(surface)
    streams = _carve_rivers(surface, elevation, random.Random(cfg.seed))
    log.debug("islands=%d  streams=%d  lake cells=%d", islands, streams, lake_cells)

    unique, counts = np.unique(surface, return_counts=True)
    total = surface.size
    summary = "  ".join(
        f"{Surface(s).name}={c / total * 100:.0f}%" for s, c in zip(unique, counts, strict=True)
    )
    log.info("surface distribution: %s", summary)

    world = World(surface, elevation.astype(np.float32))
    log.info("world ready  walkable cells: %d / %d", int(world.walkable_mask().sum()), total)
    return world
