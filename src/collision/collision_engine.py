"""
Collision engine orchestrator.

Combines conflict detection and TTC estimation to produce
a unified collision threat assessment for each tracked object.

Provides:
    - Conflict status (NO SIGNIFICANT CONFLICT / MONITOR / POTENTIAL CONFLICT / HIGH CONFLICT)
    - Estimated TTC (visual-based)
    - Estimated PET (visual-based)
    - Estimated DRAC Risk (risk category based on TTC/conflict/proximity)
    - Estimated ACT (urgency window for action)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np

from config.settings import settings
from src.motion.motion_analysis import MotionState
from src.utils.logger import get_logger

logger = get_logger(__name__)


CONFLICT_NO_SIGNIFICANT = "NO SIGNIFICANT CONFLICT"
CONFLICT_MONITOR = "MONITOR"
CONFLICT_POTENTIAL = "POTENTIAL CONFLICT"
CONFLICT_HIGH = "HIGH CONFLICT"


@dataclass
class CollisionAssessment:
    """Complete collision assessment for a single tracked object."""
    track_id: int
    class_name: str
    conflict_status: str
    estimated_ttc: Optional[float]
    estimated_pet: Optional[float]
    estimated_drac_risk: str
    estimated_act: Optional[str]
    proximity_to_ego: float
    bbox_growth_rate: float
    is_in_ego_zone: bool

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "conflict_status": self.conflict_status,
            "estimated_ttc": self.estimated_ttc,
            "estimated_pet": self.estimated_pet,
            "estimated_drac_risk": self.estimated_drac_risk,
            "estimated_act": self.estimated_act,
            "proximity_to_ego": self.proximity_to_ego,
            "bbox_growth_rate": self.bbox_growth_rate,
            "is_in_ego_zone": self.is_in_ego_zone,
        }


class CollisionEngine:
    """
    Unified collision threat assessment engine.

    Analyzes each tracked object against the simulated ego path to produce:
    - Conflict status
    - Estimated TTC (visual-based, monocular simulation)
    - Estimated PET (visual-based)
    - Estimated DRAC Risk category
    - Estimated ACT (urgency window)
    """

    def __init__(self, frame_width: Optional[int] = None, frame_height: Optional[int] = None):
        self.frame_width = frame_width or settings.FRAME_WIDTH
        self.frame_height = frame_height or settings.FRAME_HEIGHT
        self.ego_center_x = self.frame_width / 2.0
        self.ego_center_y = float(self.frame_height) * 0.5
        self.ego_zone_left = self.frame_width * settings.EGO_PATH_LEFT_RATIO
        self.ego_zone_right = self.frame_width * settings.EGO_PATH_RIGHT_RATIO
        self.assessments: Dict[int, CollisionAssessment] = {}

    def assess_all(
        self,
        motion_states: Dict[int, MotionState],
        trajectory_status: Dict[int, str],
    ) -> Dict[int, CollisionAssessment]:
        """
        Assess collision risk for all tracked objects.

        Args:
            motion_states: Dict mapping track_id to MotionState.
            trajectory_status: Dict mapping track_id to trajectory status string.

        Returns:
            Dict mapping track_id to CollisionAssessment.
        """
        self.assessments.clear()

        for track_id, state in motion_states.items():
            if len(state.positions) < 2:
                continue

            assessment = self._assess_object(state, trajectory_status.get(track_id, "STABLE PATH"))
            self.assessments[track_id] = assessment

        logger.debug("Collision assessed %d objects", len(self.assessments))
        return self.assessments

    def _assess_object(
        self,
        state: MotionState,
        traj_status: str,
    ) -> CollisionAssessment:
        """Assess a single tracked object for collision risk."""
        curr_pos = np.array(state.positions[-1])

        # Proximity to ego center
        ego_center = np.array([self.ego_center_x, self.ego_center_y])
        proximity = float(np.linalg.norm(curr_pos - ego_center))

        # Check if object is in ego zone
        in_ego_zone = self.ego_zone_left <= curr_pos[0] <= self.ego_zone_right

        # Bounding box growth rate
        bbox_growth = self._compute_bbox_growth(state)

        # Estimate TTC (visual-based)
        estimated_ttc = self._estimate_ttc(state, in_ego_zone, proximity)

        # Estimate PET (visual-based)
        estimated_pet = self._estimate_pet(state, traj_status, in_ego_zone)

        # Determine conflict status
        conflict_status = self._determine_conflict_status(
            state, estimated_ttc, in_ego_zone, proximity, traj_status
        )

        # Estimate DRAC risk
        estimated_drac = self._estimate_drac_risk(
            estimated_ttc, conflict_status, state.motion_state, proximity
        )

        # Estimate ACT
        estimated_act = self._estimate_act(estimated_ttc, conflict_status)

        return CollisionAssessment(
            track_id=state.track_id,
            class_name=state.class_name,
            conflict_status=conflict_status,
            estimated_ttc=estimated_ttc,
            estimated_pet=estimated_pet,
            estimated_drac_risk=estimated_drac,
            estimated_act=estimated_act,
            proximity_to_ego=proximity,
            bbox_growth_rate=bbox_growth,
            is_in_ego_zone=in_ego_zone,
        )

    def _compute_bbox_growth(self, state: MotionState) -> float:
        """Compute bounding box area growth rate (positive = growing)."""
        areas = list(state.area_history)
        if len(areas) < 3:
            return 0.0

        recent = areas[-min(len(areas), 5):]
        if len(recent) < 2:
            return 0.0

        changes = np.diff(recent)
        avg_area = np.mean(recent) if np.mean(recent) > 0 else 1.0
        return float(np.mean(changes) / avg_area)

    def _estimate_ttc(
        self,
        state: MotionState,
        in_ego_zone: bool,
        proximity: float,
    ) -> Optional[float]:
        """
        Estimate Time To Collision using visual information.

        This is a VIDEO-BASED SIMULATION. The value is estimated from:
        - bounding box growth rate
        - object approaching state
        - relative visual closing rate
        - proximity to ego zone

        Label as: Estimated TTC
        """
        if not state.is_approaching:
            return None

        if len(state.positions) < 3:
            return None

        # Compute visual closing rate (pixels/sec toward ego)
        ego_center = np.array([self.ego_center_x, self.ego_center_y])
        positions = state.positions

        # Measure closing over recent frames
        closing_distances = []
        for i in range(max(0, len(positions) - 5), len(positions)):
            pos = np.array(positions[i])
            closing_distances.append(float(np.linalg.norm(pos - ego_center)))

        if len(closing_distances) < 2:
            return None

        # Closing speed in pixels/sec
        dist_change = closing_distances[-1] - closing_distances[0]
        time_span = (len(closing_distances) - 1) * (1.0 / self._get_fps(state))
        closing_speed = abs(dist_change) / max(time_span, 1e-6)

        if closing_speed < 1.0:
            return None

        # TTC = current distance / closing speed
        current_dist = closing_distances[-1]
        ttc_raw = current_dist / closing_speed

        # Apply bonuses/penalties based on ego zone proximity
        if in_ego_zone:
            ttc_raw *= 0.8  # More urgent if in ego zone

        # Bounding box growth also indicates closing
        growth = self._compute_bbox_growth(state)
        if growth > 0.05:
            ttc_raw *= 0.9

        # Clamp to reasonable range
        ttc_raw = max(0.3, min(ttc_raw, 10.0))

        return round(ttc_raw, 2)

    def _estimate_pet(
        self,
        state: MotionState,
        traj_status: str,
        in_ego_zone: bool,
    ) -> Optional[float]:
        """
        Estimate Post Encroachment Time.

        PET is estimated when an object's trajectory crosses or enters
        the simulated ego path. It represents the temporal gap between
        predicted path occupancy.

        Label as: Estimated PET
        """
        if not in_ego_zone and traj_status not in ("POTENTIAL CROSSING", "CONVERGING"):
            return None

        if len(state.positions) < 3:
            return None

        # Estimate time for object to cross ego zone center
        ego_center_x = self.ego_center_x
        curr_x = state.positions[-1][0]
        velocity_x = state.velocity[0]

        if abs(velocity_x) < 1.0:
            return None

        # Time to reach ego zone center
        distance_to_center = abs(curr_x - ego_center_x)
        time_to_center = distance_to_center / abs(velocity_x)

        # PET estimate: time gap between occupancy
        if in_ego_zone:
            pet = max(0.5, time_to_center * 0.5)
        else:
            pet = time_to_center

        # Apply trajectory-based adjustments
        if traj_status == "POTENTIAL CROSSING":
            pet *= 0.7
        elif traj_status == "CONVERGING":
            pet *= 0.85

        pet = max(0.3, min(pet, 8.0))
        return round(pet, 2)

    def _determine_conflict_status(
        self,
        state: MotionState,
        estimated_ttc: Optional[float],
        in_ego_zone: bool,
        proximity: float,
        traj_status: str,
    ) -> str:
        """
        Determine conflict status based on all available evidence.

        Returns:
            NO SIGNIFICANT CONFLICT / MONITOR / POTENTIAL CONFLICT / HIGH CONFLICT
        """
        score = 0.0

        # TTC factor
        if estimated_ttc is not None:
            if estimated_ttc < settings.TTC_CRITICAL_THRESHOLD:
                score += 40
            elif estimated_ttc < settings.TTC_HIGH_THRESHOLD:
                score += 25
            elif estimated_ttc < settings.TTC_MEDIUM_THRESHOLD:
                score += 10

        # Ego zone presence
        if in_ego_zone:
            score += 20

        # Proximity factor
        if proximity < settings.CONFLICT_PROXIMITY_PIXELS:
            score += 15
        elif proximity < settings.CONFLICT_PROXIMITY_PIXELS * 2:
            score += 8

        # Motion state factor
        if state.motion_state == "APPROACHING":
            score += 15
        elif state.motion_state == "RECEDING":
            score -= 10

        # Trajectory status factor
        if traj_status == "POTENTIAL CROSSING":
            score += 20
        elif traj_status == "CONVERGING":
            score += 15
        elif traj_status == "MOVING AWAY":
            score -= 15

        # Class-based risk adjustment (vulnerable road users)
        if state.class_name.lower() in ("person", "bicycle", "motorcycle"):
            if state.motion_state == "APPROACHING":
                score += 5

        # Determine status
        if score >= 60:
            return CONFLICT_HIGH
        elif score >= 35:
            return CONFLICT_POTENTIAL
        elif score >= 15:
            return CONFLICT_MONITOR
        else:
            return CONFLICT_NO_SIGNIFICANT

    def _estimate_drac_risk(
        self,
        estimated_ttc: Optional[float],
        conflict_status: str,
        motion_state: str,
        proximity: float,
    ) -> str:
        """
        Estimate DRAC (Deceleration Rate to Avoid Collision) risk category.

        Uses visual evidence to categorize:
        LOW / MEDIUM / HIGH / CRITICAL

        Label as: Estimated DRAC Risk
        """
        score = 0.0

        if estimated_ttc is not None:
            if estimated_ttc < settings.TTC_CRITICAL_THRESHOLD:
                score += 50
            elif estimated_ttc < settings.TTC_HIGH_THRESHOLD:
                score += 30
            elif estimated_ttc < settings.TTC_MEDIUM_THRESHOLD:
                score += 15

        if conflict_status == CONFLICT_HIGH:
            score += 25
        elif conflict_status == CONFLICT_POTENTIAL:
            score += 15
        elif conflict_status == CONFLICT_MONITOR:
            score += 5

        if motion_state == "APPROACHING":
            score += 10
        elif motion_state == "RECEDING":
            score -= 5

        if proximity < settings.CONFLICT_PROXIMITY_PIXELS:
            score += 10

        if score >= 70:
            return "CRITICAL"
        elif score >= 45:
            return "HIGH"
        elif score >= 20:
            return "MEDIUM"
        return "LOW"

    def _estimate_act(
        self,
        estimated_ttc: Optional[float],
        conflict_status: str,
    ) -> Optional[str]:
        """
        Estimate the urgency window for action (ACT).

        Based on Estimated TTC and conflict level.
        Returns descriptive urgency string or N/A.

        Label as: Estimated ACT
        """
        if estimated_ttc is None:
            if conflict_status in (CONFLICT_HIGH, CONFLICT_POTENTIAL):
                return "MONITOR"
            return "N/A"

        if estimated_ttc < settings.TTC_CRITICAL_THRESHOLD:
            return "IMMEDIATE"
        elif estimated_ttc < settings.TTC_HIGH_THRESHOLD:
            return "URGENT"
        elif estimated_ttc < settings.TTC_MEDIUM_THRESHOLD:
            return "PREPARE"
        elif conflict_status in (CONFLICT_HIGH, CONFLICT_POTENTIAL):
            return "MONITOR"
        return "N/A"

    def _get_fps(self, state: MotionState) -> float:
        """Get FPS estimate from timestamps."""
        if len(state.timestamps) >= 2:
            dt = state.timestamps[-1] - state.timestamps[-2]
            if dt > 0:
                return 1.0 / dt
        return 30.0

    def get_assessment(self, track_id: int) -> Optional[CollisionAssessment]:
        """Get assessment for a specific track."""
        return self.assessments.get(track_id)

    def get_all_assessments(self) -> Dict[int, CollisionAssessment]:
        """Get all current assessments."""
        return self.assessments

    def get_high_risk_objects(self) -> List[CollisionAssessment]:
        """Return objects with HIGH CONFLICT or CRITICAL status."""
        return [
            a for a in self.assessments.values()
            if a.conflict_status in (CONFLICT_HIGH, CONFLICT_POTENTIAL)
        ]

    def reset(self):
        """Clear all collision assessment state."""
        self.assessments.clear()
