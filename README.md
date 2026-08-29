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
| 8 | Genome 2.0: new gene set, phenotype trade-offs, crossover | ⬜ next |
| 9–14 | Lifecycle, behaviour, mating, sprites, analytics, balance | ⬜ todo |

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

The simulator opens borderless at desktop size; `F11` drops it to a window.

## Setup screen

On launch you will see the configuration menu. Drag sliders to adjust
parameters, then click **Start Simulation**.

| Column | Parameters |
|--------|-----------|
| **World** | Seed, Water level, Map width, Map height |
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
    genome.py         Genome dataclass with Gaussian mutate()
    entity.py         Entity behaviour loop (move, graze, attack, reproduce)
    ecosystem.py      Ecosystem: tick(), spawn, ENTITY_CAP, Stats sampling
    spatial.py        SpatialGrid: hash buckets for O(k) neighbour queries
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

The ecosystem is **not balanced yet**. Reproduction is still unlimited — an
animal breeds whenever it has the energy — so herbivores overshoot the island's
carrying capacity, strip the grass and starve. Lifespans, limited breeding and
predator behaviour arrive in stages 9–11; the tuning pass is stage 14.
