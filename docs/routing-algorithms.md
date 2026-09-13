# Routing Algorithms: State of the Art

*Comprehensive overview of current sailing routing algorithms, their strengths, weaknesses, and optimization opportunities*

---

## **🗺️ 1. Algorithm Classification**

### **1.1 Deterministic Algorithms**

#### **Isochrone Method**
- **Concept:** Calculate lines of equal time (isochrones) from the starting point, expanding outward until the destination is reached. Each isochrone represents all positions reachable in the same elapsed time, given the forecast wind/current and the boat's polar performance.
- **Complexity:** O(n²) to O(n³) depending on implementation
- **Accuracy:** Medium-High
- **Speed:** Medium
- **Memory:** Medium

**Mathematical Foundation:**

The isochrone method is a time-stepped dynamic programming approach. For each time step Δt, the next isochrone is constructed from the current one:

1. **Position update** — For each point on the current isochrone, enumerate candidate headings ψ and compute the reachable position:
   - x_new = x_old + v(θ, w) · Δt · cos(ψ)
   - y_new = y_old + v(θ, w) · Δt · sin(ψ)
   - where v(θ, w) is the boat speed from the polar diagram at True Wind Angle θ and True Wind Speed w

2. **Cost assignment** — Each sub-route receives a cost (time, fuel, or weighted multi-objective including safety/comfort penalties)

3. **Pruning** — Points on the new isochrone that are dominated (another point reaches the same angular sector in less time) are pruned to control combinatorial explosion

4. **Iteration** — Repeat until the destination is reached; backtrack the minimum-cost path

**Key sailing concepts:**
- **Polar diagram:** Tabulates boat speed as a function of True Wind Angle (TWA) and True Wind Speed (TWS). Defines the vessel's performance envelope. Source: [ORC VPP polars](https://www.boatpolars.com/)
- **VMG (Velocity Made Good):** The component of boat speed in the direction of the destination: VMG = v · cos(angle_to_target). The optimal TWA for VMG is where the polar curve is furthest forward (upwind, ~37-45°) or furthest aft (downwind, ~145-150°)
- **TWA / TWD:** True Wind Angle (angle between heading and true wind) and True Wind Direction (direction wind blows from). Routing selects TWA relative to TWD to maximize VMG

