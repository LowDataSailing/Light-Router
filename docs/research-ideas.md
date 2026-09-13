# Research Ideas

*Open research directions and hypotheses worth investigating. These are working notes, not commitments — each item needs validation before it becomes an objective.*

---

## **🧭 Model Specialization**

### Specializing models across geographic zones

Different ocean basins have distinct weather regimes (trade winds, doldrums, Southern Ocean depressions, high-latitude ice). A single global model may underperform in specific zones.

- **Hypothesis:** Zone-specialized models (e.g. Atlantic, Indian Ocean, Southern Ocean) outperform a single global model within their zone, at the cost of extra storage and the need for zone switching logic.
- **Open questions:** How to define zone boundaries? Is the gain large enough to justify per-zone models on a low-data, edge-deployed device? Can a single model with a geographic embedding match specialized models?
- **Related:** [Meteorological Information Transfer](meteorological-info-transfer.md), [Routing Algorithms](routing-algorithms.md)

### Specializing models on specific boats — or exposing it as a feature?

Boat performance is captured by the polar diagram, which varies widely across hulls (monohull vs. multihull, displacement vs. planing, cruiser vs. racer). The question is whether the routing model itself should be boat-specialized.

- **Hypothesis A (specialization):** Boat-specific models capture nuances the polar diagram misses (trim response, sea-state-dependent speed, helm behavior) and route better for that boat.
- **Hypothesis B (feature):** Boat behavior is fully described by the polar diagram + a small set of parameters, so a single model parameterized by the polar is sufficient and boat-specialization is unnecessary.
- **Compromise to test:** Treat the polar as a model input/feature rather than baking it into a specialized model — generalizes across boats without per-boat training, and per-boat tuning (if needed) becomes a feature the user supplies.
- **Open questions:** Is there residual boat-specific signal beyond the polar? How much per-boat data is needed for specialization to pay off? This decision affects data collection strategy.
- **Related:** [Routing Algorithms](routing-algorithms.md) (polar diagrams, isochrone method)

---

## **🎯 Ground Truth & Benchmarking Strategy**

Training and evaluating routing models requires a notion of the "correct" route. The candidates below are not mutually exclusive.

### Ground truth = SOTA routers on past data

Run state-of-the-art routers (PredictWind, StormGeo AWT, qtVlm, OpenCPN Weather Routing) on archived forecasts and use their outputs as reference labels.

- **Use:** Cheap, reproducible labels at scale; lets us benchmark our low-data model against full-data SOTA without depending on those services at inference time.
- **Risk:** We inherit the SOTA routers' biases and errors — labels are only as good as the reference router. Best used to measure *relative* route quality (route quality vs. full-information reference), not absolute optimality.
- **Related:** [Benchmarking](benchmarking.md), [Literature Review](literature-review.md)

### Ideal route algorithms with a posteriori data

Compute the truly optimal route using *actual* (a posteriori / hindcast) weather rather than forecast weather. This gives an upper bound on achievable performance and quantifies the gap due to forecast error alone.

- **Use:** Aspirational reference — measures how much routing loss comes from forecast uncertainty vs. from our algorithm/model. Useful to decompose error sources.
- **Risk:** "Ideal" assumes a perfect cost model (exact polars, no tactical/comfort tradeoffs), so it is a theoretical optimum, not necessarily a route a human would sail.
- **Related:** [Routing Algorithms](routing-algorithms.md), [Benchmarking](benchmarking.md)

### Real-world skippers' trajectories

Collect actual sailed tracks (race trackers, AIS, onboard logs) as demonstration data.

- **Use:** Direct human-expert signal — grounds the model in what experienced sailors actually do, including tactical and comfort decisions that cost models miss. Natural input for imitation learning.
- **Risk:** Real trajectories reflect constraints the model may not know (gear failures, strategy, crew fatigue, fuel for motor-sailing) and may be *suboptimal* — they are demonstrations, not optima. Best combined with the cost-based references above.
- **Related:** [Routing Algorithms](routing-algorithms.md) (imitation learning), [Benchmarking](benchmarking.md)

---

## **🔗 How these connect**

The three ground-truth sources form a layered evaluation framework:

1. **A posteriori ideal** — theoretical optimum, upper bound on performance.
2. **SOTA routers on past data** — practical reference for route quality comparison; reproducible at scale.
3. **Real skipper trajectories** — human-expert demonstration data; captures real-world constraints and objectives.

Reconciling the differences between these three is itself a research question: where skippers diverge from the a posteriori ideal, the gap may be either suboptimal play or legitimate objectives (safety, comfort) our cost model fails to capture.

Model specialization (geographic zones, specific boats) interacts with all three: specialized models need zone- or boat-specific training labels, which in turn shapes what ground-truth data must be collected per zone/boat.

---

## Task-Oriented Weather Compression

### Decision-preserving compression vs. reconstruction-preserving compression

Traditional compression minimizes reconstruction error. Task-oriented compression minimizes the degradation of a downstream task. Applied to weather routing: compress weather only enough to preserve the routing decision, not to reconstruct the weather field accurately.

