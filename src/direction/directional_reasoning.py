"""
Directional reasoning module.

Determines the relative direction of each threat from the ego vehicle:
LEFT, AHEAD, or RIGHT. This information is used to provide
spatially meaningful alerts to the driver.
"""

from typing import Optional, Tuple
from enum import Enum
import numpy as np

from config.thresholds import thresholds


class Direction(Enum):
    """Relative direction of a threat from the ego vehicle."""
    LEFT = "LEFT"
    AHEAD = "AHEAD"
    RIGHT = "RIGHT"


class DirectionalReasoner:
    """
    Determines the directional relationship between the ego vehicle
    and each tracked threat.
    """

    def __init__(self):
        self.left_threshold = thresholds.direction_left_threshold
        self.right_threshold = thresholds.direction_right_threshold

    def determine_direction(
        self,
        ego_center: Tuple[float, float],
        threat_center: Tuple[float, float],
        ego_heading: float = 0.0,
    ) -> Direction:
        """
        Determine the direction of a threat relative to the ego vehicle.

        Args:
            ego_center: Ego vehicle center (x, y) in image coordinates.
            threat_center: Threat object center (x, y) in image coordinates.
            ego_heading: Ego vehicle heading in degrees.

        Returns:
            Direction enum value (LEFT, AHEAD, or RIGHT).
        """
        # Calculate angle from ego to threat
        dx = threat_center[0] - ego_center[0]
        dy = threat_center[1] - ego_center[1]

        # Angle in degrees relative to straight ahead (negative y-axis)
        angle = np.degrees(np.arctan2(dx, -dy)) - ego_heading

        # Normalize to -180 to 180
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360

        if angle < self.left_threshold:
            return Direction.LEFT
        elif angle > self.right_threshold:
            return Direction.RIGHT
        else:
            return Direction.AHEAD

    def get_direction_label(self, direction: Direction) -> str:
        """Return a human-readable direction label."""
        return direction.value

    def get_full_alert_direction(self, direction: Direction, class_name: str) -> str:
        """
        Generate a directional description for an alert.

        Example: "Motorcycle approaching from RIGHT"
        """
        direction_label = self.get_direction_label(direction)
        return f"{class_name.capitalize()} approaching from {direction_label}"
