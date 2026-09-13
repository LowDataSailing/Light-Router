# Light Router

**A communication-constrained, vessel-conditioned weather-routing system that learns the minimum meteorological representation required to make near-optimal sailing decisions.**

---

## Objectives

1. **Low-bandwidth routing** — How much weather information does a sailing router actually need? Characterize the degradation curve: route quality as a function of daily data budget (from 1 KB to unlimited).
2. **Task-oriented compression** — Don't reconstruct weather accurately; reconstruct only enough to preserve the routing decision. The loss function is routing performance degradation, not weather reconstruction error.
3. **Learned vessel performance** — Start from manufacturer polars, learn corrections from real-world observations, and condition weather representation on vessel characteristics.

## Status

This repository currently contains **research and architectural documentation**. Source code, benchmarks, and configs will be added as the project develops. See the [documentation site](https://lowdatasailing.github.io/Light-Router/) for the full specification.

## Quick Start

```bash
git clone https://github.com/LowDataSailing/Light-Router.git
cd Light-Router
uv sync --group docs
make docs-serve
```

> Implementation is not yet available. The repository is at the specification and research stage.

---

## Structure

```
Light-Router/
├── docs/              # Research and architectural documentation
├── Makefile           # Task runner (uv-based)
└── pyproject.toml     # Dependencies and project config
```

## Documentation

Full documentation: [https://lowdatasailing.github.io/Light-Router/](https://lowdatasailing.github.io/Light-Router/)

Key documents:
- [Project Description](docs/PROJECT_DESCRIPTION.md)
- [Objectives](docs/objectives.md)
- [Research Ideas](docs/research-ideas.md)
- [Literature Review](docs/literature-review.md)
- [Weather Data Transfer](docs/meteorological-info-transfer.md)
- [Routing Algorithms](docs/routing-algorithms.md)
- [Benchmarking Methodology](docs/benchmarking.md)

## Architecture

The system is built around a **deterministic core** with an **optional intelligence layer**:

- **Core (100% deterministic):** weather ingestion, compression, cache, adaptive querying, isochrone routing, safety constraints. The vessel must be able to route with no cloud dependency after receiving weather data.
- **Intelligence (optional):** learned forecast-error correction, learned data-request policy, task-oriented weather compression, adaptive vessel-performance model. If the AI layer fails, the router still works.

## Potential Collaborations

- **Infoclimat** — Potential weather data provider (GRIB2, wave models)
- **Freewinds.world** — Potential simulation and testing platform
- **Open source community** — libweatherrouting, OpenCPN Weather Routing, SIMROUTE
- **Public data sources** — NOAA, ECMWF (open data since Oct 2025), Copernicus Marine Service

---

## **📜 License**

MIT © 2026 LowDataSailing
