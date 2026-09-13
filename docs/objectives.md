# Objectives

Based on comprehensive literature review of meteorological information transfer and routing algorithms, the following **precise objectives** define what can be improved and the challenges to address.

---

## Core Research Question

> **How much weather information does a sailing router actually need?**

This is not "how much can we compress a GRIB file?" — it is "how much weather information is necessary to preserve the routing decision?" The loss function is routing performance degradation, not weather reconstruction error.

---

## Goal 1: Characterize the Bandwidth-Quality Degradation Curve

**Target:** Measure route quality as a function of daily data budget, from 1 KB/day to unlimited, and discover under what conditions 10 KB/day is sufficient and where performance collapses.

### What We Need to Build

A baseline system: GRIB parser, weather grid, boat polar, isochrone router. One route. No AI, no compression innovation. Just make it work.

Then progressively constrain the data budget:

```
1 MB → 500 KB → 250 KB → 100 KB → 50 KB → 25 KB → 10 KB → 5 KB → 2 KB → 1 KB
```

and measure:

- ETA error vs. full-information baseline
- Route distance difference
- VMG difference
- Maximum wind/wave exposure
- Time spent in unsafe conditions
- Route divergence (geographic distance between full-data and compressed-data trajectories)
- Decision divergence (did the compressed system choose the same tactical decision?)

### The Degradation Curve

The headline result is not "Light Router uses 10 KB/day." It is:

> **Light Router produces X% of full-information routing performance using Y bytes/day.**

| Daily Budget | Route Performance (hypothetical) |
|-------------:|--------------------------------:|
| 1 KB | 82% |
| 2 KB | 87% |
| 5 KB | 92% |
| 10 KB | 96% |
| 25 KB | 98% |
| Unlimited | 100% |

This curve is the project's most important research result. It gives a clear optimization objective:

```
maximize route quality
subject to B <= budget bytes/day
```

### Adaptive Bandwidth Allocation

Instead of a fixed 10 KB/day target, the deeper question is: what is the minimum bandwidth required for the current decision?

- Open ocean, steady trade winds: 5 KB may suffice
- Approaching a storm system: 15 KB needed
- Coastal navigation with complex currents: 50 KB needed
- Complex meteorological transition zone: 30 KB needed

The router should dynamically allocate its bandwidth budget based on the routing situation.

### What Can Be Improved

Based on current state of the art in [meteorological-info-transfer.md](./meteorological-info-transfer.md):

1. **Route-aware dynamic region filtering**
   - Current tools (Saildocs, NOMADS Grib Filter, PredictWind) already do region/variable/time filtering server-side
   - **Improvement:** Optimize the region selection dynamically based on route evolution, not just a static bounding box
   - Potential savings: 80-95% vs. full global (from 500 MB to 25-50 KB per update)
   - Note: Region filtering itself is not novel. Route-aware dynamic selection is the contribution.

2. **Delta encoding**
   - Current: Not used in sailing tools
   - **Improvement:** Transmit only forecast changes between updates
   - Potential savings: 70-90% for sequential forecasts
   - **Challenge:** Iridium SBD is a message-based protocol (up to 1960 bytes MO, 1890 bytes MT), not a session. Delta encoding requires both sides to maintain state about the previous forecast. If a message is lost, the delta is useless without the base. This needs an application-layer reliability mechanism. Feasibility is Medium, not High. See [meteorological-info-transfer.md](./meteorological-info-transfer.md).

3. **Variable filtering**
   - Download only essential variables for routing (wind, waves, pressure)
   - Potential savings: 50-80% reduction

4. **Temporal downsampling**
   - Lower resolution for distant forecasts (0-24h: 0.25 deg, 24-72h: 0.5 deg, 72h+: 1.0 deg)
   - Potential savings: 50-80% reduction

### Challenges

1. **Techniques interact.** The combined savings of region filtering, variable filtering, temporal downsampling, and delta encoding cannot be multiplied naively (80% x 80% x 80% does not automatically mean 99.2% reduction). An empirical curve is needed.
2. **Satellite constraints.** Iridium SBD: up to 1960 bytes per message, $0.50-5.00/MB. Message chunking and reassembly needed.
3. **Stateful connections.** Delta encoding requires maintaining state between updates. Difficult with satellite connections that may drop.
4. **Baseline matters.** The <10 KB/day target is a 10-50x improvement over the best existing filtered tools (Saildocs at 2-30 KB per manual request, PredictWind at ~150 KB/day automated), not a 1000x improvement over raw global downloads.

