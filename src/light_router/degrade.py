"""Degradation pipeline: constrain a weather package to a byte budget.

Order fixed by the Benchmark Harness spec:
1. spatial downsampling (stride on lat/lon)
2. temporal downsampling (stride on time)
3. variable filtering (keep wind only)
4. quantization (uniform b-bit per variable)
5. lossless compression (zlib on the quantized payload — measured bytes)
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np

from .weather import WeatherGrid

WIND_VARIABLES = ("u10", "v10")


@dataclass(frozen=True)
class DegradeConfig:
    spatial_stride: int = 1
    temporal_stride: int = 1
    bits: int = 16
    keep_variables: tuple[str, ...] = WIND_VARIABLES

    def fidelity_score(self) -> tuple[float, ...]:
        """Higher is better: prefer small strides and many bits."""
        return (1.0 / self.spatial_stride, 1.0 / self.temporal_stride, self.bits / 32.0)


def degrade(grid: WeatherGrid, config: DegradeConfig) -> WeatherGrid:
    """Apply the pipeline to a grid and return the degraded grid."""
    if config.spatial_stride < 1 or config.temporal_stride < 1:
        raise ValueError("strides must be >= 1")
    if not 1 <= config.bits <= 32:
        raise ValueError("bits must be in 1..32")

    times = grid.times[:: config.temporal_stride]
    lats = grid.lats[:: config.spatial_stride]
    lons = grid.lons[:: config.spatial_stride]
    if len(times) < 1 or len(lats) < 2 or len(lons) < 2:
        raise ValueError("degradation leaves an unusable grid; reduce the strides")
    data = {}
    for name in config.keep_variables:
        if name not in grid.data:
            continue
        arr = grid.data[name]
        sub = arr[
            :: config.temporal_stride,
            :: config.spatial_stride,
            :: config.spatial_stride,
        ]
        data[name] = _quantize(sub, config.bits)
    return WeatherGrid(times=times, lats=lats, lons=lons, data=data)


def _quantize(arr: np.ndarray, bits: int) -> np.ndarray:
    """Uniform quantization to `bits` bits per value, returned as float32
    (dequantized), which is what the router consumes."""
    if bits >= 32:
        return arr.astype(np.float32)
    levels = 2**bits - 1
    vmin = float(np.min(arr))
    vmax = float(np.max(arr))
    if vmax <= vmin:
        return np.full_like(arr, vmin, dtype=np.float32)
    scaled = np.round((arr - vmin) / (vmax - vmin) * levels)
    return (scaled / levels * (vmax - vmin) + vmin).astype(np.float32)


def package_size(grid: WeatherGrid, config: DegradeConfig) -> int:
    """Compressed byte size of the degraded package (header + zlib payload).

    The payload is the quantized integer code array, which is what would
    actually be transmitted; the header carries the scales/offsets.
    """
    payload = b""
    for name in config.keep_variables:
        if name not in grid.data:
            continue
        arr = grid.data[name]
        sub = arr[
            :: config.temporal_stride,
            :: config.spatial_stride,
            :: config.spatial_stride,
        ]
        if config.bits >= 32:
            codes = sub.astype(np.float32).tobytes()
        else:
            levels = 2**config.bits - 1
            vmin, vmax = float(np.min(sub)), float(np.max(sub))
            if vmax <= vmin:
                codes = np.zeros(sub.shape, dtype=np.uint64).tobytes()
            else:
                codes = (
                    np.round((sub - vmin) / (vmax - vmin) * levels)
                    .astype(np.uint64)
                    .tobytes()
                )
        payload += codes
    compressed = zlib.compress(payload, level=9)
    # header: per-variable scale/offset (2 float64) + axes (float64 each)
    header = 16 * len(config.keep_variables)
    header += 8 * (
        len(grid.times[:: config.temporal_stride])
        + len(grid.lats[:: config.spatial_stride])
        + len(grid.lons[:: config.spatial_stride])
    )
    return header + len(compressed)


def candidate_configs() -> list[DegradeConfig]:
    """Search space for the staircase, ordered by decreasing fidelity."""
    configs = []
    for spatial in (1, 2, 3, 4, 6, 8, 12, 16):
        for temporal in (1, 2, 3, 4, 6):
            for bits in (32, 16, 12, 10, 8, 6, 4):
                configs.append(DegradeConfig(spatial, temporal, bits))
    configs.sort(key=lambda c: c.fidelity_score(), reverse=True)
    return configs


def best_config_for_budget(
    grid: WeatherGrid, budget_bytes: int | None
) -> DegradeConfig | None:
    """Highest-fidelity configuration whose package fits the budget.

    None means the budget cannot be met even by the most degraded config.
    """
    for config in candidate_configs():
        if budget_bytes is None or package_size(grid, config) <= budget_bytes:
            return config
    return None
