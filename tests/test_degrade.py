import numpy as np
import pytest

from light_router.degrade import (
    DegradeConfig,
    best_config_for_budget,
    candidate_configs,
    degrade,
    package_size,
)
from light_router.synthetic import trade_wind_field


@pytest.fixture
def grid():
    lats = np.arange(10.0, 20.01, 0.25)
    lons = np.arange(-30.0, -14.99, 0.25)
    times = np.arange(0.0, 49.0, 3.0)
    return trade_wind_field(lats, lons, times)


def test_degrade_reduces_grid_size(grid):
    config = DegradeConfig(spatial_stride=2, temporal_stride=2, bits=8)
    degraded = degrade(grid, config)
    assert len(degraded.lats) == len(grid.lats[::2])
    assert len(degraded.times) == len(grid.times[::2])
    assert degraded.variables == ["u10", "v10"]


def test_degrade_preserves_field_statistics(grid):
    degraded = degrade(
        grid, DegradeConfig(spatial_stride=1, temporal_stride=1, bits=16)
    )
    assert np.allclose(degraded.data["u10"], grid.data["u10"], atol=0.05)


def test_quantization_error_grows_with_fewer_bits(grid):
    full = degrade(grid, DegradeConfig(bits=16)).data["u10"]
    coarse = degrade(grid, DegradeConfig(bits=4)).data["u10"]
    err_full = np.max(np.abs(full - grid.data["u10"]))
    err_coarse = np.max(np.abs(coarse - grid.data["u10"]))
    assert err_coarse > err_full


def test_package_size_monotonic_in_strides(grid):
    base = package_size(
        grid, DegradeConfig(spatial_stride=1, temporal_stride=1, bits=16)
    )
    coarser = package_size(
        grid, DegradeConfig(spatial_stride=2, temporal_stride=1, bits=16)
    )
    coarser_t = package_size(
        grid, DegradeConfig(spatial_stride=1, temporal_stride=2, bits=16)
    )
    fewer_bits = package_size(
        grid, DegradeConfig(spatial_stride=1, temporal_stride=1, bits=8)
    )
    assert coarser < base
    assert coarser_t < base
    assert fewer_bits < base


def test_package_size_is_honest_bytes(grid):
    size = package_size(
        grid, DegradeConfig(spatial_stride=4, temporal_stride=2, bits=8)
    )
    n_values = 2 * len(grid.times[::2]) * len(grid.lats[::4]) * len(grid.lons[::4])
    assert size < n_values  # zlib must actually compress the payload
    assert size > 100  # not empty


def test_best_config_unlimited_is_full_fidelity(grid):
    config = best_config_for_budget(grid, None)
    assert config is not None
    assert config.spatial_stride == 1
    assert config.temporal_stride == 1
    assert config.bits == 32


def test_best_config_respects_budget(grid):
    budget = package_size(
        grid, DegradeConfig(spatial_stride=2, temporal_stride=1, bits=8)
    )
    config = best_config_for_budget(grid, budget)
    assert config is not None
    assert package_size(grid, config) <= budget


def test_best_config_none_when_budget_impossible(grid):
    assert best_config_for_budget(grid, 10) is None


def test_candidate_configs_ordered_by_fidelity():
    configs = candidate_configs()
    scores = [c.fidelity_score() for c in configs]
    assert scores == sorted(scores, reverse=True)
