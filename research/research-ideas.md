# Research Ideas

Open research directions and hypotheses. These are working notes, not commitments — each item needs validation before it becomes an objective.

## Model Specialization

### Geographic zone specialization

Different ocean basins have distinct weather regimes (trade winds, doldrums, Southern Ocean depressions, high-latitude ice). A single global model may underperform in specific zones.

- Hypothesis: zone-specialized models outperform a single global model within their zone, at the cost of extra storage and zone switching logic.
- Open questions: how to define zone boundaries? Is the gain large enough to justify per-zone models on an edge device? Can a single model with a geographic embedding match specialized models?
- Related: [Meteorological Information Transfer](meteorological-info-transfer.md), [Routing Algorithms](routing-algorithms.md)

### Boat specialization vs. feature

Boat performance is captured by the polar diagram, which varies across hulls (monohull vs. multihull, displacement vs. planing, cruiser vs. racer). Should the routing model itself be boat-specialized?

- Hypothesis A (specialization): boat-specific models capture nuances the polar misses (trim response, sea-state-dependent speed, helm behavior).
- Hypothesis B (feature): boat behavior is fully described by the polar + a small set of parameters, so a single model parameterized by the polar is sufficient.
- Compromise to test: treat the polar as a model input/feature rather than baking it into a specialized model.
- Related: [Routing Algorithms](routing-algorithms.md) (polar diagrams, isochrone method)

## Ground Truth Strategy

Training and evaluating routing models requires a notion of the "correct" route. Three sources, not mutually exclusive:

1. SOTA routers on past data — run PredictWind, StormGeo AWT, qtVlm, OpenCPN Weather Routing on archived forecasts. Cheap, reproducible labels at scale. Risk: inherit SOTA routers' biases. Best for relative route quality, not absolute optimality.
2. A posteriori ideal route — compute the optimal route using actual (hindcast) weather. Upper bound on performance. Risk: assumes perfect cost model (exact polars, no tactical/comfort tradeoffs).
3. Real skipper trajectories — collect actual sailed tracks (race trackers, AIS, onboard logs). Direct human-expert signal. Risk: reflect constraints the model may not know (gear failures, strategy, fatigue) and may be suboptimal.

Reconciling these is itself a research question: where skippers diverge from the a posteriori ideal, the gap may be suboptimal play or legitimate objectives (safety, comfort) our cost model fails to capture.

## Task-Oriented Weather Compression

### Decision-preserving vs. reconstruction-preserving compression

Traditional compression minimizes reconstruction error. Task-oriented compression minimizes the degradation of a downstream task. Applied to weather routing: compress weather only enough to preserve the routing decision.

