# Life Simulator v2 — Design

An evolution sandbox: configure initial conditions, then watch a small island
ecosystem live on its own — animals forage, hunt, form groups, court, raise
young, and die — while their genes drift generation by generation. The goal is
**observation and experimentation**: set up different starting conditions and
study where the genetic balance settles.

This document describes the target design. The development roadmap and ticket
breakdown live in [PLAN.md](PLAN.md).

---

## Design pillars

1. **Evolution is the product.** Every mechanic must feed selection pressure
   that is visible in analytics. If a feature does not change which genes win,
   it must at least make the world more legible or alive.
2. **Trade-offs, not stat sticks.** No gene is strictly good. Size buys
   survivability but costs food, speed and stealth — exactly like in nature.
   Balance is emergent, not hand-authored per-gene.
3. **A living world, not a particle sim.** ~300–1000 individuals, each with a
   readable life: states, family, group, history. Detailed procedural sprites
   instead of dots; full-screen map.
4. **Deterministic experiments.** One seed → one reproducible run. All
   randomness flows through a single seeded RNG owned by the ecosystem.
5. **Simulation / rendering separation stays.** `simulation/` remains
   pygame-free and headless-runnable (tests, batch experiments).

Decisions locked with the project owner:

| Question | Decision |
|---|---|
| Stack | Keep Python + pygame-ce (evolve the current codebase) |
| Animal visuals | Procedural sprites drawn in code, cached |
| Analytics | Both: live in-game panel + exported self-contained HTML report |
| Hunting | Chase + capture roll with a chance for the prey to break free |
| Gene correlations | Physical trade-offs in the phenotype layer (genes mutate independently) |
| Time cycles | None for now (day/night & seasons in backlog) |
| Population scale | ~300–1000 individuals |
| Mate choice | Sexual selection: candidates scored by traits, not just proximity |

---

## The world

### Surfaces

One temperate biome with four **surface types** (replaces the seven v1 biomes):

| Surface | Description | Walkable | Grass |
|---|---|---|---|
| `OCEAN` | salt water surrounding the island | no | no |
| `FRESH_WATER` | rivers and lakes inside the island | no | no |
| `SAND` | beaches along every waterline | yes | no |
| `FOREST` | everything else; the living surface | yes | **yes** |

### Generation

Deterministic from a single seed:

1. **Island mask** — fBm elevation noise multiplied by a radial falloff, so the
   map is always an island in an ocean. Coastline stays noisy and interesting.
2. **Lakes** — depressions in the elevation field below a lake level.
3. **Rivers** — a few paths traced from high-elevation interior points downhill
   to the ocean, carving `FRESH_WATER` cells.
4. **Beaches** — land cells within a noise-jittered distance of any water
   become `SAND`.
5. Remaining land is `FOREST`.

Default map ≈ 320×200 cells (configurable); the window opens full-screen and
the camera fits the island on start.

### Grass

A `grass` float32 layer over `FOREST` cells — the single energy inflow of the
ecosystem.

- **Logistic regrowth**: `g += r · g · (1 − g/K)` — grass regrows fast at
  mid-density, slowly when depleted or saturated.
- **Neighbour reseeding**: a fully grazed cell (`g ≈ 0`) can only recover by
  spread from neighbouring cells: `g += s · avg(neighbour g) · (1 − g/K)`.
  Overgrazing therefore leaves visible scars that take long to heal, and herds
  must migrate.
- Rendering shows grass density directly (rich green → yellowed → bare soil),
  so grazing pressure is readable at a glance.

No day/night or seasons in v2 — a stationary world keeps experiments
interpretable. (Backlog: seasonal grass multiplier.)

---

## Genetics

### Genes (heritable, mutate independently)

| Gene | Range | Meaning |
|---|---|---|
| `size` | 0.5 – 2.5 | body mass scale |
| `speed` | 0.5 – 2.0 | base locomotion ability |
| `stealth` | 0.0 – 1.0 | camouflage / quietness |
| `vision` | 3 – 14 | perception radius (cells) |
| `sociality` | 0.0 – 1.0 | how strongly the animal seeks company |
| `mutation_rate` | 0.005 – 0.25 | Gaussian σ per gene (evolvable evolvability) |

Mutation: per-gene Gaussian noise scaled by `mutation_rate · gene_range`,
clipped to bounds (unchanged v1 mechanism).

### Phenotype layer — where correlations live

Genes are independent; the **phenotype** derives effective stats with
physical trade-offs, so correlations emerge the way they do in nature:

