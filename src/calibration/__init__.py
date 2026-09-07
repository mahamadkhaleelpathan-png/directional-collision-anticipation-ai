"""Camera calibration for metric speed estimation.

Converts image coordinates to ground-plane meters so that tracker motion
can be reported as real-world speed. Speed is ONLY reported in km/h when a
valid road-plane homography calibration exists (``config/speed_calibration.json``).
Without it the estimator refuses to produce fake ``km/h`` values.
"""

from .calibration import Calibration, clear_calibration, load_calibration, save_calibration
from .ego_motion import analyze_camera_motion
from .ground import GroundPlane, HomographyGroundPlane, bottom_center

__all__ = [
    "Calibration",
    "GroundPlane",
    "HomographyGroundPlane",
    "analyze_camera_motion",
    "bottom_center",
    "clear_calibration",
    "load_calibration",
    "save_calibration",
]