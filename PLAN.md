# Life Simulator — Development Plan

The design of the target system is in [DESIGN.md](DESIGN.md). This file tracks
the roadmap: stages, tickets, and acceptance criteria.

## Status overview

| # | Stage | Deliverable | Status |
|---|-------|-------------|--------|
| 0–6 | **v1** | world gen, entities, asexual evolution, setup screen, stats, save/load | ✅ done |
| 7 | Map 2.0 | island with rivers/lakes/beaches/mountains, grass layer, full-screen | ✅ done |
| 8 | Genome 2.0 | new gene set, phenotype trade-offs, crossover | ✅ done |
| 9 | Lifecycle | juveniles, 1–2 births per life, death causes | ✅ done |
| 10 | Behaviour | state machines, stealth detection, chase & escape | ✅ done |
| 11 | Mating & social | sexual selection, courtship, families, herds | ⬜ todo |
| 12 | Visuals 2.0 | procedural animal sprites, state cues, LOD | ⬜ todo |
| 13 | Analytics 2.0 | event log, live charts, HTML report, presets | ⬜ todo |
| 14 | Balance & polish | tuning, shipped presets, performance, docs | ⬜ todo |

v1 (stages 0–6) is complete and documented in [README.md](README.md); its
design notes were superseded by DESIGN.md.

Suggested order is as listed: each stage leaves the simulator runnable.
Stages 7–8 are foundations; 9–11 build the biology; 12–13 make it beautiful
and measurable; 14 makes it balanced and shippable.

---

## Stage 7 — Map 2.0 (island, grass, full-screen)

Goal: replace the 7-biome world with the one-biome / four-surface island and a
living grass layer; the app opens full-screen with the island fitted.

| Ticket | Description | Acceptance |
|---|---|---|
| 7.1 | Replace `Biome` enum with `Surface` (`OCEAN`, `FRESH_WATER`, `SAND`, `FOREST`, `MOUNTAIN`) + lookup tables in `config/settings.py` | ✅ old biome constants gone; tests updated |
| 7.2 | Island generator: warped fractal elevation × radial falloff → land mask, ocean all around | ✅ every map edge is `OCEAN`; one landmass dominates; speck islands drowned |
| 7.3 | Lakes (water the ocean cannot reach) and a branching river network traced downhill to the ocean | ✅ lakes and rivers on the default seed; rivers reach the ocean |
| 7.3a | Impassable mountains above a `mountain_level`, and obstacle avoidance so animals route around rock and water instead of freezing | ✅ animals aimed into rock slide around it; nothing spawns on impassable cells |
| 7.4 | Beaches: `SAND` on land cells within noise-jittered distance of water | ✅ every waterline has a sand fringe; width tunable via `shore_width` |
| 7.5 | Grass layer: `grass` float32 on `FOREST` only; logistic regrowth + neighbour reseeding; `graze_at()` API replacing `eat_at()` | ✅ regrowth curve, bare-cell recovery only via neighbours, no grass outside forest |
| 7.6 | Full-screen borderless window by default (`F11` toggle, resizable kept); camera fits island on start | ✅ app opens full-screen; `F` refits |
| 7.7 | Terrain render v2: hillshading, altitude bands, grass density shading, water depth tint, shoreline surf, canopy texture | ✅ grazing scars visibly change the map during a run; map reads as terrain, not flat colour blocks |
| 7.8 | Cleanup: delete `ui/map_screen.py`, old biome food tables, dead constants | ✅ lint clean; all tests green |

---

## Stage 8 — Genome & phenotype 2.0

Goal: the new gene set with physical trade-offs and two-parent crossover
(mechanics only — mating behaviour arrives in stage 11).

