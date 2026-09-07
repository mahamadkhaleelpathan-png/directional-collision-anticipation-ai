"""
Multi-horizon prediction orchestrator.

Coordinates predictions across all horizons and provides a unified
interface for the collision detection engine.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

from config.settings import settings
from src.motion.trajectory import Trajectory, TrajectoryGenerator
from src.prediction.future_position import FuturePositionPredictor, PredictionResult


@dataclass
class MultiHorizonResult:
    """Combined prediction results for a single object across all horizons."""
    track_id: int
    class_name: str
    predictions: List[PredictionResult]
    trajectory_quality: float

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "predictions": [p.to_dict() for p in self.predictions],
            "trajectory_quality": self.trajectory_quality,
        }


class MultiHorizonPredictor:
    """
    Orchestrates multi-horizon predictions for all tracked objects.

    Combines trajectory analysis with the future position predictor
    to produce a comprehensive prediction map.
    """

    def __init__(self, horizons: Optional[List[float]] = None):
        self.predictor = FuturePositionPredictor(horizons)
        self.results: Dict[int, MultiHorizonResult] = {}

    def predict_all(
        self, trajectory_generator: TrajectoryGenerator
    ) -> Dict[int, MultiHorizonResult]:
        """
        Generate predictions for all tracked trajectories.

        Args:
            trajectory_generator: Contains all current trajectories.

        Returns:
            Dictionary mapping track_id to MultiHorizonResult.
        """
        self.results.clear()

        for track_id, trajectory in trajectory_generator.get_all_trajectories().items():
            if trajectory.length() < 2:
                continue

            predictions = self.predictor.predict(trajectory)
            quality = self.predictor._compute_confidence(trajectory)

            self.results[track_id] = MultiHorizonResult(
                track_id=track_id,
                class_name="unknown",
                predictions=predictions,
                trajectory_quality=quality,
            )

        return self.results

    def get_predictions_for_track(self, track_id: int) -> Optional[MultiHorizonResult]:
        """Get multi-horizon predictions for a specific track."""
        return self.results.get(track_id)

    def get_all_results(self) -> Dict[int, MultiHorizonResult]:
        """Get all multi-horizon prediction results."""
        return self.results

    def reset(self):
        """Clear all prediction state."""
        self.predictor.reset()
        self.results.clear()
