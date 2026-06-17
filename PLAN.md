# Life Simulator — Design & Roadmap

A 2D life / evolution simulator in Python. The player configures the world and
starting species on the setup screen, then the ecosystem runs on its own:
creatures forage, eat, reproduce with mutations, age, and die. Natural
selection emerges from the energy balance.

---

## Technology stack

| Purpose | Library | Notes |
|---------|---------|-------|
| Window, rendering, event loop | `pygame-ce` ≥ 2.5 | community edition, faster than classic pygame |
| UI widgets (sliders, buttons) | `pygame_gui` ≥ 0.6 | used on the setup screen |
| Numeric world arrays | `numpy` ≥ 1.26 | vectorised food regrow, biome lookups |
| Terrain noise | `opensimplex` ≥ 0.4 | fractal fBm from two noise fields |
| Tests | `pytest` ≥ 8 | |
| Lint / format | `ruff` | line-length=100, rules E/W/F/I/UP/B/C4 |
| Environment | `uv` | replaces venv + pip |
| Build backend | `hatchling` | src-layout, `life-sim` console script |

Python 3.11.  `pygame-ce` is API-compatible with `pygame` but more actively
maintained and ships faster SDL2 bindings.

---

## Architecture

**Strict separation between simulation and rendering.**  The `simulation/`
package contains pure logic operating on numpy arrays and Python objects — no
pygame imports.  The `ui/` package reads simulation state and draws it.
Benefits:
- the simulation can run headless (tests, benchmarks, time-skipping);
- tick rate is decoupled from frame rate.

Data flow:
```
SetupScreen  ──►  WorldConfig + SpeciesConfig[]
                        │
                        ▼
                  Ecosystem.create()
                        │  generates world, spawns entities
                        ▼
  game loop ──►  Ecosystem.tick()  (N ticks per rendered frame)
                        │
                        ▼
                  SimScreen.draw()  ──►  display
```

The `ScreenManager` owns the active `Screen` and switches screens when
`Screen.update()` returns a new instance.

---

## Project structure

```
src/life_simulator/
  config/
    settings.py       Biome enum, colour tables, food/regrow tables,
                      window constants, HERBIVORE_COLOR, CARNIVORE_COLOR,
                      SIM_SPEED_OPTIONS
    log.py            setup() — root logger with ms timestamps to stderr
  simulation/
    world.py          World: biome (int8), food (float32), food_max (float32)
                      regrow_food(), eat_at(), is_walkable(), move_cost()
    worldgen.py       WorldConfig dataclass, generate() → World
                      fractal fBm from elevation + moisture OpenSimplex fields
    genome.py         Genome dataclass (speed, vision, metabolism, size,
                      repro_threshold, mutation_rate); mutate(), copy()
    entity.py         Entity (x, y, energy, age, alive, diet, genome)
                      step() behaviour: move → eat/attack → reproduce
    ecosystem.py      Ecosystem: tick(), create(), _spawn_initial()
                      ENTITY_CAP=2000, SpatialGrid rebuild each tick
    spatial.py        SpatialGrid: defaultdict hash buckets, rebuild(), nearby()
  ui/
    screen.py         Screen ABC (handle_event, update, draw, resize)
                      ScreenManager
    setup_screen.py   SetupScreen: three-column pygame_gui layout
                      world params | herbivore traits | carnivore traits
                      seed entry + Random button + Start Simulation button
                      values persist across window resize
    sim_screen.py     SimScreen: WorldRenderer + entity overlay + HUD
                      accumulator-based tick scheduling (up to 40 ticks/frame)
                      ESC → SetupScreen, R → restart same species new seed
    camera.py         Camera: zoom, pan_pixels(), zoom_at(), fit_to_screen()
                      visible_cell_rect() for render culling
    render.py         WorldRenderer: cached terrain Surface (1 px/cell)
                      draw_entities(): culled coloured circles by diet
    map_screen.py     Legacy stage-1 map viewer (unused; will be removed)
  __main__.py         Entry point: pygame init, window, ScreenManager(SetupScreen)
tests/
  test_worldgen.py    6 tests: determinism, seed variance, dimensions,
                      valid biomes, water_level effect, food < capacity
  test_genome.py      5 tests: copy, mutate new instance, bounds, changes,
                      zero mutation rate clamped
  test_ecosystem.py   10 tests: herb gains energy, starvation, age death,
                      reproduction, carnivore attack, tick count,
                      population never negative, determinism
Makefile
pyproject.toml        hatchling src-layout, life-sim script, dev deps, ruff cfg
```

