# Data Pipeline

Status: reference — how data flows from raw archives to published curves.
Source of truth: Notion page "Data Pipeline" (Specifications). Companion to
the Dataset Construction page (the *why*) — this file is the *how*.

## Pipeline overview

```
NOAA AWS S3 (archived GFS GRIB2)   NOMADS (current runs)   CHOM/InfoClimat (observations)
        |                                  |                         |
        +------------------+---------------+-------------------------+
                           v
        [1] ACQUISITION        raw GRIB2 / JSON cached on disk
                           v
        [2] NORMALIZATION      cfgrib -> CF-compliant xarray Dataset
                           v
        [3] SCENARIO PACKAGING forecast.zarr + reanalysis.zarr + scenario.yaml
                           v
        [4] DEGRADATION        budget staircase -> degraded packages (byte-honest)
                           v
        [5] ROUTING            Router protocol: oracle subprocess (GPX) / in-process isochrone
                           v
        [6] EVALUATION         metrics vs reference route (Mode A/B/C)
                           v
        [7] ARTIFACTS          runs/<scenario>/<ts>-<sha>/: manifest, GPX/GeoJSON, metrics, plots
                           v
        [8] TRAINING (Goal 2)  PyTorch over scenario packages; oracle reward labels cached
                           v
        [9] ENV ADAPTER (later) Gymnasium env for adaptive acquisition / Level 4
```

## [1] Acquisition

- **Purpose:** obtain *as-issued* forecasts (what the router would really have
  received), plus observations for later ground-truth work.
- **Input/Output:** NOAA AWS S3 (archived GFS GRIB2, from ~2004, no auth) as
  primary; NOMADS grib filter for current runs; Open-Meteo single-runs API as
  quick JSON alternative; CHOM/InfoClimat for station observations
  (climatology, not forecasts — verified 2026-09-27).
- **Format:** GRIB2 on disk, cached under `data/cache/` (content-addressed by
  run date + region).
- **Techno:** boto3 / plain HTTPS, `light_router.data` loaders.
- **Idea:** reanalysis is *not* a forecast — the archive must be forecasts as
  originally issued (Dataset Construction).

## [2] Normalization

- **Purpose:** one canonical in-memory representation for every source.
- **Input:** GRIB2 (or JSON for Open-Meteo).
- **Output:** CF-compliant xarray Dataset (time, latitude, longitude; u10,
  v10; time = hours since init), subset to the route box.
- **Techno:** cfgrib + xarray (the industry chain).
- **Idea:** Compatibility rule 1 — new source = new loader, nothing downstream
  changes.

## [3] Scenario packaging

- **Purpose:** the reproducible unit of experimentation and training.
- **Output:** `scenario_package/` = `forecast.zarr` + `reanalysis.zarr`
  (Mode B) + `scenario.yaml` (start/finish, start time, polar file, router
  config, budget staircase).
- **Format:** Zarr (chunked N-D, the climate-ML standard) + YAML config.
- **Techno:** xarray + zarr.
- **Idea:** forecast vs reality separation; one package = one episode
  (Gymnasium semantics).

## [4] Degradation

- **Purpose:** constrain the package to a byte budget, honestly.
- **Pipeline (fixed order):** spatial stride -> temporal stride -> variable
  filter -> b-bit quantization -> zlib (measured bytes; codes packed at b
  bits).
- **Output:** degraded xarray view + measured package size; per budget, the
  highest-fidelity config that fits (lexicographic: spatial, temporal, bits).
- **Idea:** the loss function is routing degradation, not weather
  reconstruction — but the *measurement* must be byte-honest.

## [5] Routing

- **Purpose:** compute routes on full and degraded weather.
- **Interface:** Router protocol `route(start, finish, start_time) -> Route`.
- **Oracle:** industry reference router as a pinned subprocess (GPX/CSV
  in/out); our in-process isochrone is the provisional fast surrogate,
  validated against the oracle.
- **Format:** Route waypoints in-memory; **GPX** export (sailing-world
  standard, opens in OpenCPN).
- **Idea:** the oracle defines the reward — no hand-rolled-router bias in any
  measurement or training label.

## [6] Evaluation

- **Purpose:** measure degradation vs the reference route.
- **Output:** metrics (ETA, distance, VMG, max-wind exposure, decision
  divergence, geographic divergence) reported separately, never combined;
  Modes A/B/C.
- **Format:** `metrics.csv` / `metrics.json`.
- **Idea:** Mode A isolates compression; Mode B measures real quality; Mode C
  reveals where compression error exceeds forecast error.

## [7] Artifacts

- **Purpose:** control and inspect every run (see Benchmark Harness ->
  Artifacts).
- **Output:** `runs/<scenario>/<timestamp>-<gitsha>/`: `manifest.json`
  (config, code version, data provenance/checksums), `route_reference.gpx` +
  `route_<budget>.gpx` + GeoJSON, `metrics.csv`, plots (tracks on wind-field
  underlay, degradation curves log-x, package size vs fidelity).
- **Techno:** matplotlib (optional `plot` group), gpxpy; `summarize` command
  re-renders from a run directory.
- **Idea:** opt-in via `--artifacts`; same inputs -> same artifact content.

## [8] Training data (Goal 2, later)

- **Purpose:** Level 3A encoder-decoder training.
- **Input:** scenario packages (forecast -> outcome pairs).
- **Techno:** PyTorch DataLoader over Zarr; oracle-computed reward labels
  pre-generated and cached (batch label generation, never in the gradient
  loop).
- **Idea:** loss = reconstruction floor + routing degradation (beta
  dominates); JEPA / Information Bottleneck directions in Ideas.

## [9] Environment adapter (later)

- **Purpose:** sequential-decision work (value-per-byte acquisition policy,
  Level 4 joint training).
- **Techno:** Gymnasium env wrapping scenario packages;
  reset/step/observation/action/reward semantics already fixed
  (Compatibility rule 3).
- **Idea:** OpenEnv re-evaluated only when HF-ecosystem RL post-training is
  adopted and stabilized.
