# ADR-0001: npz data packs instead of Zarr for Goal 1 experiment inputs

- Status: accepted (2026-09-27)
- Scope: Goal 1 (operational passage simulation, `data/pack.py`)
- Supersedes: the Zarr layout sketched in `specs/data-pipeline.md`
  (`forecast.zarr` + `reanalysis.zarr` + `scenario.yaml`)

## Context

The operational passage simulation needs to store and replay an
experiment's inputs: one ERA5 truth grid plus up to ~30 GFS forecast
cycles (each a small time/lat/lon wind grid). `specs/data-pipeline.md`
proposed Zarr for this. Zarr is the right call for the large multi-
decade reanalysis store of later goals; for Goal 1 it would add a
dependency (zarr, and its storage backend choices) to a core install
that is otherwise numpy + xarray only, for a few tens of MB of data.

## Decision

Goal 1 experiment inputs are stored as **data packs**: plain
directories of zlib-compressed `.npz` files (one per grid) plus a
`pack.json` manifest with sha256 checksums per file, written and
verified by `light_router.weather_data.pack` (`--export-pack` / `--pack`).
Packs are self-contained: a rerun from a pack needs no network and no
GRIB toolchain, and checksum verification on load is the provenance
check.

## Consequences

- The core install stays numpy + xarray; no new dependency.
- Packs are opaque to tools that understand Zarr; they are an
  internal exchange format, not a data platform.
- When later goals need the large reanalysis store, Zarr is
  reconsidered there on its own merits (chunked access over decades
  of data); the pack format is not a precedent against it.
