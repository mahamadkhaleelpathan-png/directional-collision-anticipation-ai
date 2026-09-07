"""
Inaction gate module.

Implements the critical logic:
    HIGH RISK + DRIVER NOT RESPONDING = GENERATE ALERT
    HIGH RISK + DRIVER ALREADY RESPONDING = SUPPRESS/REDUCE ALERT

This prevents redundant alerts when the driver is already taking
corrective action.
"""

from typing import Optional
from dataclasses import dataclass

from config.thresholds import thresholds
from src.driver_response.driver_simulator import DriverState


@dataclass
class InactionGateResult:
    """Result of the inaction gate evaluation."""
    should_alert: bool
    alert_suppressed: bool
    reason: str
    adjusted_severity: str

    def to_dict(self) -> dict:
        return {
            "should_alert": self.should_alert,
            "alert_suppressed": self.alert_suppressed,
            "reason": self.reason,
            "adjusted_severity": self.adjusted_severity,
        }


class InactionGate:
    """
    Evaluates whether an alert should be generated based on
    risk level and driver response state.
    """

    def __init__(self):
        self.last_alert_time = 0.0
        self.cooldown = thresholds.driver_response_cooldown

    def evaluate(
        self,
        risk_level: str,
        driver_state: DriverState,
        current_time: float = 0.0,
    ) -> InactionGateResult:
        """
        Evaluate whether to generate, suppress, or modify an alert.

        Args:
            risk_level: Current threat risk level (CRITICAL, HIGH, MEDIUM, LOW).
            driver_state: Current driver response state.
            current_time: Current timestamp for cooldown checking.

        Returns:
            InactionGateResult with the decision.
        """
        # Cooldown check
        if (current_time - self.last_alert_time) < self.cooldown and current_time > 0:
            return InactionGateResult(
                should_alert=False,
                alert_suppressed=True,
                reason="Alert cooldown active",
                adjusted_severity=risk_level,
            )

        # Driver is responding - suppress alert
        if driver_state.is_responding:
            return InactionGateResult(
                should_alert=False,
                alert_suppressed=True,
                reason="Driver responding - warning suppressed",
                adjusted_severity="SUPPRESSED",
            )

        # Driver not responding and risk is significant
        if risk_level in ("CRITICAL", "HIGH"):
            self.last_alert_time = current_time
            return InactionGateResult(
                should_alert=True,
                alert_suppressed=False,
                reason=f"Driver not responding to {risk_level} risk",
                adjusted_severity=risk_level,
            )

        # Medium risk - reduced alert
        if risk_level == "MEDIUM":
            return InactionGateResult(
                should_alert=True,
                alert_suppressed=False,
                reason="Medium risk detected",
                adjusted_severity="MEDIUM",
            )

        # Low risk - no alert needed
        return InactionGateResult(
            should_alert=False,
            alert_suppressed=False,
            reason="Risk level below alert threshold",
            adjusted_severity="LOW",
        )

    def reset(self):
        """Reset gate state."""
        self.last_alert_time = 0.0