- Hypothesis: a compressed weather representation with high reconstruction error can still produce near-optimal routes if it preserves the information the router uses (wind gradients, storm boundaries, thermal gradients). Conversely, a representation with low reconstruction error that shifts a storm boundary can produce a completely different route.
- Research question: what is the minimum weather representation that preserves routing decisions? Which statistics (mean, variance, quantiles, gradients, extrema) are necessary?
- Spatial structure matters: mean/median/variance can destroy localized features (a storm cell in an otherwise uniform field). Test spatial structure preservation explicitly: local extrema, directional gradients, boundary locations, connected hazardous regions, low-frequency Fourier/wavelet coefficients. The question is: what spatial features does an isochrone router actually care about?
- Related work: task-oriented compression is an active ML concept ([information bottleneck](https://en.wikipedia.org/wiki/Information_bottleneck_method), [task-aware lossy compression](https://arxiv.org/abs/2405.04144)) but has not been applied to weather routing. Coordinate-based neural networks have achieved up to 790x compression for weather/climate data ([ICLR 2023](https://arxiv.org/abs/2210.12538)), but optimized for reconstruction, not decisions.

### Vessel-conditioned weather representation

The value of a weather feature is conditional on the vessel. 12 kt at 90 TWA is fantastic for a catamaran and mediocre for a heavy cruiser.

- Hypothesis: a vessel-conditioned encoder can compress weather more aggressively than a vessel-agnostic one, because it can discard information that does not affect this particular boat's routing decisions.
- Research question: can a transformer learn a compact latent representation of weather + vessel state that preserves the information necessary for routing? Does optimal compression depend on boat type?
- Related: [Objectives](objectives.md) (Goal 3)

### Separate compression + isochrone routing (stepping stone — Level 3)

The encoder-decoder is trained to minimize routing degradation, but the router remains deterministic isochrone. Simpler, safer, easier to debug. Isolates the compression contribution from the routing contribution. See [Objectives](objectives.md) for the architecture.

## Joint Encoder-Router (Level 4 — optional extension)

### Learning to compress and route simultaneously

Train the encoder and router jointly end-to-end. The encoder learns what weather information to keep; the routing head learns to route from what was kept. They co-adapt.

```
weather + vessel state -> encoder -> compact representation (N bytes) -> routing head -> ROUTE
```

Level 4 is optional. If Level 3 achieves 10 KB/day at 95%+ route quality, the project is already successful. Level 4 asks: "Can joint training do even better?"

Why more interesting than separate compression + routing:
- The encoder doesn't waste capacity preserving weather features the router doesn't need.
- The router learns to operate directly in the compressed representation space.
- The two components co-adapt.

Why riskier:
- The router becomes a black box. The "AI fails -> deterministic fallback" property is lost unless a safety layer is added.
- The model learns to imitate the isochrone router on degraded input. To beat the isochrone, you need training signal beyond SOTA router outputs (real skipper trajectories, a posteriori optimal routes).
- Failure modes correlate with rare/dangerous conditions — where training data is thinnest.

### Connection to JEPA

[JEPA](https://arxiv.org/abs/2301.08243) (LeCun et al., 2023) predicts representations in embedding space rather than reconstructing raw data. Instead of `weather -> encoder -> latent -> decoder -> reconstructed weather`, JEPA predicts in the latent space:

```
context (what we know) -> context-encoder -> context embedding
target (what we want)  -> target-encoder  -> target embedding
predict: context embedding -> target embedding (in latent space, not pixel space)
```

Applied to weather routing: context is the compressed weather representation; target is the routing-relevant features of the full weather field. The key insight: don't predict what can't be predicted (pixel-level weather details), predict only the abstract features that matter for the task.

- Hypothesis: a JEPA-style architecture predicting routing-relevant weather features in embedding space will produce a more efficient compact representation than a reconstruction-based autoencoder.
- References: [I-JEPA (Assran et al., 2023)](https://arxiv.org/abs/2301.08243), [V-JEPA (Bardes et al., 2024)](https://ai.meta.com/blog/v-jepa/)

### Connection to Information Bottleneck

The [Information Bottleneck](https://en.wikipedia.org/wiki/Information_bottleneck_method) method compresses input X (weather) into representation T while maximizing mutual information I(T; Y) between T and the target Y (route):

```
min I(X; T) - beta * I(T; Y)
```

I(X; T) is the compression (minimize information kept). I(T; Y) is the task relevance (maximize information about the route). The [Variational Information Bottleneck](https://arxiv.org/abs/1612.00410) (Alemi et al., 2017) provides a practical approximation. The bandwidth budget B constrains I(X; T) directly.

### Connection to World Models

[World Models](https://arxiv.org/abs/1803.10122) (Ha & Schmidhuber, 2018): an agent learns a compact world model (V: vision/encoder, M: memory/dynamics, C: controller/policy) and plans within that learned representation. Applied to weather routing:

- V (encoder): weather -> compact latent representation
- M (dynamics): predict how weather and boat state evolve over time in latent space
- C (controller/router): choose a route from the latent representation and predicted evolution

The route is planned in compressed representation space, not by reconstructing the full weather field.

- Hypothesis: a world-model architecture that plans routes in latent space can achieve better route quality at a given bandwidth budget than a reconstruct-then-route pipeline, because it avoids the information loss inherent in reconstruction.

### Hybrid architecture: DL router + isochrone safety layer

```
DL router (from compressed weather) -> candidate route
  -> isochrone refinement (local optimization around candidate)
  -> safety check (probabilistic hazard exposure)
  -> final route
```

The DL router handles big-picture routing from degraded data. The isochrone does quick local refinement and safety verification (deterministic, interpretable, auditable). If the DL router fails badly, the isochrone catches it. For tactical decisions (coastal approach, squall avoidance), the isochrone runs alone.

The DL router can take 30+ minutes (planning); the isochrone refinement is seconds (tactical). On a Raspberry Pi 4 (3-7W), 30 min at 5W = 2.5 Wh — negligible against a typical boat battery (2400-4800 Wh).

## Learned Vessel Performance

### Adaptive polar from real-world observations

- Hypothesis: a vessel-performance model starting from the manufacturer polar and learning corrections from on-water observations will route significantly better than the static polar, especially for older or modified boats.
- What exists: [PredictWind "AI Polars"](https://www.predictwind.com), [University of Rostock AI Sailing](https://www.mathematik.uni-rostock.de/en/ai-sail/), Random Forest models, physics-guided ML (SPAM). Not novel individually.
- Novel combination: learned vessel performance + task-oriented weather compression + bandwidth constraint. The learned polar conditions what weather information is valuable, which conditions the compression.
- Related: [Objectives](objectives.md) (Goal 3)

### Temporal dependence in boat performance

Boat performance has temporal dynamics: sail changes take time, waves have memory, boat acceleration is not instantaneous, crew reaction is delayed. A transformer can model V_t = f(X_{t-n}, ..., X_{t-1}, X_t).

- Hypothesis: a temporal model captures dynamics that a static polar misses, improving route predictions in changing conditions.
- Open question: how much temporal context is needed? Does this matter at the timescales of weather routing (hours to days)?

## Adaptive Information Acquisition

### Value-per-byte data request policy

Given the current route, forecast uncertainty, previously downloaded data, and satellite budget, what weather data should be downloaded next?

- Candidate requests: A (5x5 deg, 3-hourly, wind only), B (10x5 deg, 6-hourly, wind + pressure), C (5x10 deg, 1-hourly, wind + waves), D (storm corridor, high resolution).
- Scoring: for each candidate, estimate expected routing improvement / bytes. Download the highest-value request.
- This is an information-theoretic control loop: spend bandwidth where it changes the decision.
- ML formulation: train a model to estimate V(request) = delta_route_quality / bytes. Training example: (current state, forecast, route, candidate request, actual improvement).
- Counterfactual evaluation: for each scenario, progressively degrade weather and find the decision boundary — the budget at which the routing decision flips (e.g., go north at 10 KB, go south at 2 KB). This "decision-critical information budget" is more informative than average ETA.
- Variable-value experiment: remove weather variables one at a time (wind, waves, current, pressure) and measure route quality impact. This produces a per-variable value ranking (e.g., wind = 85% of information value, waves = 10%, current = 5% for open ocean; wind = 45%, current = 45% near a current system). Feeds adaptive variable selection.
- Related: [Objectives](objectives.md) (Goal 1), [Benchmarking](benchmarking.md)

## How These Connect

Two architectural paths:

- Path A (stepping stone, Levels 3A/3B/3C): learned vessel model + task-oriented encoder + isochrone router. ML handles compression, router stays deterministic.
- Path B (optional extension, Level 4): joint encoder + routing head (JEPA / IB / world-model inspired) + isochrone safety layer. ML handles compression AND routing, isochrone is fallback.

Both share the same vessel model and adaptive acquisition layer. The experimental design in [Objectives](objectives.md) provides baselines at each layer. Path A is the project; Path B is the bonus.
