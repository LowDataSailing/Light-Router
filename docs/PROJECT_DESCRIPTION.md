# Light Router - Project Description

---

## Core Research Question

> **How much weather information does a sailing router actually need?**

Light Router is a communication-constrained, vessel-conditioned weather-routing system that learns the minimum meteorological representation required to make near-optimal sailing decisions. The loss function is routing performance degradation, not weather reconstruction error.

---

## Architecture

The system is built around a **deterministic core** with an **optional intelligence layer**. The vessel must be able to route with no cloud dependency after receiving weather data. If the AI layer fails, the router still works.

### Shore / Vessel Split

```
                 SHORE
        +----------------------+
        | Weather models       |
        | Satellite imagery    |
        | Ensemble processing  |
        | Heavy ML             |
        +----------+-----------+
                   |
             2-10 KB/day
                   |
                   v
        +----------------------+
        |       VESSEL         |
        |                      |
        | Compact forecast     |
        | Local cache          |
        | Routing engine       |
        | Safety engine        |
        | Boat polar           |
        +----------------------+
```

Heavy computation (ensemble processing, satellite image analysis, model training) happens on shore. The vessel receives only compact forecast data and routes autonomously.

### Vessel Architecture

Two paths, from stepping stone to target:

**Level 3 (stepping stone):** ML handles compression, isochrone handles routing.

```
              WEATHER
                 |
         +------+------+
         |             |
   Classical data   ML encoder
    processing         |
         |             |
         +------+------+
                v
         compact forecast
                |
                v
         ISOCHRONE SOLVER
                |
                v
         Safety / uncertainty
                |
                v
              ROUTE
```

**Level 4 (target):** ML handles compression AND routing jointly. Isochrone is safety fallback.

```
WEATHER + vessel state
       |
       v
   encoder (what to keep / how to compress)
       |
       v
   compact representation (N bytes)
       |
       v
   decoder-router (route from compressed representation)
       |
       v
   candidate route
       |
       v
   isochrone refinement + safety check
       |
       v
   final ROUTE
```

The encoder and router are trained jointly end-to-end. The router learns to operate directly in the compressed representation space. The isochrone remains as a deterministic safety fallback: it refines the DL candidate and catches failures. See [Research Ideas](research-ideas.md) for connections to JEPA, Information Bottleneck, and World Models.

### Feedback Loop

```
Route
  -> What weather matters?
  -> Request only that information
  -> Update route
  -> What changed?
  -> Request only the information needed
```

This is the adaptive information acquisition loop — the core research contribution.

---

## Four-Level Experimental Design

### Level 1: Classical (full information)

```
Full GRIB + static polar + isochrone router = full-information reference route
```

This is the oracle. All comparisons are relative to this.

### Level 2: Compressed (no ML)

```
Compressed GRIB (statistical aggregation) + static polar + isochrone router
```

Measure how much compression is possible without route degradation.

### Level 3: Learned compression (ML separate from router)

```
Compressed weather (neural encoder-decoder) + learned vessel model + isochrone router
```

The neural network serves the router (compression + vessel model). Stepping stone — safer, isolates the compression contribution.

### Level 4: Joint encoder-router (target)

```
Compressed weather (neural encoder) + learned vessel model
  -> decoder-router (routes from compressed representation)
  -> isochrone refinement + safety check
  -> final ROUTE
```

The encoder and router are trained jointly end-to-end. The router learns to operate in the compressed representation space. The isochrone is the safety fallback. See [Research Ideas](research-ideas.md).

---

## Objectives

### 1. Bandwidth-Quality Degradation Curve

Characterize route quality as a function of daily data budget (1 KB to unlimited). Discover under what conditions 10 KB/day is sufficient, and where performance collapses. The headline result is "X% of full-information routing performance using Y bytes/day," not just "10 KB/day."

The target is 10-50x reduction compared to best existing filtered tools (Saildocs at 2-30 KB/request, PredictWind at ~150 KB/day). Adaptive bandwidth allocation: open ocean may need 5 KB, approaching storms may need 15 KB, coastal navigation may need 50 KB.

### 2. Task-Oriented Weather Compression

Compress weather only enough to preserve the routing decision. Statistical compression (mean/median/variance per grid cell) first, then learned compression (neural encoder-decoder trained to minimize routing performance degradation, not weather reconstruction error). The target architecture goes further: train the encoder and router jointly end-to-end, so the router learns to operate directly in the compressed representation space (see [Research Ideas](research-ideas.md) for connections to JEPA, Information Bottleneck, and World Models).

### 3. Learned Vessel Performance

Start from manufacturer polar, learn corrections from real-world observations (GPS speed, wind, heading, sail config, waves, current). Build a personalized polar that routes this specific boat in its current state. Transformers may help model temporal dependence in boat performance.

### 4. Safety Under Forecast Uncertainty

