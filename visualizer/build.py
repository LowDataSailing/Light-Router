#!/usr/bin/env python3
"""Build the static run visualizer site from ``runs/`` and ``data/packs/``.

For every run directory (a directory containing ``manifest.json`` and at
least one track/route GeoJSON) this emits into ``--out`` (default
``visualizer/dist``):

    dist/
      index.html                  experiment list (generated)
      assets/                     viewer assets, copied from ``assets/``
      <scenario>/<timestamp>/
        index.html                the viewer page (template copy)
        run.json                  manifest + track index + wind availability
        wind.json                 downsampled evolving truth wind (optional)
        tracks/<name>.geojson     copied track files

The viewer itself is pure static HTML/JS (see ``assets/app.js``); this
script only prepares data. Wind frames are subsampled to
``--frame-hours`` (default 6 h) and the grid to ``--grid-stride``
(default 2) to keep pages small.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "assets"

WIND_VARIABLES = ("u10", "v10")


def sanitize(value):
    """Replace NaN/inf with None: bare NaN is invalid JSON and browsers
    reject it in JSON.parse (the run artifacts contain NaN pads)."""
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, value: object) -> None:
    write_text(path, json.dumps(sanitize(value), allow_nan=False))


def write_text(path: Path, text: str) -> None:
    """Write a file world-readable: the nginx container serves dist/ as
    another uid, and editors/tools may create 0600 sources."""
    path.write_text(text)
    path.chmod(0o644)


def find_pack(manifest: dict, packs_dir: Path) -> Path | None:
    """Locate the data pack holding the evolving truth field for a run."""
    source = manifest.get("source", {})
    pack = source.get("pack")
    if pack:
        candidate = Path(pack)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        if (candidate / "truth.npz").exists():
            return candidate
    # Fallback: match packs by scenario start date.
    start_date = source.get("start_date")
    if start_date and packs_dir.is_dir():
        for pack_json in sorted(packs_dir.glob("*/pack.json")):
            try:
                meta = json.loads(pack_json.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if meta.get("source", {}).get("start_date") == start_date:
                if (pack_json.parent / "truth.npz").exists():
                    return pack_json.parent
    return None


def export_wind(pack_dir: Path, out_dir: Path, frame_hours: float, grid_stride: int) -> dict:
    """Downsample the pack truth field into ``wind.json``; return its index entry."""
    truth = np.load(pack_dir / "truth.npz")
    time = np.asarray(truth["time"], dtype=float)
    lat = np.asarray(truth["latitude"], dtype=float)
    lon = np.asarray(truth["longitude"], dtype=float)

    dt = float(time[1] - time[0]) if len(time) > 1 else 1.0
    t_stride = max(1, int(round(frame_hours / dt)))
    t_idx = np.arange(0, len(time), t_stride)

    fields = {}
    for name in WIND_VARIABLES:
        if name not in truth:
            raise SystemExit(f"pack {pack_dir} truth.npz missing {name}")
        data = np.asarray(truth[name], dtype=np.float32)
        data = data[t_idx][:, ::grid_stride, ::grid_stride]
        fields[name] = np.round(data, 1)

    wind = {
        "frame_hours": float(time[t_idx[1]] - time[t_idx[0]]) if len(t_idx) > 1 else frame_hours,
        "times_h": [round(float(t), 1) for t in time[t_idx]],
        "lats": [round(float(v), 3) for v in lat[::grid_stride]],
        "lons": [round(float(v), 3) for v in lon[::grid_stride]],
        "u": fields["u10"].tolist(),
        "v": fields["v10"].tolist(),
    }
    write_json(out_dir / "wind.json", wind)
    return {
        "file": "wind.json",
        "frame_hours": wind["frame_hours"],
        "n_frames": len(wind["times_h"]),
        "grid": [len(wind["lats"]), len(wind["lons"])],
    }


def export_run(run_dir: Path, out_dir: Path, packs_dir: Path, frame_hours: float, grid_stride: int) -> dict | None:
    """Export one run directory; return its index entry (or None to skip)."""
    try:
        manifest = json.loads((run_dir / "manifest.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  skip {run_dir.name}: {exc}", file=sys.stderr)
        return None

    geojsons = sorted(run_dir.glob("*.geojson"))
    if not geojsons:
        print(f"  skip {run_dir.name}: no track geojson", file=sys.stderr)
        return None

    run_out = out_dir / manifest["scenario"] / run_dir.name
    (run_out / "tracks").mkdir(parents=True, exist_ok=True)

    tracks = []
    for src in geojsons:
        feature = json.loads(src.read_text())
        write_json(run_out / "tracks" / src.name, feature)
        props = feature.get("properties", {})
        tracks.append(
            {
                "name": props.get("name", src.stem),
                "file": f"tracks/{src.name}",
                "reached": props.get("reached"),
                "eta_hours": props.get("eta_hours"),
                "distance_nm": props.get("distance_nm"),
            }
        )

    wind = None
    pack_dir = find_pack(manifest, packs_dir)
    if pack_dir is not None:
        try:
            wind = export_wind(pack_dir, run_out, frame_hours, grid_stride)
            print(f"  wind: {wind['n_frames']} frames from {pack_dir.name}")
        except Exception as exc:  # noqa: BLE001 - wind is optional, never fatal
            print(f"  wind unavailable: {exc}", file=sys.stderr)
    else:
        print("  wind unavailable: no matching data pack")

    run_index = {
        "manifest": manifest,
        "tracks": tracks,
        "wind": wind,
    }
    write_json(run_out / "run.json", run_index)
    write_text(run_out / "index.html", (ASSETS / "run.html").read_text())
    for p in run_out.rglob("*"):
        p.chmod(0o755 if p.is_dir() else 0o644)

    return {
        "scenario": manifest["scenario"],
        "run": run_dir.name,
        "created_at": manifest.get("created_at"),
        "code_version": manifest.get("code_version"),
        "source_type": manifest.get("source", {}).get("type"),
        "start": manifest.get("route", {}).get("start"),
        "finish": manifest.get("route", {}).get("finish"),
        "has_wind": wind is not None,
        "tracks": tracks,
        "path": f"{manifest['scenario']}/{run_dir.name}/",
    }


def write_experiments_index(out_dir: Path, entries: list[dict]) -> None:
    cards = []
    for e in sorted(entries, key=lambda x: x["created_at"] or "", reverse=True):
        budgets = " · ".join(
            f"{t['name']}: {t['eta_hours']:.0f}h" if t.get("eta_hours") is not None else f"{t['name']}: —"
            for t in e["tracks"]
        )
        cards.append(
            f"<a class='card' href='{e['path']}'>"
            f"<h2>{e['scenario']} <span class='run-id'>{e['run']}</span></h2>"
            f"<p class='meta'>{e['created_at']} · code {e['code_version']} · {e['source_type']}"
            f"{' · wind' if e['has_wind'] else ' · no wind'}</p>"
            f"<p class='budgets'>{budgets}</p></a>"
        )
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Light-Router experiments</title>"
        "<link rel='stylesheet' href='assets/style.css'></head><body>"
        "<h1>Light-Router experiments</h1>"
        "<div class='cards'>" + "".join(cards) + "</div></body></html>"
    )
    write_text(out_dir / "index.html", html)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "runs")
    parser.add_argument("--packs-dir", type=Path, default=REPO_ROOT / "data" / "packs")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "dist")
    parser.add_argument("--frame-hours", type=float, default=6.0)
    parser.add_argument("--grid-stride", type=int, default=2)
    args = parser.parse_args()

    # Clear the contents in place, never the dist root itself: the docker
    # bind mount anchors to the root directory's inode, and rmtree+mkdir
    # would leave the container serving a deleted directory.
    if args.out.exists():
        for child in args.out.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        args.out.mkdir(parents=True)
    args.out.chmod(0o755)
    assets_out = args.out / "assets"
    shutil.copytree(ASSETS, assets_out)
    for copied in assets_out.rglob("*"):
        copied.chmod(0o755 if copied.is_dir() else 0o644)

    entries = []
    for run_dir in sorted(args.runs_dir.glob("*/*")):
        if not (run_dir / "manifest.json").exists():
            continue
        print(f"{run_dir.relative_to(args.runs_dir)}:")
        entry = export_run(run_dir, args.out, args.packs_dir, args.frame_hours, args.grid_stride)
        if entry is not None:
            entries.append(entry)

    write_experiments_index(args.out, entries)
    print(f"{len(entries)} experiment(s) -> {args.out}")


if __name__ == "__main__":
    main()
