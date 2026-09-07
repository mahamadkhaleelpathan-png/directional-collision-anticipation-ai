"""
Threat ranker module.

Ranks all detected collision threats and selects the PRIMARY THREAT
that requires the most immediate driver attention.
"""

from typing import List, Optional
from dataclasses import dataclass

from config.thresholds import thresholds
from src.collision.collision_engine import CollisionAssessment
from src.risk.severity_calculator import SeverityCalculator


@dataclass
class RankedThreat:
    """A collision threat with its computed risk score and rank."""
    assessment: CollisionAssessment
    risk_score: float
    risk_level: str
    rank: int
    is_primary: bool

    def to_dict(self) -> dict:
        return {
            **self.assessment.to_dict(),
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "rank": self.rank,
            "is_primary": self.is_primary,
        }


class ThreatRanker:
    """
    Ranks collision threats by severity and identifies the primary threat.

    The primary threat is the one with the highest risk score,
    representing the most imminent danger to the ego vehicle.
    """

    def __init__(self):
        self.severity_calculator = SeverityCalculator()
        self.ranked_threats: List[RankedThreat] = []
        self.primary_threat: Optional[RankedThreat] = None

    def rank(
        self, assessments: List[CollisionAssessment], prediction_confidences: Optional[dict] = None
    ) -> List[RankedThreat]:
        """
        Rank all collision assessments by risk score.

        Args:
            assessments: List of CollisionAssessment objects.
            prediction_confidences: Optional dict mapping track_id to confidence.

        Returns:
            List of RankedThreat objects sorted by risk (highest first).
        """
        self.ranked_threats = []
        confidences = prediction_confidences or {}

        for assessment in assessments:
            confidence = confidences.get(assessment.track_id, 0.8)
            risk_score = self.severity_calculator.calculate(assessment, confidence)
            risk_level = thresholds.get_risk_level(risk_score * 100)

            self.ranked_threats.append(RankedThreat(
                assessment=assessment,
                risk_score=risk_score,
                risk_level=risk_level,
                rank=0,
                is_primary=False,
            ))

        self.ranked_threats.sort(key=lambda t: t.risk_score, reverse=True)

        for i, ranked in enumerate(self.ranked_threats):
            ranked.rank = i + 1
            ranked.is_primary = (i == 0)

        self.primary_threat = self.ranked_threats[0] if self.ranked_threats else None
        return self.ranked_threats

    def get_primary_threat(self) -> Optional[RankedThreat]:
        """Return the highest-ranked threat."""
        return self.primary_threat

    def get_threats_above_level(self, level: str) -> List[RankedThreat]:
        """Return all threats at or above a given risk level."""
        level_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        min_level = level_order.get(level, 0)

        return [
            t for t in self.ranked_threats
            if level_order.get(t.risk_level, 0) >= min_level
        ]

    def reset(self):
        """Clear all ranking state."""
        self.ranked_threats.clear()
        self.primary_threat = None
