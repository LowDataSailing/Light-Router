# Goal 1 — Baseline System (Level 1) + Degradation Harness: Implementation Spec

Status: implemented (prototype) — see PR for review.
Source of truth: Notion workspace pages "Goal 1: Degradation Curve", "Baseline System
(Level 1)", "Benchmark Harness", "Test Scenarios", "Decisions Log" (#1, #2, #4, #9).
This file is the working spec for this PR; the user-facing docs site is unchanged.

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

- `WeatherGrid`: time axis (hours since start), lat/lon axes, variables
  (`u10`, `v10`, optional `msl`...). Bilinear spatial + linear temporal
  interpolation, vectorized. Wind magnitude/direction helpers.
- `grib.py`: load GRIB2 through cfgrib/xarray (optional dependency group
  `grib`; lazy import with a clear error message).
- `synthetic.py`: deterministic synthetic trade-wind field for tests and offline
  demo fallback.

### 2. Boat polar (`polar.py`)

- `PolarTable`: speed = f(TWS, TWA), bilinear interpolation in (TWS, TWA),
  tack/gybe symmetry (mirror TWA), no-go zone handled by the table itself.
- `synthetic_cruising_polar()`: placeholder table shaped like a cruising
  monohull (documented as such).

### 3. Isochrone router (`isochrone.py`)

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
forecast package (header + zlib payload).

### 5. Budget staircase + metrics (`staircase.py`, `metrics.py`)

- Staircase: Unlimited -> 1 MB -> 500 KB -> 250 KB -> 100 KB -> 50 KB ->
  25 KB -> 10 KB -> 5 KB -> 2 KB -> 1 KB.
- For each budget: pick the highest-fidelity configuration (spatial stride,
  temporal stride, bits) whose package fits the budget, re-route, compare to
  the Level 1 reference route.
- Metrics (reported separately, never combined): ETA difference, distance
  difference, VMG difference, max wind exposure difference, decision divergence
  (initial-bearing split), geographic divergence (mean nearest-track distance).
- Output: CSV rows + console summary.

### 6. Data clients (`data/gfs.py`, `data/chom.py`)

- `gfs.py`: NOMADS grib-filter URL builder + downloader for U10/V10 subsets.
- `chom.py`: minimal client for the open InfoClimat/CHOM climatology API
  (station search, station-parameter availability). No key required.

## Tests

pytest, no network: geo math, interpolation, polar, isochrone on synthetic
fields (reaches finish, sane ETA), pipeline monotonicity + byte accounting,
staircase budget fitting, metrics identity, URL builders, CHOM client with
mocked HTTP.

## Out of scope (explicitly)

Land avoidance, currents/waves in routing, Mode B (reanalysis) evaluation,
variable-value experiment (Phase 3), multi-scenario suite (Phase 4), any ML.
