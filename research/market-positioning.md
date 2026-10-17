# Market Positioning

## Market Size
- Professional Racing: 500-1000 teams
- Offshore Cruising: 10,000-50,000 boats
- Research Vessels: 500-1000 vessels

## Competitors

| Tool | Data Usage | AI/ML | Offline | Open Source |
|------|------------|-------|--------|------------|
| [PredictWind](https://www.predictwind.com) | ~150 KB/day (Iridium GO!) | No | Yes (mobile) | No |
| SailGrib WR | 100-300 KB/day | No | Yes | No |
| [StormGeo AWT](https://www.stormgeo.com) | 500-1000+ KB/day | Not documented | No | No |
| [qtVlm](https://sourceforge.net/projects/qtvlm/) | 500-1000 KB/day | No | Yes | No (free, proprietary) |
| [OpenCPN Weather Routing](https://opencpn.org/OpenCPN/plugins/weatherroute.html) | Varies | No | Yes | Yes |
| [Saildocs](http://www.saildocs.com) | 2-30 KB/request (manual) | No | Yes (email) | No |

## Target Segments

### Primary
- Solo/offshore sailors with unreliable or expensive satellite bandwidth
- Offshore racers with limited satellite bandwidth
- Long-distance cruisers with cost-sensitive data usage

### Secondary
- Autonomous boat developers: same value-per-byte problem, different regulatory requirements
- Research vessels: remote operations with intermittent connectivity

## Differentiation
- Data efficiency: target <10 KB/day vs. best existing filtered tools at ~150 KB/day (PredictWind) to ~30 KB/request (Saildocs, manual)
- Route-aware automation: Saildocs requires manual region/variable specification; Light Router automates this
- Task-oriented compression: compress to preserve routing decisions, not weather fidelity
- Edge-optimized: Raspberry Pi compatible, low power, offline operation
- Open source: MIT License