---

## Data model

### Biomes (`config/settings.py`)

| Biome | Colour | Food max | Regrow rate | Walkable |
|-------|--------|----------|-------------|----------|
| DEEP_WATER | dark blue | 0 | 0 | no |
| WATER | blue | 0 | 0 | no |
| SAND | sandy | 2.0 | 0.01 | yes |
| GRASS | green | 10.0 | 0.05 | yes |
| FOREST | dark green | 6.0 | 0.03 | yes |
| MOUNTAIN | grey | 0 | 0 | yes (slow) |
| SNOW | white | 0 | 0 | yes (slow) |

### World (`simulation/world.py`)

Three numpy arrays of shape `(H, W)`:
- `biome`    — int8, biome index
- `food`     — float32, current food per cell (starts at 0.6 × food_max)
- `food_max` — float32, per-cell capacity from biome lookup

### WorldGen (`simulation/worldgen.py`)

`WorldConfig` fields: `seed`, `width`, `height`, `water_level`, `climate`,
`elevation_scale`, `moisture_scale`, `octaves`.

`generate(cfg)` builds two fractal fBm noise fields (elevation + moisture)
from OpenSimplex, classifies each cell into a biome, returns a `World`.
Fully deterministic from `seed`.

### Genome (`simulation/genome.py`)

| Gene | Range | Effect |
|------|-------|--------|
| `speed` | 0.3 – 3.0 | cells moved per tick |
| `vision` | 2.0 – 15.0 | food/prey search radius |
| `metabolism` | 0.5 – 2.0 | energy cost multiplier |
| `size` | 0.5 – 3.0 | attack power, energy cost |
| `repro_threshold` | 0.4 – 0.9 | fraction of max energy needed to reproduce |
| `mutation_rate` | 0.005 – 0.30 | Gaussian noise std applied to each gene |

`mutate()` adds Gaussian noise scaled by `mutation_rate`, clips to bounds.

### Entity (`simulation/entity.py`)

Key balance constants (tuned for stable Lotka-Volterra oscillation):

```
BASE_ENERGY_COST      = 0.30   per tick, scaled by metabolism × size
MAX_ENERGY_BASE       = 20.0
EATING_AMOUNT         = 2.0    food units consumed per tick (herbivore)
EATING_GAIN           = 0.40   energy gained per food unit (deliberately low)
ATTACK_DAMAGE         = 1.8    energy removed from prey per attack tick
ATTACK_EFFICIENCY     = 0.40   fraction converted to attacker energy
ATTACK_RANGE          = 1.5    cells
CHILD_ENERGY_FRACTION = 0.65   parent gives 65% of its energy to child
MAX_AGE               = 700    ticks
```

`step()` behaviour each tick:
1. pay energy cost; die if energy ≤ 0 or age > MAX_AGE
2. herbivore: find food cell within vision → move toward it → eat
3. carnivore: find nearest herbivore within vision → move toward it → attack
4. if no target, wander (random direction, recalculated every 10 ticks)
5. if energy ≥ repro_threshold × max_energy → spawn child with mutated genome

### SpatialGrid (`simulation/spatial.py`)

Hash buckets keyed by `(floor(x / bucket_size), floor(y / bucket_size))`.
`rebuild()` runs O(N) each tick; `nearby(x, y, radius)` returns O(k) results.
Default bucket size: 8 cells.

### Ecosystem (`simulation/ecosystem.py`)

