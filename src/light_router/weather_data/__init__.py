"""Weather data: acquisition clients, loaders, and the shared downloader.

Every client produces (or helps produce) the canonical CF-compliant xarray
Dataset (Compatibility rule 1): a new data source is a new client, nothing
downstream changes. ``downloader`` holds the shared HTTP machinery
(retries, rate limits); ``grib`` loads local GRIB2 files; ``pack`` is the
self-contained experiment input format.
"""
