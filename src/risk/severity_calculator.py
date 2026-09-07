"""
Severity calculator module.

Computes a composite risk score for each collision threat based on
multiple factors: TTC, distance, closing speed, path intersection,
and prediction confidence.
"""

from typing import Optional
import numpy as np

from config.thresholds import thresholds
from src.collision.collision_engine import CollisionAssessment


class SeverityCalculator:
    """
    Calculates collision severity scores using weighted multi-factor analysis.

    Each threat receives a risk score between 0.0 (safe) and 1.0 (critical).
    """

    def __init__(self):
        self.weights = {
            "ttc": thresholds.weight_ttc,
            "distance": thresholds.weight_distance,
            "closing_speed": thresholds.weight_closing_speed,
            "path_intersection": thresholds.weight_path_intersection,
            "prediction_confidence": thresholds.weight_prediction_confidence,
        }

    def calculate(self, assessment: CollisionAssessment, prediction_confidence: float = 0.8) -> float:
        """
        Calculate the composite risk score for a collision assessment.

        Args:
            assessment: CollisionAssessment to evaluate.
            prediction_confidence: Confidence in the trajectory prediction.

        Returns:
            Risk score between 0.0 and 1.0.
        """
        ttc_score = self._ttc_to_score(assessment.estimated_ttc)
        distance_score = self._distance_to_score(assessment.proximity_to_ego)
        speed_score = self._speed_to_score(assessment.bbox_growth_rate)
        intersection_score = 1.0 if assessment.conflict_status in ("HIGH CONFLICT", "POTENTIAL CONFLICT") else 0.3

        score = (
            self.weights["ttc"] * ttc_score
            + self.weights["distance"] * distance_score
            + self.weights["closing_speed"] * speed_score
            + self.weights["path_intersection"] * intersection_score
            + self.weights["prediction_confidence"] * prediction_confidence
        )

        return float(np.clip(score, 0.0, 1.0))

    def _ttc_to_score(self, ttc: Optional[float]) -> float:
        """Convert TTC value to a 0-1 risk score."""
        if ttc is None:
            return 0.1
        if ttc <= thresholds.ttc_critical:
            return 1.0
        elif ttc <= thresholds.ttc_high:
            return 0.8
        elif ttc <= thresholds.ttc_medium:
            return 0.5
        return 0.2

    def _distance_to_score(self, distance: float) -> float:
        """Convert distance to a 0-1 risk score."""
        if distance <= thresholds.proximity_critical:
            return 1.0
        elif distance <= thresholds.proximity_high:
            return 0.7
        elif distance <= thresholds.proximity_medium:
            return 0.4
        return 0.1

    def _speed_to_score(self, closing_speed: float) -> float:
        """Convert closing speed / growth rate to a 0-1 risk score."""
        if closing_speed >= 0.1:
            return 1.0
        elif closing_speed >= 0.05:
            return 0.7
        elif closing_speed >= 0.01:
            return 0.4
        return 0.1
