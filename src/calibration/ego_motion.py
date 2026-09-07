"""Camera-motion awareness for speed estimation.

A dashcam can be STATIC (traffic camera) or MOVING. When it moves,
object displacement in the image includes the ego motion, so relative
speeds estimated from the road plane are still valid for *relative*
approach speed but the numbers should not be presented as absolute world
speed. This module samples the first few processed frames, uses sparse
Farneback optical flow on the road area to decide whether the camera is
moving, and (when calibrated) returns a scene-flow estimate of the ego
speed so the UI can be honest instead of silent.

This module never feeds the collision/risk logic.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

from config.settings import settings
from src.calibration.ground import GroundPlane


def _downscaled_gray(frame_bgr: np.ndarray) -> Tuple[np.ndarray, float]:
    h, w = frame_bgr.shape[:2]
    scale = min(1.0, 320.0 / max(w, 1))
    if scale < 1.0:
        small = cv2.resize(frame_bgr, (int(w * scale), int(h * scale)))
    else:
        small = frame_bgr
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    return gray, scale


def analyze_camera_motion(
    frames: List[np.ndarray],
    frame_indices: Optional[List[int]] = None,
    fps: float = 30.0,
    plane: Optional[GroundPlane] = None,
) -> Tuple[bool, Optional[float]]:
    """Decide whether the camera is moving and estimate ego speed in km/h.

    Returns ``(camera_moving, ego_kmh)``. ``ego_kmh`` is only produced
    when a calibrated ground plane is available and enough motion is
    present; it is a scene-flow ESTIMATE labelled as such, never a GPS
    value.
    """
    if len(frames) < 2:
        return False, None

    moving_votes: List[bool] = []
    ego_est_mps: List[float] = []

    prev_gray, scale = _downscaled_gray(frames[0])
    for i in range(1, len(frames)):
        nxt_gray, _ = _downscaled_gray(frames[i])
        h, w = prev_gray.shape[:2]
        # Road region: lower half, central band.
        roi = prev_gray[int(h * 0.45):, int(w * 0.15):int(w * 0.85)]
        prev_roi = roi
        nxt_roi = nxt_gray[int(h * 0.45):, int(w * 0.15):int(w * 0.85)]
        flow = cv2.calcOpticalFlowFarneback(
            prev_roi,
            nxt_roi,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0,
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        samples = mag[::4, ::4]
        samples = samples.ravel()
        if samples.size == 0:
            prev_gray = nxt_gray
            continue
        med = float(np.median(samples))  # px per frame at downscaled resolution
        moving_votes.append(med > 0.45)

        dt = 1.0 / max(fps, 1e-6)
        if frame_indices and i < len(frame_indices) and i >= 1:
            df = frame_indices[i] - frame_indices[i - 1]
            if df > 0:
                dt = df / max(fps, 1e-6)

        if plane is not None and plane.calibrated and dt > 0:
            ys, xs = np.mgrid[0:h, 0:w]
            # sample in native pixel coordinates for the ground mapping
            y_native = (ys[::4, ::4] / scale).astype(np.float64)
            x_native = (xs[::4, ::4] / scale).astype(np.float64)
            fx = flow[::4, ::4, 0] / scale
            fy = flow[::4, ::4, 1] / scale
            disp_m: List[float] = []
            flat_x = x_native.ravel()
            flat_y = y_native.ravel()
            flat_fx = fx.ravel()
            flat_fy = fy.ravel()
            for _k in range(0, flat_x.size, 7):
                u, v = flat_x[_k], flat_y[_k]
                a = plane.image_to_ground(u, v)
                if a is None:
                    continue
                b = plane.image_to_ground(u + flat_fx[_k], v + flat_fy[_k])
                if b is None:
                    continue
                disp_m.append(plane.ground_distance_m(a, b))
            if len(disp_m) >= 5:
                median_m_per_frame = float(np.median(disp_m))
                ego_est_mps.append(median_m_per_frame / dt)

        prev_gray = nxt_gray

    if not moving_votes:
        return False, None

    moving = float(np.mean(moving_votes)) > 0.5
    ego_kmh: Optional[float] = None
    if plane is not None and plane.calibrated and ego_est_mps:
        ego_kmh = float(np.median(ego_est_mps)) * 3.6
        ego_kmh = round(max(0.0, min(ego_kmh, settings.SPEED_MAX_KMH)), 1)
    return moving, ego_kmh