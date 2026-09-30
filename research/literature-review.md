# Literature Review

## Current Solutions

### Commercial Routing Tools

| Tool | Algorithm | Data Source | Data Usage | AI/ML | Offline | Open Source |
|------|-----------|-------------|------------|-------|--------|------------|
| PredictWind | Isochrone | NOAA, ECMWF | ~150 KB/day (Iridium GO!), up to 500 KB/day (GO! exec) | No | Yes (mobile app) | No |
| SailGrib WR | Isochrone | NOAA, Meteo France | 100-300 KB/day | No | Yes | No |
| StormGeo AWT | Proprietary | Proprietary | 500-1000+ KB/day | Not publicly documented | No | No |
| qtVlm | Isochrone | NOAA, OpenSkiron | 500-1000 KB/day | No | Yes | No (free, proprietary) |

> **Note:** Data usage figures represent filtered regional downloads, not full global GRIB files. Full global GRIB downloads are 500-800 MB. All tools listed above already implement some form of region and variable filtering.

### Open Source Projects

| Project | Language | Algorithm | Data Format | AI Support | Maturity |
|---------|----------|-----------|-------------|------------|----------|
| libweatherrouting | Python | Isochrone, modular | GRIB1/2 | Designed for extension | Medium — [github.com/dakk/libweatherrouting](https://github.com/dakk/libweatherrouting) |
| OpenCPN Weather Routing plugin | C++ | Isochrone | GRIB | No | High — [opencpn.org](https://opencpn.org/OpenCPN/plugins/weatherroute.html) |
| SIMROUTE | Python/MATLAB | A* | CMEMS (NetCDF) | No | Medium — [github.com/ManelGrifoll/SIMROUTE](https://github.com/ManelGrifoll/SIMROUTE) |
| GWeatherRouting | Python/GTK | Isochrone | GRIB | No | Medium — [github.com/dakk/gweatherrouting](https://github.com/dakk/gweatherrouting) |

### Low-Bandwidth Weather Data Services

| Service | Delivery Method | Data Selection | Cost | Typical Size |
|---------|----------------|---------------|------|--------------|
| Saildocs | Email (Iridium, Winlink, Sailmail) | Region + variable + time step | Free | 2-30 KB per request |
| NOMADS Grib Filter | HTTP | Region + variable + level + forecast hour | Free | Varies by selection |
| Winlink | HF radio (PACTOR modem) | Via Saildocs | Free (ham license) | Up to ~30 KB/message |
| Sailmail | HF radio (PACTOR modem) | Via Saildocs | ~$275/year | Up to ~30 KB/message |
| NOAA WEFAX | HF radio (fax) | Preset charts | Free | N/A (image, no data cost) |

> Saildocs already implements server-side region, variable, and time filtering. The project's contribution must go beyond manual filtering: route-aware dynamic selection, task-oriented compression, and delta encoding between updates.

### Academic Research

| Approach | Authors/Source | Algorithm | Data Efficiency | Sailing-Specific | Real-World Testing |
|----------|---------------|-----------|-----------------|-----------------|-------------------|
| Deep RL | Latinopoulos et al. (2025, JMSE) | Actor-Critic | Medium | No (commercial shipping) | Yes (AIS data) |
| AI routing for sailing | Anderson et al. (2022, ACM) | Imitation + RL | Medium | Yes | Limited |
| Ensemble routing | Multiple (Ocean Eng., JMSE) | Various + ensemble forecasts | Low (E× data) | No (shipping) | Some |
| Isochrone improvement | Chalmers (2024) | 3DMI, pruning strategies | N/A | No (ship routing) | Simulated |
| 3D Modified Isochrone | Various | 3DMI with floating grid | N/A | No (ship routing) | Simulated |
| AI in maritime (overview) | Pannell & Munoz (2024, CMR Berkeley) | N/A (business article) | N/A | No | N/A |

## Gaps

### Data Efficiency
- **Existing best:** Saildocs at 2-30 KB per manual request; PredictWind at ~150 KB/day automated
- **Project target:** <10 KB/day with route-aware automation
- **Gap:** 10-50x improvement over best existing filtered tools; requires delta encoding, adaptive resolution, and intelligent variable selection

### Extreme Event Prediction
- No commercial sailing tool offers rogue wave or microburst detection
- [StormGeo AWT](https://www.stormgeo.com) offers iceberg detection at enterprise level only
- Academic research on extreme event detection exists but is not sailing-specific

### Ensemble-Based Probabilistic Routing
- No sailing tool uses ensemble forecasts for probabilistic routing
- Research exists for commercial shipping ([Ocean Engineering](https://doi.org/10.3390/jmse9121434), [JMSE](https://www.mdpi.com/2077-1312/13/5/902)) but not for sailing
- Opportunity: download ensemble summary statistics (mean, spread, percentiles) instead of all members

### Edge Deployment
- Most tools require desktop or mobile environments
- Target: Raspberry Pi compatible with <500 MB RAM, <60 min planning inference

## References

- [PredictWind](https://www.predictwind.com) / [Offshore app tips](https://help.predictwind.com/en/articles/11085388-offshore-app-tips-and-tricks)
- [qtVlm](https://sourceforge.net/projects/qtvlm/) ([license info](https://www.meltemus.com/index.php/en/forum/qtvlm-application/93-software-license), not open source)
- [libweatherrouting](https://github.com/dakk/libweatherrouting)
- [OpenCPN Weather Routing](https://opencpn.org/OpenCPN/plugins/weatherroute.html)
- [SIMROUTE](https://github.com/ManelGrifoll/SIMROUTE) (published in Ocean Engineering)
- [Saildocs](http://www.saildocs.com)
- [Latinopoulos et al. (2025)](https://www.mdpi.com/2077-1312/13/5/902)
- [Anderson et al. (2022)](https://dl.acm.org/doi/10.1145/3581792.3581803)
- [Chalmers isochrone study (2024)](https://www.tandfonline.com/doi/full/10.1080/17445302.2024.2329011)
- [Ensemble routing (JMSE 2021)](https://doi.org/10.3390/jmse9121434)
