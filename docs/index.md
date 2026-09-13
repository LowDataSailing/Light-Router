# Light Router

A communication-constrained, vessel-conditioned weather-routing system that learns the minimum meteorological representation required to make near-optimal sailing decisions.

## Research Question

> **How much weather information does a sailing router actually need?**

Light Router approaches weather routing as a bandwidth-constrained information problem. Instead of asking "how much can we compress a GRIB file?", we ask "how much weather information is necessary to preserve the routing decision?" The loss function is routing performance degradation, not weather reconstruction error.

## Objectives

1. **Characterize the degradation curve** — Measure route quality as a function of daily data budget (1 KB to unlimited). Discover under what conditions 10 KB is sufficient, and where performance collapses.
2. **Task-oriented compression** — Compress weather only enough to preserve the sailing decision. A 90% weather reconstruction may be acceptable if it produces the same route; a 98% reconstruction that shifts a storm boundary and changes the route is not.
3. **Learned vessel performance** — Start from manufacturer polars, learn corrections from real-world observations, and condition weather representation on vessel characteristics. The value of a weather feature is conditional on the boat.

## Architecture

**Deterministic core** (100%): weather ingestion, compression, cache, adaptive querying, isochrone routing, safety constraints. The vessel must be able to route with no cloud dependency after receiving weather data.

**Intelligence layer** (optional): learned forecast-error correction, task-oriented weather compression, adaptive vessel-performance model, data-request policy. If the AI layer fails, the router still works.

## Documentation

- [Project Description](PROJECT_DESCRIPTION.md)
- [Objectives](objectives.md)
- [Research Ideas](research-ideas.md)
- [Literature Review](literature-review.md)
- [Meteorological Information Transfer](meteorological-info-transfer.md)
- [Routing Algorithms](routing-algorithms.md)
- [Benchmarking](benchmarking.md)
- [Market Positioning](market-positioning.md)
- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

## Quick Start

```bash
git clone https://github.com/LowDataSailing/Light-Router.git
cd Light-Router
uv sync --group docs
make docs-serve
```

> Implementation is not yet available. This repository is at the specification and research stage.

## License

MIT License - [LICENSE](LICENSE)

## Links

- [GitHub](https://github.com/LowDataSailing/Light-Router)
- [Organization](https://github.com/LowDataSailing)
