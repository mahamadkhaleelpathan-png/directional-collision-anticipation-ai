"""
Risk engine module.

Calculates a risk score (0-100) for each tracked object based on:
- Motion state
- Direction
- Proximity to simulated ego path
- Trajectory conflict status
- Estimated TTC
- Estimated PET
- Estimated DRAC Risk
- Estimated ACT

Identifies the PRIMARY THREAT among all tracked objects.

Risk levels:
    0-20:  SAFE
    21-40: LOW
    41-60: MEDIUM
    61-80: HIGH
    81-100: CRITICAL
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np

from config.settings import settings
from src.motion.motion_analysis import MotionState
from src.utils.logger import get_logger

logger = get_logger(__name__)
from src.collision.collision_engine import CollisionAssessment, CONFLICT_HIGH, CONFLICT_POTENTIAL, CONFLICT_MONITOR


@dataclass
class RiskResult:
    """Complete risk assessment for a single tracked object."""
    track_id: int
    class_name: str
    risk_score: float
    risk_level: str
    direction: str
    motion_state: str
    trajectory_status: str
    conflict_status: str
    estimated_ttc: Optional[float]
    estimated_pet: Optional[float]
    estimated_drac_risk: str
    estimated_act: Optional[str]
    risk_factors: Dict[str, float]

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "direction": self.direction,
            "motion_state": self.motion_state,
            "trajectory_status": self.trajectory_status,
            "conflict_status": self.conflict_status,
            "estimated_ttc": self.estimated_ttc,
            "estimated_pet": self.estimated_pet,
            "estimated_drac_risk": self.estimated_drac_risk,
            "estimated_act": self.estimated_act,
            "risk_factors": self.risk_factors,
        }


@dataclass
class PrimaryThreat:
    """The highest-risk tracked object identified as the primary threat."""
    object_type: str
    tracking_id: int
    direction: str
    motion_state: str
    trajectory_status: str
    conflict_status: str
    estimated_ttc: Optional[float]
    estimated_pet: Optional[float]
    estimated_drac_risk: str
    estimated_act: Optional[str]
    risk_score: float
    risk_level: str

    def to_dict(self) -> dict:
        return {
            "object_type": self.object_type,
            "tracking_id": self.tracking_id,
            "direction": self.direction,
            "motion_state": self.motion_state,
            "trajectory_status": self.trajectory_status,
            "conflict_status": self.conflict_status,
            "estimated_ttc": self.estimated_ttc,
            "estimated_pet": self.estimated_pet,
            "estimated_drac_risk": self.estimated_drac_risk,
            "estimated_act": self.estimated_act,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
        }


class RiskEngine:
    """
    Calculates risk scores and identifies the primary threat.
    """

    def __init__(self):
        self.risk_results: Dict[int, RiskResult] = {}
        self.primary_threat: Optional[PrimaryThreat] = None
        self.max_risk_score: float = 0.0
        self.highest_risk_object: Optional[str] = None
        self.cumulative_risk_results: Dict[int, RiskResult] = {}
        self.cumulative_max_risk: float = 0.0
        self.cumulative_highest_object: Optional[str] = None

    def analyze(
        self,
        motion_states: Dict[int, MotionState],
        collision_assessments: Dict[int, CollisionAssessment],
        directions: Dict[int, str],
        trajectory_status: Dict[int, str],
    ) -> Dict[int, RiskResult]:
        """
        Analyze all tracked objects and compute risk scores.

        Args:
            motion_states: Dict mapping track_id to MotionState.
            collision_assessments: Dict mapping track_id to CollisionAssessment.
            directions: Dict mapping track_id to direction string (LEFT/AHEAD/RIGHT).
            trajectory_status: Dict mapping track_id to trajectory status.

        Returns:
            Dict mapping track_id to RiskResult.
        """
        self.risk_results.clear()
        self.primary_threat = None
        self.max_risk_score = 0.0
        self.highest_risk_object = None

        for track_id, state in motion_states.items():
            assessment = collision_assessments.get(track_id)
            direction = directions.get(track_id, "AHEAD")
            traj_status = trajectory_status.get(track_id, "STABLE PATH")

            risk_result = self._compute_risk(
                state, assessment, direction, traj_status
            )
            self.risk_results[track_id] = risk_result

        # Identify primary threat
        self._identify_primary_threat()

        # Update cumulative stats
        for track_id, rr in self.risk_results.items():
            self.cumulative_risk_results[track_id] = rr
            if rr.risk_score > self.cumulative_max_risk:
                self.cumulative_max_risk = rr.risk_score
                self.cumulative_highest_object = f"{rr.class_name.upper()} #{rr.track_id}"

        logger.debug("Risk analyzed %d objects", len(self.risk_results))
        return self.risk_results

    def _compute_risk(
        self,
        state: MotionState,
        assessment: Optional[CollisionAssessment],
        direction: str,
        traj_status: str,
    ) -> RiskResult:
        """Compute the risk score for a single object."""
        risk_factors = {}

        # 1. Motion state factor (0-100)
        motion_score = self._motion_risk(state.motion_state)
        risk_factors["motion"] = motion_score

        # 2. Direction factor (0-100)
        dir_score = self._direction_risk(direction)
        risk_factors["direction"] = dir_score

        # 3. Proximity factor (0-100)
        prox_score = self._proximity_risk(
            assessment.proximity_to_ego if assessment else 999.0
        )
        risk_factors["proximity"] = prox_score

        # 4. Conflict factor (0-100)
        conflict_score = self._conflict_risk(
            assessment.conflict_status if assessment else "NO SIGNIFICANT CONFLICT"
        )
        risk_factors["conflict"] = conflict_score

        # 5. TTC factor (0-100)
        ttc_score = self._ttc_risk(
            assessment.estimated_ttc if assessment else None
        )
        risk_factors["ttc"] = ttc_score

        # 6. PET factor (0-100)
        pet_score = self._pet_risk(
            assessment.estimated_pet if assessment else None
        )
        risk_factors["pet"] = pet_score

        # 7. Trajectory factor (0-100)
        traj_score = self._trajectory_risk(traj_status)
        risk_factors["trajectory"] = traj_score

        # Weighted combination (0-100 scale)
        weights = {
            "motion": settings.RISK_WEIGHT_MOTION,
            "direction": settings.RISK_WEIGHT_DIRECTION,
            "proximity": settings.RISK_WEIGHT_PROXIMITY,
            "conflict": settings.RISK_WEIGHT_CONFLICT,
            "ttc": settings.RISK_WEIGHT_TTC,
            "pet": settings.RISK_WEIGHT_PET,
            "trajectory": settings.RISK_WEIGHT_TRAJECTORY,
        }

        risk_score = sum(risk_factors[k] * weights[k] for k in weights)

        # Conflict gating: if no meaningful conflict, cap the risk score
        # to prevent false alarms on normal traffic
        has_conflict = assessment is not None and assessment.conflict_status in (
            CONFLICT_HIGH, CONFLICT_POTENTIAL
        )
        has_approaching_conflict = (
            has_conflict
            and state.motion_state == "APPROACHING"
            and assessment.estimated_ttc is not None
            and assessment.estimated_ttc < settings.TTC_MEDIUM_THRESHOLD
        )

        if not has_conflict:
            # No detected conflict: cap risk to prevent false warnings
            risk_score = min(risk_score, 35.0)
        elif not has_approaching_conflict:
            # Has conflict status but not confirmed approaching with valid TTC
            risk_score = min(risk_score, 55.0)

        risk_score = float(np.clip(risk_score, 0.0, 100.0))

        risk_level = self._get_risk_level(risk_score)

        return RiskResult(
            track_id=state.track_id,
            class_name=state.class_name,
            risk_score=round(risk_score, 1),
            risk_level=risk_level,
            direction=direction,
            motion_state=state.motion_state,
            trajectory_status=traj_status,
            conflict_status=assessment.conflict_status if assessment else "NO SIGNIFICANT CONFLICT",
            estimated_ttc=assessment.estimated_ttc if assessment else None,
            estimated_pet=assessment.estimated_pet if assessment else None,
            estimated_drac_risk=assessment.estimated_drac_risk if assessment else "LOW",
            estimated_act=assessment.estimated_act if assessment else None,
            risk_factors=risk_factors,
        )

    def _motion_risk(self, motion_state: str) -> float:
        """Convert motion state to risk score (0-100)."""
        mapping = {
            "APPROACHING": 75.0,
            "MOVING LATERALLY": 40.0,
            "RECEDING": 20.0,
            "STATIONARY": 10.0,
        }
        return mapping.get(motion_state, 10.0)

    def _direction_risk(self, direction: str) -> float:
        """Convert direction to risk score (0-100).

        Direction is not inherently more risky than another.
        Risk depends on actual motion, trajectory, proximity, and conflict.
        """
        return 50.0

    def _proximity_risk(self, proximity: float) -> float:
        """Convert proximity to ego to risk score (0-100)."""
        if proximity < settings.CONFLICT_PROXIMITY_PIXELS:
            return 90.0
        elif proximity < settings.CONFLICT_PROXIMITY_PIXELS * 1.5:
            return 70.0
        elif proximity < settings.CONFLICT_PROXIMITY_PIXELS * 2.5:
            return 45.0
        elif proximity < settings.CONFLICT_PROXIMITY_PIXELS * 4:
            return 25.0
        return 10.0

    def _conflict_risk(self, conflict_status: str) -> float:
        """Convert conflict status to risk score (0-100)."""
        mapping = {
            CONFLICT_HIGH: 90.0,
            CONFLICT_POTENTIAL: 60.0,
            CONFLICT_MONITOR: 30.0,
            "NO SIGNIFICANT CONFLICT": 5.0,
        }
        return mapping.get(conflict_status, 5.0)

    def _ttc_risk(self, ttc: Optional[float]) -> float:
        """Convert estimated TTC to risk score (0-100)."""
        if ttc is None:
            return 5.0
        if ttc < settings.TTC_CRITICAL_THRESHOLD:
            return 95.0
        elif ttc < settings.TTC_HIGH_THRESHOLD:
            return 70.0
        elif ttc < settings.TTC_MEDIUM_THRESHOLD:
            return 40.0
        return 15.0

    def _pet_risk(self, pet: Optional[float]) -> float:
        """Convert estimated PET to risk score (0-100)."""
        if pet is None:
            return 5.0
        if pet < settings.PET_CRITICAL_THRESHOLD:
            return 90.0
        elif pet < settings.PET_HIGH_THRESHOLD:
            return 65.0
        elif pet < settings.PET_MEDIUM_THRESHOLD:
            return 35.0
        return 10.0

    def _trajectory_risk(self, traj_status: str) -> float:
        """Convert trajectory status to risk score (0-100)."""
        mapping = {
            "POTENTIAL CROSSING": 85.0,
            "CONVERGING": 65.0,
            "STABLE PATH": 30.0,
            "MOVING AWAY": 5.0,
        }
        return mapping.get(traj_status, 20.0)

    def _get_risk_level(self, score: float) -> str:
        """Convert numeric score to risk level."""
        if score >= settings.RISK_SCORE_HIGH_MAX:
            return "CRITICAL"
        elif score >= settings.RISK_SCORE_MEDIUM_MAX:
            return "HIGH"
        elif score >= settings.RISK_SCORE_LOW_MAX:
            return "MEDIUM"
        elif score >= settings.RISK_SCORE_SAFE_MAX:
            return "LOW"
        return "SAFE"

    def _identify_primary_threat(self):
        """Identify the highest-risk object as the PRIMARY THREAT."""
        if not self.risk_results:
            return

        sorted_results = sorted(
            self.risk_results.values(),
            key=lambda r: r.risk_score,
            reverse=True
        )

        top = sorted_results[0]
        self.max_risk_score = top.risk_score
        self.highest_risk_object = f"{top.class_name.upper()} #{top.track_id}"

        self.primary_threat = PrimaryThreat(
            object_type=top.class_name.upper(),
            tracking_id=top.track_id,
            direction=top.direction,
            motion_state=top.motion_state,
            trajectory_status=top.trajectory_status,
            conflict_status=top.conflict_status,
            estimated_ttc=top.estimated_ttc,
            estimated_pet=top.estimated_pet,
            estimated_drac_risk=top.estimated_drac_risk,
            estimated_act=top.estimated_act,
            risk_score=top.risk_score,
            risk_level=top.risk_level,
        )

    def get_primary_threat(self) -> Optional[PrimaryThreat]:
        """Return the primary threat."""
        return self.primary_threat

    def get_risk_results(self) -> Dict[int, RiskResult]:
        """Return all risk results."""
        return self.risk_results

    def get_summary(self) -> dict:
        """Return summary statistics across all frames processed."""
        if not self.cumulative_risk_results:
            return {
                "total_objects": 0,
                "max_risk_score": 0,
                "highest_risk_object": "N/A",
                "primary_threat": None,
                "risk_distribution": {"SAFE": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
            }

        distribution = {"SAFE": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for r in self.cumulative_risk_results.values():
            distribution[r.risk_level] = distribution.get(r.risk_level, 0) + 1

        return {
            "total_objects": len(self.cumulative_risk_results),
            "max_risk_score": self.cumulative_max_risk,
            "highest_risk_object": self.cumulative_highest_object or "N/A",
            "primary_threat": self.primary_threat.to_dict() if self.primary_threat else None,
            "risk_distribution": distribution,
        }

    def reset(self):
        """Clear all risk engine state."""
        self.risk_results.clear()
        self.primary_threat = None
        self.max_risk_score = 0.0
        self.highest_risk_object = None
        self.cumulative_risk_results.clear()
        self.cumulative_max_risk = 0.0
        self.cumulative_highest_object = None
