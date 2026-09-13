# Light Router

A communication-constrained, vessel-conditioned weather-routing system that learns the minimum meteorological representation required to make near-optimal sailing decisions.

## Objectives

1. Characterize the degradation curve: route quality as a function of daily data budget (1 KB to unlimited).
2. Task-oriented compression: compress weather only enough to preserve the routing decision, not weather fidelity.
3. Learned vessel performance: start from manufacturer polars, learn corrections from real-world observations.

## Status

Research and architectural documentation only. Source code, benchmarks, and configs will be added as the project develops. See the [documentation site](https://lowdatasailing.github.io/Light-Router/) for the full specification.

## Quick Start

```bash
git clone https://github.com/LowDataSailing/Light-Router.git
cd Light-Router
uv sync --group docs
make docs-serve
```

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

Deterministic core (100%): weather ingestion, compression, cache, adaptive querying, isochrone routing, safety constraints. The vessel routes with no cloud dependency after receiving weather data.

Intelligence layer (optional): learned forecast-error correction, task-oriented weather compression, adaptive vessel-performance model, data-request policy. If the AI layer fails, the router still works. See [Research Ideas](docs/research-ideas.md) for the joint encoder-router target architecture.

## Potential Collaborations

- [Infoclimat](https://www.infoclimat.fr) — potential weather data provider (GRIB2, wave models)
- [Freewinds.world](https://freewinds.world) — potential simulation and testing platform
- Open source community: [libweatherrouting](https://github.com/dakk/libweatherrouting), [OpenCPN Weather Routing](https://opencpn.org/OpenCPN/plugins/weatherroute.html), [SIMROUTE](https://github.com/ManelGrifoll/SIMROUTE)
- Public data sources: [NOAA](https://nomads.ncep.noaa.gov), [ECMWF](https://data.ecmwf.int) (open data since Oct 2025), [Copernicus Marine Service](https://marine.copernicus.eu)

## License

MIT (c) 2026 LowDataSailing
