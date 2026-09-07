"""
Driver response simulator.

Simulates driver actions in the software prototype: no action,
brake application, or steering response. This module is used
for inaction gate logic and alert suppression decisions.
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass


class DriverAction(Enum):
    """Possible driver response states."""
    NO_ACTION = "NO_ACTION"
    BRAKE_APPLIED = "BRAKE_APPLIED"
    STEERING_RESPONSE = "STEERING_RESPONSE"
    BRAKE_AND_STEER = "BRAKE_AND_STEER"


@dataclass
class DriverState:
    """Current simulated driver state."""
    action: DriverAction
    response_time: float
    confidence: float

    @property
    def is_responding(self) -> bool:
        """True if driver is actively responding to a threat."""
        return self.action != DriverAction.NO_ACTION

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "response_time": self.response_time,
            "confidence": self.confidence,
            "is_responding": self.is_responding,
        }


class DriverSimulator:
    """
    Simulates driver behavior for the software prototype.

    In a production system, this would be replaced by real
    driver monitoring sensors.
    """

    def __init__(self):
        self.current_state = DriverState(
            action=DriverAction.NO_ACTION,
            response_time=0.0,
            confidence=1.0,
        )
        self.response_history = []

    def set_action(self, action: DriverAction, response_time: float = 0.0):
        """
        Set the simulated driver action.

        Args:
            action: The driver action to simulate.
            response_time: Time since threat was detected (seconds).
        """
        self.current_state = DriverState(
            action=action,
            response_time=response_time,
            confidence=1.0,
        )
        self.response_history.append(self.current_state.to_dict())

    def simulate_auto_response(self, risk_level: str, elapsed_time: float) -> DriverAction:
        """
        Automatically simulate a driver response based on risk level.

        This is used for demo/testing purposes.

        Args:
            risk_level: Current threat risk level.
            elapsed_time: Time since threat was detected.

        Returns:
            The simulated driver action.
        """
        if risk_level == "CRITICAL" and elapsed_time > 0.5:
            action = DriverAction.BRAKE_APPLIED
        elif risk_level == "HIGH" and elapsed_time > 1.0:
            action = DriverAction.STEERING_RESPONSE
        elif risk_level == "MEDIUM" and elapsed_time > 1.5:
            action = DriverAction.BRAKE_APPLIED
        else:
            action = DriverAction.NO_ACTION

        self.set_action(action, elapsed_time)
        return action

    def get_state(self) -> DriverState:
        """Return the current driver state."""
        return self.current_state

    def reset(self):
        """Reset driver simulator to default state."""
        self.current_state = DriverState(
            action=DriverAction.NO_ACTION,
            response_time=0.0,
            confidence=1.0,
        )
        self.response_history.clear()