`tick()` sequence:
1. `world.regrow_food()` — vectorised numpy
2. `spatial.rebuild(entities)` — O(N)
3. iterate entities: `entity.step(world, spatial)` → collect newborns
4. remove dead; admit newborns up to `ENTITY_CAP = 2000` (random drop if over)
5. increment `tick_count`; log every 100 ticks

`create(world_cfg, species, pump_events=True)` calls `pygame.event.pump()`
after world generation to keep macOS from marking the window as unresponsive
during the ~1 s startup.

### SetupScreen (`ui/setup_screen.py`)

Three-column pygame_gui layout:

| Column 0 — World | Column 1 — Herbivores | Column 2 — Carnivores |
|---|---|---|
| Seed (text entry) + Random btn | Count | Count |
| Water level (slider) | Speed | Speed |
| Climate dry/wet (slider) | Vision | Vision |
| Map width (slider) | Metabolism | Metabolism |
| Map height (slider) | Repro threshold | Repro threshold |

Slider labels update in real time showing the current value.
`_Vals` dataclass preserves values across window resize rebuilds.
Pressing **Start Simulation** constructs `WorldConfig` + `SpeciesConfig[]`
and transitions to `SimScreen`.

### SimScreen (`ui/sim_screen.py`)

- Accumulator pattern: `floor(tps × dt)` ticks per frame, capped at 40.
- HUD (top-left semi-transparent panel): tick, herb count, carn count,
  speed, zoom.
- Hint bar at bottom: `Space=pause  ]/[=speed  F=fit  R=restart  ESC=menu`.
- ESC returns to `SetupScreen` (screen transition, not quit).
- R restarts with same species config but a new random seed.

---

## Performance targets

- `~2 000` entities on a `160 × 120` cell world at `≥ 50 FPS`.
- Numpy vectorisation for food regrow and biome lookups.
- `SpatialGrid` reduces neighbour search from O(N²) to O(k).
- `WorldRenderer` pre-renders the terrain to a Surface; only redraws on
  `set_world()` (world change), not every frame.
- Entity rendering culls anything outside the visible screen rect + margin.

---

## Roadmap

| # | Stage | Deliverable | Status |
|---|-------|-------------|--------|
| 0 | Skeleton | window, main loop, screen manager | ✅ done |
| 1 | World | worldgen, terrain render, pan/zoom camera | ✅ done |
| 2 | Entities | herbivores, carnivores, energy, eating, death | ✅ done |
| 3 | Evolution | genome, reproduction, mutations, SpatialGrid | ✅ done |
| 4 | Setup screen | pygame_gui menu, all params configurable | ✅ done |
| 5 | SimScreen polish | click entity → info panel (genome, energy, age); live population graph | 🔲 next |
| 6 | Stats & persistence | ring-buffer stats, matplotlib-style graph surface, save/load JSON | 🔲 planned |

---

## Stage 5 detail — SimScreen polish

**Entity info panel** (click on a creature):
- open a side panel (pygame_gui `UIPanel` or hand-drawn surface)
- display: diet, age, energy bar, all genome values
- close on second click or `Escape`

**Population graph**:
- `Stats` class: ring buffer of (tick, herb_count, carn_count) pairs
- drawn as a small chart on the SimScreen (bottom strip or overlay)
- x-axis = recent N ticks, y-axis = population; two coloured lines

---

## Stage 6 detail — Stats & persistence

**Save / load**:
- JSON format: `seed`, `world_cfg`, `species_configs`, `tick_count`
- optional full entity dump (x, y, energy, age, genome for each entity)
- compact save = just seed + config (world is fully reproducible)
- full save = config + all entity states

**Balance polish**:
- expose `mutation_rate` slider on setup screen
- add predator-prey parameter presets (stable, boom-bust, extinction-prone)
- consider seasonal food regrow multiplier

---

## Open questions (post-v1)

- Sexual reproduction with crossover between two parents.
- Day/night cycle and seasonal climate events.
- Neural-network "brain" for entity decision making.
- Multiple trophic levels (producers, herbivores, omnivores, carnivores, decomposers).
- Export evolution graphs to PNG.
- Map editor or hand-drawn seed terrain.
