# Benchmarking Methodology

## Core Experiment: The Degradation Curve

Route quality as a function of daily data budget. Same route, same weather, progressively constrain from unlimited down to 1 KB/day.

Data budget levels:

```
Unlimited -> 1 MB -> 500 KB -> 250 KB -> 100 KB -> 50 KB -> 25 KB -> 10 KB -> 5 KB -> 2 KB -> 1 KB
```

Metrics at each level (report separately, do not combine):
- ETA difference: (ETA_compressed - ETA_full) / ETA_full
- Distance difference: (dist_compressed - dist_full) / dist_full
- Max wind exposure: difference in maximum wind encountered
- Max wave exposure: difference in maximum wave height encountered
- Unsafe-hours exposure: difference in time in unsafe conditions
- Decision divergence: did the compressed system choose the same tactical decision?
- Geographic route divergence: distance between the two trajectories

The four-level experimental design (classical, compressed, learned compression, joint encoder-router) is defined in [Objectives](objectives.md). All comparisons are relative to Level 1 (full-information reference route).

## Test Methods

### Data Efficiency
- Controlled comparison: same route, same weather data
- Satellite simulation: throttle to Iridium SBD (up to 1960 bytes/message), Iridium GO! (~150 KB/day), Starlink (170-300 Mbps)
- HF radio simulation: throttle to Winlink/Sailmail PACTOR speeds (100-2400 bits/s)
- Saildocs comparison: automated route-aware requests vs. manual Saildocs (standardized: same forecast horizon, variables, spatial corridor, update frequency)
- Offline: cache 7 days of forecasts, measure degradation

### Route Quality
- Head-to-head: same conditions against PredictWind, SailGrib WR, qtVlm, OpenCPN Weather Routing
- Historical replay: archived race data, compare against actual winners
- Synthetic scenarios: Gulf Stream crossing, Southern Ocean storms, Cape Horn, Doldrums
- Monte Carlo: 1000+ simulations with forecast noise (10%, 20%, 30% error)

### Safety
- Storm detection: historical storm tracks (NOAA, ECMWF)
- Probabilistic exposure: P(Wind > 40kt | forecast) along route, P(H_s > 6m | forecast)
- Forecast disagreement: ensemble spread along candidate routes

### Computational Efficiency
- Hardware: Raspberry Pi 4/5, Jetson Nano
- Energy: Wh per route calculation (power draw x inference time)
- Inference time: planning (<60 min) vs. tactical (<1 min, isochrone fallback)
- Offline: cold start, no cloud dependency, route from cached data only
