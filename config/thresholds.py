"""
Collision anticipation thresholds and danger level definitions.
These values tune the sensitivity and behavior of the prediction engine.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Thresholds:
    """Tunable thresholds for collision detection, risk scoring, and alerting."""

    # Time-to-Collision thresholds (seconds)
    ttc_critical: float = 1.5
    ttc_high: float = 3.0
    ttc_medium: float = 5.0

    # Distance thresholds (pixels, approximated from monocular view)
    proximity_critical: float = 80.0
    proximity_high: float = 150.0
    proximity_medium: float = 250.0

    # Speed thresholds (pixels/sec)
    closing_speed_critical: float = 200.0
    closing_speed_high: float = 120.0
    closing_speed_medium: float = 60.0

    # Risk score ranges (0-100 scale for Part 2)
    risk_critical: float = 80.0
    risk_high: float = 60.0
    risk_medium: float = 40.0

    # Severity weights
    weight_ttc: float = 0.30
    weight_distance: float = 0.25
    weight_closing_speed: float = 0.25
    weight_path_intersection: float = 0.15
    weight_prediction_confidence: float = 0.05

    # Prediction confidence decay per horizon
    confidence_decay_per_second: float = 0.15

    # Inaction gate parameters
    inaction_time_threshold: float = 0.8
    driver_response_cooldown: float = 1.5

    # Trajectory parameters
    min_trajectory_points: int = 5
    trajectory_smoothing_window: int = 3

    # Directional zones (degrees from ego heading)
    direction_left_threshold: float = -30.0
    direction_right_threshold: float = 30.0

    # Part 2: PET thresholds
    pet_critical: float = 1.0
    pet_high: float = 2.0
    pet_medium: float = 3.0

    def get_risk_level(self, risk_score: float) -> str:
        """Return human-readable risk level for a given score (0-100 scale)."""
        if risk_score >= self.risk_critical:
            return "CRITICAL"
        elif risk_score >= self.risk_high:
            return "HIGH"
        elif risk_score >= self.risk_medium:
            return "MEDIUM"
        return "LOW"

    def get_ttc_level(self, ttc: float) -> str:
        """Return human-readable TTC level."""
        if ttc <= self.ttc_critical:
            return "CRITICAL"
        elif ttc <= self.ttc_high:
            return "HIGH"
        elif ttc <= self.ttc_medium:
            return "MEDIUM"
        return "LOW"

    def get_pet_level(self, pet: float) -> str:
        """Return human-readable PET level."""
        if pet <= self.pet_critical:
            return "CRITICAL"
        elif pet <= self.pet_high:
            return "HIGH"
        elif pet <= self.pet_medium:
            return "MEDIUM"
        return "LOW"


thresholds = Thresholds()
