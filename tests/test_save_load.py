"""Round-trip tests for JSON save/load."""

from __future__ import annotations

import numpy as np

from life_simulator.persistence.save_load import load_game, save_game
from life_simulator.simulation.ecosystem import Ecosystem, SpeciesConfig
from life_simulator.simulation.entity import Diet
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.worldgen import WorldConfig


def _make_ecosystem() -> tuple[Ecosystem, WorldConfig, list[SpeciesConfig]]:
    world_cfg = WorldConfig(seed=7, width=48, height=36, water_level=0.3)
    species = [
        SpeciesConfig(diet=Diet.HERBIVORE, count=20, genome=Genome(speed=1.2, vision=5.0)),
        SpeciesConfig(diet=Diet.CARNIVORE, count=4, genome=Genome(speed=1.6, vision=9.0)),
    ]
    eco = Ecosystem.create(world_cfg, species)
    for _ in range(15):
        eco.tick()
    return eco, world_cfg, species


def test_save_load_round_trip_preserves_state(tmp_path) -> None:
    eco, world_cfg, species = _make_ecosystem()
    path = tmp_path / "save.json"
    save_game(path, eco, world_cfg, species)

    loaded, loaded_cfg, loaded_species = load_game(path)

    assert loaded.tick_count == eco.tick_count
    assert len(loaded.entities) == len(eco.entities)
    assert loaded_cfg.seed == world_cfg.seed
    assert loaded_cfg.width == world_cfg.width
    assert len(loaded_species) == len(species)


def test_loaded_entities_match_originals(tmp_path) -> None:
    eco, world_cfg, species = _make_ecosystem()
    path = tmp_path / "save.json"
    save_game(path, eco, world_cfg, species)

    loaded, _, _ = load_game(path)

    for original, restored in zip(eco.entities, loaded.entities, strict=True):
        assert restored.diet == original.diet
        assert restored.age == original.age
        assert abs(restored.x - original.x) < 1e-3
        assert abs(restored.energy - original.energy) < 1e-3
        assert abs(restored.genome.speed - original.genome.speed) < 1e-6


def test_loaded_food_grid_matches(tmp_path) -> None:
    eco, world_cfg, species = _make_ecosystem()
    path = tmp_path / "save.json"
    save_game(path, eco, world_cfg, species)

    loaded, _, _ = load_game(path)

    # Food is saved rounded to 3 decimals; allow that tolerance.
    assert np.allclose(loaded.world.food, eco.world.food, atol=1e-2)


def test_loaded_world_terrain_is_reproducible(tmp_path) -> None:
    eco, world_cfg, species = _make_ecosystem()
    path = tmp_path / "save.json"
    save_game(path, eco, world_cfg, species)

    loaded, _, _ = load_game(path)

    # Terrain is regenerated from the seed, so biomes must match exactly.
    assert np.array_equal(loaded.world.biome, eco.world.biome)
