"""Degradation configuration: how a weather package is constrained.

The configuration is a model, not a pipeline step: the harness
(``harness.degrade``) applies it, the staircase searches over it, and the
operational simulation records it per planning cycle.
"""

from __future__ import annotations

from dataclasses import dataclass

WIND_VARIABLES = ("u10", "v10")


@dataclass(frozen=True)
class DegradeConfig:
    """How a weather package is constrained to a byte budget."""

    spatial_stride: int = 1
    """Take every N-th lat/lon point (1 = full resolution)."""

    temporal_stride: int = 1
    """Take every N-th forecast step (1 = full resolution)."""

    bits: int = 16
    """Quantization depth per value (32 = no quantization)."""

    keep_variables: tuple[str, ...] = WIND_VARIABLES
    """Variables kept in the package; the rest are dropped."""

    def fidelity_score(self) -> tuple[float, ...]:
        """Higher is better: prefer small strides and many bits.

        Lexicographic priority — spatial resolution first (routing decisions
        are local), then temporal resolution, then bits. A deliberate total
        order over "highest-fidelity", documented in the spec (§5).
        """
        return (1.0 / self.spatial_stride, 1.0 / self.temporal_stride, self.bits / 32.0)
