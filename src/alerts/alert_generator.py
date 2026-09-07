"""
Alert generator module.

Produces human-readable collision alerts combining risk level,
direction, and recommended driver action.
"""

from typing import Optional
from dataclasses import dataclass

from src.risk.threat_ranker import RankedThreat
from src.direction.directional_reasoning import Direction
from src.driver_response.inaction_gate import InactionGateResult


@dataclass
class CollisionAlert:
    """A formatted collision alert ready for display."""
    message: str
    risk_level: str
    direction: str
    recommended_action: str
    is_active: bool
    severity_color: str

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "risk_level": self.risk_level,
            "direction": self.direction,
            "recommended_action": self.recommended_action,
            "is_active": self.is_active,
            "severity_color": self.severity_color,
        }


class AlertGenerator:
    """
    Generates formatted collision alerts from threat assessments.
    """

    SEVERITY_COLORS = {
        "CRITICAL": "#FF0000",
        "HIGH": "#FF6600",
        "MEDIUM": "#FFAA00",
        "LOW": "#00CC00",
        "SUPPRESSED": "#888888",
    }

    RECOMMENDED_ACTIONS = {
        "CRITICAL": "BRAKE NOW",
        "HIGH": "PREPARE TO BRAKE",
        "MEDIUM": "CAUTION",
        "LOW": "MONITOR",
        "SUPPRESSED": "Driver responding",
    }

    def generate(
        self,
        ranked_threat: Optional[RankedThreat],
        direction: Direction,
        inaction_result: InactionGateResult,
    ) -> Optional[CollisionAlert]:
        """
        Generate a collision alert from threat assessment.

        Args:
            ranked_threat: The primary ranked threat.
            direction: Direction of the threat.
            inaction_result: Result from the inaction gate.

        Returns:
            CollisionAlert if alert conditions are met, None otherwise.
        """
        if ranked_threat is None:
            return None

        threat = ranked_threat.assessment
        risk_level = inaction_result.adjusted_severity

        if risk_level == "LOW":
            return None

        # Build alert message
        direction_label = direction.value
        class_name = threat.class_name.capitalize()

        if inaction_result.alert_suppressed:
            message = f"Driver responding - {risk_level} warning suppressed"
        else:
            message = f"{risk_level} RISK: {class_name} approaching from {direction_label}"

        recommended_action = self.RECOMMENDED_ACTIONS.get(risk_level, "MONITOR")
        color = self.SEVERITY_COLORS.get(risk_level, "#888888")

        return CollisionAlert(
            message=message,
            risk_level=risk_level,
            direction=direction_label,
            recommended_action=recommended_action,
            is_active=inaction_result.should_alert,
            severity_color=color,
        )

    def format_dashboard_alert(self, alert: Optional[CollisionAlert]) -> str:
        """Format alert for dashboard display."""
        if alert is None:
            return "No active threats detected."

        status = "ACTIVE" if alert.is_active else "SUPPRESSED"
        return f"[{status}] {alert.message} | Action: {alert.recommended_action}"
