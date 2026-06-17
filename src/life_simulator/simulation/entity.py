"""Entity: a single creature living on the world grid.

Behaviour is a simple priority loop each tick:
  1. Age and pay the metabolic energy cost.
  2. Die if starved or too old.
  3. Act according to diet (seek food / seek prey).
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

from life_simulator.simulation.genome import Genome

if TYPE_CHECKING:
    from life_simulator.simulation.spatial import SpatialGrid
    from life_simulator.simulation.world import World

# ---------------------------------------------------------------------------
# Diet enum
# ---------------------------------------------------------------------------


class Diet(IntEnum):
    HERBIVORE = 0
    CARNIVORE = 1


# ---------------------------------------------------------------------------
# Balance constants — centralised here so they are easy to tune in one place
# ---------------------------------------------------------------------------

#: Base energy spent per tick before genome modifiers.
BASE_ENERGY_COST: float = 0.30

#: Max energy a size-1 entity can hold.
MAX_ENERGY_BASE: float = 20.0

#: Food consumed from the cell per eating action (herbivores).
EATING_AMOUNT: float = 2.0

#: Energy gained per unit of food eaten. Deliberately low: with abundant food an
#: herbivore net-gains ~0.5 energy/tick, making reproduction take ~25 ticks
#: rather than every 2-3 ticks.
EATING_GAIN: float = 0.40

#: Energy stolen from prey per tick while within ATTACK_RANGE (carnivores).
#: Low value forces several ticks of sustained contact to drain a prey's energy.
ATTACK_DAMAGE: float = 1.8

#: Distance in cells within which a carnivore can attack.
ATTACK_RANGE: float = 1.5

#: Fraction of energy stolen from prey that the attacker keeps.
ATTACK_EFFICIENCY: float = 0.40

#: Energy given to the newborn as a fraction of parent max_energy.
#: High value (> 0.5) makes reproduction expensive to slow population growth.
CHILD_ENERGY_FRACTION: float = 0.65

#: Hard upper limit on age in ticks.
MAX_AGE: int = 700

#: Ticks between choosing a new random wander target.
WANDER_INTERVAL: int = 10


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
    """

    __slots__ = (
        "x",
        "y",
        "energy",
        "age",
        "alive",
        "diet",
        "genome",
        "_target_x",
        "_target_y",
        "_wander_timer",
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
        self.age: int = 0
        self.alive: bool = True
        self.energy: float = energy if energy is not None else self.max_energy * 0.4
        # Navigation state.
        self._target_x: float = x
        self._target_y: float = y
        self._wander_timer: int = 0

    # --- Derived stats ----------------------------------------------------- #

    @property
    def max_energy(self) -> float:
        return MAX_ENERGY_BASE * self.genome.size

    # --- Main update ------------------------------------------------------- #

    def step(self, world: World, spatial: SpatialGrid) -> Entity | None:
        """Advance by one simulation tick.

        Returns:
            A newly born child entity, or ``None``.
        """
        self.age += 1
        # Cost scales with both metabolism and size (bigger body = more upkeep).
        self.energy -= BASE_ENERGY_COST * self.genome.metabolism * self.genome.size

        if self.energy <= 0.0 or self.age > MAX_AGE:
            self.alive = False
            return None

        if self.diet == Diet.HERBIVORE:
            self._step_herbivore(world)
        else:
            self._step_carnivore(world, spatial)

        return self._try_reproduce()

    # --- Herbivore behaviour ----------------------------------------------- #

    def _step_herbivore(self, world: World) -> None:
        target = self._find_food_target(world)
        if target is None:
            target = self._wander(world)
        self._move_toward(target[0], target[1], world)

        # Eat at current cell (entity has moved; gains energy from where it now stands).
        cx, cy = int(self.x), int(self.y)
        if world.in_bounds(cx, cy):
            eaten = world.eat_at(cx, cy, EATING_AMOUNT)
            self.energy = min(self.max_energy, self.energy + eaten * EATING_GAIN)

    def _find_food_target(self, world: World) -> tuple[float, float] | None:
        """Return the position of the richest food cell in vision, or None."""
        r = int(self.genome.vision)
        x0 = max(0, int(self.x) - r)
        y0 = max(0, int(self.y) - r)
        x1 = min(world.width, int(self.x) + r + 1)
        y1 = min(world.height, int(self.y) + r + 1)
        patch = world.food[y0:y1, x0:x1]
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
        size_ratio = self.genome.size / max(prey.genome.size, 0.1)
        damage = ATTACK_DAMAGE * min(size_ratio, 2.0)
        stolen = min(prey.energy, damage)
        prey.energy -= stolen
        if prey.energy <= 0.0:
            prey.alive = False
        self.energy = min(self.max_energy, self.energy + stolen * ATTACK_EFFICIENCY)

    # --- Shared movement --------------------------------------------------- #

    def _move_toward(self, tx: float, ty: float, world: World) -> None:
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            return
        # Clamp current cell index to valid range before array lookup.
        cx = max(0, min(world.width - 1, int(self.x)))
        cy = max(0, min(world.height - 1, int(self.y)))
        cost = world.move_cost(cx, cy)
        step = min(self.genome.speed / cost, dist)
        nx = self.x + dx / dist * step
        ny = self.y + dy / dist * step
        # Keep position strictly inside world bounds so int(pos) is always valid.
        nx = max(0.0, min(world.width - 1e-6, nx))
        ny = max(0.0, min(world.height - 1e-6, ny))
        inx, iny = int(nx), int(ny)
        if world.is_walkable(inx, iny):
            self.x, self.y = nx, ny

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

    def _try_reproduce(self) -> Entity | None:
        if self.energy < self.genome.repro_threshold * self.max_energy:
            return None
        child_energy = CHILD_ENERGY_FRACTION * self.max_energy
        self.energy -= child_energy
        cx = self.x + random.uniform(-1.0, 1.0)
        cy = self.y + random.uniform(-1.0, 1.0)
        return Entity(cx, cy, self.diet, self.genome.mutate(), child_energy)