| Ticket | Description | Acceptance |
|---|---|---|
| 8.1 | New `Genome`: `size`, `speed`, `stealth`, `vision`, `sociality`, `mutation_rate` with bounds; drop `metabolism`, `repro_threshold` | ✅ mutate/copy work; bounds respected |
| 8.2 | `Phenotype` layer: `max_energy`, `tick_cost` (Kleiber), `speed`, `travel_cost`, `sprint_cost`, `stealth`, `escape_power` | ✅ tests assert trade-off directions (bigger ⇒ slower, more max energy, higher cost, less stealth) |
| 8.3 | `Genome.crossover(other)`: uniform per-gene pick + one mutation pass | ✅ child genes come from a parent ± mutation noise; variation preserved |
| 8.4 | Wire phenotype into `Entity` (movement cost, energy cap); update `SpeciesConfig` and setup-screen sliders to the new genes | ✅ sim runs on new genome end-to-end |
| 8.5 | Inspector shows genes and derived phenotype side by side | ✅ click an animal → both columns visible |

---

## Stage 9 — Lifecycle

Goal: age stages, limited reproduction, and exactly three causes of death.

| Ticket | Description | Acceptance |
|---|---|---|
| 9.1 | Lifespan = species constant ± 10% individual; age stages `JUVENILE` / `ADULT`; body growth 0.4× → 1.0× plus a coordination term | ✅ growth curve test; stage flips at 20% |
| 9.2 | Reproduction bookkeeping: `offspring` (max 2), fertility window 20–80% of life, post-birth cooldown ≈ 25% of lifespan | ✅ no entity ever exceeds 2 births; juveniles never reproduce |
| 9.3 | `DeathCause` (`STARVATION`, `OLD_AGE`, `PREDATION`) recorded on death; no other death paths remain | ✅ accounting test: seeded + births − deaths == living |
| 9.4 | Juvenile vulnerability: reduced speed/`escape_power` via coordination, lower energy value to predators | ✅ constants in settings; ready for stage 10 combat |
| 9.5 | Tests for the full lifecycle on a long headless run | ✅ 3k-tick run: both stages present, all three causes recorded |

---

## Stage 10 — Behaviour 2.0

Goal: state machines, stealth-driven detection, and the chase with an escape
roll (replaces energy-drain combat).

| Ticket | Description | Acceptance |
|---|---|---|
| 10.1 | `EntityState` enum, per-state dispatch, state shown in the inspector; ecosystem-owned `random.Random(seed)` replaces global `random` throughout | ✅ state visible in inspector; same seed ⇒ identical run |
| 10.2 | Herbivore `FORAGE` (best grass cell in vision) + `REST` when full | ✅ forages when hungry, rests when sated, flight overrides both |
| 10.3 | Detection model: `observer.vision · (1 − target.stealth)`, used by both species | ✅ unit tests with hand-built genomes; detection is not mutual |
| 10.4 | `CHASE` / `FLEE`: sprint speed and cost, give-up on distance or exhaustion | ✅ chases terminate; sprinting costs more than walking |
| 10.5 | Capture roll; escape ⇒ wound + predator cooldown; kill ⇒ death(PREDATION) + meal | ✅ probability bounds test; wounded prey loses energy |
| 10.6 | Predator `REST` (digestion) until energy < hunger threshold, then `HUNT` | ✅ a kill sends it to rest; rest ends when hunger returns |
| 10.7 | Behaviour test suite + smoke balance: default config survives 5k ticks with both species alive | CI green |

---

## Stage 11 — Mating & social behaviour

Goal: sexual selection, courtship, families, and emergent herds.

| Ticket | Description | Acceptance |
|---|---|---|
| 11.1 | `SEEK_MATE`: readiness conditions (adult, energy, fertility window, count < 2); candidate scoring `0.6·energy_ratio + 0.4·size_norm`; mutual acceptance | best-scoring mutual pair forms; loners keep foraging |
| 11.2 | `COURT`: approach, courtship timer together, child spawned via crossover near parents; both pay energy share, both `repro_count += 1` | birth event recorded with both parents |
| 11.3 | Family bonds: juveniles steer strongly toward parents; parents mildly toward offspring; bond dissolves at adulthood | juvenile avg distance to parent bounded (test) |
| 11.4 | Herd steering: cohesion toward same-species neighbours × `sociality` gene + close-range separation; applies to both species | high-sociality population clusters measurably more than low (metric test) |
| 11.5 | Shared vigilance: a fleeing herbivore alerts same-species neighbours within a radius (they flee too) | alert propagation test |

