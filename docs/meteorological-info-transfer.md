# Meteorological Information Transfer: State of the Art

*Comprehensive overview of current methods, protocols, and technologies for transmitting weather data to maritime applications*

---

## **📡 1. Data Sources**

### **1.1 Global Weather Models**

#### **NOAA (National Oceanic and Atmospheric Administration)**
- **Website:** [https://www.noaa.gov](https://www.noaa.gov)
- **Data Portal:** [https://www.ncdc.noaa.gov](https://www.ncdc.noaa.gov)
- **GRIB Data:** [https://nomads.ncep.noaa.gov](https://nomads.ncep.noaa.gov)
- **Models:**
  - **GFS (Global Forecast System):** ~13 km (0.25°) resolution for first 192 hours, degrading to ~2.5° after 192h; 384-hour (16-day) forecast; runs 4x daily (00Z, 06Z, 12Z, 18Z); 3-hourly output intervals for first 192h, 12-hourly after
    - **Documentation:** [https://www.nco.ncep.noaa.gov/pmb/products/gfs/](https://www.nco.ncep.noaa.gov/pmb/products/gfs/)
    - **Data Access:** [https://nomads.ncep.noaa.gov/dods/gfs_0p25_1hr](https://nomads.ncep.noaa.gov/dods/gfs_0p25_1hr)
    - **Server-Side Subsetting:** [NOMADS Grib Filter](https://nomads.ncep.noaa.gov/info.php?page=gribfilter) — request specific variables, levels, regions, and forecast hours; only the requested bytes are returned
    - **File Size:** Full global all-variable all-hours forecast: **500-800 MB**; single time step, wind-only (10u, 10v): ~1-2 MB compressed
  - **NAM (North American Mesoscale):** 3km-12km resolution, 84-hour forecast, 6-hourly updates
    - **Documentation:** [https://www.nco.ncep.noaa.gov/pmb/products/nam/](https://www.nco.ncep.noaa.gov/pmb/products/nam/)
    - **Data Access:** [https://nomads.ncep.noaa.gov/dods/nam](https://nomads.ncep.noaa.gov/dods/nam)
  - **RAP (Rapid Refresh):** 13km resolution, 18-hour forecast, hourly updates
    - **Documentation:** [https://rapidrefresh.noaa.gov/](https://rapidrefresh.noaa.gov/)
    - **Data Access:** [https://nomads.ncep.noaa.gov/dods/rap](https://nomads.ncep.noaa.gov/dods/rap)
  - **HRRR (High-Resolution Rapid Refresh):** 3km resolution, 18-hour forecast, hourly updates
    - **Documentation:** [https://rapidrefresh.noaa.gov/hrrr/](https://rapidrefresh.noaa.gov/hrrr/)
    - **Data Access:** [https://nomads.ncep.noaa.gov/dods/hrrr](https://nomads.ncep.noaa.gov/dods/hrrr)

#### **ECMWF (European Centre for Medium-Range Weather Forecasts)**
- **Website:** [https://www.ecmwf.int](https://www.ecmwf.int)
- **Data Portal:** [https://apps.ecmwf.int/webapi/](https://apps.ecmwf.int/webapi/)
- **Models:**
  - **IFS (Integrated Forecast System):** 9 km (~0.1°) resolution (HRES), 15-day forecast, runs 2x daily (00Z, 12Z)
    - **Documentation:** [https://confluence.ecmwf.int/display/FCST](https://confluence.ecmwf.int/display/FCST)
    - **Data Access:** [https://data.ecmwf.int/forecasts/](https://data.ecmwf.int/forecasts/) — open data since October 1, 2025 (no registration required for core products)
    - **Open Data Info:** [https://confluence.ecmwf.int/display/DAC/ECMWF+open+data](https://confluence.ecmwf.int/display/DAC/ECMWF+open+data)
    - **File Size:** Full global all-variable all-hours forecast: **300-600 MB**; single time step, wind-only: ~0.5-1 MB compressed
  - **ERA5 (Reanalysis):** 0.25° resolution, hourly data from 1940-present
    - **Documentation:** [https://confluence.ecmwf.int/display/CKB/ERA5+data+documentation](https://confluence.ecmwf.int/display/CKB/ERA5+data+documentation)
    - **Data Access:** [https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels](https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels)

#### **UK Met Office**
- **Website:** [https://www.metoffice.gov.uk](https://www.metoffice.gov.uk)
- **Data Hub:** [https://datahub.metoffice.gov.uk](https://datahub.metoffice.gov.uk)
- **Models:**
  - **UM (Unified Model):** 0.11°-0.23° resolution, global coverage
    - **Documentation:** [https://www.metoffice.gov.uk/research/weather/science-behind/weather-models/unified-model](https://www.metoffice.gov.uk/research/weather/science-behind/weather-models/unified-model)
  - **MOGREPS (Met Office Global and Regional Ensemble Prediction System):** Ensemble forecasts
    - **Documentation:** [https://www.metoffice.gov.uk/research/weather/science-behind/weather-models/mogreps](https://www.metoffice.gov.uk/research/weather/science-behind/weather-models/mogreps)

#### **DWD (Deutscher Wetterdienst - German Weather Service)**
- **Website:** [https://www.dwd.de](https://www.dwd.de)
- **Open Data Server:** [https://opendata.dwd.de](https://opendata.dwd.de)
- **Models:**
  - **ICON (Icosahedral Nonhydrostatic):** 2.2km-13km resolution, global coverage
    - **Documentation:** [https://www.dwd.de/EN/ourservices/cdc/cdc.html](https://www.dwd.de/EN/ourservices/cdc/cdc.html)
    - **Data Access:** [https://opendata.dwd.de/weather/grib/](https://opendata.dwd.de/weather/grib/)
  - **COSMO:** 2.8km resolution, Europe-focused
    - **Documentation:** [https://www.dwd.de/EN/ourservices/cdc/cdc.html](https://www.dwd.de/EN/ourservices/cdc/cdc.html)

#### **Meteo France**
- **Website:** [https://www.meteofrance.com](https://www.meteofrance.com)
- **Data Portal:** [https://donneespubliques.meteofrance.fr](https://donneespubliques.meteofrance.fr)
- **Models:**
  - **AROME:** 1.3km-2.5km resolution, France/Europe
    - **Documentation:** [https://www.umr-cnrm.fr/spip.php?article268](https://www.umr-cnrm.fr/spip.php?article268)
  - **ARPEGE:** 0.1°-0.5° resolution, global
    - **Documentation:** [https://www.umr-cnrm.fr/spip.php?article268](https://www.umr-cnrm.fr/spip.php?article268)

#### **Infoclimat (France)**
- **Website:** [https://www.infoclimat.fr](https://www.infoclimat.fr)
- **API Documentation:** [https://api.infoclimat.fr](https://api.infoclimat.fr)
- **Data:** GRIB2 format, high-resolution models for Europe
- **Coverage:** Global data available via API
- **Access:** Requires API key (free tier available)

#### **JMA (Japan Meteorological Agency)**
- **Website:** [https://www.jma.go.jp](https://www.jma.go.jp)
- **Data:** [https://www.jma.go.jp/jma/indexe.html](https://www.jma.go.jp/jma/indexe.html)
- **Models:**
  - **GSM (Global Spectral Model):** 0.25° resolution, 84-hour forecast
  - **MSM (Mesoscale Model):** 5km resolution, Japan-focused

---

## **📦 2. Data Formats**

### **2.1 GRIB (GRIdded Binary)**
- **Standard:** WMO FM 92 GRIB Edition 1 and Edition 2
- **Documentation:** [https://www.wmo.int/pages/prog/www/WDM/Guides/Guide-binary-2.html](https://www.wmo.int/pages/prog/www/WDM/Guides/Guide-binary-2.html)
- **Specifications:** [https://www.nco.ncep.noaa.gov/pmb/docs/grib2/](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/)
- **Libraries:**
  - **wgrib2:** [https://www.cpc.ncep.noaa.gov/products/wesley/wgrib2/](https://www.cpc.ncep.noaa.gov/products/wesley/wgrib2/)
  - **pygrib:** [https://github.com/jswhit/pygrib](https://github.com/jswhit/pygrib)
  - **cfgrib:** [https://github.com/ecmwf/cfgrib](https://github.com/ecmwf/cfgrib) (Python interface, built on ecCodes)
  - **ecCodes:** [https://github.com/ecmwf/eccodes](https://github.com/ecmwf/eccodes) (ECMWF's GRIB/BUFR library; successor to the deprecated grib-api)

#### **GRIB1 vs GRIB2**
| **Feature** | **GRIB1** | **GRIB2** |
|------------|----------|----------|
| **Complexity** | Simple | Complex |
| **Data Types** | Limited | Extensive |
| **Compression** | Basic | Advanced (CCSDS, JPEG2000, PNG) |
| **File Size** | Larger | Smaller (better compression) |
| **Adoption** | Legacy | Modern standard |
| **Support** | All models | Most modern models |

#### **GRIB2 Compression Methods**
| **Method** | **Code** | **Compression Ratio** | **Lossless** | **Implementation** |
|-----------|---------|----------------------|-------------|-------------------|
| None | 0 | 1:1 | Yes | All |
| Complex Packing | 2 | 1.5-2:1 | Yes | All |
| Simple Packing | 51 | 2-3:1 | Yes | All |
| CCSDS | 5.41 | 3-4:1 | Yes | cfgrib, ecCodes |
| JPEG2000 | 5.42 | 4-5:1 | No | cfgrib, ecCodes |
| PNG | 5.43 | 3-4:1 | Yes | cfgrib, ecCodes |

### **2.2 NetCDF (Network Common Data Form)**
- **Website:** [https://www.unidata.ucar.edu/software/netcdf/](https://www.unidata.ucar.edu/software/netcdf/)
- **Standard:** Self-describing, machine-independent data format
- **Libraries:**
  - **netCDF4:** [https://github.com/Unidata/netcdf4-python](https://github.com/Unidata/netcdf4-python)
  - **xarray:** [https://github.com/pydata/xarray](https://github.com/pydata/xarray) (NetCDF support)
- **Advantages:**
  - Human-readable metadata
  - Easy to subset and manipulate
  - Wide tool support
- **Disadvantages:**
  - Larger file sizes than GRIB
  - Slower for large datasets

### **2.3 GeoJSON**
- **Standard:** [https://tools.ietf.org/html/rfc7946](https://tools.ietf.org/html/rfc7946)
- **Use Case:** Weather data for web applications
- **Advantages:**
  - JSON-based, easy to parse
  - Works natively in web browsers
- **Disadvantages:**
  - Very large file sizes for gridded data
  - Not efficient for numerical weather data

### **2.4 JSON (Custom Schemes)**
- **Use Case:** API responses, custom applications
- **Example:** OpenWeatherMap API ([https://openweathermap.org/api](https://openweathermap.org/api))
- **Advantages:**
  - Easy to parse
  - Human-readable
- **Disadvantages:**
  - Extremely inefficient for gridded data
  - Large file sizes

---

## **📡 3. Transfer Protocols**

### **3.1 HTTP/HTTPS**
- **Standard:** RFC 7230-7237
- **Use Case:** Most common for weather data transfer
- **Tools:**
  - **curl:** [https://curl.se/](https://curl.se/)
  - **wget:** [https://www.gnu.org/software/wget/](https://www.gnu.org/software/wget/)
  - **requests (Python):** [https://github.com/psf/requests](https://github.com/psf/requests)
- **Compression:**
  - **gzip:** [RFC 1952](https://tools.ietf.org/html/rfc1952)
  - **deflate:** [RFC 1951](https://tools.ietf.org/html/rfc1951)
  - **brotli:** [RFC 7932](https://tools.ietf.org/html/rfc7932)

### **3.2 FTP/SFTP**
- **FTP:** [RFC 959](https://tools.ietf.org/html/rfc959)
- **SFTP:** [RFC 4253](https://tools.ietf.org/html/rfc4253)
- **Use Case:** Bulk data transfer (e.g., NOAA, ECMWF)
- **Tools:**
  - **lftp:** [https://lftp.yar.ru/](https://lftp.yar.ru/)
  - **FileZilla:** [https://filezilla-project.org/](https://filezilla-project.org/)

### **3.3 Satellite-Specific Protocols**

#### **Iridium**
- **Website:** [https://www.iridium.com](https://www.iridium.com)
- **Developer Portal:** [https://developer.iridium.com](https://developer.iridium.com)
- **Protocols:**
  - **SBD (Short Burst Data):** up to 1960 bytes (MO) / 1890 bytes (MT) per message
    - **Documentation:** [https://developer.iridium.com/iridium-developer-portal/technical-resources/sbd/](https://developer.iridium.com/iridium-developer-portal/technical-resources/sbd/)
    - **Speed:** 2.4 KB/s (burst), 1.2 KB/s (sustained)
    - **Latency:** 1-2 seconds
    - **Cost:** $0.50-5.00/MB
    - **Note:** SBD is a message-based protocol, not a session. Messages are acknowledged but there is no guaranteed ordering or session state. Application-layer reliability (sequence numbers, checksums, retransmission) is required for any multi-message data transfer.
  - **RUDICS (Router-Based Unrestricted Digital Internetworking Connectivity Solution):**
    - **Documentation:** [https://developer.iridium.com/iridium-developer-portal/technical-resources/rudics/](https://developer.iridium.com/iridium-developer-portal/technical-resources/rudics/)
    - **Speed:** 2.4-100+ KB/s (depends on plan)
    - **Cost:** $1-10/MB
- **Optimization Techniques:**
  - **Message chunking:** Split large files into SBD messages
  - **Compression:** Use gzip, bzip2, or custom before transmission
  - **Delta encoding:** Only send changes
  - **Binary encoding:** More efficient than text

#### **Starlink**
- **Website:** [https://www.starlink.com](https://www.starlink.com)
- **Maritime:** [https://www.starlink.com/maritime](https://www.starlink.com/maritime)
- **Speed:** 170-300 Mbps download (typical), 20-60 Mbps upload
- **Latency:** 20-45 ms
- **Cost:** $250/month (50 GB priority) to $2,150/month (2 TB); $185/month personal plan (territorial waters only)
- **Coverage:** Global (except poles)
- **Note:** Starlink's high bandwidth makes it less relevant for ultra-low-data routing, but it is increasingly the primary connection for cruising yachts. The low-data constraint is most relevant for Iridium and HF radio backup scenarios.

#### **Inmarsat**
- **Website:** [https://www.inmarsat.com](https://www.inmarsat.com)
- **Services:**
  - **FleetBroadband:** 10-100 KB/s
  - **Fleet One:** 10-50 KB/s
  - **IsatData Pro:** 10-100 bytes per message
- **Cost:** $1-10/MB
- **Coverage:** Global

#### **Globalstar**
- **Website:** [https://www.globalstar.com](https://www.globalstar.com)
- **Speed:** 1-9.6 KB/s
- **Cost:** $0.50-2.00/MB
- **Coverage:** Global

#### **Thuraya**
- **Website:** [https://www.thuraya.com](https://www.thuraya.com)
- **Speed:** 1-444 KB/s
- **Cost:** $1-5/MB
- **Coverage:** Regional (Europe, Africa, Asia, Australia)

### **3.4 Email-Based Weather Services**

These services are the primary method used by offshore sailors for low-bandwidth weather data. They work over any email-capable connection (Iridium, HF radio, Starlink) and already implement region, variable, and time filtering server-side.

#### **Saildocs**
- **Website:** [http://www.saildocs.com](http://www.saildocs.com)
- **How it works:** Send a formatted email request to `query@saildocs.com`; receive a custom GRIB file back as an attachment
- **Example request (email subject):** `send gfs:20N,60N,160W,120W|2,2|24,48,72|WIND,WAVES`
- **Features:** Region subsetting, variable selection, time step selection, scheduled deliveries
- **Data sources:** GFS, COAMPS, NDFD, WW3, and others
- **Cost:** Free
- **Typical file size:** 2-30 KB for a regional wind/wave GRIB
- **Relevance:** Saildocs already implements the region/variable/time filtering that this project proposes as a novel improvement. The project's contribution must go beyond what Saildocs already offers.

#### **Winlink**
- **Website:** [https://www.winlink.org](https://www.winlink.org)
- **How it works:** Global radio email system for licensed amateur radio operators; uses HF/SSB radio with PACTOR modems
- **Speed:** 100-2400 bits/s depending on PACTOR version and conditions
- **Features:** Email, weather GRIB requests (via Saildocs), text forecasts, position reporting
- **Cost:** Free (requires amateur radio license)
- **File size limit:** Up to ~30 KB per message (Pactor-4); ~10 KB (Pactor-2)
- **Software:** [Airmail](https://www.winlink.org/Airmail) or [Winlink Express](https://www.winlink.org/WinlinkExpress)

#### **Sailmail**
- **Website:** [https://www.sailmail.com](https://www.sailmail.com)
- **How it works:** User-funded marine HF radio email network (no ham license required)
- **Speed:** Same as Winlink (PACTOR modems)
- **Features:** Email, weather GRIB requests (via Saildocs), limited business use
- **Cost:** ~$275/year membership
- **File size limit:** ~30 KB (Pactor-4), ~10 KB (Pactor-2)

### **3.5 HF Radio Weather Fax (WEFAX)**

- **How it works:** National weather services broadcast weather charts as facsimile images via HF radio; receivable with an HF receiver and laptop soundcard (no data subscription)
- **NOAA Schedules:** [https://www.weather.gov/media/marine/rfax.pdf](https://www.weather.gov/media/marine/rfax.pdf)
- **Coverage:** Global (NOAA, DWD, JMA, Met Service stations)
- **Cost:** Free (requires HF receiver only)
- **Data content:** Surface analysis, sea state, satellite imagery, forecast charts — as images, not digital GRIB
- **Software:** [JVComm32](http://www.jvcomm.de/), [ fldigi](https://fldigi.w1kchip.net/)
- **Relevance:** Zero bandwidth cost; complementary to GRIB-based routing as a backup and for visual situational awareness

### **3.6 Copernicus Marine Service (CMEMS)**

- **Website:** [https://marine.copernicus.eu](https://marine.copernicus.eu)
- **Data Store:** [https://data.marine.copernicus.eu](https://data.marine.copernicus.eu)
- **Data:** Ocean wave forecasts (WAM, WW3), ocean currents, sea surface temperature, salinity
- **Access:** Free, open data (requires registration for API)
- **Relevance:** Wave and current data are essential for accurate sailing routing — wind alone is insufficient. CMEMS is the primary open source for this data.
- **Use in routing:** Used by TIMEZERO, SIMROUTE, and other routing tools

---

## **🔧 4. Compression Techniques**

### **4.1 General Compression**
| **Algorithm** | **Typical Ratio** | **Speed** | **Implementation** | **Best For** |
|--------------|------------------|-----------|-------------------|-------------|
| gzip | 3-4:1 | Fast | Built-in | Text, JSON |
| bzip2 | 4-5:1 | Slow | Built-in | Text, structured data |
| xz | 5-6:1 | Very Slow | Built-in | Archives |
| zstd | 3-5:1 | Very Fast | [https://github.com/facebook/zstd](https://github.com/facebook/zstd) | General purpose |
| brotli | 4-5:1 | Medium | [https://github.com/google/brotli](https://github.com/google/brotli) | Web (HTTP) |

### **4.2 Weather-Specific Compression**

#### **Delta Encoding**
- **Concept:** Store only differences between consecutive forecasts
- **Implementation:**
  - Store previous forecast
  - Calculate difference (delta)
  - Compress delta
  - Reconstruct on client
- **Savings:** 70-90% for sequential forecasts
- **Challenges:**
  - Requires stateful connection (both sides must maintain the previous forecast state)
  - First transmission still large
  - Complex reconstruction logic
  - **Critical for this project:** Iridium SBD is a message-based protocol, not a session. If a delta message is lost, the delta is useless without the base. This requires an application-layer reliability mechanism (sequence numbers, checksums, retransmission, fallback to full snapshot). Without this, delta encoding over SBD has Medium feasibility, not High. The 70-90% savings figure assumes reliable delivery, which SBD does not guarantee natively.

#### **Region Filtering**
- **Concept:** Download only data for the area of interest
- **Implementation:**
  - Define bounding box (lat/lon)
  - Request only data within bounds
  - Dynamically adjust as needed
- **Savings:** 80-95% for route-specific data
- **Example:**
  - Full global GFS GRIB: 500-800 MB
  - Route corridor (5°x5°), wind only, 3 time steps: 25-50 KB
- **Note:** This is already implemented by Saildocs (email-based) and the NOMADS Grib Filter service (HTTP-based). The project's contribution is in optimizing the region selection dynamically based on route evolution, not in the filtering itself.

#### **Temporal Downsampling**
- **Concept:** Use lower resolution for distant forecasts
- **Implementation:**
  - 0-24h: Full resolution (0.25°)
  - 24-72h: Medium resolution (0.5°)
  - 72h+: Low resolution (1.0°)
- **Savings:** 50-80%

#### **Variable Filtering**
- **Concept:** Download only needed weather variables
- **Example Variables:**
  - Wind speed/direction (10u, 10v)
  - Pressure (prmsl)
  - Precipitation (prate)
  - Temperature (2t)
  - Waves (htsgw, wvdir)
- **Savings:** 50-80% (depending on variables needed)

#### **Custom Binary Encoding**
- **Concept:** Optimize encoding for weather data patterns
- **Techniques:**
  - Quantization: Reduce precision (e.g., 0.1 kn wind speed)
  - Bit-packing: Store values in minimal bits
  - Predictive encoding: Model-based compression
- **Savings:** 60-80% (on top of GRIB compression)

---

## **📊 5. Data Size Analysis**

### **5.1 GRIB File Sizes**

Sizes below are per single forecast time step unless otherwise noted. "Full" means all standard variables (wind, pressure, temperature, precipitation, waves) at all standard levels.

| **Resolution** | **Area** | **Variables** | **File Size (GRIB2, single time step)** | **Full forecast run (all time steps)** | **Update Frequency** |
|---------------|----------|---------------|----------------------------------------|---------------------------------------|----------------------|
| 0.25° (~28km) | Global | Wind only (10u, 10v) | 1-2 MB | 50-200 MB | 6h |
| 0.25° | Global | Wind + Pressure | 2-4 MB | 100-400 MB | 6h |
| 0.25° | Global | Full | 4-8 MB | 500-800 MB | 6h |
| 0.5° | Global | Wind only | 0.3-0.7 MB | 15-50 MB | 6h |
| 0.5° | Global | Wind + Pressure | 0.6-1.5 MB | 30-100 MB | 6h |
| 0.5° | Regional (10°x10°) | Full | 8-40 KB | 0.5-2 MB | 6h |
| 1.0° | Global | Wind only | 80-150 KB | 5-15 MB | 12h |
| 0.25° | Route corridor (5°x5°) | Wind only | 5-15 KB | 25-50 KB (3 time steps) | 6h |

**Key insight:** The difference between a full global download and a route-corridor subset is 3-4 orders of magnitude. Existing tools that download regional subsets already achieve 100-300 KB per update. The project's <10 KB/day target requires going further: aggressive variable filtering, temporal downsampling, and delta encoding on top of region filtering.

### **5.2 Typical Data Consumption**
| **Tool** | **Data Source** | **Connection** | **Resolution** | **Variables** | **Daily Usage** |
|----------|----------------|---------------|---------------|---------------|----------------|
| PredictWind (Iridium GO!) | NOAA, ECMWF | Iridium | 0.25°-0.5° | Wind, pressure | ~150 KB/day |
| PredictWind (GO! exec) | NOAA, ECMWF | Iridium | 0.25°-0.5° | Full | up to 500 KB/day |
| SailGrib WR | NOAA, Meteo France | Various | 0.25°-1.0° | Selected | 100-300 KB/day |
| qtVlm | NOAA, OpenSkiron | Various | 0.25° | Full | 500-1000 KB/day |
| Saildocs (manual request) | GFS, WW3, etc. | Email (any) | 0.5°-2.5° | Selected | 2-30 KB per request |
| StormGeo AWT | Proprietary | Various | 0.25° | Full | 500-1000+ KB/day |

**Note:** Tools like PredictWind and SailGrib WR already use region filtering and variable selection. Their 100-500 KB/day figures represent filtered regional downloads, not full global files. Saildocs can achieve even lower data usage with manual request tuning, but requires the sailor to manually specify the region, variables, and time steps — it has no intelligent route-aware optimization.

---

## **🎯 6. Optimization Opportunities**

### **6.1 For Satellite Transfer (Iridium)**
| **Technique** | **Potential Savings** | **Feasibility** | **Implementation Complexity** |
|--------------|----------------------|-----------------|-------------------------------|
| Delta Encoding | 70-90% | Medium | Medium | Not used in sailing tools |
| Region Filtering | 80-95% | High | Low |
| Temporal Downsampling | 50-80% | High | Medium |
| Variable Filtering | 50-80% | High | Low |
| Custom Binary Encoding | 60-80% | Medium | High |
| GRIB2 Compression | 20-30% | High | Low (built-in) |
| **Combined** | **90-99%** | Medium | Medium | Savings cannot be multiplied naively; techniques interact. An empirical degradation curve is needed. |

### **6.2 For Starlink/High-Bandwidth**
| **Technique** | **Potential Savings** | **Feasibility** |
|--------------|----------------------|-----------------|
| Region Filtering | 80-95% | High |
| Variable Filtering | 50-80% | High |
| GRIB2 Compression | 20-30% | High |
| **Combined** | **85-95%** | High |

---

## **🔗 7. Key Standards and References**

### **7.1 Standards**
- **WMO GRIB2:** [https://www.wmo.int/pages/prog/www/WDM/Guides/Guide-binary-2.html](https://www.wmo.int/pages/prog/www/WDM/Guides/Guide-binary-2.html)
- **NOAA GRIB2 Documentation:** [https://www.nco.ncep.noaa.gov/pmb/docs/grib2/](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/)
- **ECMWF GRIB2 Guide:** [https://confluence.ecmwf.int/display/GRIB](https://confluence.ecmwf.int/display/GRIB)
- **NetCDF Standard:** [https://www.unidata.ucar.edu/software/netcdf/docs/](https://www.unidata.ucar.edu/software/netcdf/docs/)
- **GeoJSON Standard:** [https://tools.ietf.org/html/rfc7946](https://tools.ietf.org/html/rfc7946)

### **7.2 Data Sources**
- **NOAA NOMADS:** [https://nomads.ncep.noaa.gov](https://nomads.ncep.noaa.gov)
- **NOMADS Grib Filter (server-side subsetting):** [https://nomads.ncep.noaa.gov/info.php?page=gribfilter](https://nomads.ncep.noaa.gov/info.php?page=gribfilter)
- **ECMWF Open Data:** [https://data.ecmwf.int](https://data.ecmwf.int) (free since October 2025)
- **Copernicus Climate Data Store:** [https://cds.climate.copernicus.eu](https://cds.climate.copernicus.eu)
- **Copernicus Marine Service (CMEMS):** [https://marine.copernicus.eu](https://marine.copernicus.eu) (waves, currents)
- **DWD Open Data:** [https://opendata.dwd.de](https://opendata.dwd.de)
- **Meteo France Open Data:** [https://donneespubliques.meteofrance.fr](https://donneespubliques.meteofrance.fr)
- **Infoclimat API:** [https://api.infoclimat.fr](https://api.infoclimat.fr)

### **7.3 Satellite Services**
- **Iridium Developer:** [https://developer.iridium.com](https://developer.iridium.com)
- **Starlink Maritime:** [https://www.starlink.com/maritime](https://www.starlink.com/maritime)
- **Inmarsat:** [https://www.inmarsat.com](https://www.inmarsat.com)
- **Globalstar:** [https://www.globalstar.com](https://www.globalstar.com)

### **7.4 Email-Based and HF Radio Services**
- **Saildocs:** [http://www.saildocs.com](http://www.saildocs.com)
- **Winlink:** [https://www.winlink.org](https://www.winlink.org)
- **Sailmail:** [https://www.sailmail.com](https://www.sailmail.com)
- **NOAA Weather Fax Schedules:** [https://www.weather.gov/media/marine/rfax.pdf](https://www.weather.gov/media/marine/rfax.pdf)

### **7.5 Compression and GRIB Libraries**
- **zstd:** [https://github.com/facebook/zstd](https://github.com/facebook/zstd)
- **brotli:** [https://github.com/google/brotli](https://github.com/google/brotli)
- **ecCodes (GRIB/BUFR, replaces grib-api):** [https://github.com/ecmwf/eccodes](https://github.com/ecmwf/eccodes)
- **cfgrib:** [https://github.com/ecmwf/cfgrib](https://github.com/ecmwf/cfgrib)
- **pygrib:** [https://github.com/jswhit/pygrib](https://github.com/jswhit/pygrib)

---

**© 2026 LowDataSailing**  
**Last Updated:** September 6, 2026  
**Version:** 1.0
