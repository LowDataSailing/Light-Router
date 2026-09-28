# Goal 1 — Baseline System (Level 1) + Degradation Harness: Implementation Spec

Status: implemented (prototype) — see PR for review.
Source of truth: Notion workspace pages "Goal 1: Degradation Curve", "Baseline System
(Level 1)", "Benchmark Harness", "Test Scenarios", "Decisions Log" (#1, #2, #4, #9,
#15-#18), plus the cross-goal specs `compatibility-principles.md` and
`data-pipeline.md` in this directory.
This file is the working spec for this PR; the user-facing docs site is unchanged.

## Compatibility rules honored here

Per `compatibility-principles.md` (binding on every PR), this prototype honors:

- **Rule 1 (CF xarray canonical):** the in-memory weather representation is a
  CF-compliant xarray Dataset (dims time/latitude/longitude, variables
  u10/v10, time = hours since forecast initialization). Loaders
  (`grib.load_grib_wind`) produce it, the harness and routers consume it
  (`dataset.to_cf_dataset` / `grid_from_dataset`). `WeatherGrid` is the
  transitional internal numpy view used by the isochrone engine; it does not
  appear in any public interface.
- **Rule 2 (Router protocol):** routers implement the runtime-checkable
  `Router` protocol (`route(start, finish, start_time) -> Route`). The
  harness takes a router factory `Callable[[xr.Dataset], Router]`
  (`staircase.run_staircase`, `scenario.surrogate_router_factory`), so the
  oracle subprocess can replace the in-repo router without touching the
  harness. The in-repo isochrone is the *provisional surrogate* (Decision
  #15); it is labeled as such until validated against the industry oracle.
- **Rule 3 (Gymnasium semantics):** the experiment unit is the `Scenario`
  (weather + endpoints + staircase) = one episode; `reset` = scenario
  construction, `step` = one budget level, observation = the degraded
  package, reward = `RouteMetrics` vs the reference. No env loop yet (first
  iterations are supervised); the naming is fixed so the Gymnasium adapter
  is a thin wrapper.
- **Rule 4 (real data):** reported staircase results run on real GFS forecasts
  (`data/gfs.py`); the synthetic fields are unit-test fixtures and offline demo
  fallback only.
- **Rule 5 (polar format):** `PolarTable.from_polar_csv` /
  `to_polar_csv` read and write the OpenCPN-compatible polar CSV (first row =
  TWS, first column = TWA, cells = boat speed), so a real polar file can
  replace the synthetic fixture (Decision #12) without touching the router.

## Objective

Deliver the two Goal 1 prerequisites as runnable code:

1. **Baseline System (Level 1)** — a working isochrone router that computes the
   full-information reference route from a weather grid + boat polar. No ML, no
   compression. This is the oracle every degradation measurement is relative to.
2. **Benchmark Harness** — the framework that progressively constrains the data
   budget, re-routes on degraded weather, and measures route-quality degradation
   (budget staircase, degradation pipeline, metrics).

Research question: *How much weather information does a sailing router actually need?*

## Scope decisions (from the Decisions Log and the 2026-09-13 review)

- Language: Python (#9). Packaging: `src/light_router`, numpy core dependency.
- Polar: generic cruising boat, **synthetic placeholder** (#12 open: synthetic vs
  OpenCPN library). The polar is a table with bilinear interpolation so the source
  can be swapped without touching the router.
- Weather source: GFS 0.25 deg via NOMADS grib filter (secondary source per the
  Data Sources page). The InfoClimat/CHOM open portal provides observations, not
  forecasts (verified 2026-09-27), so it cannot serve as routing input; it is
  integrated as an observation client (buoys measuring waves/SST) for later
  Mode B ground-truth work.
- No land avoidance (decision #3 open; review recommends deferring).
- Single planning-time forecast per scenario (challenge #4 deferred): the whole
  degraded forecast package counts against the daily budget.
- First scenario: open-ocean trade wind, no land: Canary Islands -> Cape Verde
  (short enough to fit inside a 120 h GFS horizon at cruising speed). The
  Canaries -> Caribbean route from the Test Scenarios page needs a 15-25 day
  horizon and is out of prototype scope.

## Components

### 1. Weather grid (`weather.py`, `grib.py`, `synthetic.py`)

- `WeatherGrid`: the internal numpy view — time axis (hours since start),
  lat/lon axes, variables (`u10`, `v10`, optional `msl`...). Bilinear spatial
  + linear temporal interpolation, vectorized. Wind magnitude/direction
  helpers. Public interfaces speak the canonical CF Dataset
  (`dataset.py`: `to_cf_dataset` / `grid_from_dataset`); `WeatherGrid` is
  not exported.
- `grib.py`: load GRIB2 through cfgrib/xarray (optional dependency group
  `grib`; lazy import with a clear error message) and return the canonical
  CF Dataset.
- `synthetic.py`: deterministic synthetic trade-wind field for tests and offline
  demo fallback, plus `add_storm()` — a compact, time-pulsing storm overlay
  placed on the direct route. Smooth uniform fields degrade for free (they
  compress to a few KB at full fidelity), so the storm is what makes the
  bandwidth-quality curve measurable.

### 2. Boat polar (`polar.py`)

- `PolarTable`: speed = f(TWS, TWA), bilinear interpolation in (TWS, TWA),
  tack/gybe symmetry (mirror TWA), no-go zone handled by the table itself.
- `synthetic_cruising_polar()`: placeholder table shaped like a cruising
  monohull (documented as such).

### 3. Isochrone router (`isochrone.py`)

- Implements the `Router` protocol (`route(start, finish, start_time) ->
  Route`, runtime-checkable); `IsochroneRouter.from_dataset(weather, polar,
  config)` binds a CF Dataset. The provisional surrogate (Decision #15).

- Time-stepped isochrone expansion: from each reachable point at time t,
  candidate headings, polar speed at the local interpolated wind, move
  `v * dt` nautical miles, geographic-bin pruning (keep best progress toward
  the finish per bin), parent pointers, backtrack from the first point that
  reaches the finish radius.
- Output `Route`: waypoints (lat, lon, time, heading, speed, tws, twa), ETA,
  total distance, reached flag (partial route if the horizon is exhausted).
- No land avoidance, no currents (Level 1).

### 4. Degradation pipeline (`degrade.py`)

Applied in the order fixed by the Benchmark Harness page:

1. spatial downsampling (stride on lat/lon)
2. temporal downsampling (stride on time)
3. variable filtering (keep wind only)
4. quantization (uniform b-bit per variable)
5. lossless compression (zlib on the quantized payload — measured, not estimated)

`package_size()` returns the honest compressed byte size of the degraded
forecast package (header + zlib payload). The payload is the quantized code
array packed at b bits per value — not an upcast intermediate — so the bits
dimension genuinely moves the measured size. The header is decodable on its
own: a 4-byte length prefix, a JSON document (variable names, bit depth,
per-variable dequantization scales), then the strided time/lat/lon axes as
float64 — a receiver can reconstruct the grid from header + payload with no
out-of-band knowledge. `degrade()` and `package_size()` share one
quantization helper and cannot diverge.

### 5. Budget staircase + metrics (`staircase.py`, `metrics.py`, `scenario.py`)

- `run_staircase(weather: xr.Dataset, router_factory, start, finish,
  staircase, start_time)` — the harness speaks the CF Dataset and the
  Router protocol through a factory `Callable[[xr.Dataset], Router]`
  (defined once, next to the protocol, as `isochrone.RouterFactory`);
  `start_time` (hours since forecast initialization) is forwarded to the
  reference router and every budget-level router. `Scenario.run` wraps
  the harness as one episode (Gymnasium semantics, rule 3).

- Staircase: Unlimited -> 1 MB -> 500 KB -> 250 KB -> 100 KB -> 50 KB ->
  25 KB -> 10 KB -> 5 KB -> 2 KB -> 1 KB.
- For each budget: pick the highest-fidelity configuration (spatial stride,
  temporal stride, bits) whose package fits the budget, re-route, compare to
  the Level 1 reference route. "Highest-fidelity" is the lexicographic order
  (spatial, temporal, bits): spatial resolution first because routing
  decisions are local, then temporal, then bits.
- Metrics (reported separately, never combined): ETA difference, distance
  difference, VMG difference, max wind exposure difference, decision divergence
  (initial-bearing split), geographic divergence (mean distance from each
  point of the degraded track to the nearest point of the reference track).
- Output: CSV rows (`write_csv`) + console summary (`format_summary`).

### 6. Operational passage simulation (`simulate.py`, `data/era5.py`)

The staircase above answers "how much worse is the route computed from one
degraded forecast?" A real router at sea answers a different question: it
receives a new (degraded) forecast every cycle, replans from its current
position, and the boat sails on whatever the weather actually does. The
operational simulation mimics that, virtually, for a past passage — the
whole passage is one experiment (one episode):

- **Truth**: the boat advances on measured weather — ERA5 reanalysis via
  the Open-Meteo archive API (`data/era5.py`, no key; batched point
  requests reassembled into a grid, throttled + retried against the API's
  rate limits). The truth grid is on the absolute passage clock (hours
  since passage start).
- **Cycles**: every `cycle_hours` (aligned with GFS 00/06/12/18Z) the
  router receives the newest GFS run, degraded to the budget
  (`best_config_for_budget` -> `degrade`), and replans from its current
  position through the Router protocol (rule 2). If the budget is
  unreachable even fully degraded, the boat keeps the previous plan.
- **Advance**: each `dt_hours` step the boat follows the current plan at
  the speed the *true* wind allows (polar speed at the experienced
  TWA) — never the forecast wind.
- `run_operational_staircase` repeats the passage once per budget; the
  reward-relevant number is actual passage time vs the unlimited-data
  reference, plus total bytes received.
- Artifacts (opt-in, same `--artifacts` flag): the operational run
  directory adds `passage.csv` (one row per budget: actual outcome) and
  `cycles.csv` (one row per planning cycle: what was received and
  believed), writes the actual tracks as `track_<budget>.gpx/.geojson`,
  and plots the tracks on the measured-wind underlay plus the
  passage-time-vs-budget curve.
- **Data packs** (`data/pack.py`): `--export-pack DIR` writes the
  experiment's inputs (truth + cycles) as a self-contained,
  checksummed directory (compressed npz + `pack.json` manifest with
  sha256 per file); `--pack DIR` reruns the experiment with zero
  network access and no GRIB toolchain, verifying checksums on load.
  Packs and raw caches are heavy data: they stay on the fetch machine
  (gitignored, `data/packs/`, `data/cache/`), never in git; the
  manifest is mirrored off-site (Google Drive) as the provenance
  record.

### 7. Artifacts (opt-in)

Every staircase run can write a self-contained run directory for inspection and
comparison. **Opt-in via `--artifacts` (default off)** — plain runs stay fast
and CI-friendly.

Run directory layout: `runs/<scenario>/<timestamp>-<gitsha>/`

- `manifest.json` — config, code version (git SHA), data provenance and
  checksums (the "control" part of the run)
- `route_reference.gpx` + `route_<budget>.gpx` — GPX is the sailing-world
  standard (opens directly in OpenCPN); a GeoJSON twin is written for web
  viewers and QGIS
- `metrics.csv` — the staircase table (same rows as the console summary)
- Plots (matplotlib, optional dependency group `plot`):
  1. all tracks color-coded by budget on a wind-field underlay
  2. degradation curves per metric vs budget (log-x)
  3. package size vs fidelity
- `summarize` command re-renders all comparisons from an existing run
  directory without re-running the router

Same inputs produce the same artifact content (Decision #18).

**Run directories are never committed.** They are experiment output, not
source: they stay on the machine that produced them (gitignored,
`runs/`), like the heavy data (raw GRIB caches, data packs). To share a
run for review, publish the run directory (or its plots) outside git
and link it from the PR; the manifest and checksums inside the
directory remain the provenance record.

### 8. Data clients (`data/gfs.py`, `data/chom.py`)

- `gfs.py`: NOMADS grib-filter URL builder + downloader for U10/V10 subsets
  (recent runs only — NOMADS serves ~14 days).
- `gfs_archive.py`: historical GFS from the NOAA Open Data S3 bucket
  (`noaa-gfs-bdp-pds`) via wgrib2-index range requests — only the UGRD/VGRD
  10 m messages are fetched (~2 MB per forecast hour instead of ~1 GB).
  Required for any scenario older than ~14 days (rule 4).
- `chom.py`: minimal client for the open InfoClimat/CHOM climatology API
  (station search, station-parameter availability). No key required.
- `era5.py`: ERA5 reanalysis (the measured-weather truth) via the
  Open-Meteo archive API; feeds the operational simulation above.

## Tests

pytest, no network: geo math, interpolation, polar, isochrone on synthetic
fields (reaches finish, sane ETA), pipeline monotonicity + byte accounting,
staircase budget fitting, metrics identity, URL builders, CHOM client with
mocked HTTP, ERA5 wind conversion + rate-limit retry (mocked), simulation
loop on synthetic truth/forecasts (replan boundaries, budget caps,
truth-not-forecast), operational artifacts layout.

## Out of scope (explicitly)

Land avoidance, currents/waves in routing, Mode B (routing *on* reanalysis
forecasts — ERA5 is used as measured truth only), variable-value experiment
(Phase 3), multi-scenario suite (Phase 4), any ML.
