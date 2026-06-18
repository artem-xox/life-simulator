# life-simulator

A 2D life and evolution simulator in Python. Configure the world and starting
species on the setup screen, then watch the ecosystem run on its own: creatures
forage, eat, reproduce with random mutations, age, and die — and natural
selection emerges from the balance.

See [PLAN.md](PLAN.md) for the full design and roadmap.

## Status

| Stage | Description | State |
|-------|-------------|-------|
| 0 | Project skeleton: window, main loop, screen manager | ✅ done |
| 1 | World generation, terrain rendering, pan/zoom camera | ✅ done |
| 2 | Entities: herbivores, carnivores, energy, eating, death | ✅ done |
| 3 | Genome, asexual reproduction, mutations, spatial index | ✅ done |
| 4 | Setup screen (pygame_gui sliders + Start button) | ✅ done |
| 5 | SimScreen polish: entity info on click, population graph | ✅ done |
| 6 | Statistics, save/load, balance (mutation rate) | ✅ done |

## Requirements

* Python 3.11+
* [uv](https://docs.astral.sh/uv/) for environment management

## Setup & run

```bash
make install   # create the virtualenv and install all dependencies
make run       # launch the simulator
```

## Setup screen

On launch you will see the configuration menu. Drag sliders to adjust
parameters, then click **Start Simulation**.

| Column | Parameters |
|--------|-----------|
| **World** | Seed, Water level, Climate (dry ↔ wet), Map width, Map height |
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
| `R` | restart with a new random seed (same species) |
| `S` / `L` | save / load the simulation |
| `G` | toggle the population graph |
| `ESC` | return to setup menu |

The HUD shows live counts; the bottom-right graph plots herbivore and
carnivore populations over time. Click any creature to open the inspector
panel with its full genome, energy bar, and age.

## Development

```bash
make test       # run tests with full output
make test-fast  # run tests quietly
make lint       # ruff check (read-only)
make fmt        # ruff fix + format in-place
make fmt-check  # ruff check + format --check (CI-safe)
make ci         # fmt-check + test in one shot
make clean      # remove __pycache__, .pytest_cache, build artifacts
```

## Project layout

```
src/life_simulator/
  config/
    settings.py       biome definitions, window constants, balance values
    log.py            centralised logging (ms timestamps to stderr)
  simulation/
    world.py          World: biome grid + food arrays + regrow logic
    worldgen.py       WorldConfig, generate() → World via OpenSimplex noise
    genome.py         Genome dataclass with Gaussian mutate()
    entity.py         Entity behaviour loop (move, eat, attack, reproduce)
    ecosystem.py      Ecosystem: tick(), spawn, ENTITY_CAP=2000, Stats sampling
    spatial.py        SpatialGrid: hash buckets for O(k) neighbour queries
    stats.py          Stats: ring buffer of population + average-genome samples
  persistence/
    save_load.py      JSON save/load of full simulation state
  ui/
    screen.py         Screen ABC + ScreenManager transition logic
    setup_screen.py   pygame_gui configuration menu (sliders + Start/Load)
    sim_screen.py     simulation view: world + HUD + inspector + graph
    camera.py         Camera: zoom, pan, clamp, visible-rect culling
    render.py         WorldRenderer + draw_entities + selection/picking
  __main__.py         entry point (uv run life-sim)
tests/                pytest suite (30 tests)
Makefile              dev workflow shortcuts
```
