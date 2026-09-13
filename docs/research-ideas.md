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
- **Related work:** Task-oriented compression is an active ML concept (information bottleneck, task-aware lossy compression) but has not been applied to weather routing. Coordinate-based neural networks have achieved up to 790x compression for weather/climate data, but optimized for reconstruction, not decisions. See [Objectives](objectives.md), [Meteorological Info Transfer](meteorological-info-transfer.md).

### Vessel-conditioned weather representation

The value of a weather feature is conditional on the vessel. 12 kt at 90 TWA is fantastic for a catamaran and mediocre for a heavy cruiser. The weather representation should be conditioned on the boat's polar/performance characteristics.

- **Hypothesis:** A vessel-conditioned encoder can compress weather more aggressively than a vessel-agnostic one, because it can discard information that does not affect this particular boat's routing decisions.
- **Research question:** Can a transformer learn a compact latent representation of weather + vessel state that preserves the information necessary for routing? Does the optimal compression depend on the boat type?
- **Related:** [Routing Algorithms](routing-algorithms.md) (polar diagrams, isochrone method), [Objectives](objectives.md) (Goal 3: Learned Vessel Performance)

### Alternative: separate compression + isochrone routing (stepping stone)

The above approaches assume the isochrone router stays fixed and the ML layer only handles compression. This is a valid stepping stone: it's simpler, safer, and easier to debug. The encoder-decoder is trained to minimize routing degradation, but the router itself remains deterministic.

```
weather -> encoder -> latent -> transmit -> decoder -> reconstructed weather -> isochrone -> route
```

This architecture is the Level 3 baseline for the experimental design. It's worth building first because it isolates the compression contribution from the routing contribution. But the joint encoder-router architecture below is the more ambitious target.

---

## Joint Encoder-Router Architecture

### Learning to compress and route simultaneously

Instead of training an encoder-decoder for compression and keeping the isochrone router fixed, train the encoder and the router jointly end-to-end. The encoder learns what weather information to keep; the router learns to route from what was kept. They co-adapt.

```
weather + vessel state
       |
       v
   encoder (what to keep / how to compress)
       |
       v
   compact representation (N bytes)
       |
       v
   decoder-router (route directly from compact representation)
       |
       v
   ROUTE
```

Trained end-to-end on the abundant training data (historical weather + SOTA isochrone reference routes), with the loss being routing performance degradation. No intermediate weather reconstruction step.

**Why this is more interesting than separate compression + routing:**

- The encoder doesn't waste capacity preserving weather features the router doesn't need.
- The router doesn't have to reconstruct weather it will never see — it learns to operate directly in the compressed representation space.
- The two components co-adapt: as the router learns to extract signal from compressed data, the encoder learns to emphasize that signal.

**Why this is riskier:**

- The router becomes a black box. The "AI fails -> deterministic fallback" property is lost unless a safety layer is added (see Hybrid Architecture below).
- The model learns to imitate the isochrone router on degraded input. It doesn't learn to do *better* than the isochrone — it learns to approximate it. To beat the isochrone, you need training signal beyond SOTA router outputs (e.g., real skipper trajectories, a posteriori optimal routes).
- Failure modes are likely correlated with rare/dangerous conditions — exactly where training data is thinnest.

### Connection to JEPA

The Joint Embedding Predictive Architecture (JEPA, LeCun et al., 2023) predicts representations in embedding space rather than reconstructing raw data. Instead of:

```
weather -> encoder -> latent -> decoder -> reconstructed weather
```

JEPA-style prediction operates in the latent space:

```
context (what we know) -> context-encoder -> context embedding
target (what we want)  -> target-encoder  -> target embedding
predict: context embedding -> target embedding (in latent space, not pixel space)
```

Applied to weather routing, this maps naturally:

- **Context:** the compressed weather representation we can afford to transmit
- **Target:** the routing-relevant features of the full weather field (not the full field itself)
- **Prediction:** learn to predict the routing-relevant features from the compressed representation, in embedding space

The key JEPA insight: don't predict what can't be predicted (pixel-level weather details), predict only the abstract features that matter for the task. This is exactly "decision-preserving compression" formalized as a representation learning problem.

