# Compatibility Principles

Status: binding — these rules bind every goal and every PR.
Source of truth: Notion page "Compatibility Principles" (Specifications).
This file is the repo mirror for PR review; code that touches data, routing, or
the harness states which rules it honors, and the spec axis of code review
checks them.

Project principle: **compatibility over invention.** Real-world data,
industry-standard formats and algorithms, minimal re-code. Anything that exists
in the open-source ecosystem is adopted, not rebuilt.

## 1. Canonical data model: CF-compliant xarray

- The in-memory weather representation is a **CF-compliant xarray Dataset**
  (dimensions: time, latitude, longitude; variables: u10, v10, later Hs /
  currents / msl; time = hours since forecast initialization).
- Loaders produce it; routers and the harness consume it. On disk, scenario
  packages store it as **Zarr**.
- Adding a data source = writing a loader. Nothing downstream changes.
- The current `WeatherGrid` class is a transitional internal view; it must not
  appear in any public interface.

## 2. Router interface: the Router protocol

Routers implement a **Router protocol**:
`route(start, finish, start_time) -> Route`. The Level 1 oracle must be
replaceable by an external reference router without changing the harness.

- The **oracle is an industry reference router** (selection pending survey:
  OpenCPN WeatherRouting plugin and alternatives), run as a **pinned
  subprocess** — never linked into our code (GPL isolation; our code stays
  MIT).
- The oracle is a **batch label generator**: reference routes, evaluation
  scores, and training reward labels are computed offline, in parallel,
  cached. The oracle is never called inside a gradient loop.
- The in-repo isochrone implementation is **provisional**: a fast in-process
  surrogate for inner loops, validated against the oracle on the same
  scenarios. Replaceable, and labeled as such.

## 3. Environment interface: Gymnasium-compatible semantics (fixed now, adapter later)

First ML iterations are supervised (Goal 2 Level 3A: encoder-decoder over
scenario datasets) — no environment loop is needed. The **semantics and naming
are fixed now**: it costs nothing at this stage and gives battle-ready task
breakdown and naming conventions.

- **scenario** = one scenario package (forecast + reanalysis + config) = one
  environment **episode**
- **reset()** loads a scenario package; **step()** = one planning cycle:
  request data within budget -> receive degraded package -> route
- **observation** = degraded weather package + vessel state; **action** =
  data request (adaptive acquisition); **reward** = route quality vs the
  oracle reference
- The adapter is implemented when sequential-decision work starts
  (value-per-byte acquisition policy, Level 4). **Gymnasium** is the API
  standard. **OpenEnv** is re-evaluated only if/when HF-ecosystem RL
  post-training is adopted and the API has stabilized.

## 4. Real data for reported results

- Every published curve or report runs on **real archived forecasts**
  (as-issued; NOAA AWS S3 primary candidate — see Dataset Construction).
- Synthetic weather fields are **unit-test fixtures only**, never in reported
  results.
- Forecast-vs-reanalysis discipline per the Dataset Construction page (Modes
  A/B/C).

## 5. Industry polar format

- Polars load from industry-standard polar files (OpenCPN-compatible). The
  synthetic cruising polar is a test fixture, not a research input (Decision
  #12 direction: real polar).
