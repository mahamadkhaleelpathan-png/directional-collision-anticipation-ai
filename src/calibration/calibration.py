"""Load/save/validate the speed-calibration configuration.

Calibration lives in ``config/speed_calibration.json`` inside the project
(STEP 31: the project's existing config mechanism). While uncalibrated the
system exposes no ``km/h`` values at all - speed reports
``NOT_CALIBRATED``. Calibration is optional and never required to open the
dashboard.

World coordinate convention chosen for the manual UI::

    A (0,0) ----------- B (width_m, 0)
      |                    |
      |      ROAD          |      Z ahead
      |                    |
    D (0, depth_m) ------ C (width_m, depth_m)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from config.settings import settings
from src.calibration.ground import GroundPlane, HomographyGroundPlane, ImagePoint, WorldPoint


@dataclass
class Calibration:
    """Immutable-ish snapshot of the calibration state for one analysis run."""

    ground_plane: GroundPlane
    image_points: List[ImagePoint] = None  # type: ignore[assignment]
    world_points_meters: List[WorldPoint] = None  # type: ignore[assignment]

    @property
    def configured(self) -> bool:
        return bool(self.ground_plane.calibrated)

    def to_status_dict(self) -> dict:
        d = self.ground_plane.to_status_dict()
        d["image_points"] = self.image_points
        d["world_points_meters"] = self.world_points_meters
        return d


def _calibration_path() -> Path:
    return Path(settings.SPEED_CALIBRATION_FILE)


def load_calibration() -> Calibration:
    """Load and validate the configured calibration (or none)."""
    empty_plane = GroundPlane(
        source="none",
        calibrated=False,
        note="SPEED N/A - CALIBRATION REQUIRED. Click CALIBRATE SPEED to map 4 road "
             "points to known world dimensions.",
    )
    path = _calibration_path()
    if not path.is_file():
        return Calibration(ground_plane=empty_plane, image_points=[], world_points_meters=[])
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return Calibration(
            ground_plane=GroundPlane(
                source="none",
                calibrated=False,
                note=f"SPEED CALIBRATION ERROR: cannot read config ({exc}).",
            ),
            image_points=[],
            world_points_meters=[],
        )

    if not data.get("enabled"):
        return Calibration(ground_plane=empty_plane, image_points=[], world_points_meters=[])

    image_points = [tuple(map(float, p)) for p in data.get("image_points", [])]
    world_points = [tuple(map(float, p)) for p in data.get("world_points_meters", [])]

    plane = HomographyGroundPlane(
        source=str(data.get("source", "manual")),
        image_points=image_points,
        world_points_meters=world_points,
    )
    if len(image_points) != 4 or len(world_points) != 4:
        plane.calibrated = False
        plane.note = "SPEED CALIBRATION ERROR: exactly 4 image and 4 world points required"
    return Calibration(ground_plane=plane, image_points=image_points, world_points_meters=world_points)


def save_calibration(
    image_points: List[Tuple[float, float]],
    width_m: float,
    depth_m: float,
    source: str = "manual-hud",
) -> Calibration:
    """Validate and persist a 4-point calibration.

    World points are assigned from the entered road dimensions as
    documented in the module docstring. Raises ValueError when invalid.
    """
    if len(image_points) != 4:
        raise ValueError("Exactly 4 image points are required (A, B, C, D).")
    try:
        width = float(width_m)
        depth = float(depth_m)
    except (TypeError, ValueError):
        raise ValueError("Road width and distance must be numbers.")  # noqa: BLE001
    if width <= 0 or depth <= 0:
        raise ValueError("Road width and distance must be positive meters.")
    if not (0.5 <= width <= 20.0):
        raise ValueError("Road width looks unusual (expected roughly 0.5-20 m).")
    if not (1.0 <= depth <= 200.0):
        raise ValueError("Road distance looks unusual (expected roughly 1-200 m).")

    plane = HomographyGroundPlane(
        source=source,
        image_points=list(image_points),
        world_points_meters=[
            (0.0, 0.0),
            (width, 0.0),
            (width, depth),
            (0.0, depth),
        ],
    )
    if not plane.calibrated:
        raise ValueError(f"Invalid calibration: {plane.note}")

    path = _calibration_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "enabled": True,
        "source": source,
        "image_points": [[float(x), float(y)] for x, y in image_points],
        "world_points_meters": [[float(x), float(z)] for x, z in plane.world_points_meters],
        "_world_layout": "A=(0,0), B=(width,0), C=(width,depth), D=(0,depth); X=lateral, Z=ahead",
        "_resolution_hint": "click points on the source video's native resolution",
    }
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)
    return Calibration(
        ground_plane=plane,
        image_points=list(image_points),
        world_points_meters=list(plane.world_points_meters),
    )


def clear_calibration() -> Calibration:
    """Remove the calibration file and return the uncalibrated state."""
    path = _calibration_path()
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
    return load_calibration()


def get_calibration_path() -> Path:
    return _calibration_path()