"""JSON save/load for a running simulation.

A save captures everything needed to reproduce the scene exactly:

* the :class:`WorldConfig` (terrain is deterministic from its seed);
* the starting :class:`SpeciesConfig` list (so a restart re-rolls the same setup);
* the current food grid (a dynamic resource not recoverable from the seed alone);
* every living entity's position, energy, age, diet, and full genome.

On load the world terrain is regenerated from the seed, the saved food grid is
applied over it, and entities are reconstructed verbatim.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, fields
from pathlib import Path

import numpy as np

from life_simulator.simulation.ecosystem import Ecosystem, SpeciesConfig
from life_simulator.simulation.entity import Diet, Entity
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.worldgen import WorldConfig, generate

log = logging.getLogger(__name__)

#: Bumped whenever the on-disk format changes incompatibly.
SAVE_VERSION = 1

#: Default save file used by the in-game save/load hotkeys.
DEFAULT_SAVE_PATH = Path("life_sim_save.json")


def _genome_to_dict(g: Genome) -> dict[str, float]:
    return {f.name: getattr(g, f.name) for f in fields(g)}


def _genome_from_dict(d: dict[str, float]) -> Genome:
    valid = {f.name for f in fields(Genome)}
    return Genome(**{k: v for k, v in d.items() if k in valid})


def _entity_to_dict(e: Entity) -> dict:
    return {
        "x": round(e.x, 4),
        "y": round(e.y, 4),
        "energy": round(e.energy, 4),
        "age": e.age,
        "diet": int(e.diet),
        "genome": _genome_to_dict(e.genome),
    }


def save_game(
    path: str | Path,
    ecosystem: Ecosystem,
    world_cfg: WorldConfig,
    species: list[SpeciesConfig],
) -> None:
    """Write the full simulation state to ``path`` as JSON."""
    data = {
        "version": SAVE_VERSION,
        "tick_count": ecosystem.tick_count,
        "world_cfg": asdict(world_cfg),
        "species": [
            {
                "diet": int(s.diet),
                "count": s.count,
                "genome": _genome_to_dict(s.genome),
            }
            for s in species
        ],
        "food": np.round(ecosystem.world.food, 3).tolist(),
        "entities": [_entity_to_dict(e) for e in ecosystem.entities],
    }
    Path(path).write_text(json.dumps(data))
    log.info(
        "saved game  path=%s  tick=%d  entities=%d",
        path,
        ecosystem.tick_count,
        len(ecosystem.entities),
    )


def load_game(path: str | Path) -> tuple[Ecosystem, WorldConfig, list[SpeciesConfig]]:
    """Load a saved game; return ``(ecosystem, world_cfg, species)``.

    Raises:
        ValueError: if the file's save version is unsupported.
    """
    data = json.loads(Path(path).read_text())
    version = data.get("version")
    if version != SAVE_VERSION:
        raise ValueError(f"unsupported save version: {version!r} (expected {SAVE_VERSION})")

    valid = {f.name for f in fields(WorldConfig)}
    world_cfg = WorldConfig(**{k: v for k, v in data["world_cfg"].items() if k in valid})

    species = [
        SpeciesConfig(
            diet=Diet(int(s["diet"])),
            count=int(s["count"]),
            genome=_genome_from_dict(s["genome"]),
        )
        for s in data["species"]
    ]

    # Terrain is reproducible from the seed; the dynamic food grid is restored.
    world = generate(world_cfg)
    if "food" in data:
        food = np.asarray(data["food"], dtype=np.float32)
        if food.shape == world.food.shape:
            world.food = np.clip(food, 0.0, world.food_max)
        else:
            log.warning(
                "saved food grid %s != world %s; keeping regenerated food",
                food.shape,
                world.food.shape,
            )

    entities = [
        Entity(
            x=float(d["x"]),
            y=float(d["y"]),
            diet=Diet(int(d["diet"])),
            genome=_genome_from_dict(d["genome"]),
            energy=float(d["energy"]),
        )
        for d in data["entities"]
    ]
    for ent, d in zip(entities, data["entities"], strict=True):
        ent.age = int(d["age"])

    eco = Ecosystem.from_saved(world, entities, int(data["tick_count"]))
    log.info(
        "loaded game  path=%s  tick=%d  entities=%d",
        path,
        eco.tick_count,
        len(entities),
    )
    return eco, world_cfg, species