- **Hypothesis:** A compressed weather representation with high reconstruction error can still produce near-optimal routes if it preserves the information the router actually uses (wind gradients, storm boundaries, thermal gradients). Conversely, a representation with low reconstruction error that slightly shifts a storm boundary can produce a completely different route.
- **Research question:** What is the minimum weather representation that preserves routing decisions? Which statistics (mean, variance, quantiles, gradients, extrema) are necessary, and which are redundant?
- **Approach:** Start with progressive grid aggregation (mean/median/variance per coarser cell). Measure at what aggregation level the optimal sailing decision starts changing. Then train a neural encoder-decoder where the loss function is `alpha * reconstruction_error + beta * routing_performance_degradation` (beta should dominate).
- **Related work:** Task-oriented compression is an active ML concept (information bottleneck, task-aware lossy compression) but has not been applied to weather routing. Coordinate-based neural networks have achieved up to 790x compression for weather/climate data, but optimized for reconstruction, not decisions. See [Objectives](objectives.md), [Meteorological Info Transfer](meteorological-info-transfer.md).

### Vessel-conditioned weather representation

The value of a weather feature is conditional on the vessel. 12 kt at 90 TWA is fantastic for a catamaran and mediocre for a heavy cruiser. The weather representation should be conditioned on the boat's polar/performance characteristics.

- **Hypothesis:** A vessel-conditioned encoder can compress weather more aggressively than a vessel-agnostic one, because it can discard information that does not affect this particular boat's routing decisions.
- **Research question:** Can a transformer learn a compact latent representation of weather + vessel state that preserves the information necessary for routing? Does the optimal compression depend on the boat type?
- **Related:** [Routing Algorithms](routing-algorithms.md) (polar diagrams, isochrone method), [Objectives](objectives.md) (Goal 3: Learned Vessel Performance)

---

## Learned Vessel Performance

### Adaptive polar from real-world observations

The traditional polar is static: V = f(TWS, TWA). Reality is richer: V = f(TWS, TWA, waves, current, heel, sail config, reefing, displacement, crew behavior, fatigue, ...).

- **Hypothesis:** A vessel-performance model that starts from the manufacturer polar and learns corrections from on-water observations will route significantly better than the static polar, especially for older or modified boats where the manufacturer polar is inaccurate.
- **What exists:** PredictWind "AI Polars" (commercial), University of Rostock AI Sailing (academic), Random Forest models, physics-guided ML (SPAM). AI polars are not novel individually.
- **Novel combination:** Learned vessel performance + task-oriented weather compression + bandwidth constraint. The learned polar conditions what weather information is valuable, which in turn conditions the compression.
- **Related:** [Routing Algorithms](routing-algorithms.md) (polar diagrams), [Objectives](objectives.md) (Goal 3)

### Temporal dependence in boat performance

Boat performance has temporal dynamics: sail changes take time, waves have memory, boat acceleration is not instantaneous, crew reaction is delayed. A transformer can model V_t = f(X_{t-n}, ..., X_{t-1}, X_t).

- **Hypothesis:** A temporal model of boat performance captures dynamics that a static polar misses, improving route predictions in changing conditions (gusts, wave trains, sail transitions).
- **Open question:** How much temporal context is needed? 10 minutes? 1 hour? Does this matter at the timescales of weather routing (hours to days)?
- **Related:** [Routing Algorithms](routing-algorithms.md)

---

## Adaptive Information Acquisition

### Value-per-byte data request policy

Given the current route, forecast uncertainty, previously downloaded data, and satellite budget, what weather data should be downloaded next?

- **Candidate requests:** A: 5x5 deg, 3-hourly, wind only. B: 10x5 deg, 6-hourly, wind + pressure. C: 5x10 deg, 1-hourly, wind + waves. D: storm corridor, high resolution.
- **Scoring:** For each candidate, estimate expected routing improvement / bytes. Download the highest-value request.
- **This is the core Light Router research contribution.** It is an information-theoretic control loop: spend bandwidth where it changes the decision.
- **ML formulation:** Train a model to estimate V(request) = delta_route_quality / bytes. Each training example: (current state, forecast, route, candidate request, actual improvement).
- **Related:** [Objectives](objectives.md) (Goal 1), [Benchmarking](benchmarking.md)

---

## How These Connect

The three research directions form a coherent system:

```
Learned vessel model (what does this boat need?)
       +
Task-oriented encoder (what weather matters for this boat?)
       +
Adaptive acquisition (what should we download next?)
       =
Light Router
```

The vessel model conditions the weather representation, which conditions the data acquisition policy. The three-level experimental design (classical -> compressed -> learned) provides baselines at each layer.

The ground-truth strategy from the earlier section applies to all three: the a posteriori ideal gives the upper bound, SOTA routers give the practical reference, and real skipper trajectories ground the model in real-world behavior.

---

**© 2026 LowDataSailing**