---

## Goal 2: Task-Oriented Weather Compression

**Target:** Learn a compressed weather representation that preserves routing decisions, not weather fidelity.

### The Key Insight

Traditional compression asks: "How accurately can I reconstruct the original data with N bytes?"

Task-oriented compression asks: "How accurately can I reproduce the sailing decision with N bytes?"

These are not the same thing. A 90% weather reconstruction may produce an identical route. A 98% weather reconstruction that slightly shifts a storm boundary may produce a completely different (and worse) route.

### Approach

#### Statistical compression (no ML)

Start with progressive grid aggregation. Instead of transmitting full grid cells, transmit summary statistics:

- mean / median / variance per coarser grid cell
- min / max / quantiles
- spatial gradients
- temporal derivatives

Then measure: at what aggregation level does the optimal sailing decision start changing?

This is already a valuable experiment. A grid region with uniform wind can be replaced by its mean. A region with a storm embedded in it cannot — mean alone would destroy the critical feature.

#### Learned compression (ML)

Train an encoder to produce a compact latent representation of the weather grid. The decoder reconstructs weather information for the routing solver.

**Critical design choice:** Do not train the encoder-decoder to minimize weather reconstruction error. Train it to minimize routing performance degradation.

```
FULL WEATHER GRID
       |
       v
  Neural Encoder
       |
       v
  latent vector (N bytes)
       |
       v
  transmit
       |
       v
  Neural Decoder
       |
       v
  reconstructed weather (for isochrone solver)
       |
       v
  ROUTE (compare to full-information reference route)
```

The loss function is:

```
L = alpha * weather_reconstruction_error + beta * routing_performance_degradation
```

where beta should dominate.

### Ground Truth

Use full-resolution weather + best available conventional router (isochrone with full GRIB) as the **full-information reference route**. Not "ground truth" — the forecast itself is uncertain and the polar is imperfect. This is an oracle under the chosen weather forecast, polar model, and routing algorithm.

Then separately validate against reality: forecast -> route -> actual observed sailing.

---

## Goal 3: Learned Vessel Performance

**Target:** Build an adaptive vessel-performance model that starts from the manufacturer polar and learns corrections from real-world observations.

### Why the Polar Matters

The polar diagram is the bridge between the weather model and the boat. Traditional weather routers (LuckGrib, SailGrib, qtVlm) all use polars: V = f(TWS, TWA). This is already standard.

The traditional polar is static. Reality is not. Actual boat speed depends on:

```
V = f(TWS, TWA, waves, current, heel, sail config, reefing,
      displacement, boat condition, crew behavior, tack/gybe, fatigue, ...)
```

### What Already Exists

- PredictWind has an "AI Polars" feature using stored polar + DataHub data
- Academic work: Random Forest models for polar generation, physics-guided ML (SPAM), ANN-based performance prediction
- University of Rostock AI Sailing project: tooling for generating polars from measurements

AI polars are not novel individually. The interesting combination is: learned vessel performance + task-oriented weather compression + bandwidth constraint.

### Approach

1. Start with manufacturer polar
2. Observe: GPS speed, wind speed/direction, heading, heel, sail configuration, wave conditions, current
3. Learn corrections: model predicts 7.3 kt at 14 kt TWS / 110 TWA, actual is 6.5 kt
4. After sufficient observations: personalized polar that routes this specific boat in its current state

### Where Transformers Could Help

Boat performance has temporal dependence. The boat's speed at time t may depend on the recent sequence (sail changes take time, waves have memory, boat acceleration has dynamics, crew doesn't instantly react).

A transformer can model that temporal context:

```
V_t = f(X_{t-n}, ..., X_{t-1}, X_t)
```

This is more interesting than replacing a lookup table with a neural network.

---

## Goal 4: Safety Under Forecast Uncertainty

**Target:** Minimize probability of exposure to predefined hazardous conditions under forecast uncertainty.

### v1 Safety Scope (included)

