"""Code provenance: identifying the version that produced an artifact.

Both run directories (``reporting.artifacts``) and data packs
(``weather_data.pack``) record the code version that created them, so a
result can always be traced back to the commit that produced it.
"""

from __future__ import annotations

import subprocess


def git_sha() -> str:
    """Short commit hash of the working tree, or "unknown" outside git."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
