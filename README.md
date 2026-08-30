# life-simulator

A 2D life and evolution simulator in Python. Configure the world and starting
species on the setup screen, then watch the ecosystem run on its own: creatures
forage, eat, reproduce with random mutations, age, and die — and natural
selection emerges from the balance.

See [DESIGN.md](DESIGN.md) for the design and [PLAN.md](PLAN.md) for the roadmap.

## Status

| Stage | Description | State |
|-------|-------------|-------|
| 0–6 | v1: world, entities, asexual evolution, setup screen, stats, save/load | ✅ done |
| 7 | Map 2.0: island with rivers, lakes, beaches and mountains; grass layer; full-screen | ✅ done |
| 8 | Genome 2.0: new gene set, phenotype trade-offs, crossover | ✅ done |
| 9 | Lifecycle: juveniles, limited breeding, causes of death | ✅ done |
| 10 | Behaviour: hunt/rest modes, stealth detection, chases | ⬜ next |
| 11–14 | Mating, sprites, analytics, balance | ⬜ todo |

## The world

One temperate island in an ocean, generated deterministically from a seed.

| Surface | Walkable | Grass |
|---------|----------|-------|
| Ocean | no | no |
| Rivers and lakes | no | no |
| Sand | yes | no |
| Forest | yes | **yes** |
| Mountain | no | no |

Water and rock are both hard obstacles: animals can neither swim nor climb, so
ranges and rivers have to be walked around.

## Life

An animal is born at 40% of the size its genes call for, and small and clumsy
enough to be easy prey. It grows up over the first fifth of its life, breeds at
most twice inside a window in the middle of it, and dies of exactly one of three
things: starvation, old age, or being eaten.

Its genes — size, speed, stealth, vision, sociality and mutation rate — mutate
independently, but what a body can actually *do* is derived from them with
physical trade-offs. Growing large banks a reserve that outgrows the body and
costs less upkeep per unit of itself, and pays for it in pace, concealment and
absolute upkeep. Click any animal to see its genes beside the body they made.

Grass grows only in the forest, and it grows *logistically* — from what is
still standing, fastest at middling density. A cell grazed to bare earth has
nothing left to grow from and recovers only by seeding in from its neighbours,
so an overgrazed patch heals slowly from its edges and leaves a visible scar in
the meantime. The map is shaded by grass density, so you can see where the
herds have been.

## Requirements

* Python 3.11+
* [uv](https://docs.astral.sh/uv/) for environment management

## Setup & run

```bash
make install
```

```bash
make run
```

The simulator opens full-screen; `F11` drops it to a window.

The default map is 640×400 cells — about two screen pixels per cell full-screen,
so terrain reads as landscape rather than as tiles. Raise it in the setup screen
for finer detail; terrain features scale with the map, so a larger map is the
same island in more detail rather than a different, busier one.

## Setup screen

On launch you will see the configuration menu. Drag sliders to adjust
parameters, then click **Start Simulation**.

| Column | Parameters |
|--------|-----------|
| **World** | Seed, Water level, Map width (240–1200), Map height (150–750) |
| **Herbivores** | Count, Speed, Vision, Metabolism, Repro threshold, Mutation rate |
| **Carnivores** | Count, Speed, Vision, Metabolism, Repro threshold, Mutation rate |

Click **Random** to roll a new seed without changing other settings.
**Load Saved Game** resumes the last save (`life_sim_save.json`) directly.

## Simulation controls

| Input | Action |
|-------|--------|
| left-drag | pan camera |
| left-click | select / inspect an entity (shows genome, energy, age) |
| mouse wheel | zoom toward cursor |
| `Space` | pause / resume |
| `]` / `[` | speed up / slow down |
| `F` | fit world to screen |
| `F11` | toggle fullscreen / windowed |
| `R` | restart with a new random seed (same species) |
| `S` / `L` | save / load the simulation |
| `G` | toggle the population graph |
| `ESC` | return to setup menu |

## Development

```bash
make ci
```

| Target | What it does |
|--------|--------------|
| `make test` | run tests with full output |
| `make test-fast` | run tests quietly |
| `make lint` | ruff check + pylint (read-only) |
| `make pylint` | pylint on all tracked files (mirrors the GitHub workflow) |
| `make fmt` | ruff fix + format in-place |
| `make fmt-check` | ruff check + format --check (CI-safe) |
| `make ci` | fmt-check + pylint + test in one shot |
| `make clean` | remove `__pycache__`, `.pytest_cache`, build artifacts |

Linting is enforced in CI by the [Pylint workflow](.github/workflows/pylint.yml).
Pylint's configuration lives in the `[tool.pylint.*]` sections of
[pyproject.toml](pyproject.toml).

## Project layout

```
src/life_simulator/
  config/
    settings.py       surface definitions, terrain palette, balance values
    log.py            centralised logging (ms timestamps to stderr)
  simulation/
    world.py          World: surface + elevation + grass, logistic regrowth
    worldgen.py       WorldConfig, generate() → island from vectorised Perlin
    genome.py         Genome: six genes, Gaussian mutate(), crossover()
    phenotype.py      Phenotype: genes → abilities, with physical trade-offs
    entity.py         Entity behaviour loop (move, graze, attack, reproduce)
    ecosystem.py      Ecosystem: tick(), spawn, ENTITY_CAP, Stats sampling
    spatial.py        SpatialGrid: hash buckets for O(k) neighbour queries
    grid.py           shared numpy neighbourhood maths (blur, dilate, spread)
    stats.py          Stats: ring buffer of population + average-genome samples
  persistence/
    save_load.py      JSON save/load of full simulation state
  ui/
    screen.py         Screen ABC + ScreenManager transition logic
    setup_screen.py   pygame_gui configuration menu (sliders + Start/Load)
    sim_screen.py     simulation view: world + HUD + inspector + graph
    camera.py         Camera: zoom, pan, clamp, visible-rect culling
    render.py         terrain shading (hillshade, depth, grass) + entities
  __main__.py         entry point (uv run life-sim)
tests/                pytest suite
Makefile              dev workflow shortcuts
```

## Known gaps

The ecosystem is **not balanced yet**, though it now usually persists: across
six seeds, five herbivore populations survived 15 000 ticks on a 320×200 map.

Predators are the weak point. A carnivore still feeds by draining energy on
contact — there is no hunting, no chase and no rest after a kill — so predation
accounts for about 1% of deaths and carnivores usually die out early. Stage 10
replaces that model wholesale. The tuning pass is stage 14.