- Gale/storm identification (threshold-based + forecast-disagreement detection)
- Extreme wind exposure
- Extreme wave height
- Rapidly deteriorating conditions
- Forecast disagreement / uncertainty quantification

### Future Modules (deferred from v1)

- Rogue-wave prediction: historical observations are limited; a model with 95% accuracy can still be useless for rare catastrophic events. Defer until sufficient data exists.
- Iceberg detection: requires satellite imagery, which is architecturally incompatible with a 10 KB/day on-vessel budget. Could be handled by a shore-side service (heavy compute on shore, compact hazard alert downlinked to vessel). Defer until shore/vessel architecture is implemented.
- Microburst prediction: requires high-resolution wind data (>1 km), which is not available at the bandwidths targeted. Defer.

### Probabilistic Safety Metrics

Instead of undefined "99% safety," use measurable probabilistic definitions:

- P(Wind > 40 kt | forecast) — route around areas where this exceeds a threshold
- P(H_s > 6 m | forecast) — significant wave height exceedance probability
- P(rapid deterioration | forecast) — probability of conditions worsening faster than a defined rate

Route to minimize expected exposure to hazardous conditions, weighted by severity.

---

## Three-Level Experimental Design

Every goal above fits into a layered experimental design where each layer has a baseline:

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

### Level 3: Learned (with ML)

```
Compressed weather (neural encoder) + learned vessel model + isochrone router
```

Measure whether the learned system can recover performance that conventional compression loses.

The neural network serves the router, it does not replace it:

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
              ROUTE
```

This gives interpretability + deterministic routing + ML compression. Much safer than a black-box routing model.

---

## Success Metrics

### Bandwidth-Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Degradation curve | Characterized from 1 KB to unlimited | Route quality at each budget level |
| Daily data usage | <10 KB/day (target operating point) | Monitor all downloads |
| Route quality vs. full-information | Report multiple metrics separately | Compare compressed vs. full-data route |

### Route Quality Metrics (reported separately, not combined)

| Metric | Definition | Measurement |
|--------|-----------|-------------|
| ETA difference | (ETA_compressed - ETA_full) / ETA_full | Compare routes |
| Distance difference | (dist_compressed - dist_full) / dist_full | Compare routes |
| Max wind exposure | Difference in maximum wind encountered | Compare routes |
| Unsafe-hours exposure | Difference in time spent in unsafe conditions | Compare routes |
| Decision divergence | Did the compressed system choose the same tactical decision? | Compare route topology |
| Geographic route divergence | Distance between the two trajectories | Compare paths |

### Safety Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| P(Wind > threshold) | Probability of exceeding wind threshold given forecast | Minimize |
| P(H_s > threshold) | Probability of exceeding wave height threshold | Minimize |
| Forecast disagreement | Spread across ensemble members along route | Report |

### Computational Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Inference time | <1 minute | Wall-clock |
| Memory usage | <500 MB | RAM monitoring |
| Offline operation | Route with no cloud dependency after receiving weather data | Cold-start test |

---

## Implementation Roadmap

### Month 1: Baseline

Build: GRIB -> parser -> weather grid -> polar -> isochrone router, with one route. No AI, no compression innovation. Just make it work.

### Month 2: Bandwidth Simulator

Create: full weather -> compression/query layer -> 1 KB / 2 KB / 5 KB / 10 KB / 25 KB. Benchmark route degradation. This is where the research starts becoming real.

### Month 3: Adaptive Information Acquisition

Add: current route -> forecast uncertainty -> candidate weather requests -> value-per-byte scoring -> best request. This is the actual Light Router research contribution.

### Month 4+: Learned Compression and Vessel Models

Only after the baseline and degradation curve exist: train neural encoders for task-oriented compression, learn vessel-performance corrections, experiment with vessel-conditioned weather representation.

---

## References

- **Meteorological Info Transfer:** [./meteorological-info-transfer.md](./meteorological-info-transfer.md)
- **Routing Algorithms:** [./routing-algorithms.md](./routing-algorithms.md)
- **Research Ideas:** [./research-ideas.md](./research-ideas.md)
- **Benchmarking:** [./benchmarking.md](./benchmarking.md)
- **Current Tools Comparison:** [./literature-review.md](./literature-review.md)

---

(c) 2026 LowDataSailing
**Last Updated:** September 2026
**Version:** 2.0
