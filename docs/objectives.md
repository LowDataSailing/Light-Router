# Objectives

## Core Research Question

> How much weather information does a sailing router actually need?

The loss function is routing performance degradation, not weather reconstruction error.

## Goal 1: Bandwidth-Quality Degradation Curve

Measure route quality as a function of daily data budget (1 KB to unlimited). Discover under what conditions 10 KB/day is sufficient and where performance collapses.

Build a baseline: GRIB parser, weather grid, boat polar, isochrone router, one route. No AI, no compression. Then progressively constrain the data budget:

```
1 MB -> 500 KB -> 250 KB -> 100 KB -> 50 KB -> 25 KB -> 10 KB -> 5 KB -> 2 KB -> 1 KB
```

Measure at each level:
- ETA error vs. full-information baseline
- Route distance difference
- VMG difference
- Maximum wind/wave exposure
- Time spent in unsafe conditions
- Route divergence (geographic distance between trajectories)
- Decision divergence (did the compressed system choose the same tactical decision?)

The headline result: "Light Router produces X% of full-information routing performance using Y bytes/day."

| Daily Budget | Route Performance (hypothetical) |
|-------------:|--------------------------------:|
| 1 KB | 82% |
| 2 KB | 87% |
| 5 KB | 92% |
| 10 KB | 96% |
| 25 KB | 98% |
| Unlimited | 100% |

Optimization objective: maximize route quality subject to B <= budget bytes/day.

### Adaptive Bandwidth Allocation

The minimum bandwidth depends on the routing situation:
- Open ocean, steady trade winds: ~5 KB
- Approaching a storm system: ~15 KB
- Coastal navigation with complex currents: ~50 KB
- Complex meteorological transition zone: ~30 KB

### Compression Techniques

Based on current state of the art in [meteorological-info-transfer.md](./meteorological-info-transfer.md):

1. Route-aware dynamic region filtering — Saildocs and NOMADS already do region/variable/time filtering. The contribution is dynamic selection based on route evolution, not static bounding boxes. Savings: 80-95% vs. full global.
2. Delta encoding — transmit only forecast changes. Savings: 70-90%. Challenge: Iridium SBD is message-based (up to 1960 bytes MO / 1890 bytes MT), not a session. Lost messages make deltas useless without the base. Requires application-layer reliability. Feasibility: Medium.
3. Variable filtering — download only essential variables (wind, waves, pressure). Savings: 50-80%.
4. Temporal downsampling — lower resolution for distant forecasts (0-24h: 0.25 deg, 24-72h: 0.5 deg, 72h+: 1.0 deg). Savings: 50-80%.

### Challenges

- Techniques interact — combined savings cannot be multiplied naively. An empirical curve is needed.
- Satellite constraints — Iridium SBD: up to 1960 bytes per message, $0.50-5.00/MB.
- Delta encoding requires stateful connections — difficult with satellite connections that may drop.
- Baseline matters — <10 KB/day is a 10-50x improvement over best existing filtered tools (Saildocs 2-30 KB/request, PredictWind ~150 KB/day), not a 1000x improvement over raw global downloads.

## Goal 2: Task-Oriented Weather Compression

Learn a compressed weather representation that preserves routing decisions, not weather fidelity.

Traditional compression asks: "How accurately can I reconstruct the original data with N bytes?"
Task-oriented compression asks: "How accurately can I reproduce the sailing decision with N bytes?"

A 90% weather reconstruction may produce an identical route. A 98% reconstruction that shifts a storm boundary may produce a completely different route.

### Statistical compression (no ML)

Progressive grid aggregation: transmit summary statistics (mean, median, variance, min/max, quantiles, spatial gradients, temporal derivatives) per coarser grid cell. Measure at what aggregation level the optimal sailing decision starts changing.

### Learned compression (Level 3)

Train a neural encoder-decoder. The encoder produces a compact latent representation; the decoder reconstructs weather for the isochrone solver. Train to minimize routing performance degradation, not weather reconstruction error.

```
weather -> encoder -> latent (N bytes) -> transmit -> decoder -> isochrone -> ROUTE
```

Loss: `L = alpha * reconstruction_error + beta * routing_degradation` (beta should dominate).

### Joint encoder-router (Level 4 — target)

Train the encoder and router jointly end-to-end. The router learns to operate directly in the compressed representation space. No intermediate weather reconstruction.

```
weather + vessel state -> encoder -> latent (N bytes) -> decoder-router -> candidate route
  -> isochrone refinement + safety check -> final ROUTE
```

The isochrone remains as a safety fallback. The DL router can take 30-60 minutes (planning); isochrone refinement is seconds (tactical). See [Research Ideas](research-ideas.md) for connections to JEPA, Information Bottleneck, and World Models.

### Ground Truth

Use full-resolution weather + isochrone router as the full-information reference route. Not "ground truth" — the forecast is uncertain and the polar is imperfect. This is an oracle under the chosen weather forecast, polar model, and routing algorithm. Validate separately against reality: forecast -> route -> actual observed sailing.

## Goal 3: Learned Vessel Performance

Build an adaptive vessel-performance model starting from the manufacturer polar, learning corrections from real-world observations.