---

## Stage 12 — Visuals 2.0

Goal: the map full of animals that look and read like animals.

| Ticket | Description | Acceptance |
|---|---|---|
| 12.1 | Sprite factory: procedural deer-like / wolf-like silhouettes drawn with pygame primitives; cache keyed by (species, size bucket, facing, frame, stage) | no per-frame drawing of primitives; cache hit rate ~100% in steady state |
| 12.2 | Animation: 4-frame walk cycle driven by velocity; idle pose; facing from movement direction (flip/rotate) | animals visibly walk, not glide |
| 12.3 | Gene-driven look: scale from size × growth curve; fur tint from `stealth`; juvenile proportions (small body, big head) | two extreme genomes are visually distinct at a glance |
| 12.4 | State cues: Zzz (rest), hearts (courtship), wound flash, sprint streaks | each state identifiable without the inspector |
| 12.5 | LOD: below zoom threshold render simple oval markers | zoomed-out view of 1000 animals ≥ 50 FPS |
| 12.6 | Inspector v2: name, state, age stage, repro count, family links; HUD counts by species and state | — |
| 12.7 | Name generator: every animal gets a readable name used in inspector & event log | — |
| 12.8 | Camera follow mode: key to lock camera on selected animal | follow survives target movement; ESC releases |

---

## Stage 13 — Analytics 2.0 & experiments

Goal: the observation tooling the project exists for.

| Ticket | Description | Acceptance |
|---|---|---|
| 13.1 | Event log: births (parents), deaths (cause, age, position), hunts (kill/escape), matings; ring buffer + cumulative counters | events queryable by type; counters monotone |
| 13.2 | Stats v2: per-species series of population, mean+std per gene, grass coverage, hunt success; adaptive downsampling for unbounded runs | 100k-tick run fits in bounded memory; series continuous |
| 13.3 | Live panel v2: tabs — population chart, gene-trend chart (mean ± std bands), current gene histograms | toggle keys; readable at full-screen |
| 13.4 | HTML report exporter: single self-contained file (inline JSON + inline JS/SVG charts, no CDN): config, dynamics, gene evolution, distributions (start/mid/now), hunt success, death causes, lifespan histogram | opens offline in a browser; one key press in-game |
| 13.5 | Raw export: CSV/JSON of time series + event log next to the report | loadable in pandas |
| 13.6 | Experiment presets: JSON schema (world + per-species gene means/counts); setup screen rework for new params + preset picker | preset round-trips through the setup screen |
| 13.7 | Save format v2 for full new state (genome, stage, states, families, grass); drop v1 compatibility | save → load → identical continued run (seeded test) |

---

## Stage 14 — Balance & polish

Goal: a tuned default world and a clean release.

| Ticket | Description | Acceptance |
|---|---|---|
| 14.1 | Tuning pass on all constants (energy flow, chase, grass) toward a stable baseline | default preset: both species alive after 20k ticks in ≥ 8/10 seeds |
| 14.2 | Ship three presets: *Stable Meadow*, *Predator Pressure*, *Scarce Grass* | each shows a distinct documented dynamic |
| 14.3 | Performance validation: profile tick + render at 1000 entities on 320×200 | ≥ 50 FPS; hot paths documented |
| 14.4 | Determinism audit: all randomness through the ecosystem RNG | same seed twice ⇒ byte-identical stats series |
| 14.5 | Docs: README v2 (controls, screenshots/GIF, experiment guide), DESIGN/PLAN sync | — |

---

## Working agreement

- Every stage ends green: `make ci` (ruff + pylint + pytest) passes.
- Simulation code stays pygame-free; every new mechanic gets headless tests.
- Balance constants live in `config/settings.py`, never inline.
- Update the status table above as stages complete.
