"""Entity: a single creature living on the world grid.

Each tick an animal ages, pays for its body, decides what state it is in, and
acts on it. The state machine is small on purpose — forage, rest, flee, hunt,
chase — but it is where most of what happens in a run comes from: a herd that
spends its day fleeing does not eat, and a predator that has just fed leaves
the prey alone for a long while.

Two animals do not see each other equally. Detection range is the observer's
vision reduced by the other's concealment, so a stealthy animal is noticed late
by a sharp-eyed one and a conspicuous predator announces itself. That single
rule is what gives the stealth gene its teeth.

Adding new genes: add them to Genome — the phenotype turns them into abilities,
and Entity reads those rather than the genes directly.
"""

from __future__ import annotations

import math
import random
from enum import IntEnum
from typing import TYPE_CHECKING

import numpy as np

from life_simulator.config.settings import (
    BASE_ESCAPE_CHANCE,
    BREEDING_COOLDOWN_FRACTION,
    CAPTURE_RANGE,
    CHASE_EXHAUSTION_FRACTION,
    CHASE_GIVE_UP_MARGIN,
    CHILD_ENERGY_FRACTION,
    ESCAPE_JUVENILE_PENALTY,
    ESCAPE_POWER_WEIGHT,
    ESCAPE_SPEED_WEIGHT,
    FERTILITY_END_FRACTION,
    FERTILITY_START_FRACTION,
    FLEE_MEMORY,
    GRAZE_AMOUNT,
    GRAZE_ENERGY_GAIN,
    GRAZER_REST_THRESHOLD,
    HUNGER_THRESHOLD,
    JUVENILE_FRACTION,
    JUVENILE_PREY_VALUE,
    KILL_ENERGY_PER_SIZE,
    LIFESPAN_BASE,
    LIFESPAN_VARIATION,
    MAX_ESCAPE_CHANCE,
    MAX_OFFSPRING,
    MIN_ESCAPE_CHANCE,
    RECAPTURE_COOLDOWN,
    REPRODUCTION_THRESHOLD,
    SPRINT_SPEED_MULTIPLIER,
    WANDER_INTERVAL,
    WOUND_ENERGY_LOSS,
)
from life_simulator.simulation.genome import Genome
from life_simulator.simulation.phenotype import Phenotype

if TYPE_CHECKING:
    from life_simulator.simulation.spatial import SpatialGrid
    from life_simulator.simulation.world import World


class Diet(IntEnum):
    HERBIVORE = 0
    CARNIVORE = 1


class DeathCause(IntEnum):
    """Why an animal died. There are only three ways out of this world."""

    STARVATION = 0
    OLD_AGE = 1
    PREDATION = 2


class LifeStage(IntEnum):
    """Whether an animal has finished growing up."""

    JUVENILE = 0
    ADULT = 1


class EntityState(IntEnum):
    """What an animal is doing right now."""

    FORAGE = 0
    REST = 1
    FLEE = 2
    HUNT = 3
    CHASE = 4


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


