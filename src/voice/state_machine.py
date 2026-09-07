"""Controlled state machine for the voice assistant lifecycle.

Both the backend (event generation) and the frontend (audio playback) drive
the same small set of states, so the allowed transitions live here in one
place. Invalid transitions are rejected silently (the caller keeps its
current state) instead of raising.
"""

from __future__ import annotations

from typing import Dict, Set

STATE_IDLE = "IDLE"
STATE_MONITORING = "MONITORING"
STATE_LISTENING = "LISTENING"
STATE_THINKING = "THINKING"
STATE_SPEAKING = "SPEAKING"
STATE_MUTED = "MUTED"
STATE_ERROR = "ERROR"
STATE_OFFLINE = "OFFLINE"

ALL_STATES = (
    STATE_IDLE,
    STATE_MONITORING,
    STATE_LISTENING,
    STATE_THINKING,
    STATE_SPEAKING,
    STATE_MUTED,
    STATE_ERROR,
    STATE_OFFLINE,
)

_ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    STATE_IDLE: {STATE_MONITORING, STATE_OFFLINE},
    STATE_MONITORING: {
        STATE_SPEAKING,
        STATE_LISTENING,
        STATE_MUTED,
        STATE_OFFLINE,
        STATE_ERROR,
        STATE_IDLE,
    },
    STATE_LISTENING: {
        STATE_THINKING,
        STATE_MONITORING,
        STATE_MUTED,
        STATE_OFFLINE,
        STATE_ERROR,
        STATE_IDLE,
    },
    STATE_THINKING: {
        STATE_SPEAKING,
        STATE_MONITORING,
        STATE_MUTED,
        STATE_OFFLINE,
        STATE_ERROR,
        STATE_IDLE,
    },
    STATE_SPEAKING: {
        STATE_MONITORING,
        STATE_MUTED,
        STATE_OFFLINE,
        STATE_ERROR,
        STATE_IDLE,
    },
    STATE_MUTED: {STATE_MONITORING, STATE_OFFLINE, STATE_ERROR, STATE_IDLE},
    STATE_ERROR: {STATE_MONITORING, STATE_OFFLINE, STATE_IDLE},
    STATE_OFFLINE: {STATE_MONITORING, STATE_IDLE},
}


class VoiceStateMachine:
    """Minimal finite state machine guarding voice assistant transitions."""

    def __init__(self, initial: str = STATE_IDLE) -> None:
        if initial not in ALL_STATES:
            initial = STATE_IDLE
        self._state = initial

    @property
    def state(self) -> str:
        return self._state

    def can_transition(self, target: str) -> bool:
        return target in _ALLOWED_TRANSITIONS.get(self._state, set())

    def transition(self, target: str) -> bool:
        """Transition only when allowed. Returns True if the state changed."""
        try:
            if self.can_transition(target):
                self._state = target
                return True
        except Exception:  # noqa: BLE001 - transition must never raise
            pass
        return False

    def reset(self) -> None:
        self._state = STATE_IDLE