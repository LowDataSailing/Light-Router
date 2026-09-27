# Benchmarking Methodology

## Core Experiment: The Degradation Curve

Route quality as a function of daily data budget. Same route, same weather, progressively constrain from unlimited down to 1 KB/day.

Data budget levels:

```
Unlimited -> 1 MB -> 500 KB -> 250 KB -> 100 KB -> 50 KB -> 25 KB -> 10 KB -> 5 KB -> 2 KB -> 1 KB
```

### Degradation Pipeline

```
Full GRIB -> Budget Constraint -> Degraded Weather -> Isochrone Router -> Degraded Route
```

Methods, applied in order:

1. Spatial downsampling — coarsen the lat/lon grid
2. Temporal downsampling — reduce forecast time steps
3. Variable filtering — drop non-essential variables
4. Quantization — reduce precision of remaining values
5. Lossless compression — entropy coding of the result

The pipeline estimates byte size after each step and stops when the budget is met.

Metrics at each level (report separately, do not combine):
- ETA difference: (ETA_compressed - ETA_full) / ETA_full
- Distance difference: (dist_compressed - dist_full) / dist_full
- VMG difference: difference in velocity-made-good
- Max wind exposure: difference in maximum wind encountered
- Max wave exposure: difference in maximum wave height encountered
- Unsafe-hours exposure: difference in time in unsafe conditions
- Decision divergence: did the compressed system choose the same tactical decision?
- Decision boundary: at what budget does the routing decision flip? (e.g., go north at 10 KB, go south at 2 KB)
- Geographic route divergence: distance between the two trajectories

### Variable-Value Experiment

Remove weather variables one at a time (wind, waves, current, pressure) and measure route quality impact. This produces a per-variable value ranking that feeds adaptive variable selection. Example result: wind = 85% of information value for open ocean, current = 45% near the Gulf Stream.

The experimental design (Levels 1, 2, 3A, 3B, 3C, 4) is defined in [Objectives](objectives.md). All comparisons are relative to Level 1 (full-information reference route).

### Evaluation Modes

- Mode A (forecast-consistent): route on the degraded forecast, evaluate on the same forecast — isolates the compression effect
- Mode B (reality-consistent): route on the degraded forecast, evaluate on reanalysis — measures real routing quality but conflates compression with forecast error
- Mode C (dual-reporting): report both — the difference reveals where compression error exceeds forecast error

Start with Mode A; add Mode B once archived forecasts and reanalysis are integrated.

## Test Scenarios

Initial benchmark routes:

| Scenario | Route | Key challenge |
|----------|-------|---------------|
| Open ocean trade-wind | Canary Islands -> Caribbean | Steady trade winds, long distance, minimal decision points |
| Storm avoidance | Azores -> UK | North Atlantic low-pressure system — route around a storm, decision-critical |
| Brittany -> Canaries | Brittany -> Canary Islands | Coastal departure + Atlantic crossing, mixed conditions |

Future candidates: Gulf Stream crossing (Florida -> Bermuda, current + wind interaction), Doldrums crossing (Canaries -> Caribbean via the ITCZ, wind holes), English Channel crossing (tidal currents, land avoidance), Southern Ocean (Cape Town -> Sydney, strong westerlies, big waves).

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
