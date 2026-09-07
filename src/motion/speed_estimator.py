"""Per-track real-world speed estimation (additive, calibration-gated).

Consumes the EXISTING ByteTrack bounding boxes - no new detector, no new
tracker, no re-processing (STEP 32/33). For every tracked road user it
maintains a bounded history of ground-plane positions and computes:

    ground position = H @ (bottom_center of bounding box)
    speed = |ground_now - ground_anchor| / (t_now - t_anchor)

where ``t = frame_number / source_fps``. Time therefore always comes from
the SOURCE FPS and the source frame number, never from the processing
rate, and frame skipping is handled implicitly because the delta is
``(current_frame - anchor_frame) / source_fps``.

No ``km/h`` value is ever produced while the scene is not calibrated
(status ``NOT_CALIBRATED``). Raw estimates are exponentially smoothed,
outliers over ``SPEED_MAX_KMH`` (or spikes vs. the running EMA) are
rejected, and an honest ESTIMATION CONFIDENCE heuristic is attached.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from config.settings import settings
from src.calibration.calibration import Calibration
from src.calibration.ground import GroundPlane, bottom_center

# Speed statuses (STEP 24).
SPEED_NOT_CALIBRATED = "NOT_CALIBRATED"
SPEED_CALCULATING = "CALCULATING"
SPEED_ESTIMATED = "ESTIMATED"
SPEED_LOW_CONFIDENCE = "LOW_CONFIDENCE"
SPEED_TRACK_LOST = "TRACK_LOST"
SPEED_UNAVAILABLE = "UNAVAILABLE"

_MS_TO_KMH = 3.6


def mps_to_kmh(mps: float) -> float:
    """Convert metres/second to kilometres/hour."""
    return float(mps) * _MS_TO_KMH


def kmh_to_mps(kmh: float) -> float:
    """Convert kilometres/hour to metres/second."""
    return float(kmh) / _MS_TO_KMH


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


@dataclass
class SpeedResult:
    """Per-frame speed estimate for one tracked object.

    ``speed_kmh`` is the full ground-plane speed magnitude
    (STEP 25 default unit). ``approach_kmh`` is the longitudinal closing
    component (how fast the object is moving toward/away along the road's
    Z axis), which is the quantity most relevant to TTC-style analysis.
    ``speed_confidence`` is an ESTIMATION CONFIDENCE heuristic, labelled
    as such and never presented as a statistically calibrated value.
    """

    track_id: int
    frame: int
    timestamp_s: float
    speed_mps: Optional[float]
    speed_kmh: Optional[float]
    approach_kmh: Optional[float]
    speed_confidence: Optional[float]
    speed_status: str
    distance_m: float = 0.0
    delta_time_s: float = 0.0


class TrackSpeedEstimator:
    """Bounded per-track ground-motion history + speed estimates."""

    def __init__(
        self,
        fps: float,
        calibration: Optional[Calibration] = None,
        camera_moving: bool = False,
    ) -> None:
        self.fps = max(float(fps or 30.0), 1e-6)
        self.calibration = calibration or Calibration(ground_plane=GroundPlane())
        self.camera_moving = camera_moving

        self._hist: Dict[int, Deque[Tuple[float, Optional[Tuple[float, float]], float]]] = {}
        self._ema_kmh: Dict[int, Optional[float]] = {}
        self._outliers: Dict[int, int] = {}
        self._last_frame: Dict[int, int] = {}
        self._raw_recent: Dict[int, Deque[float]] = {}
        self._cur_estimate: Dict[int, SpeedResult] = {}
        self._cleaned_up_at: int = 0

    # ------------------------------------------------------------------
    def update(
        self,
        track_id: int,
        frame_idx: int,
        bbox: Tuple[float, float, float, float],
        detection_conf: float = 0.5,
    ) -> SpeedResult:
        """Feed one tracked frame to the speed estimator.

        ``bbox`` is the existing ByteTrack box in full-frame pixel
        coordinates. Returns a ``SpeedResult`` encoding the current state;
        the caller serializes the fields into the existing track metadata.
        """
        t = float(frame_idx) / self.fps

        # Guard against out-of-order/duplicate frames (STEP 35).
        last = self._last_frame.get(track_id)
        if last is not None and frame_idx <= last:
            return self._cur_estimate.get(track_id, self._stub(track_id, frame_idx, t))
        self._last_frame[track_id] = frame_idx

        if track_id not in self._hist:
            self._hist[track_id] = deque(maxlen=settings.SPEED_HISTORY_LENGTH)
            self._raw_recent[track_id] = deque(maxlen=5)
            self._outliers[track_id] = 0
            self._ema_kmh[track_id] = None

        ground: Optional[Tuple[float, float]] = None
        if self.calibration.configured and self.calibration.ground_plane is not None:
            try:
                ground = self.calibration.ground_plane.image_to_ground(*bottom_center(tuple(bbox)))
            except Exception:  # noqa: BLE001
                ground = None

        valid_box = (
            isinstance(bbox, (tuple, list)) and len(bbox) == 4
            and (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0
        )
        if not valid_box:
            ground = None

        self._hist[track_id].append((t, ground, float(detection_conf) if ground is not None else 0.0))

        result = self._compute(track_id, frame_idx, t)
        self._cur_estimate[track_id] = result
        return result

    # ------------------------------------------------------------------
    def _valid_history(self, track_id: int) -> List[Tuple[float, Tuple[float, float], float]]:
        return [(t, g, c) for (t, g, c) in self._hist.get(track_id, []) if g is not None]

    def _compute(self, track_id: int, frame_idx: int, t: float) -> SpeedResult:
        base = self._stub(track_id, frame_idx, t)
        if not self.calibration.configured:
            base.speed_status = SPEED_NOT_CALIBRATED
            return base

        valid = self._valid_history(track_id)
        if len(valid) < settings.SPEED_MIN_HISTORY_FRAMES:
            base.speed_status = SPEED_CALCULATING
            return base

        anchor_idx = -1
        for i in range(len(valid) - 2, -1, -1):
            if t - valid[i][0] >= settings.SPEED_MEASUREMENT_WINDOW_S:
                anchor_idx = i
                break
        if anchor_idx < 0:
            base.speed_status = SPEED_CALCULATING
            return base

        t0, g0, _ = valid[anchor_idx]
        t1, g1, _ = valid[-1]
        dt = t1 - t0
        if dt <= 0.0:
            base.speed_status = SPEED_CALCULATING
            return base

        dX = g1[0] - g0[0]
        dZ = g1[1] - g0[1]
        dist = math.hypot(dX, dZ)
        base.distance_m = round(float(dist), 4)
        base.delta_time_s = round(float(dt), 4)

        raw_mps = dist / dt
        raw_kmh = mps_to_kmh(raw_mps)

        # --- Outlier / spike rejection (STEP 9) ---
        prev_ema = self._ema_kmh.get(track_id)
        rejected = False
        if raw_kmh > settings.SPEED_MAX_KMH:
            rejected = True
        elif prev_ema is not None and raw_kmh > (prev_ema * settings.SPEED_SPIKE_FACTOR + settings.SPEED_SPIKE_OFFSET_KMH):
            rejected = True
        if rejected:
            self._outliers[track_id] = self._outliers.get(track_id, 0) + 1
            if prev_ema is not None:
                conf = self._confidence(track_id, len(valid), 1.0)
                conf = max(0.05, conf - 0.35)
                base.speed_mps = prev_ema / _MS_TO_KMH
                base.speed_kmh = round(prev_ema, 1)
                base.approach_kmh = self._approach_kmh(g0, g1, dt, prev_ema)
                base.speed_confidence = round(conf, 2)
                base.speed_status = SPEED_LOW_CONFIDENCE
                return base
            base.speed_status = SPEED_CALCULATING
            return base

        # --- Exponential smoothing (STEP 8) ---
        self._raw_recent[track_id].append(raw_kmh)
        ema = raw_kmh if prev_ema is None else (
            settings.SPEED_EMA_ALPHA * raw_kmh + (1.0 - settings.SPEED_EMA_ALPHA) * prev_ema
        )
        self._ema_kmh[track_id] = ema

        conf = self._confidence(track_id, len(valid), ema)
        status = SPEED_LOW_CONFIDENCE if conf < 0.45 else SPEED_ESTIMATED
        base.speed_mps = round(ema / _MS_TO_KMH, 2)
        base.speed_kmh = round(ema, 1)
        base.approach_kmh = self._approach_kmh(g0, g1, dt, ema)
        base.speed_confidence = round(conf, 2)
        base.speed_status = status
        return base

    def _approach_kmh(self, g0: Tuple[float, float], g1: Tuple[float, float], dt: float, ema_kmh: float) -> float:
        """Longitudinal (Z-axis) closing magnitude, scaled to match the EMA directionality."""
        dZ = abs(g1[1] - g0[1])
        approach_mps = (dZ / dt) if dt > 0 else 0.0
        # Use the EMA as a smoother guard: lateral-only motion must not inflate this.
        return round(min(mps_to_kmh(approach_mps), ema_kmh + 5.0), 1)

    # ------------------------------------------------------------------
    def _confidence(self, track_id: int, valid_count: int, ema_kmh: float) -> float:
        """Honest ESTIMATION CONFIDENCE heuristic (STEP 10 / 29).

        Deliberately labelled a heuristic: it blends detection confidence,
        track age, history sufficiency, measurement consistency and recent
        outlier rate, and is reduced when the camera is moving.
        """
        c = 0.30
        # history sufficiency
        c += 0.10 * min(1.0, valid_count / (settings.SPEED_MIN_HISTORY_FRAMES * 2.0))
        # detection confidence
        confs = [cc for (_, _, cc) in self._hist.get(track_id, [])]
        if confs:
            c += 0.15 * float(np.mean(confs))
        # measurement consistency (low relative scatter of recent raws)
        raws = list(self._raw_recent.get(track_id, []))
        if len(raws) >= 3 and ema_kmh > 5.0:
            std = float(np.std(raws))
            cv = std / max(ema_kmh, 1e-6)
            c += 0.15 * (1.0 - min(1.0, cv / 0.5))
        else:
            c += 0.05
        # track age
        c += 0.05 * min(1.0, valid_count / 30.0)
        # outliers penalize
        out = self._outliers.get(track_id, 0)
        c -= 0.10 * min(1.0, out / 5.0)
        if self.camera_moving:
            c *= 0.80
        return _clamp01(c)

    # ------------------------------------------------------------------
    def cleanup(self, active_track_ids, frame_idx: int) -> None:
        """Prune tracks that disappeared long ago (STEP 33 memory bound)."""
        stale_ids = [
            tid for tid in list(self._hist.keys())
            if tid not in active_track_ids
            and (frame_idx - self._last_frame.get(tid, frame_idx)) > settings.SPEED_STALE_FRAMES
        ]
        for tid in stale_ids:
            self._hist.pop(tid, None)
            self._ema_kmh.pop(tid, None)
            self._outliers.pop(tid, None)
            self._last_frame.pop(tid, None)
            self._raw_recent.pop(tid, None)
            self._cur_estimate.pop(tid, None)

    def status_for(self, track_id: int, current_frame: int) -> str:
        """Status for a track that disappeared (STEP 24: TRACK LOST)."""
        last = self._last_frame.get(track_id)
        if last is None:
            return SPEED_UNAVAILABLE
        if (current_frame - last) > settings.SPEED_STALE_FRAMES:
            return SPEED_TRACK_LOST
        est = self._cur_estimate.get(track_id)
        return est.speed_status if est else SPEED_UNAVAILABLE

    def last_estimate(self, track_id: int) -> Optional[SpeedResult]:
        return self._cur_estimate.get(track_id)

    @staticmethod
    def _stub(track_id: int, frame: int, t: float) -> SpeedResult:
        return SpeedResult(
            track_id=track_id,
            frame=frame,
            timestamp_s=round(t, 3),
            speed_mps=None,
            speed_kmh=None,
            approach_kmh=None,
            speed_confidence=None,
            speed_status=SPEED_UNAVAILABLE,
        )