"""
Future position prediction module.

Predicts where tracked objects will be at specified future time horizons
using constant velocity and heading-based extrapolation.

Returns trajectory status:
    MOVING AWAY      - object receding, no convergence with ego path
    STABLE PATH      - object on steady trajectory, no crossing predicted
    CONVERGING       - object trajectory converging toward ego path
    POTENTIAL CROSSING - object predicted to cross the ego path
"""

from typing import Dict, List, Optional, Tuple
import numpy as np

from config.settings import settings
from src.motion.trajectory import Trajectory


class PredictionResult:
    """Stores prediction output for a single track at one horizon."""

    def __init__(self, track_id: int, horizon: float):
        self.track_id = track_id
        self.horizon = horizon
        self.predicted_position: Optional[Tuple[float, float]] = None
        self.confidence: float = 0.0
        self.velocity_vector: Tuple[float, float] = (0.0, 0.0)
        self.trajectory_status: str = "STABLE PATH"

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "horizon": self.horizon,
            "predicted_position": self.predicted_position,
            "confidence": self.confidence,
            "velocity_vector": self.velocity_vector,
            "trajectory_status": self.trajectory_status,
        }


class FuturePositionPredictor:
    """
    Predicts future positions of tracked objects using
    constant-velocity linear extrapolation.
    """

    def __init__(self, horizons: Optional[List[float]] = None,
                 frame_width: Optional[int] = None, frame_height: Optional[int] = None):
        """
        Initialize the predictor.

        Args:
            horizons: List of prediction horizons in seconds.
            frame_width: Actual video frame width in pixels.
            frame_height: Actual video frame height in pixels.
        """
        self.horizons = horizons or settings.TRAJECTORY_FUTURE_HORIZONS
        self.frame_width = frame_width or settings.FRAME_WIDTH
        self.frame_height = frame_height or settings.FRAME_HEIGHT
        self.predictions: Dict[int, List[PredictionResult]] = {}

    def predict(self, trajectory: Trajectory) -> List[PredictionResult]:
        """
        Predict future positions for all configured horizons.

        Args:
            trajectory: Trajectory of the tracked object.

        Returns:
            List of PredictionResult for each horizon.
        """
        results = []
        velocity = trajectory.get_velocity_vector()
        points = trajectory.get_points()

        # Compute confidence based on trajectory quality
        confidence = self._compute_confidence(trajectory)

        for horizon in self.horizons:
            result = PredictionResult(
                track_id=trajectory.track_id,
                horizon=horizon,
            )

            if len(points) < 2:
                result.predicted_position = tuple(points[-1]) if len(points) > 0 else None
                result.confidence = 0.0
                result.trajectory_status = "STABLE PATH"
            else:
                last_pos = points[-1]
                predicted_x = last_pos[0] + velocity[0] * horizon
                predicted_y = last_pos[1] + velocity[1] * horizon
                result.predicted_position = (float(predicted_x), float(predicted_y))
                result.confidence = max(0.0, confidence - settings.CONFIDENCE_DECAY * horizon)
                result.trajectory_status = self._classify_trajectory_status(
                    points, velocity, horizon, last_pos
                )

            result.velocity_vector = velocity
            results.append(result)

        self.predictions[trajectory.track_id] = results
        return results

    def _classify_trajectory_status(
        self,
        points: np.ndarray,
        velocity: Tuple[float, float],
        horizon: float,
        current_pos: np.ndarray,
    ) -> str:
        """
        Classify trajectory status based on predicted path relative to ego zone.

        Uses the ego path (center region of frame) as reference.
        """
        frame_width = self.frame_width
        ego_left = frame_width * settings.EGO_PATH_LEFT_RATIO
        ego_right = frame_width * settings.EGO_PATH_RIGHT_RATIO
        ego_center_x = frame_width / 2.0

        vx, vy = velocity

        # If moving away (vy > 0 means moving down in image = receding), no crossing
        if vy > 10 and abs(vx) < abs(vy) * 0.5:
            return "MOVING AWAY"

        # Check if current or predicted position enters the ego zone
        predicted_x = current_pos[0] + vx * horizon
        predicted_y = current_pos[1] + vy * horizon

        # Check if predicted path enters ego zone
        in_ego_zone = ego_left <= predicted_x <= ego_right

        # Check convergence: is the object moving toward the ego center line?
        lateral_distance_to_center = abs(current_pos[0] - ego_center_x)
        predicted_lateral_distance = abs(predicted_x - ego_center_x)

        is_converging = predicted_lateral_distance < lateral_distance_to_center

        # Check if the trajectory crosses the ego zone boundaries
        crosses_ego = (current_pos[0] < ego_left and predicted_x > ego_right) or \
                      (current_pos[0] > ego_right and predicted_x < ego_left)

        if crosses_ego:
            return "POTENTIAL CROSSING"
        elif is_converging:
            return "CONVERGING"
        elif in_ego_zone:
            return "STABLE PATH"
        else:
            return "STABLE PATH"

    def _compute_confidence(self, trajectory: Trajectory) -> float:
        """
        Compute prediction confidence based on trajectory data quality.

        Longer, more consistent trajectories yield higher confidence.
        """
        n_points = trajectory.length()
        if n_points < 3:
            return 0.3
        elif n_points < 10:
            return 0.6
        elif n_points < 30:
            return 0.8
        return 0.95

    def get_predictions(self, track_id: int) -> List[PredictionResult]:
        """Get predictions for a specific track."""
        return self.predictions.get(track_id, [])

    def get_all_predictions(self) -> Dict[int, List[PredictionResult]]:
        """Get all current predictions."""
        return self.predictions

    def reset(self):
        """Clear all prediction state."""
        self.predictions.clear()
