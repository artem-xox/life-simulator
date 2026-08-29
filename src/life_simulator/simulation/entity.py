"""Entity: a single creature living on the world grid.

Behaviour is a simple priority loop each tick:
  1. Age and pay the metabolic energy cost.
  2. Die if starved or too old.
  3. Act according to diet (seek grass / seek prey).
  4. Reproduce if energy is high enough.

Adding new behaviours: subclass Entity or extend the _step_* methods.
Adding new genes: add them to Genome — Entity reads them via self.genome.
"""

from __future__ import annotations

import math
import random
from enum import IntEnum
from typing import TYPE_CHECKING

import numpy as np

from life_simulator.config.settings import (
    ATTACK_DAMAGE,
    ATTACK_EFFICIENCY,
    ATTACK_RANGE,
    CHILD_ENERGY_FRACTION,
    GRAZE_AMOUNT,
    GRAZE_ENERGY_GAIN,
    MAX_AGE,
    REPRODUCTION_THRESHOLD,
    WANDER_INTERVAL,
)
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.phenotype import Phenotype

if TYPE_CHECKING:
    from life_simulator.simulation.spatial import SpatialGrid
    from life_simulator.simulation.world import World

# ---------------------------------------------------------------------------
# Diet enum
# ---------------------------------------------------------------------------


class Diet(IntEnum):
    HERBIVORE = 0
    CARNIVORE = 1


#: Headings an entity tries, in order, when its direct path is blocked by water
#: or rock. Turning aside rather than stopping lets it slide along an obstacle
#: and work its way around. Each entity mirrors this list (see ``_turn_bias``)
#: so a herd meeting a mountain splits around both sides instead of piling up.
_AVOID_DEFLECTIONS: tuple[float, ...] = (
    0.0,
    math.pi / 4,
    -math.pi / 4,
    math.pi / 2,
    -math.pi / 2,
    3 * math.pi / 4,
    -3 * math.pi / 4,
)


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


