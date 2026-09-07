"""
Warning logic module.

Implements the decision logic for when and how to present
warnings to the driver based on threat characteristics.
"""

from typing import Optional, List
from dataclasses import dataclass

from src.risk.threat_ranker import RankedThreat
from src.alerts.alert_generator import CollisionAlert


@dataclass
class WarningDecision:
    """Decision on how to present a warning."""
    show_visual_warning: bool
    show_audio_warning: bool
    warning_duration: float
    warning_priority: int
    display_text: str

    def to_dict(self) -> dict:
        return {
            "show_visual_warning": self.show_visual_warning,
            "show_audio_warning": self.show_audio_warning,
            "warning_duration": self.warning_duration,
            "warning_priority": self.warning_priority,
            "display_text": self.display_text,
        }


class WarningLogic:
    """
    Determines warning presentation parameters based on
    threat severity and system state.
    """

    def __init__(self):
        self.current_decision: Optional[WarningDecision] = None

    def decide(
        self,
        alert: Optional[CollisionAlert],
        ranked_threat: Optional[RankedThreat],
    ) -> Optional[WarningDecision]:
        """
        Make a warning presentation decision.

        Args:
            alert: The generated collision alert.
            ranked_threat: The primary ranked threat.

        Returns:
            WarningDecision or None if no warning needed.
        """
        if alert is None or not alert.is_active:
            self.current_decision = None
            return None

        risk_level = alert.risk_level

        if risk_level == "CRITICAL":
            decision = WarningDecision(
                show_visual_warning=True,
                show_audio_warning=True,
                warning_duration=5.0,
                warning_priority=1,
                display_text=alert.message,
            )
        elif risk_level == "HIGH":
            decision = WarningDecision(
                show_visual_warning=True,
                show_audio_warning=True,
                warning_duration=3.0,
                warning_priority=2,
                display_text=alert.message,
            )
        elif risk_level == "MEDIUM":
            decision = WarningDecision(
                show_visual_warning=True,
                show_audio_warning=False,
                warning_duration=2.0,
                warning_priority=3,
                display_text=alert.message,
            )
        else:
            decision = None

        self.current_decision = decision
        return decision

    def get_current_decision(self) -> Optional[WarningDecision]:
        """Return the current warning decision."""
        return self.current_decision

    def reset(self):
        """Reset warning logic state."""
        self.current_decision = None
