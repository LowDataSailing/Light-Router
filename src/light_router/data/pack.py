"""Experiment data packs: self-contained scenario data, rerunnable at will.

A pack is one directory holding everything the operational simulation
needs to rerun an experiment with **zero network access and no GRIB
toolchain** (no ecCodes, no cfgrib — the core numpy + xarray install
suffices):

- ``truth.npz`` — the measured-weather grid (ERA5) on the absolute clock
- ``cycle_<init_hour:04d>.npz`` — one GFS run per planning cycle, time =
  lead hours since its own initialization
- ``pack.json`` — manifest: schema version, scenario, provenance, and a
  sha256 per file

Files are compressed numpy ``.npz`` archives; loading rebuilds the canonical
CF Dataset, validated by ``grid_from_dataset``. Checksums are verified on
load, so a pack cannot silently rot. Heavy raw caches (GRIB, API JSON) stay
on the machine that fetched them — the pack is the portable artifact.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr

from ..artifacts import git_sha
from ..simulate import ForecastCycle

PACK_MANIFEST = "pack.json"
TRUTH_NAME = "truth.npz"
SCHEMA_VERSION = 1


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_npz(path: Path, weather: xr.Dataset) -> None:
    np.savez_compressed(
        path,
        time=np.asarray(weather["time"].values, dtype=np.float64),
        latitude=np.asarray(weather["latitude"].values, dtype=np.float64),
        longitude=np.asarray(weather["longitude"].values, dtype=np.float64),
        u10=np.asarray(weather["u10"].values, dtype=np.float32),
        v10=np.asarray(weather["v10"].values, dtype=np.float32),
    )


def _read_npz(path: Path) -> xr.Dataset:
    with np.load(path) as data:
        return xr.Dataset(
            data_vars={
                "u10": (
                    ("time", "latitude", "longitude"),
                    np.asarray(data["u10"], dtype=np.float32),
                ),
                "v10": (
                    ("time", "latitude", "longitude"),
                    np.asarray(data["v10"], dtype=np.float32),
                ),
            },
            coords={
                "time": ("time", np.asarray(data["time"], dtype=np.float64)),
                "latitude": (
                    "latitude",
                    np.asarray(data["latitude"], dtype=np.float64),
                ),
                "longitude": (
                    "longitude",
                    np.asarray(data["longitude"], dtype=np.float64),
                ),
            },
        )


def cycle_file_name(init_hour: float) -> str:
    """Pack file name of the forecast cycle at ``init_hour``."""
    return f"cycle_{int(init_hour):04d}.npz"


def write_pack(
    pack_dir: Path,
    *,
    scenario: str,
    truth: xr.Dataset,
    cycles: list[ForecastCycle],
    source: dict[str, object],
) -> Path:
    """Write a data pack: truth + one file per forecast cycle + manifest."""
    pack_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}

    truth_path = pack_dir / TRUTH_NAME
    _write_npz(truth_path, truth)
    files[TRUTH_NAME] = _sha256(truth_path)

    cycle_entries: list[dict[str, object]] = []
    for cycle in sorted(cycles, key=lambda c: c.init_hour):
        name = cycle_file_name(cycle.init_hour)
        path = pack_dir / name
        _write_npz(path, cycle.weather)
        files[name] = _sha256(path)
        cycle_entries.append({"file": name, "init_hour": cycle.init_hour})

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "scenario": scenario,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_version": git_sha(),
        "source": source,
        "truth_file": TRUTH_NAME,
        "cycles": cycle_entries,
        "files_sha256": files,
    }
    (pack_dir / PACK_MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    return pack_dir


def load_pack(
    pack_dir: Path, *, verify: bool = True
) -> tuple[xr.Dataset, list[ForecastCycle]]:
    """Load a data pack: (truth, cycles), checksums verified by default."""
    manifest = json.loads((pack_dir / PACK_MANIFEST).read_text())
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"pack schema version {manifest['schema_version']} is not "
            f"supported (expected {SCHEMA_VERSION})"
        )

    for name, expected in manifest["files_sha256"].items():
        path = pack_dir / name
        if not path.exists():
            raise FileNotFoundError(f"pack file missing: {path}")
        if verify and _sha256(path) != expected:
            raise ValueError(f"pack file corrupted (sha256 mismatch): {path}")

    truth = _read_npz(pack_dir / manifest["truth_file"])
    cycles = [
        ForecastCycle(
            init_hour=float(entry["init_hour"]),
            weather=_read_npz(pack_dir / str(entry["file"])),
        )
        for entry in manifest["cycles"]
    ]
    return truth, cycles
