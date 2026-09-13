# Light Router

A communication-constrained, vessel-conditioned weather-routing system that learns the minimum meteorological representation required to make near-optimal sailing decisions.

## Research Question

> How much weather information does a sailing router actually need?

The loss function is routing performance degradation, not weather reconstruction error. See [Objectives](objectives.md) for the full specification.

## Architecture

Deterministic core (100%): weather ingestion, compression, cache, adaptive querying, isochrone routing, safety constraints. The vessel routes with no cloud dependency after receiving weather data.

Intelligence layer (optional): task-oriented weather compression, adaptive vessel-performance model, data-request policy. If the AI layer fails, the router still works. See [Research Ideas](research-ideas.md) for the joint encoder-router target architecture.

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

## Quick Start

```bash
git clone https://github.com/LowDataSailing/Light-Router.git
cd Light-Router
uv sync --group docs
make docs-serve
```

Research and specification stage. No source code yet.

## License

MIT License - [LICENSE](LICENSE)

## Links

- [GitHub](https://github.com/LowDataSailing/Light-Router)
- [Organization](https://github.com/LowDataSailing)
