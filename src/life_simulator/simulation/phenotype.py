"""Phenotype: what a genome actually makes of a body.

Genes mutate independently, but traits are not independent in the world: mass
has to be carried, fed and hidden. This module derives an animal's real
abilities from its genes, and every derivation is a trade-off, so no gene is
simply better than its alternative.

Growing large buys a deep energy reserve, a real chance of tearing free of a
predator, and — because metabolism scales sub-linearly with mass — a lower
upkeep *per unit of body*. It costs absolute upkeep, pace, and concealment.
Growing small is the mirror bargain. Which side wins is not written down
anywhere; it depends on how much grass there is and how many predators are
hunting, which is exactly the question the simulation exists to ask.

The relationships:

======================  ============================================
``max_energy``          ``E · size^1.2`` — reserves outgrow the body
``tick_cost``           ``C · size^0.75`` — Kleiber's law
``speed``               ``gene / size^0.4`` — mass drags
``travel_cost``         ``T · size^0.75`` — charged per cell moved
``sprint_cost``         ``tick_cost · K · speed^2`` — quadratic in pace
``stealth``             ``gene − P · (size − 1)`` — bulk is conspicuous
``escape_power``        ``size`` — leverage against a predator
======================  ============================================
"""

from __future__ import annotations

from dataclasses import dataclass

from life_simulator.config.settings import (
    BASE_ENERGY_COST,
    ENERGY_SIZE_EXPONENT,
    MAX_ENERGY_BASE,
    MAX_STEALTH,
    METABOLIC_SIZE_EXPONENT,
    SPEED_SIZE_EXPONENT,
    SPRINT_COST_FACTOR,
    STEALTH_SIZE_PENALTY,
    TRAVEL_ENERGY_FACTOR,
)
from life_simulator.simulation.genome import Genome


@dataclass(frozen=True)
class Phenotype:
    """The abilities a genome yields at a given stage of growth.

    Attributes:
        body_size: realised size — genetic size scaled by how grown the animal
            is. A juvenile carries the same genes in a smaller body.
        max_energy: how much energy the body can hold.
        tick_cost: energy burnt per tick simply staying alive.
        speed: cells per tick at a walk, after the drag of carrying the body.
        travel_cost: energy spent per cell travelled. Charged by distance, so
            a faster animal pays more per tick for covering more ground.
        sprint_cost: energy per tick burnt running flat out, on top of upkeep.
        stealth: realised concealment in [0, MAX_STEALTH]; how much of an
            observer's vision it defeats.
        escape_power: leverage when trying to tear free of a predator.
    """

    body_size: float
    max_energy: float
    tick_cost: float
    speed: float
    travel_cost: float
    sprint_cost: float
    stealth: float
    escape_power: float

    @classmethod
    def of(cls, genome: Genome, growth: float = 1.0) -> Phenotype:
        """Derive the phenotype of ``genome`` in a body ``growth`` of full size.

        Args:
            growth: how far the animal has grown, from 0 to 1. Juveniles are
                built from the same genes in a smaller body, and so are slower,
                cheaper to run, and easier to catch.
        """
        body = genome.size * growth
        tick_cost = BASE_ENERGY_COST * body**METABOLIC_SIZE_EXPONENT
        speed = genome.speed / body**SPEED_SIZE_EXPONENT

        # Concealment is judged against a full-grown body: a small animal is
        # hard to see because it is small, whatever its genes say.
        stealth = genome.stealth - STEALTH_SIZE_PENALTY * (body - 1.0)

        return cls(
            body_size=body,
            max_energy=MAX_ENERGY_BASE * body**ENERGY_SIZE_EXPONENT,
            tick_cost=tick_cost,
            speed=speed,
            travel_cost=TRAVEL_ENERGY_FACTOR * body**METABOLIC_SIZE_EXPONENT,
            sprint_cost=tick_cost * SPRINT_COST_FACTOR * speed**2,
            stealth=min(MAX_STEALTH, max(0.0, stealth)),
            escape_power=body,
        )