Minimize probability of exposure to predefined hazardous conditions. v1 includes: gale/storm identification, extreme wind/wave exposure, rapidly deteriorating conditions, forecast disagreement detection. Rogue waves, icebergs, and microbursts are deferred to future modules (see [Objectives](objectives.md)).

---

## Metrics

| Category | Metric | Target |
|----------|--------|--------|
| Data | Daily consumption | <10 KB/day (target operating point) |
| Data | Degradation curve | Characterized from 1 KB to unlimited |
| Route | ETA difference vs. full-information | Report at each budget level |
| Route | Distance difference | Report at each budget level |
| Route | Decision divergence | Report at each budget level |
| Route | Geographic route divergence | Report at each budget level |
| Safety | P(Wind > threshold) | Minimize |
| Safety | P(H_s > threshold) | Minimize |
| Performance | Inference time | <1 minute |
| Performance | Memory usage | <500 MB |
| Performance | Offline operation | Route with no cloud dependency after receiving weather data |

---

## Use Cases

### Primary

- **Solo/offshore sailor** with unreliable or expensive satellite bandwidth — the core user story
- **Circumnavigation 2027** — real-world validation in extreme conditions
- **Offshore racing** — limited satellite bandwidth scenarios

### Secondary (shared core problem, divergent requirements)

- **Research vessels** — remote operations with intermittent connectivity
- **Autonomous boats** — fully automated navigation (same value-per-byte problem, different safety/regulatory requirements)

---

## Validation Strategy

### Platforms
1. **Freewinds.world** - Potential simulation and showcase platform (virtual sailing, route validation)
2. **OpenCPN** - Open source integration for community testing
3. **Custom Simulator** - Full control for edge cases

### Methodology
- **Degradation curve:** same route, same weather, progressively constrain data budget from 1 KB to unlimited
- **Head-to-Head:** same conditions against PredictWind, SailGrib WR, qtVlm, OpenCPN Weather Routing
- **Historical Replay:** use archived race data, compare against actual winners
- **Synthetic Scenarios:** Gulf Stream crossing, Southern Ocean storms, Cape Horn, Doldrums
- **Monte Carlo:** 1000+ simulations with forecast noise (10%, 20%, 30% error)

---

## Potential Collaborations

### Weather Data Sources
- **NOAA NOMADS:** Free GFS data with server-side Grib Filter subsetting
- **ECMWF Open Data:** Free 9 km IFS forecasts since October 2025
- **Copernicus Marine Service (CMEMS):** Wave and current data
- **Saildocs:** Email-based GRIB delivery for low-bandwidth scenarios
- **Infoclimat:** Potential primary data provider (not yet contacted)

### Simulation and Testing
- **Freewinds.world:** Potential simulation platform (not yet contacted)

### Open Source Community
- **libweatherrouting:** [https://github.com/dakk/libweatherrouting](https://github.com/dakk/libweatherrouting) — Python routing library
- **OpenCPN Weather Routing:** [https://opencpn.org/OpenCPN/plugins/weatherroute.html](https://opencpn.org/OpenCPN/plugins/weatherroute.html) — Open source isochrone routing
- **SIMROUTE:** [https://github.com/ManelGrifoll/SIMROUTE](https://github.com/ManelGrifoll/SIMROUTE) — A* routing with CMEMS data

---

## Roadmap

### Phase 1: Baseline (Month 1)
GRIB -> parser -> weather grid -> polar -> isochrone router. One route. No AI, no compression. Just make it work.

### Phase 2: Bandwidth Simulator (Month 2)
Full weather -> compression/query layer -> 1 KB / 2 KB / 5 KB / 10 KB / 25 KB. Benchmark route degradation.

### Phase 3: Adaptive Information Acquisition (Month 3)
Current route -> forecast uncertainty -> candidate weather requests -> value-per-byte scoring -> best request.

### Phase 4: Learned Compression and Vessel Models (Month 4+)
Neural encoders for task-oriented compression, learned vessel-performance corrections, vessel-conditioned weather representation. Only after the baseline and degradation curve exist.

---

## Additional Documentation
- [Objectives](objectives.md)
- [Research Ideas](research-ideas.md)
- [Literature Review](literature-review.md)
- [Meteorological Information Transfer](meteorological-info-transfer.md)
- [Routing Algorithms](routing-algorithms.md)
- [Benchmarking Methodology](benchmarking.md)
- [Market Positioning](market-positioning.md)

---

## Related Resources
- [NOAA NOMADS](https://nomads.ncep.noaa.gov) — Free weather data
- [ECMWF Open Data](https://data.ecmwf.int) — Free since October 2025
- [Copernicus Marine Service](https://marine.copernicus.eu) — Wave and current data
- [Saildocs](http://www.saildocs.com) — Email-based GRIB service
- [Infoclimat](https://www.infoclimat.fr) — Potential data provider
- [Freewinds.world](https://freewinds.world) — Potential simulation platform

---

(c) 2026 LowDataSailing