```
max_energy   = E_BASE · size^1.2          # big bodies store more
tick_cost    = C_BASE · size^0.75         # Kleiber's law: big is efficient per kg,
                                          # but expensive in absolute terms
eff_speed    = speed / size^0.4           # big is slower
sprint_cost  = tick_cost · SPRINT_K · eff_speed^2   # sprinting burns quadratically
eff_stealth  = clamp(stealth − S_K · (size − 1), 0, 0.95)  # big is conspicuous
escape_power = size                       # big prey breaks free more often
```

Consequences the player should observe, not be told: a lineage drifting toward
large size needs richer grass patches, gets caught less by starvation of
predators but more by them noticing it; a stealth build trends small and
starves less from chases; speed builds pay for it in energy.

Constants (`E_BASE`, `C_BASE`, exponents…) live in `config/settings.py` and are
tuned in the balance stage.

### Reproduction: crossover + mutation

Everyone is single-sex; any two ready adults of the same species can pair.

- **Uniform crossover**: each gene is taken from a random parent (50/50), then
  the child genome is mutated once. This preserves population variance better
  than blending.
- Both parents pay an energy share to the child; both increment their
  reproduction counter.

### Sexual selection

When an animal is ready to mate it scores every ready candidate within vision:

```
score = 0.6 · candidate_energy / candidate_max_energy   # honest condition signal
      + 0.4 · candidate_size_norm                       # preference for size
```

It approaches the best-scoring candidate (which must also accept — both must be
in the mate-seeking state). Fixed weights in v2 keep experiments
interpretable; evolvable preference is in the backlog.

---

## Lifecycle

```
birth ──(20% of lifespan)──► adult ──(fertility window)──► old age ──► death
JUVENILE                     ADULT
```

- **Lifespan**: species constant ± 10% individual variation (seeded RNG).
- **Juvenile** (first 20% of life): body grows from 0.4× to 1.0× of genetic
  size; cannot reproduce; reduced speed and `escape_power` (easy prey); worth
  less energy to a predator; **stays with family** — strong steering pull
  toward its parents.
- **Adult**: may reproduce inside a fertility window (20%–80% of life),
  at most **2 times per life**, with a cooldown of ~25% of lifespan after each
  child — so 1–2 offspring per life emerges naturally.
- **Death causes — exactly three**: starvation (energy ≤ 0), old age
  (age ≥ lifespan), predation (eaten). No disease, no accidents. Every death
  records its cause for analytics.

---

## Behaviour

Per-entity finite state machine; the current state is visible in the renderer
and the inspector.

### Herbivore

| State | Behaviour |
|---|---|
| `FORAGE` (default) | seek the best grass cell in vision (FOREST only), graze it; drift with the herd |
| `FLEE` | sprint away from a detected predator; ends when the predator is lost |
| `SEEK_MATE` / `COURT` | see Mating |
| `REST` | brief idle when well-fed and no threat; herbivores rest little |
| `FOLLOW_FAMILY` | juveniles shadow their parents |

### Predator

| State | Behaviour |
|---|---|
| `HUNT` | roam / stalk until prey detected, then chase |
| `REST` | long digestion after a kill — until energy drops below a hunger threshold (~50% of max); rest duration therefore emerges from metabolism |
| `SEEK_MATE` / `COURT` | see Mating |
| `FOLLOW_FAMILY` | juveniles shadow their parents |

### Detection — stealth vs vision

Both directions are asymmetric and gene-driven:

```
predator detects prey at range:  pred.vision · (1 − prey.eff_stealth)
prey detects predator at range:  prey.vision · (1 − pred.eff_stealth)
```

A stealthy predator gets closer before the prey bolts; stealthy prey is simply
not seen. Vigilance while grazing uses the same rule.

### The chase

1. Predator detects prey → `CHASE`; prey (if it detects the predator) →
   `FLEE`. Both sprint at `eff_speed · SPRINT_MULT` and pay `sprint_cost`.
2. Chase ends when: the predator closes to capture range (→ capture roll), the
   gap exceeds a give-up distance, or the predator's energy drops below a
   give-up floor (exhaustion).