- **Hypothesis:** A JEPA-style architecture that predicts routing-relevant weather features in embedding space (not raw weather) will produce a more efficient compact representation than a reconstruction-based autoencoder, because it doesn't waste capacity on unpredictable or task-irrelevant details.
- **References:** I-JEPA (Assran et al., 2023): [https://arxiv.org/abs/2301.08243](https://arxiv.org/abs/2301.08243), V-JEPA (Bardes et al., 2024): [https://ai.meta.com/blog/v-jepa/](https://ai.meta.com/blog/v-jepa/)

### Connection to Information Bottleneck

The Information Bottleneck (IB) method (Tishby et al.) provides the theoretical framework: compress the input X (weather) into a representation T while maximizing the mutual information I(T; Y) between T and the target Y (route). Formally:

```
min I(X; T) - beta * I(T; Y)
```

where I(X; T) is the compression (minimize information kept) and I(T; Y) is the task relevance (maximize information about the route). The Variational Information Bottleneck (VIB) provides a practical approximation for deep learning.

This gives a principled objective for the encoder: transmit the minimum information about weather that preserves the maximum information about the route. The bandwidth budget B constrains I(X; T) directly.

- **References:** Information Bottleneck (Tishby & Zaks, 2015): [Wikipedia](https://en.wikipedia.org/wiki/Information_bottleneck_method), Variational IB (Alemi et al., 2017): [https://arxiv.org/abs/1612.00410](https://arxiv.org/abs/1612.00410)

### Connection to World Models

Ha & Schmidhuber (2018) showed that an agent can learn a compact world model (V: vision/encoder, M: memory/dynamics, C: controller/policy) and plan within that learned representation — "dreaming" in latent space. Applied to weather routing:

- **V (encoder):** weather -> compact latent representation
- **M (dynamics):** predict how the weather and boat state evolve over time in latent space
- **C (controller/router):** choose a route from the latent representation and predicted evolution

The route is planned in the compressed representation space, not by reconstructing the full weather field and then running a classical router. The model "dreams" the weather evolution from compressed data and routes within that dream.

- **Hypothesis:** A world-model architecture that plans routes in latent space (without reconstructing weather) can achieve better route quality at a given bandwidth budget than a reconstruct-then-route pipeline, because it avoids the information loss inherent in the reconstruction step.
- **References:** World Models (Ha & Schmidhuber, 2018): [https://arxiv.org/abs/1803.10122](https://arxiv.org/abs/1803.10122)

### Hybrid architecture: DL router + isochrone safety layer

The joint encoder-router replaces the isochrone as the primary routing engine, but the isochrone remains as a safety fallback:

```
DL router (from compressed weather) -> candidate route
    -> isochrone refinement (local optimization around candidate)
    -> safety check (probabilistic hazard exposure)
    -> final route
```

The DL router handles big-picture routing from degraded data (where it has an advantage over isochrone: it can learn to extract signal that classical methods miss). The isochrone does a quick local refinement and safety verification (where it has an advantage: deterministic, interpretable, auditable).

- If the DL router produces something reasonable, the isochrone polishes it.
- If the DL router fails badly, the isochrone catches it and produces a safe fallback.
- For tactical decisions (coastal approach, squall avoidance), the isochrone runs alone on local data.

This gives the DL ambition without the safety risk. The inference time budget supports this: the DL router can take 30+ minutes (planning), while the isochrone refinement is seconds (tactical).

### Inference time and energy

For offshore routing, inference time is not the binding constraint. A 30-60 minute inference is acceptable for a planning decision on timescales of hours to days. The binding constraint is energy:

- Raspberry Pi 4: 3-7W under load
- 30 min inference at 5W = 2.5 Wh
- Typical boat battery: 2400-4800 Wh
- Satellite modem per download: likely draws more than the router per computation

Energy should be a metric (Wh per route calculation), but it's likely not the bottleneck. The one exception: tactical decisions (approaching coast, squall avoidance) need fast inference. The hybrid architecture handles this — the isochrone fallback is fast.

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

The research directions form a layered system with two architectural paths:

```
Path A (stepping stone):
  Learned vessel model + task-oriented encoder + isochrone router
  (ML handles compression, router stays deterministic)

Path B (target):
  Joint encoder-router (JEPA / IB / world-model inspired)
  + isochrone safety layer
  (ML handles compression AND routing, isochrone is fallback)
```

Path A is simpler, safer, and isolates the compression contribution. Path B is more ambitious: the encoder and router co-adapt, potentially discovering routing strategies that classical methods miss on degraded input. Both share the same vessel model and adaptive acquisition layer.

The four-level experimental design (classical -> compressed -> learned compression -> joint encoder-router) provides baselines at each layer. See [Objectives](objectives.md).

The ground-truth strategy applies to all levels: the a posteriori ideal gives the upper bound, SOTA routers give the practical reference, and real skipper trajectories provide signal beyond what SOTA routers can teach (the key to beating, not just matching, the isochrone).

---

**© 2026 LowDataSailing**
