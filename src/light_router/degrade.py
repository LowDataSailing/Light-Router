"""Degradation pipeline: constrain a weather package to a byte budget.

Order fixed by the Benchmark Harness spec:
1. spatial downsampling (stride on lat/lon)
2. temporal downsampling (stride on time)
3. variable filtering (keep wind only)
4. quantization (uniform b-bit per variable)
5. lossless compression (zlib on the quantized payload — measured bytes)
"""

from __future__ import annotations

import json
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
        """Higher is better: prefer small strides and many bits.

        Lexicographic priority — spatial resolution first (routing decisions
        are local), then temporal resolution, then bits. A deliberate total
        order over "highest-fidelity", documented in the spec (§5).
        """
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
    data = {
        name: _quantize(sub, config.bits) for name, sub in _sliced(grid, config).items()
    }
    return WeatherGrid(times=times, lats=lats, lons=lons, data=data)


def _sliced(grid: WeatherGrid, config: DegradeConfig) -> dict[str, np.ndarray]:
    """Stride-subsampled arrays for the variables kept by the config."""
    data = {}
    for name in config.keep_variables:
        if name not in grid.data:
            continue
        arr = grid.data[name]
        data[name] = arr[
            :: config.temporal_stride,
            :: config.spatial_stride,
            :: config.spatial_stride,
        ]
    return data


def _codes(sub: np.ndarray, bits: int) -> tuple[np.ndarray, float, float]:
    """Uniform quantization of `sub` to `bits` bits.

    Returns (integer codes in 0..2^bits-1, vmin, vmax); vmin/vmax are the
    scales the receiver needs to dequantize.
    """
    vmin, vmax = float(np.min(sub)), float(np.max(sub))
    if vmax <= vmin:
        return np.zeros(sub.shape, dtype=np.uint64), vmin, vmax
    levels = 2**bits - 1
    codes = np.round((sub - vmin) / (vmax - vmin) * levels).astype(np.uint64)
    return codes, vmin, vmax


def _quantize(arr: np.ndarray, bits: int) -> np.ndarray:
    """Quantize to `bits` bits per value and dequantize back to float32,
    which is what the router consumes."""
    if bits >= 32:
        return arr.astype(np.float32)
    codes, vmin, vmax = _codes(arr, bits)
    levels = 2**bits - 1
    return (codes / levels * (vmax - vmin) + vmin).astype(np.float32)


def _pack_codes(codes: np.ndarray, bits: int) -> bytes:
    """Pack integer codes at `bits` bits per value (LSB-first, zero-padded
    to a byte boundary) — the payload that would actually be transmitted."""
    flat = codes.ravel().astype(np.uint64)
    bits_matrix = ((flat[:, None] >> np.arange(bits, dtype=np.uint64)) & 1).astype(
        np.uint8
    )
    stream = bits_matrix.ravel()
    pad = (8 - stream.size % 8) % 8
    if pad:
        stream = np.concatenate([stream, np.zeros(pad, dtype=np.uint8)])
    return np.packbits(stream).tobytes()


def package_size(grid: WeatherGrid, config: DegradeConfig) -> int:
    """Compressed byte size of the degraded package (header + zlib payload).

    The payload is the b-bit-packed quantized code array, which is what
    would actually be transmitted. The header is decodable on its own:
    a 4-byte big-endian length prefix, then a JSON document carrying the
    variable names, the bit depth and the per-variable (vmin, vmax)
    dequantization scales, then the strided time/lat/lon axes as float64.
    A receiver can reconstruct the grid from header + payload without
    any out-of-band knowledge.
    """
    sliced = _sliced(grid, config)
    payload = b""
    scales: dict[str, list[float]] = {}
    for name, sub in sliced.items():
        if config.bits >= 32:
            payload += sub.astype(np.float32).tobytes()
        else:
            codes, vmin, vmax = _codes(sub, config.bits)
            payload += _pack_codes(codes, config.bits)
            scales[name] = [vmin, vmax]
    compressed = zlib.compress(payload, level=9)
    meta = json.dumps(
        {
            "variables": sorted(sliced),
            "bits": config.bits,
            "scales": scales,
        },
        separators=(",", ":"),
    ).encode()
    header = len(meta).to_bytes(4, "big") + meta
    header += (
        grid.times[:: config.temporal_stride].astype(np.float64).tobytes()
        + grid.lats[:: config.spatial_stride].astype(np.float64).tobytes()
        + grid.lons[:: config.spatial_stride].astype(np.float64).tobytes()
    )
    return len(header) + len(compressed)


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
