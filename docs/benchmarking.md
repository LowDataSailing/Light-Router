# Benchmarking Methodology

## Core Experiment: The Degradation Curve

The most important benchmark is the **bandwidth-quality degradation curve**: route quality as a function of daily data budget. Same route, same weather, progressively constrain the data budget from unlimited down to 1 KB/day.

### Data Budget Levels

```
Unlimited -> 1 MB -> 500 KB -> 250 KB -> 100 KB -> 50 KB -> 25 KB -> 10 KB -> 5 KB -> 2 KB -> 1 KB
```

### Metrics at Each Level

Report separately (do not combine into a single "route quality" number):

- **ETA difference:** (ETA_compressed - ETA_full) / ETA_full
- **Distance difference:** (dist_compressed - dist_full) / dist_full
- **Max wind exposure:** difference in maximum wind encountered
- **Max wave exposure:** difference in maximum wave height encountered
- **Unsafe-hours exposure:** difference in time spent in unsafe conditions
- **Decision divergence:** did the compressed system choose the same tactical decision? (e.g., go north vs. go south)
- **Geographic route divergence:** distance between the two trajectories

### Four-Level Experimental Design

| Level | Weather | Vessel Model | Router | Purpose |
|-------|---------|-------------|-------|---------|
| 1. Classical | Full GRIB | Static polar | Isochrone | Full-information reference route (oracle) |
| 2. Compressed | Statistical aggregation | Static polar | Isochrone | Measure compression-only degradation |
| 3. Learned compression | Neural encoder-decoder | Learned polar | Isochrone | Measure whether ML compression recovers lost performance |
| 4. Joint encoder-router | Neural encoder | Learned polar | DL router + isochrone fallback | Measure whether joint training beats separate compression + routing |

All comparisons are relative to Level 1 (the full-information reference route, not "ground truth"). Level 4 is the target architecture — the DL router handles big-picture routing from compressed data, the isochrone refines and provides a safety fallback.

## Dimensions

### 1. Data Efficiency
Measure bytes downloaded per day and per update.

### 2. Route Quality
Compare route time, distance, safety, and decision divergence against the full-information reference route (Level 1).

### 3. Safety Under Uncertainty
Validate probabilistic safety metrics: P(Wind > threshold | forecast), P(H_s > threshold | forecast), forecast disagreement across ensemble members along the route.

### 4. Computational Efficiency
Test on Raspberry Pi: inference time, memory usage, battery impact, offline operation (cold start with no cloud dependency).

## Test Methods

### Data Efficiency
- Controlled comparison: same route, same weather data
- Satellite simulation: throttle to Iridium SBD (up to 1960 bytes/message), Iridium GO! (~150 KB/day typical), and Starlink (170-300 Mbps)
- HF radio simulation: throttle to Winlink/Sailmail PACTOR speeds (100-2400 bits/s)
- Saildocs comparison: compare automated route-aware requests vs. manual Saildocs requests (standardized: same forecast horizon + same variables + same spatial corridor + same update frequency)
- Offline performance: cache 7 days of forecasts, measure degradation

### Route Quality
- Head-to-head: same conditions against PredictWind, SailGrib WR, qtVlm, OpenCPN Weather Routing
- Historical replay: use archived race data, compare against actual winners
- Synthetic scenarios: Gulf Stream crossing, Southern Ocean storms, Cape Horn, Doldrums
- Monte Carlo: 1000+ simulations with forecast noise (10%, 20%, 30% error)
- Low-data comparison: compare route quality when data is limited to <10 KB/day vs. full data

### Safety
- Storm detection: historical storm tracks (NOAA, ECMWF)
- Probabilistic exposure: P(Wind > 40kt | forecast) along route, P(H_s > 6m | forecast)
- Forecast disagreement: ensemble spread along candidate routes

### Computational Efficiency
- Hardware tests: Raspberry Pi 4/5, Jetson Nano
- Algorithm complexity: scale with waypoints, forecast length, resolution
- Energy: measure Wh per route calculation (power draw x inference time)
- Inference time: planning (<60 min acceptable) vs. tactical (<1 min, isochrone fallback)
- Offline test: cold start, no cloud dependency, route from cached data only