**Implementation:**
- **libweatherrouting (Python):** [https://github.com/dakk/libweatherrouting](https://github.com/dakk/libweatherrouting) — Docs: [https://dakk.github.io/libweatherrouting/](https://dakk.github.io/libweatherrouting/)
- **qtVlm (C++/Qt):** [https://sourceforge.net/projects/qtvlm/](https://sourceforge.net/projects/qtvlm/) — Free but proprietary
- **OpenCPN Weather Routing plugin:** [https://opencpn.org/OpenCPN/plugins/weatherroute.html](https://opencpn.org/OpenCPN/plugins/weatherroute.html) — Open source, isochrone-based
- **SailGrib WR:** [https://www.sailgrib.com](https://www.sailgrib.com)

**Strengths:**
- The standard algorithm for sailing routing; used by virtually all production tools
- Naturally handles wind-dependent boat speed via polar diagrams
- Handles time-dependent weather (forecasts change at each time step)

**Weaknesses:**
- Computationally expensive for high resolution (pruning is critical)
- No inherent uncertainty handling (deterministic forecasts only)
- Multi-objective optimization requires custom cost function design
- Pruning can discard globally optimal paths (angular sector pruning is a heuristic)

**References:**
- **Strategies to improve the isochrone algorithm for ship voyage optimisation** (2024), Chalmers University: [https://www.tandfonline.com/doi/full/10.1080/17445302.2024.2329011](https://www.tandfonline.com/doi/full/10.1080/17445302.2024.2329011)
- **3D Modified Isochrone (3DMI) method:** [https://www.researchgate.net/publication/267621767](https://www.researchgate.net/publication/267621767)
- **Benchmark study of five optimization algorithms for weather routing:** [https://files01.core.ac.uk/download/pdf/289287244.pdf](https://files01.core.ac.uk/download/pdf/289287244.pdf)
- **LuckGrib routing documentation (isochrones explained):** [https://routing.luckgrib.com/intro/isochrones/index.html](https://routing.luckgrib.com/intro/isochrones/index.html)

---

#### **Dijkstra's Algorithm**
- **Concept:** Find the shortest path in a weighted graph by iteratively selecting the node with the smallest tentative distance.
- **Complexity:** O(E + V log V) with priority queue (where E = edges, V = vertices)
- **Accuracy:** Medium
- **Speed:** Fast
- **Memory:** Low-Medium

**Implementation:**
- **FastSeas:** [https://www.fastseas.com](https://www.fastseas.com)
- **Custom implementations in many routing tools**

**Strengths:**
- Guaranteed to find the shortest path if all weights are non-negative
- Simple to implement
- Fast for sparse graphs

**Weaknesses:**
- Does not account for time-dependent weather (assumes static conditions)
- Requires discretization of continuous space
- Less accurate for sailing (where speed depends on wind angle)

**References:**
- **Original Paper:** Edsger W. Dijkstra (1959) - "A Note on Two Problems in Connexion with Graphs" [https://www.cs.utexas.edu/users/EWD/transcriptions/EWD01xx/EWD136.html](https://www.cs.utexas.edu/users/EWD/transcriptions/EWD01xx/EWD136.html)
- **CLRS Book:** "Introduction to Algorithms" (Chapter 24) [https://walkccc.me/CLRS/Chap24/24.3.html](https://walkccc.me/CLRS/Chap24/24.3.html)

---

#### **A* Algorithm**
- **Concept:** Informed search algorithm that uses a heuristic to guide the search towards the goal.
- **Complexity:** O(E + V log V) in best case, O(E) in worst case
- **Accuracy:** High (with good heuristic)
- **Speed:** Very Fast
- **Memory:** Medium

**Implementation:**
- **Custom implementations in routing software**
- **Open-source libraries:** [https://github.com/qiao/PathFinding.js](https://github.com/qiao/PathFinding.js) (JavaScript example)

**Strengths:**
- Faster than Dijkstra's for pathfinding
- Uses heuristic to guide search (e.g., straight-line distance to goal)
- Guaranteed to find optimal path if heuristic is admissible

**Weaknesses:**
- Heuristic must be admissible (never overestimates true cost)
- Still assumes static weather conditions
- Requires careful tuning of heuristic for sailing applications

**References:**
- **Original Paper:** Peter Hart, Nils Nilsson, Bertram Raphael (1968) - "A Formal Basis for the Heuristic Determination of Minimum-Cost Paths" [https://ieeexplore.ieee.org/document/4082128](https://ieeexplore.ieee.org/document/4082128)
- **A* Tutorial:** [https://www.redblobgames.com/pathfinding/a-star/introduction.html](https://www.redblobgames.com/pathfinding/a-star/introduction.html)

---

### **1.2 Probabilistic Algorithms**

#### **Monte Carlo Tree Search (MCTS)**
- **Concept:** Combines tree search with random sampling to find optimal paths under uncertainty.
- **Complexity:** O(iterations × depth)
- **Accuracy:** High (with sufficient iterations)
- **Speed:** Slow (computationally expensive)
- **Memory:** High

**Implementation:**
- **Academic research:** Various proposals in maritime routing literature
- **Open-source:** [https://github.com/pbharrin/mcts](https://github.com/pbharrin/mcts) (Python implementation)

**Strengths:**
- Handles uncertainty in weather forecasts
- Can balance multiple objectives (speed, safety, comfort)
- Theoretically optimal with infinite iterations

**Weaknesses:**
- Very computationally expensive
- Requires many iterations for accuracy
- Difficult to tune for real-time applications

**References:**
- **Original Paper:** Rémi Coulom (2006) - "Efficient Selectivity and Backup Operators in Monte-Carlo Tree Search" [https://hal.inria.fr/inria-00118122/document](https://hal.inria.fr/inria-00118122/document)
- **Survey:** Cameron Browne et al. (2012) - "A Survey of Monte Carlo Tree Search Methods" [https://arxiv.org/abs/1204.2652](https://arxiv.org/abs/1204.2652)

---

#### **Markov Decision Process (MDP)**
- **Concept:** Models the routing problem as a Markov decision process, where the state includes position and weather conditions.
- **Complexity:** O(S²A) for value iteration (S = states, A = actions)
- **Accuracy:** High (with good model)
- **Speed:** Medium-Slow
- **Memory:** High

**Implementation:**
- **Academic research:** Various papers on maritime routing
- **Open-source:** [https://github.com/sawyerbf/MDPToolbox](https://github.com/sawyerbf/MDPToolbox) (MATLAB)

**Strengths:**
- Handles uncertainty in weather
- Can optimize for multiple objectives
- Theoretically sound framework

**Weaknesses:**
- Requires modeling the entire state space
- Computationally expensive for large state spaces
- Difficult to apply to real-time routing

**References:**
- **MDP Introduction:** [https://en.wikipedia.org/wiki/Markov_decision_process](https://en.wikipedia.org/wiki/Markov_decision_process)
- **Maritime MDP:** [https://www.sciencedirect.com/science/article/pii/S0360835215000212](https://www.sciencedirect.com/science/article/pii/S0360835215000212)

---

#### **Ensemble-Based Probabilistic Routing**
- **Concept:** Instead of using a single deterministic forecast, use an ensemble of forecasts (20-50+ members with perturbed initial conditions) to compute a probability distribution of outcomes for each route. Select routes that are robust across the ensemble, not just optimal for one forecast.
- **Complexity:** O(E × algorithm_cost) where E = number of ensemble members
- **Accuracy:** High (quantifies and exploits uncertainty)
- **Speed:** Slow (must run routing for multiple forecast scenarios)
- **Memory:** High

**How it works:**
1. Download ensemble forecast (e.g., NOAA GEFS with 31 members, ECMWF ENS with 51 members)
2. For each ensemble member, run the routing algorithm (isochrone, A*, etc.)
3. Aggregate results: compute the distribution of arrival times, fuel consumption, and safety risk across all members
4. Select the route that optimizes expected value while minimizing variance (robust optimization)

**Data efficiency implication:** Ensemble forecasts are larger than deterministic forecasts (E× more data), which creates tension with the low-data goal. However, ensemble probability information can be compressed: instead of downloading all members, download the ensemble mean, spread, and key percentile fields — potentially achievable in a few KB for a route corridor.

**Implementation:**
- **NOAA GEFS:** 31 members, 0.5° resolution, 16-day forecast [https://nomads.ncep.noaa.gov](https://nomads.ncep.noaa.gov)
- **ECMWF ENS:** 51 members, ~18 km resolution, 15-day forecast (open data since Oct 2025)
- **Research:** "A Comprehensive Approach to Account for Weather Uncertainties in Ship Route Optimization" [https://doi.org/10.3390/jmse9121434](https://doi.org/10.3390/jmse9121434)

**Strengths:**
- Directly addresses forecast uncertainty — the dominant source of routing error
- Enables risk-aware routing (e.g., avoid routes with high probability of storm encounter)
- More realistic than deterministic routing for long voyages (>48h)

**Weaknesses:**
- E× more computation (or requires clever sampling)
- Ensemble data is E× larger (mitigated by downloading summary statistics)
- More complex decision-making framework

**References:**
- **Ocean Engineering (2022):** "Uncertainty-informed ship voyage optimization" [https://www.sciencedirect.com/science/article/abs/pii/S0029801822021709](https://www.sciencedirect.com/science/article/abs/pii/S0029801822021709)
- **JMSE (2021):** "A Comprehensive Approach to Account for Weather Uncertainties" [https://doi.org/10.3390/jmse9121434](https://doi.org/10.3390/jmse9121434)
- **JMSE (2025):** "Anomalous Behavior in Weather Forecast Uncertainty" [https://www.mdpi.com/2077-1312/13/6/1185](https://www.mdpi.com/2077-1312/13/6/1185)

#### **Genetic Algorithms**
- **Concept:** Evolve a population of routes using selection, crossover, and mutation operators.
- **Complexity:** O(n × generations) (n = population size)
- **Accuracy:** Medium-High (depends on tuning)
- **Speed:** Slow (many iterations required)
- **Memory:** Medium

**Implementation:**
- **Academic research:** Various applications in maritime routing
- **Open-source:** [https://github.com/DEAP/deap](https://github.com/DEAP/deap) (Python evolutionary algorithms)

**Strengths:**
- Can handle complex, non-linear objectives
- Can escape local optima
- Flexible and adaptable

**Weaknesses:**
- No guarantee of optimality
- Requires careful tuning of parameters
- Computationally expensive
- Difficult to apply in real-time

**References:**
- **DEAP Documentation:** [https://deap.readthedocs.io](https://deap.readthedocs.io)
- **Genetic Algorithms:** [https://en.wikipedia.org/wiki/Genetic_algorithm](https://en.wikipedia.org/wiki/Genetic_algorithm)

---

#### **Particle Swarm Optimization (PSO)**
- **Concept:** Uses a swarm of particles to explore the solution space, guided by personal and global best solutions.
- **Complexity:** O(n × iterations) (n = swarm size)
- **Accuracy:** Medium-High
- **Speed:** Medium
- **Memory:** Low

**Implementation:**
- **Academic research:** Maritime routing applications
- **Open-source:** [https://github.com/JamesChuanggg/pyswarm](https://github.com/JamesChuanggg/pyswarm) (Python)

**Strengths:**
- Simple to implement
- Fewer parameters to tune than genetic algorithms
- Can handle non-linear objectives

**Weaknesses:**
- No guarantee of optimality
- Can get stuck in local optima
- Requires careful parameter tuning

**References:**
- **Original Paper:** James Kennedy, Russell Eberhart (1995) - "Particle Swarm Optimization" [https://ieeexplore.ieee.org/document/488968](https://ieeexplore.ieee.org/document/488968)
- **PSO Tutorial:** [https://towardsdatascience.com/particle-swarm-optimization-visualized-and-explained-42589e701099](https://towardsdatascience.com/particle-swarm-optimization-visualized-and-explained-42589e701099)

---

#### **Ant Colony Optimization (ACO)**
- **Concept:** Inspired by ant foraging behavior, uses pheromone trails to guide the search for optimal paths.
- **Complexity:** O(n × iterations) (n = number of ants)
- **Accuracy:** Medium-High
- **Speed:** Medium-Slow
- **Memory:** Medium

**Implementation:**
- **Academic research:** Some maritime applications
- **Open-source:** [https://github.com/rhgrant10/acopy](https://github.com/rhgrant10/acopy) (Python)

**Strengths:**
- Naturally suited for pathfinding problems
- Can find good solutions in complex spaces
- Parallelizable

**Weaknesses:**
- Slow convergence
- Requires careful parameter tuning
- Memory-intensive for large problems

**References:**
- **Original Paper:** Marco Dorigo (1992) - "Optimization, Learning and Natural Algorithms" [https://www.sciencedirect.com/science/article/pii/0925231296000359](https://www.sciencedirect.com/science/article/pii/0925231296000359)
- **ACO Tutorial:** [https://towardsdatascience.com/ant-colony-optimization-aco-for-travelling-salesman-problem-tsp-1e625c93495e](https://towardsdatascience.com/ant-colony-optimization-aco-for-travelling-salesman-problem-tsp-1e625c93495e)

---

## **🤖 2. AI/ML-Based Algorithms**

### **2.1 Reinforcement Learning**

#### **Deep Reinforcement Learning (DRL)**
- **Concept:** Uses deep neural networks to learn optimal routing policies through interaction with the environment.
- **Complexity:** O(iterations × network_size)
- **Accuracy:** High (with sufficient training)
- **Speed:** Slow (training), Fast (inference)
- **Memory:** Very High

**Implementation:**
- **MDPI Research (2025):** "Marine Voyage Optimization and Weather Routing with Deep Reinforcement Learning" [https://www.mdpi.com/2077-1312/13/5/902](https://www.mdpi.com/2077-1312/13/5/902) — uses real AIS data and weather info, Actor-Critic approach
- **Frameworks:**
  - **Stable Baselines3:** [https://github.com/DLR-RM/stable-baselines3](https://github.com/DLR-RM/stable-baselines3)
  - **RLlib:** [https://github.com/ray-project/ray](https://github.com/ray-project/ray)

**Strengths:**
- Can learn complex routing strategies
- Adapts to different boat types and conditions
- Potential for superior performance

**Weaknesses:**
- Requires large amounts of training data
- Computationally expensive to train
- Black-box nature (difficult to interpret)
- No real-world validation in sailing routing (existing work focuses on commercial shipping)

**References:**
- **Latinopoulos et al. (2025):** "Marine Voyage Optimization and Weather Routing with Deep Reinforcement Learning" JMSE 13(5), 902 [https://www.mdpi.com/2077-1312/13/5/902](https://www.mdpi.com/2077-1312/13/5/902)
- **CMR Berkeley (2024):** "Utilizing AI for Maritime Transport Optimization" — a business overview of AI in maritime shipping (not a routing algorithm paper) [https://cmr.berkeley.edu/2024/12/utilizing-ai-for-maritime-transport-optimization/](https://cmr.berkeley.edu/2024/12/utilizing-ai-for-maritime-transport-optimization/)

---

#### **Imitation Learning**
- **Concept:** Learns to mimic expert routing decisions from demonstration data.
- **Complexity:** O(n × network_size) (n = number of demonstrations)
- **Accuracy:** High (with good demonstrations)
- **Speed:** Fast (after training)
- **Memory:** High

**Implementation:**
- **Anderson et al. (2022):** "Route Optimization for Sailing Vessels using Artificial Intelligence Techniques" — 5th Intl. Conf. on Computational Intelligence and Intelligent Systems [https://dl.acm.org/doi/10.1145/3581792.3581803](https://dl.acm.org/doi/10.1145/3581792.3581803)
- **Frameworks:**
  - **Imitation Learning Library:** [https://github.com/HumanCompatibleAI/imitation](https://github.com/HumanCompatibleAI/imitation)

**Strengths:**
- Can leverage existing expert routes
- More data-efficient than reinforcement learning
- Easier to validate (compares to known good routes)

**Weaknesses:**
- Requires high-quality demonstration data
- Limited by the quality of demonstrations
- May not generalize beyond training distribution
- No production implementations in sailing routing

**References:**
- **Anderson, Sithungu, Ehlers (2022):** "Route Optimization for Sailing Vessels using Artificial Intelligence Techniques" [https://dl.acm.org/doi/10.1145/3581792.3581803](https://dl.acm.org/doi/10.1145/3581792.3581803)

---

#### **Supervised Learning**
- **Concept:** Learns to predict optimal routes or waypoints from input features (weather, boat polars, etc.).
- **Complexity:** O(n × network_size) (n = training samples)
- **Accuracy:** Medium-High
- **Speed:** Fast
- **Memory:** Medium

**Implementation:**
- **Custom implementations**
- **Frameworks:**
  - **PyTorch:** [https://pytorch.org/](https://pytorch.org/)
  - **TensorFlow:** [https://www.tensorflow.org/](https://www.tensorflow.org/)
  - **scikit-learn:** [https://scikit-learn.org/](https://scikit-learn.org/)

**Strengths:**
- Fast inference
- Can learn from historical data
- Interpretable models possible

**Weaknesses:**
- Requires labeled training data
- May not generalize to new conditions
- Limited by training data quality

---

### **2.2 Neural Network Architectures**

#### **Graph Neural Networks (GNNs)**
- **Concept:** Uses graph structures to represent the routing problem, with nodes as positions and edges as possible moves.
- **Complexity:** O(V + E) per layer (V = vertices, E = edges)
- **Accuracy:** High (for graph-structured problems)
- **Speed:** Medium
- **Memory:** Medium

**Implementation:**
- **No confirmed maritime routing implementations found in literature as of 2025**
- **Frameworks:**
  - **PyTorch Geometric:** [https://github.com/pyg-team/pytorch_geometric](https://github.com/pyg-team/pytorch_geometric)
  - **DGL (Deep Graph Library):** [https://github.com/dmlc/dgl](https://github.com/dmlc/dgl)

**Strengths:**
- Naturally represents routing as a graph problem
- Can capture spatial relationships
- Works well with irregular grids

**Weaknesses:**
- Requires graph construction
- Computationally expensive for large graphs
- Limited maritime applications

**References:**
- **PyTorch Geometric:** [https://pytorch-geometric.readthedocs.io](https://pytorch-geometric.readthedocs.io)
- **DGL:** [https://www.dgl.ai/](https://www.dgl.ai/)

---

#### **Convolutional Neural Networks (CNNs)**
- **Concept:** Uses convolutional layers to process gridded weather data (e.g., GRIB files).
- **Complexity:** O(H × W × C) per layer (H = height, W = width, C = channels)
- **Accuracy:** High (for image-like data)
- **Speed:** Medium
- **Memory:** High

**Implementation:**
- **Weather prediction:** Various applications
- **Frameworks:**
  - **PyTorch:** [https://pytorch.org/](https://pytorch.org/)
  - **TensorFlow:** [https://www.tensorflow.org/](https://www.tensorflow.org/)

**Strengths:**
- Good for processing gridded weather data
- Can capture spatial patterns
- Translation equivariant

**Weaknesses:**
- Requires fixed-size inputs
- Not naturally suited for pathfinding
- Computationally expensive

---

#### **Transformer Networks**
- **Concept:** Uses self-attention to capture long-range dependencies in weather data.
- **Complexity:** O(n²) per layer (n = sequence length)
- **Accuracy:** Very High (with sufficient data)
- **Speed:** Slow
- **Memory:** Very High

**Implementation:**
- **Emerging in weather prediction**
- **Frameworks:**
  - **Hugging Face Transformers:** [https://github.com/huggingface/transformers](https://github.com/huggingface/transformers)

**Strengths:**
- Captures long-range dependencies
- State-of-the-art in many domains
- Flexible architecture

**Weaknesses:**
- Very computationally expensive
- Requires large amounts of data
- Difficult to train
- No maritime routing applications yet

**References:**
- **Original Paper:** Vaswani et al. (2017) - "Attention Is All You Need" [https://arxiv.org/abs/1706.03762](https://arxiv.org/abs/1706.03762)
- **Hugging Face:** [https://huggingface.co/](https://huggingface.co/)

---

## **⚖️ 3. Algorithm Comparison**

| **Algorithm** | **Accuracy** | **Speed** | **Memory** | **Uncertainty Handling** | **Multi-Objective** | **Implementation** |
|--------------|-------------|-----------|------------|-------------------------|--------------------|-------------------|
| Isochrone | Medium-High | Medium | Medium | No | No | Easy |
| Dijkstra | Medium | Fast | Low-Medium | No | No | Easy |
| A* | High | Very Fast | Medium | No | No | Medium |
| MCTS | High | Slow | High | Yes | Yes | Hard |
| MDP | High | Medium-Slow | High | Yes | Yes | Hard |
| Genetic Algorithm | Medium-High | Slow | Medium | No | Yes | Medium |
| PSO | Medium-High | Medium | Low | No | Yes | Easy |
| ACO | Medium-High | Medium-Slow | Medium | No | Yes | Medium |
| Deep RL | High | Fast (inference) | Very High | Yes | Yes | Very Hard |
| Imitation Learning | High | Fast | High | Limited | Yes | Hard |
| Supervised Learning | Medium-High | Fast | Medium | No | Limited | Medium |
| GNN | High | Medium | Medium | Limited | Yes | Hard |
| CNN | High | Medium | High | No | Limited | Medium |
| Transformer | Very High | Slow | Very High | Limited | Limited | Very Hard |

---

## **🎯 4. Algorithm Selection Guide**

### **4.1 For Low Data Routing (v1)**
| **Requirement** | **Recommended Algorithm** | **Rationale** |
|---------------|---------------------------|--------------|
| V1 routing engine | **Isochrone** | Standard sailing algorithm; naturally handles polar diagrams and time-dependent weather |
| Fast inference | Isochrone | Low computational cost; runs on Raspberry Pi |
| Low memory | Isochrone | Minimal memory footprint with pruning |
| Edge deployment | Isochrone | Raspberry Pi compatible; <500 MB RAM, <1 minute |

**V1 architecture:** Isochrone planner + adaptive forecast acquisition + uncertainty-aware cost function. Do not replace the routing engine with an AI algorithm. The neural network serves the router (compression, vessel model, data-request policy), it does not replace it.

### **4.2 For Learned Compression (Level 3)**
| **Requirement** | **Recommended Approach** | **Rationale** |
|---------------|---------------------------|--------------|
| Task-oriented weather compression | Neural encoder-decoder | Train to minimize routing degradation, not reconstruction error |
| Vessel-conditioned representation | Transformer (weather + vessel state) | Attention over temporal sequence; learns what weather matters for this boat |
| Adaptive data requests | Value-per-byte scoring (ML or heuristic) | Information-theoretic control loop: spend bandwidth where it changes the decision |

### **4.3 For Joint Encoder-Router (Level 4 — target)**
| **Requirement** | **Recommended Approach** | **Rationale** |
|---------------|---------------------------|--------------|
| Joint compression + routing | Encoder + decoder-router, trained end-to-end | Encoder and router co-adapt; no weather reconstruction needed |
| Latent-space routing | JEPA-style prediction in embedding space | Predict routing-relevant features, not raw weather; avoids wasting capacity on unpredictable details |
| Planning inference | DL router (<60 min) + isochrone refinement (seconds) | Relaxed inference time for planning; isochrone fallback for tactical |
| Safety fallback | Isochrone refinement + probabilistic safety check | Deterministic safety layer catches DL failures |

See [Research Ideas](research-ideas.md) for connections to JEPA, Information Bottleneck, and World Models.

### **4.4 For Safety (v1)**
| **Requirement** | **Recommended Approach** | **Rationale** |
|---------------|---------------------------|--------------|
| Storm/ Gale identification | Threshold-based + forecast disagreement | Conventional meteorological thresholds are well-validated |
| Extreme wind/wave exposure | Probabilistic (P(Wind > threshold | forecast)) | Minimize probability of exposure, not undefined "99% safety" |
| Rapidly deteriorating conditions | Temporal derivative of forecast fields | Detect acceleration in wind/wave trends |

**Deferred to future modules:** rogue-wave prediction, iceberg detection (requires satellite imagery — shore-side), microburst prediction (requires high-res wind data). See [Objectives](objectives.md).

---

## **🔧 5. Implementation Considerations**

### **5.1 Computational Constraints**
| **Device** | **CPU** | **RAM** | **Power** | **Constraints** |
|-----------|---------|---------|-----------|----------------|
| Raspberry Pi 4 | 4x 1.8GHz | 4-8 GB | 3-7W | Limited CPU, memory |
| Raspberry Pi 5 | 4x 2.4GHz | 4-8 GB | 5-15W | Better than Pi 4 |
| Jetson Nano | 4x 1.43GHz | 4 GB | 5-10W | GPU available |
| Typical Laptop | 4-8 core | 8-16 GB | 30-60W | No constraints |

### **5.2 Time Constraints**
| **Use Case** | **Max Inference Time** | **Recommended Algorithm** |
|-------------|------------------------|---------------------------|
| Real-time routing | <1 minute | A*, Isochrone, Imitation Learning |
| Pre-voyage planning | 5-10 minutes | MCTS, MDP, Genetic Algorithm |
| Offline optimization | 30+ minutes | MCTS, MDP, Deep RL |

### **5.3 Memory Constraints**
| **Memory Limit** | **Recommended Algorithm** |
|-----------------|---------------------------|
| <500 MB | A*, Dijkstra, Isochrone |
| <1 GB | A*, Isochrone, PSO, ACO |
| <2 GB | MCTS (small), Genetic Algorithm |
| >2 GB | MCTS, MDP, Deep RL |

---

## **📈 6. Performance Metrics**

### **6.1 Data Efficiency Metrics**
| **Metric** | **Definition** | **Target** | **Measurement** |
|-----------|---------------|------------|----------------|
| Degradation curve | Route quality vs. daily data budget (1 KB to unlimited) | Characterized | Route quality at each budget level |
| Daily Data Usage | Total bytes downloaded per day | <10 KB/day (target operating point) | Monitor all downloads |
| Per-Update Usage | Bytes per forecast update | Report at each budget level | Measure each fetch |

### **6.2 Route Quality Metrics (reported separately)**
| **Metric** | **Definition** | **Target** | **Measurement** |
|-----------|---------------|------------|----------------|
| ETA difference | (ETA_compressed - ETA_full) / ETA_full | Report at each budget level | Compare to full-information reference route |
| Distance difference | (dist_compressed - dist_full) / dist_full | Report at each budget level | Compare routes |
| Max wind exposure | Difference in maximum wind encountered | Report | Compare routes |
| Decision divergence | Did the compressed system choose the same tactical decision? | Report | Compare route topology |
| Geographic route divergence | Distance between the two trajectories | Report | Compare paths |

### **6.3 Safety Metrics (probabilistic)**
| **Metric** | **Definition** | **Target** | **Measurement** |
|-----------|---------------|------------|----------------|
| P(Wind > threshold) | Probability of exceeding wind threshold given forecast | Minimize | Ensemble-based estimation |
| P(H_s > threshold) | Probability of exceeding wave height threshold | Minimize | Ensemble-based estimation |
| Forecast disagreement | Spread across ensemble members along route | Report | Ensemble statistics |

### **6.4 Computational Efficiency Metrics**
| **Metric** | **Definition** | **Target** | **Measurement** |
|-----------|---------------|------------|----------------|
| Inference Time | Time to calculate route | <1 minute | Wall-clock time |
| Memory Usage | RAM consumed | <500 MB | Monitor RAM |
| CPU Usage | CPU load | <50% | Monitor CPU |
| Battery Impact | Energy consumed | <1 Wh | Measure power draw |
| Offline operation | Route with no cloud dependency after receiving weather data | Required | Cold-start test |

---

## **🔗 7. Key References**

### **7.1 Algorithm References**
- **Isochrone Method:** [https://github.com/dakk/libweatherrouting](https://github.com/dakk/libweatherrouting)
- **Dijkstra's Algorithm:** [https://www.cs.utexas.edu/users/EWD/transcriptions/EWD01xx/EWD136.html](https://www.cs.utexas.edu/users/EWD/transcriptions/EWD01xx/EWD136.html)
- **A* Algorithm:** [https://ieeexplore.ieee.org/document/4082128](https://ieeexplore.ieee.org/document/4082128)
- **MCTS:** [https://hal.inria.fr/inria-00118122/document](https://hal.inria.fr/inria-00118122/document)
- **MDP:** [https://en.wikipedia.org/wiki/Markov_decision_process](https://en.wikipedia.org/wiki/Markov_decision_process)
- **Genetic Algorithms:** [https://en.wikipedia.org/wiki/Genetic_algorithm](https://en.wikipedia.org/wiki/Genetic_algorithm)
- **PSO:** [https://ieeexplore.ieee.org/document/488968](https://ieeexplore.ieee.org/document/488968)
- **ACO:** [https://www.sciencedirect.com/science/article/pii/0925231296000359](https://www.sciencedirect.com/science/article/pii/0925231296000359)

### **7.2 AI/ML References**
- **Deep RL (Latinopoulos et al., 2025):** [https://www.mdpi.com/2077-1312/13/5/902](https://www.mdpi.com/2077-1312/13/5/902)
- **CMR Berkeley (2024):** Business overview, not a routing algorithm [https://cmr.berkeley.edu/2024/12/utilizing-ai-for-maritime-transport-optimization/](https://cmr.berkeley.edu/2024/12/utilizing-ai-for-maritime-transport-optimization/)
- **Imitation Learning (Anderson et al., 2022):** [https://dl.acm.org/doi/10.1145/3581792.3581803](https://dl.acm.org/doi/10.1145/3581792.3581803)
- **Transformers:** [https://arxiv.org/abs/1706.03762](https://arxiv.org/abs/1706.03762)
- **GNNs:** [https://pytorch-geometric.readthedocs.io](https://pytorch-geometric.readthedocs.io)
- **Ensemble routing:** [https://doi.org/10.3390/jmse9121434](https://doi.org/10.3390/jmse9121434)

### **7.3 Maritime-Specific References**
- **libweatherrouting (Python):** [https://github.com/dakk/libweatherrouting](https://github.com/dakk/libweatherrouting)
- **GWeatherRouting (Python/GTK):** [https://github.com/dakk/gweatherrouting](https://github.com/dakk/gweatherrouting)
- **qtVlm (free, proprietary):** [https://sourceforge.net/projects/qtvlm/](https://sourceforge.net/projects/qtvlm/)
- **OpenCPN Weather Routing plugin (open source):** [https://opencpn.org/OpenCPN/plugins/weatherroute.html](https://opencpn.org/OpenCPN/plugins/weatherroute.html)
- **SIMROUTE (open source, A* + CMEMS):** [https://github.com/ManelGrifoll/SIMROUTE](https://github.com/ManelGrifoll/SIMROUTE)
- **SailGrib WR:** [https://www.sailgrib.com](https://www.sailgrib.com)
- **PredictWind:** [https://www.predictwind.com](https://www.predictwind.com)
- **StormGeo AWT:** [https://www.stormgeo.com](https://www.stormgeo.com)
- **Isochrone improvement (Chalmers, 2024):** [https://www.tandfonline.com/doi/full/10.1080/17445302.2024.2329011](https://www.tandfonline.com/doi/full/10.1080/17445302.2024.2329011)

---

## **🎯 8. Improvement Opportunities**

### **8.1 Data Efficiency Improvements**
| **Opportunity** | **Current State** | **Potential Improvement** | **Feasibility** | **Challenge** |
|---------------|------------------|--------------------------|-----------------|---------------|
| Region Filtering | Already exists (Saildocs, NOMADS Grib Filter, SailGrib WR) | Route-aware dynamic selection | High | Dynamic corridor prediction |
| Variable Filtering | Already exists (Saildocs, PredictWind) | Vessel-conditioned variable selection | High | Determining needed variables per boat |
| Temporal Downsampling | Partial (some tools) | Adaptive resolution based on forecast horizon | High | Accuracy tradeoff |
| Delta Encoding | Not used in sailing tools | 70-90% reduction for sequential updates | **Medium** | Stateful connection over SBD; message loss makes delta useless without base. Needs application-layer reliability. |
| Custom Binary Encoding | Not used | 60-80% on top of GRIB compression | Medium | Encoding design, compatibility |
| Task-Oriented Compression | Not used (novel) | Compress to preserve routing decision, not weather | Medium | Requires training data and ML pipeline |
| Ensemble Summary Compression | Not used | Download mean/spread instead of all members | Medium | Loss of tail information |
| **Combined** | N/A | **90-99% reduction vs. full global** | **Medium** | Techniques interact; empirical curve needed, not naive multiplication |

> **Note:** The baseline for comparison matters. Full global GRIB downloads are 500-800 MB. Tools like Saildocs and PredictWind already achieve 100-500 KB/day through region and variable filtering. The project's <10 KB/day target is a 10-50x improvement over the best existing filtered tools, not a 1000x improvement over raw global downloads.

### **8.2 Algorithm Improvements**
| **Opportunity** | **Current State** | **Potential Improvement** | **Feasibility** | **Challenge** |
|---------------|------------------|--------------------------|-----------------|---------------|
| Isochrone (v1) | Standard in production tools | Add uncertainty-aware cost function | High | Multi-objective cost design |
| Adaptive data acquisition | Not used | Value-per-byte request policy | High | Scoring function design |
| Learned vessel performance | Exists commercially (PredictWind AI Polars) | Personalized polar from on-water observations | Medium | Data collection, online learning |
| Vessel-conditioned compression | Not used (novel) | Compress weather based on what matters for this boat | Medium | Training data, model design |

### **8.3 Safety Improvements (v1 scope)**
| **Opportunity** | **Current State** | **Potential Improvement** | **Feasibility** | **Challenge** |
|---------------|------------------|--------------------------|-----------------|---------------|
| Storm detection | Basic threshold-based | Threshold + forecast disagreement | High | Data quality |
| Extreme wind/wave exposure | Basic | Probabilistic P(threshold | forecast) | High | Ensemble data access |
| Rapidly deteriorating conditions | Not widely used | Temporal derivative monitoring | High | Forecast resolution |

**Deferred (future modules):** rogue wave prediction, iceberg detection (shore-side satellite imagery), microburst prediction (high-res wind data). See [Objectives](objectives.md).

---

## **⚠️ 9. Challenges**

### **9.1 Technical Challenges**
1. **Data Efficiency vs. Accuracy:**
   - Higher compression = lower accuracy
   - Need to find optimal tradeoff

2. **Edge Deployment:**
   - Limited CPU and memory
   - Battery constraints
   - Need for real-time performance

3. **Uncertainty Handling:**
   - Weather forecasts are uncertain
   - Need to propagate uncertainty through routing
   - Computationally expensive

4. **Multi-Objective Optimization:**
   - Speed vs. safety vs. comfort vs. fuel
   - No clear optimal solution
   - Requires careful weighting

5. **Real-World Validation:**
   - Difficult to validate without real sailing
   - Historical data may not capture all conditions
   - Requires extensive testing

### **9.2 Data Challenges**
1. **Data Access:**
   - Some data sources require registration
   - Some require payment
   - Some have usage limits

2. **Data Quality:**
   - Weather forecasts have errors
   - Resolution may be insufficient
   - Update frequency may be too low

3. **Data Size:**
   - Full GRIB files are large (100-1000 KB)
   - Need for compression and filtering
   - Satellite bandwidth limitations

### **9.3 Algorithm Challenges**
1. **Computational Complexity:**
   - Some algorithms are too slow for real-time
   - Need for optimization and approximation

2. **Memory Usage:**
   - Some algorithms require too much memory
   - Need for memory-efficient implementations

3. **Training Data:**
   - AI/ML algorithms require large amounts of data
   - Maritime routing data is limited
   - Need for synthetic data generation

4. **Validation:**
   - Difficult to validate without real-world testing
   - Need for comprehensive benchmarking

---

**© 2026 LowDataSailing**  
**Last Updated:** September 6, 2026  
**Version:** 1.0
