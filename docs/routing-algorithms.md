# Routing Algorithms: State of the Art

## 1. Algorithm Classification

### 1.1 Deterministic Algorithms

#### Isochrone Method
- Concept: Calculate lines of equal time (isochrones) from the starting point, expanding outward until the destination is reached. Each isochrone represents all positions reachable in the same elapsed time, given the forecast wind/current and the boat's polar performance.
- Complexity: O(n²) to O(n³) depending on implementation
- Accuracy: Medium-High
- Speed: Medium
- Memory: Medium

Mathematical foundation: The isochrone method is a time-stepped dynamic programming approach. For each time step Δt, the next isochrone is constructed from the current one:

1. Position update — For each point on the current isochrone, enumerate candidate headings ψ and compute the reachable position:
   - x_new = x_old + v(θ, w) · Δt · cos(ψ)
   - y_new = y_old + v(θ, w) · Δt · sin(ψ)
   - where v(θ, w) is the boat speed from the polar diagram at True Wind Angle θ and True Wind Speed w

2. Cost assignment — Each sub-route receives a cost (time, fuel, or weighted multi-objective including safety/comfort penalties)

3. Pruning — Points on the new isochrone that are dominated (another point reaches the same angular sector in less time) are pruned to control combinatorial explosion

4. Iteration — Repeat until the destination is reached; backtrack the minimum-cost path

Key sailing concepts:
- Polar diagram: Tabulates boat speed as a function of TWA and TWS. Defines the vessel's performance envelope. Source: [ORC VPP polars](https://www.boatpolars.com/)
- VMG (Velocity Made Good): The component of boat speed in the direction of the destination: VMG = v · cos(angle_to_target). The optimal TWA for VMG is where the polar curve is furthest forward (upwind, ~37-45°) or furthest aft (downwind, ~145-150°)
- TWA / TWD: True Wind Angle (angle between heading and true wind) and True Wind Direction (direction wind blows from). Routing selects TWA relative to TWD to maximize VMG

