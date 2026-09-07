"""
Motion analysis module.

Computes position, velocity, direction, heading, and motion classification
for each tracked road user based on frame-to-frame observations.

Motion states:
    APPROACHING   - object moving toward ego (bounding box growing, closing)
    RECEDING      - object moving away from ego (bounding box shrinking, opening)
    MOVING LATERALLY - dominant horizontal movement
    STATIONARY    - negligible movement over recent frames
"""

from typing import Dict, List, Optional, Tuple
from collections import deque
import numpy as np

from config.settings import settings


class MotionState:
    """Stores the computed motion state for a single tracked object."""

    def __init__(self, track_id: int, class_name: str):
        self.track_id = track_id
        self.class_name = class_name
        self.positions: List[Tuple[float, float]] = []
        self.timestamps: List[float] = []
        self.bbox_history: deque = deque(maxlen=settings.MOTION_HISTORY_LENGTH)
        self.area_history: deque = deque(maxlen=settings.MOTION_HISTORY_LENGTH)
        self.velocity: Tuple[float, float] = (0.0, 0.0)
        self.speed: float = 0.0
        self.heading: float = 0.0
        self.direction: float = 0.0
        self.is_approaching: bool = False
        self.motion_state: str = "STATIONARY"
        self.smoothed_speed: float = 0.0

    def to_dict(self) -> dict:
        """Serialize motion state to dictionary."""
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "position": self.positions[-1] if self.positions else (0, 0),
            "velocity": self.velocity,
            "speed": self.speed,
            "heading": self.heading,
            "direction": self.direction,
            "is_approaching": self.is_approaching,
            "motion_state": self.motion_state,
        }


