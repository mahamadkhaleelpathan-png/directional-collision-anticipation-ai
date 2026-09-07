"""Road-plane geometry for speed estimation.

The only honest way to turn image motion into real-world speed is to
project image points onto the road plane in metric units. That requires
an explicit calibration (a homography from known image points to known
world meters). Without calibration the module deliberately refuses to
produce ``km/h`` values.

Coordinate conventions
----------------------
* Image points: ``(u, v)`` in pixels, origin top-left of the video frame.
* World/ground points: ``(X, Z)`` meters on a flat road plane directly
  below the camera. ``Z`` is the distance ahead of the ego vehicle along
  the road, ``X`` is the lateral offset. This keeps the forward axis
  explicit so longitudinal (approach) speed can be separated from lateral
  motion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

ImagePoint = Tuple[float, float]  # (u, v) pixels
WorldPoint = Tuple[float, float]  # (X, Z) meters


def bottom_center(bbox: Tuple[float, float, float, float]) -> ImagePoint:
    """Approximate ground-contact point of a vehicle from its bounding box.

    The bottom-center of the box is where the object touches the road
    plane, which is the point that obeys the planar (homography) mapping.
    """
    x1, y1, x2, y2 = bbox
    width = max(x2 - x1, 1.0)
    return (float((x1 + x2) / 2.0), float(y2))


@dataclass
class GroundPlane:
    """Base class: maps image pixels to road-plane meters.

    ``calibrated`` is the single source of truth the speed estimator uses
    to decide whether km/h output is legitimate.
    """

    source: str = "none"
    calibrated: bool = False
    note: str = ""

    def image_to_ground(self, u: float, v: float) -> Optional[WorldPoint]:
        """Return ground-plane ``(X, Z)`` metres for a pixel ``(u, v)``.

        Returns None when the point maps outside the calibrated region
        (for example above the horizon) or when there is no calibration.
        """
        raise NotImplementedError

    def ground_distance_m(self, a: WorldPoint, b: WorldPoint) -> float:
        """Euclidean distance between two ground-plane points, in meters."""
        return math.hypot(b[0] - a[0], b[1] - a[1])

    def to_status_dict(self) -> dict:
        return {
            "configured": self.calibrated,
            "source": self.source,
            "label": "CALIBRATED" if self.calibrated else "NOT CALIBRATED",
            "note": self.note,
        }


@dataclass
class HomographyGroundPlane(GroundPlane):
    """Road-plane homography derived from 4 known image->world points.

    ``cv2`` computes the exact projective transform for four
    corresponding points; it is validated numerically so an invalid
    calibration never silently produces garbage.
    """

    width: int = 0
    height: int = 0
    image_points: List[ImagePoint] = None  # type: ignore[assignment]
    world_points_meters: List[WorldPoint] = None  # type: ignore[assignment]
    _H: Optional[np.ndarray] = None

    def __post_init__(self) -> None:
        if not self._valid_points():
            self.calibrated = False
            self._H = None
            self.note = "SPEED CALIBRATION ERROR: 4 non-degenerate points required"
            return
        try:
            H = cv2.getPerspectiveTransform(
                np.array(self.image_points, dtype=np.float32),
                np.array(self.world_points_meters, dtype=np.float32),
            )
        except cv2.error as exc:  # noqa: BLE001
            self.calibrated = False
            self._H = None
            self.note = f"SPEED CALIBRATION ERROR: {exc}"
            return
        if H is None or not np.all(np.isfinite(H)) or abs(float(np.linalg.det(H))) < 1e-12:
            self.calibrated = False
            self._H = None
            self.note = "SPEED CALIBRATION ERROR: transformation is numerically invalid"
            return
        invertible = np.all(np.isfinite(np.linalg.inv(H)))
        if not invertible:
            self.calibrated = False
            self._H = None
            self.note = "SPEED CALIBRATION ERROR: transformation cannot be inverted"
            return
        self._H = H.astype(np.float64)
        self.calibrated = True
        self.note = "CALIBRATED SPEED ESTIMATE (road-plane homography)"

    def _valid_points(self) -> bool:
        if not self.image_points or not self.world_points_meters:
            return False
        if len(self.image_points) != 4 or len(self.world_points_meters) != 4:
            return False
        # No duplicated image points.
        pts = np.array(self.image_points, dtype=np.float64)
        for i in range(4):
            for j in range(i + 1, 4):
                if np.linalg.norm(pts[i] - pts[j]) < 1e-6:
                    return False
        # Image polygon must have non-zero area (not collinear).
        if abs(self._polygon_area(pts)) < 1.0:
            return False
        # World dimensions must be positive.
        world = np.array(self.world_points_meters, dtype=np.float64)
        if not np.all(np.isfinite(world)):
            return False
        spreads = world.max(axis=0) - world.min(axis=0)
        if not (spreads[0] > 0.0 and spreads[1] > 0.0):
            return False
        return True

    @staticmethod
    def _polygon_area(pts: np.ndarray) -> float:
        x, y = pts[:, 0], pts[:, 1]
        return float(0.5 * abs(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)))

    def image_to_ground(self, u: float, v: float) -> Optional[WorldPoint]:
        if self._H is None:
            return None
        p = np.array([float(u), float(v), 1.0], dtype=np.float64)
        out = self._H @ p
        if abs(out[2]) < 1e-9:
            return None
        X = float(out[0] / out[2])
        Z = float(out[1] / out[2])
        if not (np.isfinite(X) and np.isfinite(Z)):
            return None
        # Bound the mapping to a sane neighbourhood of the calibrated region
        # (a few hundred meters ahead) so far/above-horizon pixels never
        # produce absurd velocities. This is a guard, not a calibration.
        if Z < -200.0 or Z > 500.0 or abs(X) > 400.0:
            return None
        return (X, Z)