class Entity:
    """A single creature on the world grid.

    Attributes:
        x, y: floating-point position in world cells (origin at top-left).
        energy: current energy; death occurs at or below zero.
        age: number of ticks since birth.
        alive: False after the entity has died (natural or predation).
        diet: HERBIVORE or CARNIVORE — determines feeding behaviour.
        genome: heritable traits; passed (with mutation) to offspring.
        body: the abilities those genes yield — speed, upkeep, reserves and
            concealment, all derived with the trade-offs of carrying a body.
    """

    __slots__ = (
        "x",
        "y",
        "energy",
        "age",
        "alive",
        "diet",
        "genome",
        "body",
        "_target_x",
        "_target_y",
        "_wander_timer",
        "_turn_bias",
    )

    def __init__(
        self,
        x: float,
        y: float,
        diet: Diet,
        genome: Genome,
        energy: float | None = None,
    ) -> None:
        self.x = x
        self.y = y
        self.diet = diet
        self.genome = genome
        self.body = Phenotype.of(genome)
        self.age: int = 0
        self.alive: bool = True
        self.energy: float = energy if energy is not None else self.body.max_energy * 0.4
        # Navigation state.
        self._target_x: float = x
        self._target_y: float = y
        self._wander_timer: int = 0
        # Which way this individual prefers to turn around an obstacle.
        self._turn_bias: float = 1.0 if random.random() < 0.5 else -1.0

    # --- Main update ------------------------------------------------------- #

    def step(self, world: World, spatial: SpatialGrid) -> Entity | None:
        """Advance by one simulation tick.

        Returns:
            A newly born child entity, or ``None``.
        """
        self.age += 1
        self.energy -= self.body.tick_cost

        if self.energy <= 0.0 or self.age > MAX_AGE:
            self.alive = False
            return None

        if self.diet == Diet.HERBIVORE:
            self._step_herbivore(world)
        else:
            self._step_carnivore(world, spatial)

        return self._try_reproduce(world)

    # --- Herbivore behaviour ----------------------------------------------- #

    def _step_herbivore(self, world: World) -> None:
        target = self._find_grass_target(world)
        if target is None:
            target = self._wander(world)
        self._move_toward(target[0], target[1], world)

        # Graze at current cell (entity has moved; gains energy where it now stands).
        cx, cy = int(self.x), int(self.y)
        if world.in_bounds(cx, cy):
            eaten = world.graze_at(cx, cy, GRAZE_AMOUNT)
            self.energy = min(self.body.max_energy, self.energy + eaten * GRAZE_ENERGY_GAIN)

    def _find_grass_target(self, world: World) -> tuple[float, float] | None:
        """Return the position of the richest grass cell in vision, or None."""
        r = int(self.genome.vision)
        x0 = max(0, int(self.x) - r)
        y0 = max(0, int(self.y) - r)
        x1 = min(world.width, int(self.x) + r + 1)
        y1 = min(world.height, int(self.y) + r + 1)
        patch = world.grass[y0:y1, x0:x1]
        if patch.size == 0 or float(patch.max()) <= 0.0:
            return None
        idx = int(np.argmax(patch))
        fy, fx = divmod(idx, patch.shape[1])
        return float(x0 + fx), float(y0 + fy)

    # --- Carnivore behaviour ----------------------------------------------- #

    def _step_carnivore(self, world: World, spatial: SpatialGrid) -> None:
        prey = self._find_prey(spatial)
        if prey is not None:
            self._move_toward(prey.x, prey.y, world)
            if math.hypot(self.x - prey.x, self.y - prey.y) < ATTACK_RANGE:
                self._attack(prey)
        else:
            tx, ty = self._wander(world)
            self._move_toward(tx, ty, world)

    def _find_prey(self, spatial: SpatialGrid) -> Entity | None:
        best: Entity | None = None
        best_dist = float("inf")
        for other in spatial.nearby(self.x, self.y, self.genome.vision):
            if other is self or not other.alive or other.diet != Diet.HERBIVORE:
                continue
            d = math.hypot(self.x - other.x, self.y - other.y)
            if d < self.genome.vision and d < best_dist:
                best_dist = d
                best = other
        return best

    def _attack(self, prey: Entity) -> None:
        # Relative size affects how much damage is dealt vs. absorbed.
        size_ratio = self.body.body_size / max(prey.body.body_size, 0.1)
        damage = ATTACK_DAMAGE * min(size_ratio, 2.0)
        stolen = min(prey.energy, damage)
        prey.energy -= stolen
        if prey.energy <= 0.0:
            prey.alive = False
        self.energy = min(self.body.max_energy, self.energy + stolen * ATTACK_EFFICIENCY)

    # --- Shared movement --------------------------------------------------- #

    def _move_toward(self, tx: float, ty: float, world: World) -> None:
        """Step towards a target, turning aside if water or rock is in the way."""
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            return
        # Clamp current cell index to valid range before array lookup.
        cx = max(0, min(world.width - 1, int(self.x)))
        cy = max(0, min(world.height - 1, int(self.y)))
        cost = world.move_cost(cx, cy)
        step = min(self.body.speed / cost, dist)
        heading = math.atan2(dy, dx)

        for deflection in _AVOID_DEFLECTIONS:
            angle = heading + deflection * self._turn_bias
            nx = self.x + math.cos(angle) * step
            ny = self.y + math.sin(angle) * step
            # Keep position strictly inside world bounds so int(pos) is always valid.
            nx = max(0.0, min(world.width - 1e-6, nx))
            ny = max(0.0, min(world.height - 1e-6, ny))
            if world.is_walkable(int(nx), int(ny)):
                self.energy -= self.body.travel_cost * math.hypot(nx - self.x, ny - self.y)
                self.x, self.y = nx, ny
                return

    def _wander(self, world: World) -> tuple[float, float]:
        """Return a cached random walkable target, refreshed every WANDER_INTERVAL ticks."""
        self._wander_timer -= 1
        if self._wander_timer <= 0:
            self._wander_timer = WANDER_INTERVAL
            r = self.genome.vision
            for _ in range(12):
                tx = self.x + random.uniform(-r, r)
                ty = self.y + random.uniform(-r, r)
                tx = max(0.0, min(world.width - 1.0, tx))
                ty = max(0.0, min(world.height - 1.0, ty))
                if world.is_walkable(int(tx), int(ty)):
                    self._target_x = tx
                    self._target_y = ty
                    break
        return self._target_x, self._target_y

    # --- Reproduction ------------------------------------------------------ #

    def _try_reproduce(self, world: World) -> Entity | None:
        if self.energy < REPRODUCTION_THRESHOLD * self.body.max_energy:
            return None
        child_energy = CHILD_ENERGY_FRACTION * self.body.max_energy
        self.energy -= child_energy
        cx, cy = self._birth_spot(world)
        return Entity(cx, cy, self.diet, self.genome.mutate(), child_energy)

    def _birth_spot(self, world: World) -> tuple[float, float]:
        """Find somewhere beside the parent to put a newborn.

        Without this a child can land in a lake or on a mountainside, where it
        is stranded: nothing can walk out of a cell it could never walk into.
        """
        for _ in range(6):
            cx = self.x + random.uniform(-1.0, 1.0)
            cy = self.y + random.uniform(-1.0, 1.0)
            cx = max(0.0, min(world.width - 1e-6, cx))
            cy = max(0.0, min(world.height - 1e-6, cy))
            if world.is_walkable(int(cx), int(cy)):
                return cx, cy
        return self.x, self.y
