"""Ecosystem: the top-level simulation object that orchestrates each tick.

One tick:
  1. Regrow food on the world grid.
  2. Rebuild the spatial index from living entities.
  3. Step every living entity (they may die or spawn children).
  4. Collect children; remove dead entities.
  5. Increment tick counter.

Keeping the list mutation outside entity.step() avoids iterator-invalidation
issues and makes the order of updates deterministic.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

import numpy as np

from life_simulator.simulation.entity import Diet, Entity
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.spatial import SpatialGrid
from life_simulator.simulation.stats import Stats
from life_simulator.simulation.world import World
from life_simulator.simulation.worldgen import WorldConfig, generate

log = logging.getLogger(__name__)


@dataclass
class SpeciesConfig:
    """Spawn parameters for one starting species.

    Attributes:
        diet: HERBIVORE or CARNIVORE.
        count: number of individuals placed at the start.
        genome: prototype genome — each spawned entity gets a copy (not shared).
    """

    diet: Diet
    count: int
    genome: Genome = field(default_factory=Genome)


class Ecosystem:
    """Holds the world and all entities; drives the simulation loop.

    Attributes:
        world: the terrain and food grid.
        entities: all currently living entities.
        tick_count: total simulation ticks elapsed.
    """

    # Hard cap on total living entities. When the cap is reached, newborns are
    # dropped at random. This keeps tick latency bounded and prevents runaway
    # population explosions from freezing the simulation.
    ENTITY_CAP: int = 2_000

    # Log a population snapshot every this many ticks.
    _LOG_INTERVAL: int = 100

    # Record a stats sample every this many ticks (keeps the buffer covering a
    # useful time window even at high simulation speeds).
    _SAMPLE_INTERVAL: int = 5

    def __init__(self, world: World) -> None:
        self.world = world
        self.entities: list[Entity] = []
        self.spatial = SpatialGrid()
        self.tick_count: int = 0
        self.stats = Stats()

    @classmethod
    def create(
        cls,
        world_cfg: WorldConfig,
        species: list[SpeciesConfig],
        *,
        pump_events: bool = False,
    ) -> Ecosystem:
        """Build an Ecosystem from configs and populate it with initial entities.

        Args:
            pump_events: if True, call ``pygame.event.pump()`` after world
                generation to keep the OS window responsive during startup.
        """
        log.info("creating ecosystem  cap=%d", cls.ENTITY_CAP)

        log.info("step 1/3 — generating world...")
        world = generate(world_cfg)

        if pump_events:
            # Keep the OS from marking the window as 'not responding' while we
            # do heavy work before the event loop starts.
            try:
                import pygame

                pygame.event.pump()
                log.debug("event pump ok")
            except Exception as exc:
                log.debug("event pump skipped: %s", exc)

        eco = cls(world)

        log.info("step 2/3 — spawning initial entities...")
        eco._spawn_initial(species)

        if pump_events:
            try:
                import pygame

                pygame.event.pump()
            except Exception:
                pass

        eco.stats.record(eco.tick_count, eco.entities)

        log.info(
            "step 3/3 — ecosystem ready  entities=%d  (herb=%d  carn=%d)",
            len(eco.entities),
            eco.herbivore_count,
            eco.carnivore_count,
        )
        return eco

    @classmethod
    def from_saved(cls, world: World, entities: list[Entity], tick_count: int) -> Ecosystem:
        """Rebuild an Ecosystem from a loaded save (pre-built world + entities)."""
        eco = cls(world)
        eco.entities = entities
        eco.tick_count = tick_count
        eco.stats.record(tick_count, entities)
        return eco

    # --- Population queries ------------------------------------------------ #

    @property
    def herbivore_count(self) -> int:
        return sum(1 for e in self.entities if e.diet == Diet.HERBIVORE)

    @property
    def carnivore_count(self) -> int:
        return sum(1 for e in self.entities if e.diet == Diet.CARNIVORE)

    # --- Simulation loop --------------------------------------------------- #

    def tick(self) -> None:
        """Advance the simulation by one step."""
        self.world.regrow_food()
        self.spatial.rebuild(self.entities)

        newborns: list[Entity] = []
        for entity in self.entities:
            if not entity.alive:
                continue
            child = entity.step(self.world, self.spatial)
            if child is not None:
                newborns.append(child)

        # Remove dead entities first, then admit newborns up to the cap.
        self.entities = [e for e in self.entities if e.alive]
        slots = max(0, self.ENTITY_CAP - len(self.entities))
        if slots and newborns:
            if len(newborns) > slots:
                random.shuffle(newborns)
                newborns = newborns[:slots]
            self.entities.extend(newborns)
        self.tick_count += 1

        if self.tick_count % self._SAMPLE_INTERVAL == 0:
            self.stats.record(self.tick_count, self.entities)

        if self.tick_count % self._LOG_INTERVAL == 0:
            log.info(
                "tick=%d  total=%d  herb=%d  carn=%d",
                self.tick_count,
                len(self.entities),
                self.herbivore_count,
                self.carnivore_count,
            )

    # --- Initialisation ---------------------------------------------------- #

    def _spawn_initial(self, species: list[SpeciesConfig]) -> None:
        # Vectorised walkable-cell search — much faster than a Python loop over
        # every cell calling world.is_walkable().
        from life_simulator.simulation.world import _WALKABLE_TABLE

        walkable_mask = _WALKABLE_TABLE[self.world.biome] > 0  # (H, W) bool
        ys, xs = np.where(walkable_mask)
        walkable = list(zip(xs.tolist(), ys.tolist(), strict=True))

        log.debug("walkable cells: %d", len(walkable))

        if not walkable:
            log.warning("no walkable cells — no entities will be spawned")
            return

        for spec in species:
            positions = random.choices(walkable, k=spec.count)
            for px, py in positions:
                self.entities.append(
                    Entity(
                        x=float(px) + random.random(),
                        y=float(py) + random.random(),
                        diet=spec.diet,
                        genome=spec.genome.copy(),
                    )
                )
            log.debug(
                "spawned %d %s entities",
                spec.count,
                spec.diet.name,
            )
