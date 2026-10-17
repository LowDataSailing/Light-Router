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
