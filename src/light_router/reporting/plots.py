"""Run plots: the more visual the better.

Three charts per run (matplotlib, optional dependency group ``plot``, lazy
import, Agg backend — no display needed):

1. all tracks color-coded by budget on a wind-field underlay
2. degradation curves per metric vs budget (log-x)
3. package size vs fidelity
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from light_router.routing import Route
from light_router.simulation.simulate import PassageResult
from light_router.harness.staircase import StaircaseResult


def _require_pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot

        return pyplot
    except ImportError as exc:  # pragma: no cover - exercised via importorskip
        raise ImportError(
            "plots require the optional 'plot' dependency group: uv sync --group plot"
        ) from exc


def plot_tracks(
    out_path: Path,
    tracks: dict[str, Route],
    weather: xr.Dataset | None = None,
    title: str = "Routes by budget",
) -> None:
    """Chart (a): tracks color-coded by budget on a wind-field underlay."""
    plt = _require_pyplot()
    fig, ax = plt.subplots(figsize=(8, 8))

    if weather is not None and "u10" in weather and "v10" in weather:
        u = weather["u10"].isel(time=0).values
        v = weather["v10"].isel(time=0).values
        speed = np.hypot(u, v)
        lon2d, lat2d = np.meshgrid(
            weather["longitude"].values, weather["latitude"].values
        )
        stride = max(1, max(speed.shape) // 30)
        contour = ax.contourf(lon2d, lat2d, speed, levels=15, cmap="Blues", alpha=0.6)
        fig.colorbar(contour, ax=ax, label="wind speed (m/s), t=0")
        ax.quiver(
            lon2d[::stride, ::stride],
            lat2d[::stride, ::stride],
            u[::stride, ::stride],
            v[::stride, ::stride],
            color="0.4",
            scale=120,
            width=0.002,
            alpha=0.6,
        )

    cmap = plt.get_cmap("viridis")
    n = max(len(tracks) - 1, 1)
    for i, (label, route) in enumerate(tracks.items()):
        color = "black" if label == "reference" else cmap(i / n)
        ax.plot(
            route.lon,
            route.lat,
            color=color,
            linewidth=1.2 + 1.2 * (label == "reference"),
            label=label,
        )
    if tracks:
        first = next(iter(tracks.values()))
        ax.plot(first.lon[0], first.lat[0], "g^", ms=8, label="start")

    ax.set_xlabel("longitude (deg E)")
    ax.set_ylabel("latitude (deg N)")
    ax.set_title(title)
    ax.legend(fontsize=7, loc="best")
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_degradation(out_path: Path, result: StaircaseResult) -> None:
    """Chart (b): degradation curves per metric vs budget (log-x)."""
    plt = _require_pyplot()
    rows = [r for r in result.rows if r.budget_bytes is not None]
    budgets = np.array([r.budget_bytes for r in rows], dtype=float)
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    panels = [
        ("ETA difference (%)", [r.metrics.eta_diff_pct for r in rows]),
        ("distance difference (%)", [r.metrics.distance_diff_pct for r in rows]),
        ("VMG difference (kt)", [r.metrics.vmg_diff_kt for r in rows]),
        (
            "geographic divergence (nm)",
            [r.metrics.geographic_divergence_nm for r in rows],
        ),
    ]
    for ax, (label, values) in zip(axes.flat, panels):
        ax.plot(budgets, values, "o-")
        ax.set_xscale("log")
        ax.set_ylabel(label)
        ax.grid(True, alpha=0.3)
    for ax in axes[-1]:
        ax.set_xlabel("budget (bytes)")
    fig.suptitle("Route-quality degradation vs data budget")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_size_fidelity(out_path: Path, result: StaircaseResult) -> None:
    """Chart (c): package size vs fidelity (spatial / temporal stride, bits)."""
    plt = _require_pyplot()
    rows = result.rows
    x = np.arange(len(rows))
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(x - 0.2, [r.spatial_stride for r in rows], 0.4, label="spatial stride")
    ax1.bar(x + 0.2, [r.temporal_stride for r in rows], 0.4, label="temporal stride")
    ax1.set_yscale("log")
    ax1.set_ylabel("stride (log)")
    ax1.set_xticks(x)
    ax1.set_xticklabels([r.budget for r in rows], rotation=45, ha="right")

    ax2 = ax1.twinx()
    ax2.plot(x, [r.bits for r in rows], "o-", color="tab:red", label="bits")
    ax2.set_ylabel("quantization bits", color="tab:red")

    ax3 = ax1.twinx()
    ax3.spines["right"].set_position(("outward", 50))
    ax3.plot(
        x, [r.package_bytes for r in rows], "s-", color="tab:green", label="package"
    )
    ax3.set_ylabel("package bytes", color="tab:green")
    ax3.set_yscale("log")

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    h3, l3 = ax3.get_legend_handles_labels()
    ax1.legend(h1 + h2 + h3, l1 + l2 + l3, fontsize=8)
    ax1.set_title("Package size vs fidelity configuration")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def write_plots(run_dir: Path, result: StaircaseResult, weather: xr.Dataset) -> None:
    """Write the three charts into the run directory."""
    tracks: dict[str, Route] = {"reference": result.reference}
    tracks.update({row.budget: row.route for row in result.rows})
    plot_tracks(run_dir / "plot_tracks.png", tracks, weather)
    plot_degradation(run_dir / "plot_degradation.png", result)
    plot_size_fidelity(run_dir / "plot_size_fidelity.png", result)


def plot_passage_budget(out_path: Path, results: list[PassageResult]) -> None:
    """Operational chart: actual passage time vs per-cycle data budget."""
    plt = _require_pyplot()
    unlimited = next((r for r in results if r.budget_bytes is None), None)
    rows = [r for r in results if r.budget_bytes is not None]
    fig, ax = plt.subplots(figsize=(8, 5))
    if rows:
        budgets = np.array([r.budget_bytes for r in rows], dtype=float)
        hours = np.array([r.passage_hours for r in rows], dtype=float)
        ax.plot(budgets, hours, "o-")
        ax.set_xscale("log")
    if unlimited is not None:
        ax.axhline(
            unlimited.passage_hours,
            color="black",
            linestyle="--",
            label=f"unlimited data ({unlimited.passage_hours:.1f} h)",
        )
    ax.set_xlabel("data budget per forecast cycle (bytes, log)")
    ax.set_ylabel("actual passage time (h)")
    ax.set_title("Passage time vs bandwidth budget (measured weather)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def write_operational_plots(
    run_dir: Path, results: list[PassageResult], truth: xr.Dataset
) -> None:
    """Write the operational charts: actual tracks on the truth wind, budget curve."""
    from light_router.harness.staircase import budget_label

    tracks = {budget_label(r.budget_bytes): r.as_route() for r in results}
    plot_tracks(
        run_dir / "plot_tracks.png",
        tracks,
        truth,
        title="Actual tracks by budget (measured wind underlay)",
    )
    plot_passage_budget(run_dir / "plot_passage_budget.png", results)