The polar diagram is the bridge between weather and boat. Traditional routers (LuckGrib, SailGrib, qtVlm) all use polars: V = f(TWS, TWA). The traditional polar is static. Reality is not:

```
V = f(TWS, TWA, waves, current, heel, sail config, reefing,
      displacement, boat condition, crew behavior, tack/gybe, fatigue, ...)
```

What already exists: PredictWind "AI Polars" (commercial), University of Rostock [AI Sailing](https://www.mathematik.uni-rostock.de/en/ai-sail/) (academic), Random Forest models, physics-guided ML (SPAM). AI polars are not novel individually. The novel combination is: learned vessel performance + task-oriented weather compression + bandwidth constraint.

Approach: start with manufacturer polar, observe (GPS speed, wind, heading, heel, sail config, waves, current), learn corrections, build personalized polar.

Transformers could model temporal dependence in boat performance (sail changes take time, waves have memory, boat acceleration has dynamics): V_t = f(X_{t-n}, ..., X_{t-1}, X_t).

## Goal 4: Safety Under Forecast Uncertainty

Minimize probability of exposure to predefined hazardous conditions under forecast uncertainty.

v1 scope: gale/storm identification (threshold + forecast-disagreement), extreme wind/wave exposure, rapidly deteriorating conditions, forecast disagreement quantification.

Deferred: rogue-wave prediction (limited historical data), iceberg detection (requires satellite imagery — shore-side), microburst prediction (requires high-res wind data >1 km).

Probabilistic safety metrics:
- P(Wind > 40 kt | forecast) — route around areas exceeding a threshold
- P(H_s > 6 m | forecast) — significant wave height exceedance probability
- P(rapid deterioration | forecast) — probability of conditions worsening faster than a defined rate

## Four-Level Experimental Design

| Level | Weather | Vessel Model | Router | Purpose |
|-------|---------|-------------|--------|---------|
| 1. Classical | Full GRIB | Static polar | Isochrone | Full-information reference route (oracle) |
| 2. Compressed | Statistical aggregation | Static polar | Isochrone | Measure compression-only degradation |
| 3. Learned compression | Neural encoder-decoder | Learned polar | Isochrone | Measure whether ML compression recovers lost performance |
| 4. Joint encoder-router | Neural encoder | Learned polar | DL router + isochrone fallback | Measure whether joint training beats separate compression + routing |

Level 3 (stepping stone): ML serves the router, does not replace it. Safer, isolates compression contribution.

Level 4 (target): encoder and router co-adapt. Riskier (black-box router) but potentially more powerful. Isochrone safety layer mitigates risk.

## Success Metrics

### Bandwidth-Quality

| Metric | Target | Measurement |
|--------|--------|-------------|
| Degradation curve | Characterized from 1 KB to unlimited | Route quality at each budget level |
| Daily data usage | <10 KB/day (target operating point) | Monitor all downloads |

### Route Quality (reported separately)

| Metric | Definition | Measurement |
|--------|-----------|-------------|
| ETA difference | (ETA_compressed - ETA_full) / ETA_full | Compare routes |
| Distance difference | (dist_compressed - dist_full) / dist_full | Compare routes |
| Max wind exposure | Difference in maximum wind encountered | Compare routes |
| Unsafe-hours exposure | Difference in time in unsafe conditions | Compare routes |
| Decision divergence | Same tactical decision? | Compare route topology |
| Geographic route divergence | Distance between trajectories | Compare paths |

### Safety

| Metric | Definition | Target |
|--------|-----------|--------|
| P(Wind > threshold) | Exceedance probability given forecast | Minimize |
| P(H_s > threshold) | Wave height exceedance probability | Minimize |
| Forecast disagreement | Ensemble spread along route | Report |

### Computational

| Metric | Target | Measurement |
|--------|--------|-------------|
| Planning inference time | <60 min | Wall-clock |
| Tactical inference time | <1 min (isochrone fallback) | Wall-clock |
| Memory usage | <500 MB | RAM monitoring |
| Energy per route | Report (Wh) | Power draw x inference time |
| Offline operation | No cloud dependency after receiving weather data | Cold-start test |

## Implementation Roadmap

1. Month 1 — Baseline: GRIB -> parser -> weather grid -> polar -> isochrone router, one route. No AI.
2. Month 2 — Bandwidth simulator: compression/query layer at 1 KB / 2 KB / 5 KB / 10 KB / 25 KB. Benchmark route degradation.
3. Month 3 — Adaptive information acquisition: route -> forecast uncertainty -> candidate weather requests -> value-per-byte scoring -> best request.
4. Month 4 — Learned compression and vessel models (Level 3): neural encoders, vessel-performance corrections.
5. Month 5+ — Joint encoder-router (Level 4): end-to-end training, JEPA-style prediction, isochrone safety layer. Compare against Level 3.

## References

- [Meteorological Info Transfer](meteorological-info-transfer.md)
- [Routing Algorithms](routing-algorithms.md)
- [Research Ideas](research-ideas.md)
- [Benchmarking](benchmarking.md)
- [Literature Review](literature-review.md)
