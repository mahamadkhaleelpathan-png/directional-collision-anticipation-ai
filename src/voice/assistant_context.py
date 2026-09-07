"""Rules-based conversational answers for the voice assistant.

The backend is the single source of truth: every reply is derived strictly
from job context passed in as a plain dict. The assistant NEVER invents
numbers; anything unknown produces an explicit "I don't have ..." reply so
the user immediately knows the state was incomplete.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

_HELP_ANSWER = (
    "I'm your AI voice safety assistant. Ask me about the current risk, "
    "the direction of threats, detected objects, time to collision, speeds, "
    "or calibration status."
)


def _approach(direction: Optional[str]) -> str:
    d = (direction or "AHEAD").upper()
    if d == "LEFT":
        return "coming from your left"
    if d == "RIGHT":
        return "coming from your right"
    if d == "AHEAD":
        return "coming from ahead"
    return "in the scene"


def build_assistant_context(
    status: str,
    stats: Optional[Dict[str, Any]] = None,
    worst: Optional[Dict[str, Any]] = None,
    calibrated: bool = False,
    speed_min_confidence: float = 0.6,
) -> Dict[str, Any]:
    """Assemble the plain-dict context used by :func:`answer_question`."""
    return {
        "status": status or "unknown",
        "worst": worst or {},
        "class_counts": (stats or {}).get("class_counts") or {},
        "calibrated": bool(calibrated),
        "speed_min_confidence": float(speed_min_confidence),
    }


def answer_question(question: Optional[str], context: Optional[Dict[str, Any]]) -> str:
    """Answer a free-form question using only the provided context."""
    q = (question or "").lower().strip()
    ctx = context or {}
    worst = ctx.get("worst") or {}
    level = str(worst.get("risk_level") or "SAFE").upper()
    ttc = worst.get("ttc")
    direction = worst.get("direction")
    speed_kmh = worst.get("speed_kmh")
    speed_confidence = worst.get("speed_confidence")
    speed_status = str(worst.get("speed_status") or "").upper()

    if not q:
        return _HELP_ANSWER

    if any(token in q for token in ("who are you", "help", "what can you", "capabilities")):
        return _HELP_ANSWER

    if "calibrat" in q:
        if ctx.get("calibrated"):
            return "Speed calibration is active, so object speeds can be reported reliably."
        return "Speed calibration is not configured, so I can only describe motion qualitatively."

    if any(token in q for token in ("speed", "how fast", "km/h", "kmh", "kilometer", "mph", "fast", "slow")):
        min_conf = float(ctx.get("speed_min_confidence") or 0.6)
        if (
            speed_status == "ESTIMATED"
            and speed_kmh is not None
            and speed_confidence is not None
            and speed_confidence >= min_conf
        ):
            obj = str(worst.get("class_name") or "object").lower()
            return f"The {obj} is moving at about {float(speed_kmh):.0f} kilometers per hour."
        return "I don't have a reliable speed estimate right now."

    if any(token in q for token in ("risk", "danger", "unsafe", "safe", "collision", "crash", "threat", "ttc", "impact", "time to")):
        if level in ("CRITICAL", "HIGH", "MEDIUM"):
            parts = [f"Current risk level is {level}."]
            if direction and direction != "AHEAD":
                parts.append(f"Threat is {_approach(direction)}.")
            if ttc is not None and ttc > 0:
                parts.append(f"Estimated time to collision is about {ttc:.1f} seconds.")
            return " ".join(parts)
        return "The scene is currently safe — no immediate collision threat detected."

    if any(token in q for token in ("how many", "count of", "detect", "track", "objects", "vehicles")):
        counts = ctx.get("class_counts") or {}
        if not counts:
            return "No detections to report yet."
        total = int(sum(counts.values()) or 0)
        top = sorted(counts.items(), key=lambda kv: int(kv[1] or 0), reverse=True)[:3]
        top_text = ", ".join(f"{str(k)} {v}" for k, v in top)
        return f"{total} detections across the simulation. Most seen: {top_text}."

    if any(token in q for token in ("direction", "left", "right", "ahead", "where")):
        if level in ("CRITICAL", "HIGH", "MEDIUM") and direction:
            return f"The main threat is {_approach(direction)}."
        return "No directional threat is present right now."

    return (
        "I don't have an answer for that yet. Try asking about risk, direction, "
        "detections, speed, or calibration."
    )