class MotionAnalyzer:
    """
    Analyzes motion of tracked objects over time.

    Maintains position history and computes velocity, heading,
    and motion classification (APPROACHING / RECEDING / LATERAL / STATIONARY).
    """

    def __init__(self, fps: Optional[int] = None):
        """
        Initialize the motion analyzer.

        Args:
            fps: Frames per second of the input video.
        """
        self.fps = fps or settings.VIDEO_FPS
        self.dt = 1.0 / self.fps
        self.motion_states: Dict[int, MotionState] = {}
        self.frame_count: int = 0

    def update(self, track_id: int, class_name: str,
               center: Tuple[float, float], ego_center: Tuple[float, float] = (640, 720),
               bbox: Optional[Tuple[int, int, int, int]] = None):
        """
        Update motion state for a tracked object.

        Args:
            track_id: Unique track identifier.
            class_name: Detected object class.
            center: Center (x, y) of the bounding box in pixel coordinates.
            ego_center: Center of the ego vehicle in pixel coordinates.
            bbox: Optional bounding box (x1, y1, x2, y2) for area analysis.
        """
        self.frame_count += 1

        if track_id not in self.motion_states:
            self.motion_states[track_id] = MotionState(track_id, class_name)

        state = self.motion_states[track_id]
        state.positions.append(center)
        state.timestamps.append(self.frame_count * self.dt)

        # Track bounding box area for growth/shrink analysis
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            area = max(1.0, float((x2 - x1) * (y2 - y1)))
            state.bbox_history.append(bbox)
            state.area_history.append(area)

        # Keep bounded history
        max_hist = settings.MOTION_HISTORY_LENGTH
        if len(state.positions) > max_hist:
            state.positions = state.positions[-max_hist:]
            state.timestamps = state.timestamps[-max_hist:]

        # Need at least 2 frames to compute velocity
        if len(state.positions) < 2:
            return

        # Compute velocity from last two positions
        prev = np.array(state.positions[-2])
        curr = np.array(state.positions[-1])
        delta = curr - prev

        state.velocity = (float(delta[0] / self.dt), float(delta[1] / self.dt))
        state.speed = float(np.linalg.norm(delta) / self.dt)

        # Compute heading in degrees (0 = right, 90 = down in image coords)
        if state.speed > 0.1:
            state.heading = float(np.degrees(np.arctan2(delta[1], delta[0])))

        # Determine approaching or receding using area growth as primary indicator
        # (distance to ego center at bottom of frame increases for approaching objects,
        # which incorrectly marks them as receding)
        area_trend = self._compute_area_trend(state)
        if len(state.area_history) >= 3:
            state.is_approaching = area_trend > 0
        else:
            ego = np.array(ego_center)
            to_ego_before = np.linalg.norm(prev - ego)
            to_ego_after = np.linalg.norm(curr - ego)
            state.is_approaching = to_ego_after < to_ego_before

        # Classify motion state
        state.motion_state = self._classify_motion(state, ego_center)

        # Compute smoothed speed for stable readings
        state.smoothed_speed = self._smooth_speed(state)

    def _classify_motion(self, state: MotionState, ego_center: Tuple[float, float]) -> str:
        """
        Classify the motion state of an object into:
        APPROACHING / RECEDING / MOVING LATERALLY / STATIONARY
        """
        positions = state.positions
        if len(positions) < 3:
            return "STATIONARY"

        # Check if stationary: very low speed over recent frames
        recent_speeds = []
        for i in range(max(1, len(positions) - settings.MOTION_SMOOTHING_WINDOW), len(positions)):
            if i > 0:
                p1 = np.array(positions[i - 1])
                p2 = np.array(positions[i])
                dist = np.linalg.norm(p2 - p1)
                recent_speeds.append(dist)

        avg_recent_speed = np.mean(recent_speeds) if recent_speeds else 0.0

        if avg_recent_speed < settings.STATIONARY_DISPLACEMENT_THRESHOLD:
            return "STATIONARY"

        # Analyze bounding box area growth/shrink for approaching/receding
        area_trend = self._compute_area_trend(state)

        # Compute horizontal vs vertical movement dominance
        recent_positions = list(positions)[-settings.MOTION_SMOOTHING_WINDOW:]
        if len(recent_positions) < 2:
            return "STATIONARY"

        dx_total = 0.0
        dy_total = 0.0
        for i in range(1, len(recent_positions)):
            dx_total += abs(recent_positions[i][0] - recent_positions[i - 1][0])
            dy_total += abs(recent_positions[i][1] - recent_positions[i - 1][1])

        # Check lateral movement dominance
        if dx_total > 0 and dy_total > 0:
            lateral_ratio = dx_total / max(dy_total, 1e-6)
        elif dx_total > 0:
            lateral_ratio = float('inf')
        else:
            lateral_ratio = 0.0

        # If horizontal movement strongly dominates, classify as LATERAL
        if lateral_ratio > settings.LATERAL_DOMINANCE_RATIO and dx_total > 20:
            return "MOVING LATERALLY"

        # Use ego-relative closing and area trend for approaching/receding
        ego = np.array(ego_center)
        curr_pos = np.array(positions[-1])

        # Combine closing movement + area growth for robust classification
        if state.is_approaching and area_trend > -settings.APPROACHING_AREA_GROWTH_RATE:
            return "APPROACHING"
        elif not state.is_approaching and area_trend < settings.APPROACHING_AREA_GROWTH_RATE:
            return "RECEDING"
        elif state.is_approaching:
            return "APPROACHING"
        else:
            return "RECEDING"

    def _compute_area_trend(self, state: MotionState) -> float:
        """
        Compute the trend of bounding box area change.
        Positive = growing (approaching), Negative = shrinking (receding).
        Returns normalized rate.
        """
        areas = list(state.area_history)
        if len(areas) < 3:
            return 0.0

        recent = areas[-min(len(areas), settings.MOTION_SMOOTHING_WINDOW):]
        if len(recent) < 2:
            return 0.0

        # Compute average area change rate
        changes = np.diff(recent)
        avg_area = np.mean(recent) if np.mean(recent) > 0 else 1.0
        normalized_rate = np.mean(changes) / avg_area

        return float(normalized_rate)

    def _smooth_speed(self, state: MotionState) -> float:
        """Compute smoothed speed from recent position history."""
        positions = state.positions
        window = min(len(positions), settings.MOTION_SMOOTHING_WINDOW)
        if window < 2:
            return state.speed

        recent = positions[-window:]
        speeds = []
        for i in range(1, len(recent)):
            p1 = np.array(recent[i - 1])
            p2 = np.array(recent[i])
            dist = np.linalg.norm(p2 - p1)
            speeds.append(dist / self.dt)

        return float(np.mean(speeds)) if speeds else state.speed

    def cleanup_stale_states(self, active_track_ids: set):
        """Remove motion states for tracks that are no longer active."""
        stale_ids = [tid for tid in self.motion_states if tid not in active_track_ids]
        for tid in stale_ids:
            del self.motion_states[tid]

    def get_motion_state(self, track_id: int) -> Optional[MotionState]:
        """Get the current motion state for a track."""
        return self.motion_states.get(track_id)

    def get_all_states(self) -> List[MotionState]:
        """Get motion states for all tracked objects."""
        return list(self.motion_states.values())

    def get_approaching_objects(self) -> List[MotionState]:
        """Return all objects currently approaching the ego vehicle."""
        return [s for s in self.motion_states.values() if s.is_approaching]

    def reset(self):
        """Clear all motion analysis state."""
        self.motion_states.clear()
        self.frame_count = 0