3. **Capture roll** (prey's chance to break free):

   ```
   p_escape = clamp(BASE_ESCAPE
                    + a · (prey.eff_speed − pred.eff_speed)
                    + b · (prey.escape_power / pred.size − 0.5)
                    − juvenile_penalty,
                    0.05, 0.90)
   ```

   - **Escape**: prey loses a chunk of energy (wounded), gets a brief burst of
     panic speed; predator suffers a short re-capture cooldown.
   - **Kill**: prey dies (cause: predation); predator gains
     `KILL_GAIN · prey.size` energy (juveniles worth less) and enters `REST`.

### Groups and sociality

No explicit "herd" objects — groups **emerge** from steering forces:

- cohesion toward same-species neighbours within a social radius, weighted by
  the individual's `sociality` gene;
- separation at close range (no stacking);
- juveniles add a strong pull toward their parents; parents a mild pull toward
  their offspring.

Because `sociality` mutates, herding itself evolves: grouped prey spots
predators earlier (shared vigilance — a fleeing neighbour alerts the group),
but a dense herd strips grass faster and attracts hunts. Predators may evolve
loose packs or lone hunting depending on prey density.

---

## Visuals

### Window & map

- Full-screen (borderless desktop resolution) by default, resizable; the map is
  large and the camera fits the island on start. Pan/zoom as in v1.

### Procedural animal sprites

No external assets — sprites are drawn with pygame primitives into cached
surfaces, keyed by `(species, size bucket, facing, animation frame, stage)`:

- **Herbivore**: deer-like silhouette — body ellipse, head + ears, short tail,
  4-frame leg walk cycle.
- **Predator**: wolf-like — angular body, pointed muzzle and ears, bushy tail,
  same walk cycle.
- **Gene-driven look**: sprite scale from `size` × age growth curve; fur tint
  darkens/desaturates with `stealth` (camouflage you can see); juveniles are
  small with oversized heads.
- **State cues**: Zzz over resting animals, hearts during courtship, a brief
  flash when wounded, motion streaks while sprinting.
- **LOD**: below a zoom threshold sprites collapse to simple oval markers so a
  zoomed-out overview stays fast and readable.
- Every animal gets a generated **name** shown in the inspector and event log
  ("Bramble starved at age 2381"). Pure flavour, big empathy payoff.

### Terrain rendering

- Grass density shading per cell (green → yellow → bare), water depth tint,
  a light shoreline edge, decorative seeded tree sprites in the forest.

---

## Analytics

The reason the project exists. Two delivery channels:

### Live panel (in-game)

- Population chart per species (v1, kept).
- **Gene evolution chart**: mean ± std band per gene over time, per species.
- **Gene histograms**: current distribution snapshot per gene.
- Toggleable tabs; render-only, reads `Stats`.

### Data collection

- `Stats` v2: per-species time series — population, mean and std of every
  gene, grass coverage, hunt success rate — with adaptive downsampling so
  arbitrarily long runs fit in memory.
- **Event log**: births (with parents), deaths (with cause, age, location),
  hunts (success/escape), matings. Ring buffer for the UI + cumulative
  counters for the report.

### HTML report export

One key press → a **self-contained** HTML file (inline data + inline JS/SVG
charts, no CDN):

- run configuration and seed;
- population dynamics;
- per-gene evolution with mean ± std bands;
- gene distributions at run start / middle / now;
- hunt success rate over time;
- death-cause breakdown and lifespan distribution.

Plus raw **CSV/JSON export** of the time series and event log for custom
analysis in pandas.

### Experiments

- Named **presets** (JSON): world params + per-species starting gene means and
  counts. Setup screen gets a preset picker; three presets ship: stable
  meadow, predator pressure, scarce grass.

---

## Technology

| Purpose | Choice | Notes |
|---|---|---|
| Engine / rendering | `pygame-ce` | kept from v1 |
| UI widgets | `pygame_gui` | setup screen |
| Arrays / grass math | `numpy` | vectorised regrowth |
| Terrain noise | `opensimplex` | island / rivers / moisture |
| Tests | `pytest` | simulation stays headless-testable |
| Lint / CI | `ruff` + `pylint` (GitHub Actions) | kept |
| Env / build | `uv` + `hatchling` | kept |

Performance envelope: 1000 entities on a 320×200 grid at ≥ 50 FPS. Python
objects per entity are fine at this scale; the `SpatialGrid` and sprite/terrain
caching carry the load. Determinism: one `random.Random(seed)` owned by the
`Ecosystem`, passed to everything that rolls dice.

---

## Backlog (explicitly out of v2)

- Day/night cycle and seasons (grass multiplier, night stealth bonus).
- Thirst: drinking at `FRESH_WATER` (the map already distinguishes it).
- Evolvable mate preference (runaway sexual selection).
- Carcasses and scavenging; omnivores; more trophic levels.
- Lineage / family-tree visualisation; per-lineage analytics.
- Heatmaps: death locations, grazing pressure over time.
- Replay recording; camera follow-mode cinematics.
- Batch headless experiment runner (N seeds → aggregated report).