Implementation:
- [libweatherrouting (Python)](https://github.com/dakk/libweatherrouting) — Docs: [dakk.github.io/libweatherrouting](https://dakk.github.io/libweatherrouting/)
- [qtVlm (C++/Qt)](https://sourceforge.net/projects/qtvlm/) — Free but proprietary
- [OpenCPN Weather Routing plugin](https://opencpn.org/OpenCPN/plugins/weatherroute.html) — Open source, isochrone-based
- [SailGrib WR](https://www.sailgrib.com)

Strengths: standard algorithm for sailing routing; naturally handles wind-dependent boat speed via polar diagrams; handles time-dependent weather.

Weaknesses: computationally expensive for high resolution (pruning is critical); no inherent uncertainty handling; multi-objective optimization requires custom cost function design; pruning can discard globally optimal paths.

References:
- [Strategies to improve the isochrone algorithm (2024, Chalmers)](https://www.tandfonline.com/doi/full/10.1080/17445302.2024.2329011)
- [3D Modified Isochrone (3DMI) method](https://www.researchgate.net/publication/267621767)
- [Benchmark study of five optimization algorithms for weather routing](https://files01.core.ac.uk/download/pdf/289287244.pdf)
- [LuckGrib routing documentation (isochrones explained)](https://routing.luckgrib.com/intro/isochrones/index.html)

#### Dijkstra's Algorithm
- Concept: Find the shortest path in a weighted graph by iteratively selecting the node with the smallest tentative distance.
- Complexity: O(E + V log V) with priority queue
- Accuracy: Medium
- Speed: Fast
- Memory: Low-Medium

Implementation: [FastSeas](https://www.fastseas.com), custom implementations in many routing tools.

Strengths: guaranteed shortest path for non-negative weights; simple; fast for sparse graphs.

Weaknesses: does not account for time-dependent weather; requires discretization of continuous space; less accurate for sailing (speed depends on wind angle).

References: [Dijkstra (1959)](https://www.cs.utexas.edu/users/EWD/transcriptions/EWD01xx/EWD136.html), [CLRS Chapter 24](https://walkccc.me/CLRS/Chap24/24.3.html)

#### A* Algorithm
- Concept: Informed search algorithm that uses a heuristic to guide the search towards the goal.
- Complexity: O(E + V log V) best case, O(E) worst case
- Accuracy: High (with good heuristic)
- Speed: Very Fast
- Memory: Medium

Implementation: custom implementations, [PathFinding.js](https://github.com/qiao/PathFinding.js) (JavaScript).

Strengths: faster than Dijkstra; heuristic-guided; guaranteed optimal if heuristic is admissible.

Weaknesses: heuristic must be admissible; assumes static weather; requires careful tuning for sailing.

References: [Hart, Nilsson, Raphael (1968)](https://ieeexplore.ieee.org/document/4082128), [A* Tutorial — Red Blob Games](https://www.redblobgames.com/pathfinding/a-star/introduction.html)

### 1.2 Probabilistic Algorithms

#### Monte Carlo Tree Search (MCTS)
- Concept: Combines tree search with random sampling to find optimal paths under uncertainty.
- Complexity: O(iterations × depth)
- Accuracy: High (with sufficient iterations)
- Speed: Slow
- Memory: High

Implementation: academic research, [github.com/pbharrin/mcts](https://github.com/pbharrin/mcts) (Python).

Strengths: handles uncertainty; balances multiple objectives; theoretically optimal with infinite iterations.

Weaknesses: very computationally expensive; requires many iterations; difficult for real-time.

References: [Coulom (2006)](https://hal.inria.fr/inria-00118122/document), [Browne et al. (2012) — Survey of MCTS](https://arxiv.org/abs/1204.2652)

#### Markov Decision Process (MDP)
- Concept: Models routing as a Markov decision process with state including position and weather conditions.
- Complexity: O(S²A) for value iteration
- Accuracy: High (with good model)
- Speed: Medium-Slow
- Memory: High

Implementation: academic research, [MDPToolbox](https://github.com/sawyerbf/MDPToolbox) (MATLAB).

Strengths: handles uncertainty; multi-objective; theoretically sound.

Weaknesses: requires modeling entire state space; expensive for large state spaces; difficult for real-time.

References: [MDP — Wikipedia](https://en.wikipedia.org/wiki/Markov_decision_process), [Maritime MDP](https://www.sciencedirect.com/science/article/pii/S0360835215000212)

#### Ensemble-Based Probabilistic Routing
- Concept: Use an ensemble of forecasts (20-50+ members with perturbed initial conditions) to compute a probability distribution of outcomes for each route. Select routes robust across the ensemble, not just optimal for one forecast.
- Complexity: O(E × algorithm_cost) where E = ensemble members
- Accuracy: High (quantifies and exploits uncertainty)
- Speed: Slow
- Memory: High

How it works:
1. Download ensemble forecast (e.g., NOAA GEFS 31 members, ECMWF ENS 51 members)
2. For each member, run the routing algorithm
3. Aggregate: compute distribution of arrival times, fuel consumption, safety risk
4. Select route optimizing expected value while minimizing variance

Data efficiency: ensemble forecasts are E× larger, creating tension with the low-data goal. However, ensemble probability information can be compressed — download mean, spread, and key percentile fields instead of all members.

Implementation: [NOAA GEFS](https://nomads.ncep.noaa.gov) (31 members, 0.5°, 16-day), ECMWF ENS (51 members, ~18 km, 15-day, open data since Oct 2025).

Strengths: directly addresses forecast uncertainty; enables risk-aware routing; more realistic for long voyages (>48h).

Weaknesses: E× more computation; E× larger data (mitigated by summary statistics); more complex decision framework.

References:
- [Uncertainty-informed ship voyage optimization (Ocean Engineering, 2022)](https://www.sciencedirect.com/science/article/abs/pii/S0029801822021709)
- [A Comprehensive Approach to Account for Weather Uncertainties (JMSE, 2021)](https://doi.org/10.3390/jmse9121434)
- [Anomalous Behavior in Weather Forecast Uncertainty (JMSE, 2025)](https://www.mdpi.com/2077-1312/13/6/1185)

#### Genetic Algorithms
- Concept: Evolve a population of routes using selection, crossover, and mutation.
- Complexity: O(n × generations)
- Accuracy: Medium-High
- Speed: Slow
- Memory: Medium

Implementation: academic research, [DEAP](https://github.com/DEAP/deap) (Python).

Strengths: handles complex non-linear objectives; escapes local optima; flexible.

Weaknesses: no optimality guarantee; careful parameter tuning; expensive; difficult for real-time.

References: [DEAP Documentation](https://deap.readthedocs.io), [Genetic Algorithms — Wikipedia](https://en.wikipedia.org/wiki/Genetic_algorithm)

#### Particle Swarm Optimization (PSO)
- Concept: Uses a swarm of particles to explore the solution space, guided by personal and global best solutions.
- Complexity: O(n × iterations)
- Accuracy: Medium-High
- Speed: Medium
- Memory: Low

Implementation: academic research, [pyswarm](https://github.com/JamesChuanggg/pyswarm) (Python).

Strengths: simple; fewer parameters than GA; handles non-linear objectives.

Weaknesses: no optimality guarantee; can get stuck in local optima; requires tuning.

References: [Kennedy & Eberhart (1995)](https://ieeexplore.ieee.org/document/488968)

#### Ant Colony Optimization (ACO)
- Concept: Inspired by ant foraging, uses pheromone trails to guide the search.
- Complexity: O(n × iterations)
- Accuracy: Medium-High
- Speed: Medium-Slow
- Memory: Medium

Implementation: academic research, [acopy](https://github.com/rhgrant10/acopy) (Python).

Strengths: naturally suited for pathfinding; handles complex spaces; parallelizable.

Weaknesses: slow convergence; requires tuning; memory-intensive for large problems.

References: [Dorigo (1992)](https://www.sciencedirect.com/science/article/pii/0925231296000359)

## 2. AI/ML-Based Algorithms

### 2.1 Reinforcement Learning

#### Deep Reinforcement Learning (DRL)
- Concept: Uses deep neural networks to learn routing policies through interaction with the environment.
- Complexity: O(iterations × network_size)
- Accuracy: High (with sufficient training)
- Speed: Slow (training), Fast (inference)
- Memory: Very High

Implementation: [Latinopoulos et al. (2025) — Marine Voyage Optimization, JMSE 13(5)](https://www.mdpi.com/2077-1312/13/5/902) (Actor-Critic, real AIS data). Frameworks: [Stable Baselines3](https://github.com/DLR-RM/stable-baselines3), [RLlib](https://github.com/ray-project/ray).

Strengths: learns complex strategies; adapts to different boats/conditions; potential for superior performance.

Weaknesses: requires large training data; expensive to train; black-box; no real-world validation in sailing routing (existing work focuses on commercial shipping).

References: [Latinopoulos et al. (2025)](https://www.mdpi.com/2077-1312/13/5/902), [CMR Berkeley (2024) — business overview, not a routing algorithm](https://cmr.berkeley.edu/2024/12/utilizing-ai-for-maritime-transport-optimization/)

#### Imitation Learning
- Concept: Learns to mimic expert routing decisions from demonstration data.
- Complexity: O(n × network_size)
- Accuracy: High (with good demonstrations)
- Speed: Fast (after training)
- Memory: High

Implementation: [Anderson et al. (2022) — Route Optimization for Sailing Vessels, ACM](https://dl.acm.org/doi/10.1145/3581792.3581803). Framework: [imitation library](https://github.com/HumanCompatibleAI/imitation).

Strengths: leverages expert routes; more data-efficient than RL; easier to validate.

Weaknesses: requires high-quality demonstrations; limited by demonstration quality; may not generalize; no production implementations in sailing.

References: [Anderson, Sithungu, Ehlers (2022)](https://dl.acm.org/doi/10.1145/3581792.3581803)

#### Supervised Learning
- Concept: Learns to predict optimal routes or waypoints from input features (weather, boat polars).
- Complexity: O(n × network_size)
- Accuracy: Medium-High
- Speed: Fast
- Memory: Medium

Implementation: custom. Frameworks: [PyTorch](https://pytorch.org/), [scikit-learn](https://scikit-learn.org/).

Strengths: fast inference; learns from historical data; interpretable models possible.

Weaknesses: requires labeled data; may not generalize; limited by training data quality.

### 2.2 Neural Network Architectures

#### Graph Neural Networks (GNNs)
- Concept: Uses graph structures to represent routing, with nodes as positions and edges as possible moves.
- Complexity: O(V + E) per layer
- Accuracy: High (for graph-structured problems)
- Speed: Medium
- Memory: Medium

Implementation: no confirmed maritime routing implementations as of 2025. Frameworks: [PyTorch Geometric](https://github.com/pyg-team/pytorch_geometric), [DGL](https://github.com/dmlc/dgl).

Strengths: naturally represents routing as graph; captures spatial relationships; works with irregular grids.

Weaknesses: requires graph construction; expensive for large graphs; limited maritime applications.

#### Convolutional Neural Networks (CNNs)
- Concept: Uses convolutional layers to process gridded weather data (GRIB files).
- Complexity: O(H × W × C) per layer
- Accuracy: High (for image-like data)
- Speed: Medium
- Memory: High

Implementation: various weather prediction applications. Frameworks: [PyTorch](https://pytorch.org/).

Strengths: good for gridded weather data; captures spatial patterns; translation equivariant.

Weaknesses: requires fixed-size inputs; not naturally suited for pathfinding; expensive.

#### Transformer Networks
- Concept: Uses self-attention to capture long-range dependencies in weather data.
- Complexity: O(n²) per layer
- Accuracy: Very High (with sufficient data)
- Speed: Slow
- Memory: Very High

Implementation: emerging in weather prediction. Framework: [Hugging Face Transformers](https://github.com/huggingface/transformers).

Strengths: captures long-range dependencies; state-of-the-art in many domains; flexible.

Weaknesses: very expensive; requires large data; difficult to train; no maritime routing applications yet.

References: [Vaswani et al. (2017) — Attention Is All You Need](https://arxiv.org/abs/1706.03762)

## 3. Algorithm Comparison

These ratings reflect general properties from the literature, not empirical results on this specific task. Actual performance must be benchmarked.

| Algorithm | Speed | Memory | Uncertainty | Multi-Objective | Implementation |
|-----------|-------|--------|-------------|-----------------|----------------|
| Isochrone | Medium | Medium | No | No | Easy |
| Dijkstra | Fast | Low-Medium | No | No | Easy |
| A* | Very Fast | Medium | No | No | Medium |
| MCTS | Slow | High | Yes | Yes | Hard |
| MDP | Medium-Slow | High | Yes | Yes | Hard |
| Genetic Algorithm | Slow | Medium | No | Yes | Medium |
| PSO | Medium | Low | No | Yes | Easy |
| ACO | Medium-Slow | Medium | No | Yes | Medium |
| Deep RL | Fast (inference) | Very High | Yes | Yes | Very Hard |
| Imitation Learning | Fast | High | Limited | Yes | Hard |
| Supervised Learning | Fast | Medium | No | Limited | Medium |
| GNN | Medium | Medium | Limited | Yes | Hard |
| CNN | Medium | High | No | Limited | Medium |
| Transformer | Slow | Very High | Limited | Limited | Very Hard |

## 4. Algorithm Selection Guide

### 4.1 For Low Data Routing (v1)

| Requirement | Recommended | Rationale |
|-------------|-------------|-----------|
| V1 routing engine | Isochrone | Standard sailing algorithm; handles polar diagrams and time-dependent weather |
| Fast inference | Isochrone | Low computational cost; runs on Raspberry Pi |
| Low memory | Isochrone | Minimal memory footprint with pruning |
| Edge deployment | Isochrone | Raspberry Pi compatible; <500 MB RAM |

V1 architecture: isochrone planner + adaptive forecast acquisition + uncertainty-aware cost function. The neural network serves the router (compression, vessel model, data-request policy), it does not replace it.

### 4.2 For Learned Compression (Level 3)

| Requirement | Recommended Approach | Rationale |
|-------------|----------------------|-----------|
| Task-oriented weather compression | Neural encoder-decoder | Train to minimize routing degradation, not reconstruction error |
| Vessel-conditioned representation | Transformer (weather + vessel state) | Attention over temporal sequence; learns what weather matters for this boat |
| Adaptive data requests | Value-per-byte scoring (ML or heuristic) | Information-theoretic control loop: spend bandwidth where it changes the decision |

### 4.3 For Joint Encoder-Router (Level 4 — optional)

| Requirement | Recommended Approach | Rationale |
|-------------|----------------------|-----------|
| Joint compression + routing | Encoder + routing head, trained end-to-end | Encoder and routing head co-adapt; no weather reconstruction needed |
| Latent-space routing | JEPA-style prediction in embedding space | Predict routing-relevant features, not raw weather |
| Planning inference | DL router (<60 min) + isochrone refinement (seconds) | Relaxed inference time for planning; isochrone fallback for tactical |
| Safety fallback | Isochrone refinement + probabilistic safety check | Deterministic safety layer catches DL failures |

See [Research Ideas](research-ideas.md) for connections to JEPA, Information Bottleneck, and World Models.

### 4.4 For Safety (v1)

| Requirement | Recommended Approach | Rationale |
|-------------|----------------------|-----------|
| Storm/gale identification | Threshold-based + forecast disagreement | Conventional meteorological thresholds are well-validated |
| Extreme wind/wave exposure | Probabilistic P(Wind > threshold \| forecast) | Minimize probability of exposure |
| Rapidly deteriorating conditions | Temporal derivative of forecast fields | Detect acceleration in wind/wave trends |

Deferred to future modules: rogue-wave prediction, iceberg detection (requires satellite imagery — shore-side), microburst prediction (requires high-res wind data). See [Objectives](objectives.md).

## 5. Implementation Considerations

| Device | CPU | RAM | Power | Constraints |
|--------|-----|-----|-------|------------|
| Raspberry Pi 4 | 4x 1.8GHz | 4-8 GB | 3-7W | Limited CPU, memory |
| Raspberry Pi 5 | 4x 2.4GHz | 4-8 GB | 5-15W | Better than Pi 4 |
| Jetson Nano | 4x 1.43GHz | 4 GB | 5-10W | GPU available |
| Typical Laptop | 4-8 core | 8-16 GB | 30-60W | No constraints |

Isochrone runs within <500 MB RAM on Raspberry Pi. See [Objectives](objectives.md) for inference time targets.

## 6. Improvement Opportunities

### 6.1 Data Efficiency

| Opportunity | Potential Improvement | Feasibility | Challenge |
|------------|----------------------|-------------|-----------|
| Region Filtering | Route-aware dynamic selection | High | Dynamic corridor prediction |
| Variable Filtering | Vessel-conditioned variable selection | High | Determining needed variables per boat |
| Temporal Downsampling | Adaptive resolution based on forecast horizon | High | Accuracy tradeoff |
| Delta Encoding | 70-90% reduction for sequential updates | Medium | Stateful connection over SBD; needs application-layer reliability |
| Custom Binary Encoding | 60-80% on top of GRIB compression | Medium | Encoding design, compatibility |
| Task-Oriented Compression | Compress to preserve routing decision, not weather | Medium | Requires training data and ML pipeline |
| Ensemble Summary Compression | Download mean/spread instead of all members | Medium | Loss of tail information |
| Combined | 90-99% reduction vs. full global | Medium | Techniques interact; empirical curve needed |

### 6.2 Algorithm

| Opportunity | Potential Improvement | Feasibility | Challenge |
|------------|----------------------|-------------|-----------|
| Isochrone (v1) | Add uncertainty-aware cost function | High | Multi-objective cost design |
| Adaptive data acquisition | Value-per-byte request policy | High | Scoring function design |
| Learned vessel performance | Personalized polar from on-water observations | Medium | Data collection, online learning |
| Vessel-conditioned compression | Compress weather based on what matters for this boat | Medium | Training data, model design |

### 6.3 Safety (v1 scope)

| Opportunity | Potential Improvement | Feasibility | Challenge |
|------------|----------------------|-------------|-----------|
| Storm detection | Threshold + forecast disagreement | High | Data quality |
| Extreme wind/wave exposure | Probabilistic P(threshold \| forecast) | High | Ensemble data access |
| Rapidly deteriorating conditions | Temporal derivative monitoring | High | Forecast resolution |

Deferred: rogue wave prediction, iceberg detection (shore-side satellite imagery), microburst prediction (high-res wind data). See [Objectives](objectives.md).

Related: [Objectives](objectives.md), [Benchmarking](benchmarking.md), [Literature Review](literature-review.md), [Research Ideas](research-ideas.md), [Meteorological Info Transfer](meteorological-info-transfer.md)
