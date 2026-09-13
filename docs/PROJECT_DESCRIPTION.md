# Light Router — Project Description

## Overview

Light Router is a communication-constrained, vessel-conditioned weather-routing system that learns the minimum meteorological representation required to make near-optimal sailing decisions.

## Architecture

### Shore / Vessel Split

```
SHORE: weather models, satellite imagery, ensemble processing, heavy ML
  |
  | 2-10 KB/day
  v
VESSEL: compact forecast, local cache, routing engine, safety engine, boat polar
```

Heavy computation happens on shore. The vessel receives compact forecast data and routes autonomously.

### Vessel Architecture

Level 3 (stepping stone): ML handles compression, isochrone handles routing.

```
weather -> ML encoder -> compact forecast -> isochrone solver -> safety/uncertainty -> ROUTE
```

Level 4 (optional extension): ML handles compression AND routing jointly. Isochrone is safety fallback.

```
weather + vessel state -> encoder -> compact representation -> routing head -> candidate route
  -> isochrone refinement + safety check -> final ROUTE
```

The encoder and routing head are trained jointly end-to-end. The isochrone remains as a deterministic safety fallback. See [Research Ideas](research-ideas.md) for connections to JEPA, Information Bottleneck, and World Models. See [Objectives](objectives.md) for the experimental design.

### Adaptive Information Acquisition

```
Route -> What weather matters? -> Request only that information -> Update route -> What changed? -> Request only the information needed
```

Spend bandwidth where it changes the decision.

## Use Cases

Primary: solo/offshore sailor with unreliable or expensive satellite bandwidth. Also: circumnavigation, offshore racing.

Secondary: autonomous boats (same value-per-byte problem, different regulatory requirements), research vessels (intermittent connectivity).

## Validation Strategy

- Degradation curve: same route, same weather, progressively constrain data budget from 1 KB to unlimited
- Head-to-head: same conditions against PredictWind, SailGrib WR, qtVlm, OpenCPN Weather Routing
- Historical replay: archived race data
- Synthetic scenarios: Gulf Stream crossing, Southern Ocean storms, Cape Horn, Doldrums
- Monte Carlo: 1000+ simulations with forecast noise (10%, 20%, 30% error)

See [Benchmarking](benchmarking.md) for full methodology.

## Collaborations

Weather data: [NOAA NOMADS](https://nomads.ncep.noaa.gov), [ECMWF Open Data](https://data.ecmwf.int) (free since Oct 2025), [Copernicus Marine Service](https://marine.copernicus.eu), [Saildocs](http://www.saildocs.com), [Infoclimat](https://www.infoclimat.fr) (not yet contacted).

Simulation: [Freewinds.world](https://freewinds.world) (not yet contacted).

Open source: [libweatherrouting](https://github.com/dakk/libweatherrouting), [OpenCPN Weather Routing](https://opencpn.org/OpenCPN/plugins/weatherroute.html), [SIMROUTE](https://github.com/ManelGrifoll/SIMROUTE).

## Documentation

- [Objectives](objectives.md) — goals, experimental design, metrics, roadmap
- [Research Ideas](research-ideas.md) — hypotheses, JEPA/IB/World Models connections
- [Literature Review](literature-review.md) — competitor analysis
- [Meteorological Information Transfer](meteorological-info-transfer.md) — data sources, formats, protocols
- [Routing Algorithms](routing-algorithms.md) — algorithm survey and selection guide
- [Benchmarking](benchmarking.md) — test methodology
- [Market Positioning](market-positioning.md) — market analysis
