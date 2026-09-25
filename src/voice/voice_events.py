"""Voice event data structures shared by the backend and the frontend payload.

The transport contract is additive: a ``voice_alert`` WebSocket message is a
flat dict produced by :meth:`VoiceEvent.to_dict` plus a ``"type"`` field.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

RISK_LEVELS = ("SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL")

SEVERITY_ORDER: Dict[str, int] = {
    "SAFE": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

# Playback priority per risk level. A higher number preempts a lower one
# while the frontend audio queue is speaking.
PRIORITY_MAP: Dict[str, int] = {
    "SAFE": 10,
    "LOW": 10,
    "MEDIUM": 50,
    "HIGH": 80,
    "CRITICAL": 100,
}

# New events at/above this priority interrupt the utterance being spoken.
INTERRUPT_PRIORITY: int = PRIORITY_MAP["HIGH"]

# Conversational answers and the "Test voice" button.
QUERY_PRIORITY: int = 60
TEST_PRIORITY: int = 75


@dataclass
class VoiceEvent:
    """A single backend-generated voice alert."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    kind: str = "risk_alert"
    risk_level: str = "SAFE"
    direction: str = "AHEAD"
    text: str = ""
    track_id: Optional[int] = None
    class_name: Optional[str] = None
    risk_score: float = 0.0
    ttc: Optional[float] = None
    speed_kmh: Optional[float] = None
    speed_confidence: Optional[float] = None
    speed_status: Optional[str] = None
    priority: int = 10
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    trigger: str = "stability_satisfied"
    # Part 4 multilingual + speed-validation metadata (additive).
    language: str = ""
    speed_valid: bool = False
    speed_timestamp_s: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe dict delivered over the WebSocket as ``voice_alert``.

        Additive aliases: ``message`` (== text), ``vehicle_class``
        (== class_name), ``ttc_seconds`` (== ttc) and ``locale``
        (== language). Original keys stay so existing WebSocket clients are
        never broken.
        """
        d = asdict(self)
        d["message"] = self.text
        d["vehicle_class"] = self.class_name
        d["ttc_seconds"] = self.ttc
        d["locale"] = self.language
        return d