class Entity:
    """A single creature on the world grid.

    Attributes:
        x, y: floating-point position in world cells (origin at top-left).
        energy: current energy; death occurs at or below zero.
        age: number of ticks since birth.
        alive: False after the entity has died.
        death_cause: why it died, or None while it lives.
        diet: HERBIVORE or CARNIVORE — determines feeding behaviour.
        state: what it is doing this tick.
        genome: heritable traits; passed (with mutation) to offspring.
        body: the abilities those genes yield — speed, upkeep, reserves and
            concealment, all derived with the trade-offs of carrying a body.
            It is rebuilt as a juvenile grows, then settles.
        lifespan: age in ticks at which this individual dies of old age.
        offspring: how many young it has already had, capped at MAX_OFFSPRING.
    """

    __slots__ = (
        "x",
        "y",
        "energy",
        "age",
        "alive",
        "diet",
        "state",
        "genome",
        "body",
        "lifespan",
        "offspring",
        "death_cause",
        "_rng",
        "_breeding_rest_until",
        "_fully_grown",
        "_flee_until",
        "_threat_x",
        "_threat_y",
        "_quarry",
        "_capture_rest_until",
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
        age: int = 0,
        rng: random.Random | None = None,
    ) -> None:
        # Randomness is per-animal rather than global: the ecosystem hands every
        # creature the same seeded generator, which is what lets a whole run be
        # reproduced from its seed.
        self._rng = rng if rng is not None else random.Random()

        self.x = x
        self.y = y
        self.diet = diet
        self.genome = genome
        self.age = age
        # No two animals get exactly the same span, so a cohort born together
        # does not also die together and leave the world briefly empty.
        self.lifespan: int = round(
            LIFESPAN_BASE * (1.0 + self._rng.uniform(-LIFESPAN_VARIATION, LIFESPAN_VARIATION))
        )
        self.body = Phenotype.of(genome, self.maturity)
        self.alive: bool = True
        self.death_cause: DeathCause | None = None
        self.state: EntityState = EntityState.HUNT if diet is Diet.CARNIVORE else EntityState.FORAGE
        self.offspring: int = 0
        self._breeding_rest_until: int = 0
        self._fully_grown: bool = self.maturity >= 1.0
        self.energy: float = energy if energy is not None else self.body.max_energy * 0.4

        # What it is running from, and what it is running after.
        self._flee_until: int = 0
        self._threat_x: float = x
        self._threat_y: float = y
        self._quarry: Entity | None = None
        self._capture_rest_until: int = 0

        # Navigation state.
        self._target_x: float = x
        self._target_y: float = y
        self._wander_timer: int = 0
        # Which way this individual prefers to turn around an obstacle.
        self._turn_bias: float = 1.0 if self._rng.random() < 0.5 else -1.0

    # --- Life stage -------------------------------------------------------- #

    @property
    def maturity(self) -> float:
        """How far this animal has grown up, from 0 at birth to 1 at adulthood."""
        growing_until = JUVENILE_FRACTION * self.lifespan
        if growing_until <= 0.0:
            return 1.0
        return min(1.0, self.age / growing_until)

    @property
    def stage(self) -> LifeStage:
        return LifeStage.ADULT if self.maturity >= 1.0 else LifeStage.JUVENILE

    @property
    def prey_value(self) -> float:
        """Multiplier on the energy a predator gets from eating this animal."""
        return 1.0 if self.stage is LifeStage.ADULT else JUVENILE_PREY_VALUE

    def die(self, cause: DeathCause) -> None:
        """Mark this animal dead, recording why."""
        self.alive = False
        self.death_cause = cause

    # --- Perception -------------------------------------------------------- #

    def distance_to(self, other: Entity) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def detection_range(self, other: Entity) -> float:
        """How close ``other`` must be before this animal notices it.

        The sight is the observer's, the concealment is the target's — so two
        animals will often not see each other at the same moment.
        """
        return self.genome.vision * (1.0 - other.body.stealth)

    def can_see(self, other: Entity) -> bool:
        return self.distance_to(other) <= self.detection_range(other)

    # --- Main update ------------------------------------------------------- #

    def step(self, world: World, spatial: SpatialGrid) -> Entity | None:
        """Advance by one simulation tick.

        Returns:
            A newly born child entity, or ``None``.
        """
        self.age += 1
        if not self._fully_grown:
            # Still growing, so its abilities change from tick to tick. The
            # flag rather than the life stage is what stops this: by the tick an
            # animal turns adult its stage has already flipped, so testing the
            # stage would skip the last rebuild and leave it a fraction short of
            # its full body for the rest of its life.
            self.body = Phenotype.of(self.genome, self.maturity)
            self._fully_grown = self.maturity >= 1.0

        self.energy -= self.body.tick_cost
        if self._check_death():
            return None

        if self.diet is Diet.HERBIVORE:
            self._act_as_grazer(world, spatial)
        else:
            self._act_as_hunter(world, spatial)

        # Running is expensive enough to kill, so death is checked again after
        # acting rather than only at the top of the tick.
        if self._check_death():
            return None

        return self._try_reproduce(world)

    def _check_death(self) -> bool:
        if self.energy <= 0.0:
            self.die(DeathCause.STARVATION)
            return True
        if self.age >= self.lifespan:
            self.die(DeathCause.OLD_AGE)
            return True
        return False

    # --- Herbivore --------------------------------------------------------- #

    def _act_as_grazer(self, world: World, spatial: SpatialGrid) -> None:
        threat = self._nearest_threat(spatial)
        if threat is not None:
            self._threat_x, self._threat_y = threat.x, threat.y
            self._flee_until = self.age + FLEE_MEMORY

        if self.age < self._flee_until:
            self.state = EntityState.FLEE
            self._flee(world)
        elif self.energy >= GRAZER_REST_THRESHOLD * self.body.max_energy:
            # Full, and nothing is after it. Standing still costs least.
            self.state = EntityState.REST
        else:
            self.state = EntityState.FORAGE
            self._forage(world)

    def _nearest_threat(self, spatial: SpatialGrid) -> Entity | None:
        """Return the closest predator this animal can actually see."""
        best: Entity | None = None
        best_distance = float("inf")
        for other in spatial.nearby(self.x, self.y, self.genome.vision):
            if other.diet is not Diet.CARNIVORE or not other.alive:
                continue
            distance = self.distance_to(other)
            if distance < best_distance and self.can_see(other):
                best_distance = distance
                best = other
        return best

    def _flee(self, world: World) -> None:
        """Run directly away from where the danger was last seen."""
        self._sprint_toward(
            self.x + (self.x - self._threat_x),
            self.y + (self.y - self._threat_y),
            world,
        )

    def _forage(self, world: World) -> None:
        target = self._find_grass_target(world)
        if target is None:
            target = self._wander(world)
        self._move_toward(target[0], target[1], world)

        # Graze at current cell (entity has moved; gains energy where it stands).
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

    # --- Carnivore --------------------------------------------------------- #

    def _act_as_hunter(self, world: World, spatial: SpatialGrid) -> None:
        if self.energy >= HUNGER_THRESHOLD * self.body.max_energy:
            # Digesting. A big meal buys a long rest, and that rest is what
            # lets a prey population breathe between hunts.
            self.state = EntityState.REST
            self._quarry = None
            return

        quarry = self._pick_quarry(spatial)
        if quarry is None:
            self.state = EntityState.HUNT
            self._quarry = None
            tx, ty = self._wander(world)
            self._move_toward(tx, ty, world)
            return

        self.state = EntityState.CHASE
        self._quarry = quarry
        self._sprint_toward(quarry.x, quarry.y, world)
        if self.distance_to(quarry) <= CAPTURE_RANGE and self.age >= self._capture_rest_until:
            self._attempt_capture(quarry)

    def _pick_quarry(self, spatial: SpatialGrid) -> Entity | None:
        """Choose prey to run down: whichever visible animal is closest.

        A chase already under way is kept while the prey stays within reach, so
        a predator commits to one animal instead of switching every time another
        strays a little nearer.
        """
        current = self._quarry
        if current is not None and current.alive and not self._has_given_up(current):
            return current

        best: Entity | None = None
        best_distance = float("inf")
        for other in spatial.nearby(self.x, self.y, self.genome.vision):
            if other.diet is not Diet.HERBIVORE or not other.alive:
                continue
            distance = self.distance_to(other)
            if distance < best_distance and self.can_see(other):
                best_distance = distance
                best = other
        return best

    def _has_given_up(self, quarry: Entity) -> bool:
        """Whether to break off a chase — the prey is clear, or the legs are gone."""
        if self.energy < CHASE_EXHAUSTION_FRACTION * self.body.max_energy:
            return True
        return self.distance_to(quarry) > self.detection_range(quarry) + CHASE_GIVE_UP_MARGIN

    def escape_chance(self, prey: Entity) -> float:
        """Probability that ``prey`` tears free of this predator.

        Pace decides most of it and leverage the rest: prey that is fast for its
        build slips away, and a heavy one can wrench itself loose. A juvenile has
        neither. The bounds keep every hunt uncertain — there is no sure kill and
        no sure escape.
        """
        chance = (
            BASE_ESCAPE_CHANCE
            + ESCAPE_SPEED_WEIGHT * (prey.body.speed - self.body.speed)
            + ESCAPE_POWER_WEIGHT * (prey.body.escape_power / self.body.body_size - 0.5)
        )
        if prey.stage is LifeStage.JUVENILE:
            chance -= ESCAPE_JUVENILE_PENALTY
        return min(MAX_ESCAPE_CHANCE, max(MIN_ESCAPE_CHANCE, chance))

    def _attempt_capture(self, prey: Entity) -> None:
        """Try to bring down prey that has been run to ground."""
        if self._rng.random() < self.escape_chance(prey):
            # It tore free: hurt, but away. The predator has to regather before
            # it can seize anything again.
            prey.energy *= 1.0 - WOUND_ENERGY_LOSS
            self._capture_rest_until = self.age + RECAPTURE_COOLDOWN
            self._quarry = None
            return

        prey.die(DeathCause.PREDATION)
        meal = KILL_ENERGY_PER_SIZE * prey.body.body_size * prey.prey_value
        self.energy = min(self.body.max_energy, self.energy + meal)
        self._quarry = None
        self.state = EntityState.REST

    # --- Movement ---------------------------------------------------------- #

    def _sprint_toward(self, tx: float, ty: float, world: World) -> None:
        """Run flat out, paying for it. Sprinting is quadratic in pace."""
        self.energy -= self.body.sprint_cost
        self._move_toward(tx, ty, world, speed_scale=SPRINT_SPEED_MULTIPLIER)

    def _move_toward(self, tx: float, ty: float, world: World, speed_scale: float = 1.0) -> None:
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
        step = min(self.body.speed * speed_scale / cost, dist)
        heading = math.atan2(dy, dx)

        for deflection in _AVOID_DEFLECTIONS:
            angle = heading + deflection * self._turn_bias
            nx = self.x + math.cos(angle) * step
            ny = self.y + math.sin(angle) * step
            # Keep position strictly inside world bounds so int(pos) is valid.
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
                tx = self.x + self._rng.uniform(-r, r)
                ty = self.y + self._rng.uniform(-r, r)
                tx = max(0.0, min(world.width - 1.0, tx))
                ty = max(0.0, min(world.height - 1.0, ty))
                if world.is_walkable(int(tx), int(ty)):
                    self._target_x = tx
                    self._target_y = ty
                    break
        return self._target_x, self._target_y

    # --- Reproduction ------------------------------------------------------ #

    def _can_breed(self) -> bool:
        """Whether this animal is in a position to have young right now.

        Four gates, and every one of them matters to the shape of a population:
        it has to be grown, inside the fertile middle of its life, rested since
        its last birth, and not already at its lifetime limit.
        """
        if self.offspring >= MAX_OFFSPRING:
            return False
        if self.age < FERTILITY_START_FRACTION * self.lifespan:
            return False
        if self.age > FERTILITY_END_FRACTION * self.lifespan:
            return False
        return self.age >= self._breeding_rest_until

    def _try_reproduce(self, world: World) -> Entity | None:
        if not self._can_breed():
            return None
        if self.energy < REPRODUCTION_THRESHOLD * self.body.max_energy:
            return None

        cx, cy = self._birth_spot(world)
        child = Entity(cx, cy, self.diet, self.genome.mutate(self._rng), rng=self._rng)

        # A newborn body is a fraction of its parent's and cannot hold a
        # parent-sized share of energy. Transferring the full share regardless
        # would start it at nearly twice its own capacity — an invariant every
        # other path respects — so the parent only gives what fits.
        given = min(CHILD_ENERGY_FRACTION * self.body.max_energy, child.body.max_energy)
        child.energy = given
        self.energy -= given

        self.offspring += 1
        self._breeding_rest_until = self.age + round(BREEDING_COOLDOWN_FRACTION * self.lifespan)
        return child

    def _birth_spot(self, world: World) -> tuple[float, float]:
        """Find somewhere beside the parent to put a newborn.

        Without this a child can land in a lake or on a mountainside, where it
        is stranded: nothing can walk out of a cell it could never walk into.
        """
        for _ in range(6):
            cx = self.x + self._rng.uniform(-1.0, 1.0)
            cy = self.y + self._rng.uniform(-1.0, 1.0)
            cx = max(0.0, min(world.width - 1e-6, cx))
            cy = max(0.0, min(world.height - 1e-6, cy))
            if world.is_walkable(int(cx), int(cy)):
                return cx, cy
        return self.x, self.y
