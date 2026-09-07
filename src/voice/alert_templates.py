"""Natural-language phrase builders for voice alerts (and the all-clear).

Kept as plain, deterministic functions so the generated sentences are
unit-testable and the exact wording cannot drift across refactors.

``build_alert_text`` produces the English sentences (item 12/13/14 exact
strings preserved), while ``build_alert_text_lang`` in :mod:`src.voice.languages`
produces the localized sentences. ``build_voice_message`` is the single entry
point used by the voice manager and returns the structured dict required by
item 24 (text, language, risk_level, priority, track_id, speed_kmh,
speed_valid, ...).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from src.voice.languages import DEFAULT_LANGUAGE, build_alert_text_lang, round_speed
from src.voice.voice_events import PRIORITY_MAP

_BASE_TEXT: Dict[str, str] = {
    "MEDIUM": "Caution. Medium collision risk detected.",
    "HIGH": "Warning. High collision risk detected.",
    "CRITICAL": "Emergency. Critical collision risk. Slow down immediately.",
}


def _direction_phrases(direction: Optional[str]) -> Tuple[str, str]:
    """Return (approach phrase, location phrase) for a direction token."""
    d = (direction or "AHEAD").upper()
    if d == "LEFT":
        return "from your left", "on your left"
    if d == "RIGHT":
        return "from your right", "on your right"
    if d == "AHEAD":
        return "from ahead", "ahead"
    return "nearby", "nearby"


def _speed_clause_en(speed_kmh: Optional[float], track_id: Optional[int]) -> str:
    """English comma-,prefixed speed clause, e.g. ", vehicle 17 moving at
    approximately 46 kilometers per hour"."""
    rs = round_speed(speed_kmh)
    if rs is None or rs <= 0:
        return ""
    vehicle = f", vehicle #{track_id}" if track_id is not None else ""
    return f"{vehicle} moving at approximately {rs} kilometers per hour"


def build_alert_text(
    risk_level: str,
    direction: Optional[str] = "AHEAD",
    ttc: Optional[float] = None,
    speed_kmh: Optional[float] = None,
    class_name: Optional[str] = None,
    ttc_max_s: float = 10.0,
    include_speed: bool = False,
    track_id: Optional[int] = None,
) -> str:
    """Build a single-line English sentence for a risk situation.

    The output is deterministic so callers and tests can assert on stable
    substrings such as "left", "right", "ahead" and "kilometers per hour".
    The per-level base sentences (item 12) are returned verbatim when no
    direction/TTC/speed detail is present; direction, TTC and the same-track
    speed are appended as clauses (items 13/14).
    """
    level = (risk_level or "SAFE").upper()

    if level == "SAFE":
        return "Road ahead is clear."

    approach, location = _direction_phrases(direction)

    ttc_clause = ""
    if ttc is not None and ttc > 0 and ttc <= ttc_max_s:
        ttc_clause = f" in about {ttc:.1f} seconds"

    speed_clause = ""
    if include_speed and speed_kmh is not None:
        speed_clause = _speed_clause_en(speed_kmh, track_id)

    has_detail = (
        (direction or "AHEAD").upper() != "AHEAD" or bool(ttc_clause) or bool(speed_clause)
    )

    if level == "CRITICAL":
        if not has_detail:
            return _BASE_TEXT["CRITICAL"]
        return (
            f"Emergency. Critical collision risk {approach}{ttc_clause}{speed_clause}."
            " Slow down immediately."
        )

    if level == "HIGH":
        if not has_detail:
            return _BASE_TEXT["HIGH"]
        return f"Warning. High collision risk {approach}{ttc_clause}{speed_clause}. Reduce speed."

    if level == "MEDIUM":
        if not has_detail:
            return _BASE_TEXT["MEDIUM"]
        return f"Caution. Medium collision risk {approach}{ttc_clause}{speed_clause}."

    # LOW and any other sub-threshold level: calmly name the location.
    return f"Object detected {location}."


def build_voice_message(
    risk_level: str,
    direction: Optional[str] = "AHEAD",
    ttc: Optional[float] = None,
    speed_kmh: Optional[float] = None,
    speed_confidence: Optional[float] = None,
    ttc_max_s: float = 10.0,
    include_speed: bool = False,
    vehicle_class: Optional[str] = None,
    track_id: Optional[int] = None,
    language: str = DEFAULT_LANGUAGE,
) -> Dict[str, Any]:
    """Structured voice message builder (item 24).

    Returns a flat dict carrying the exact sentence plus transport metadata:
    ``text, language, spoken_language, fallback_language, risk_level,
    priority, track_id, speed_kmh, speed_valid, direction, ttc_seconds,
    vehicle_class, speed_confidence``.

    ``include_speed`` must only be True after the caller (voice manager)
    already validated calibration/confidence/staleness/max-reasonable-checks.
    """
    level = (risk_level or "SAFE").upper()
    is_english = str(language or "").lower().startswith("en")

    if is_english:
        text = build_alert_text(
            risk_level=level,
            direction=direction,
            ttc=ttc,
            speed_kmh=speed_kmh,
            class_name=vehicle_class,
            ttc_max_s=ttc_max_s,
            include_speed=include_speed,
            track_id=track_id,
        )
        spoken = "en-IN"
    else:
        text, spoken = build_alert_text_lang(
            risk_level=level,
            direction=direction,
            ttc=ttc,
            speed_kmh=speed_kmh,
            class_name=vehicle_class,
            track_id=track_id,
            language=language or DEFAULT_LANGUAGE,
            ttc_max_s=ttc_max_s,
            include_speed=include_speed,
        )

    rs = round_speed(speed_kmh) if (include_speed and speed_kmh is not None) else None
    speed_valid = bool(include_speed and rs is not None and rs > 0)

    return {
        "text": text,
        "language": language or DEFAULT_LANGUAGE,
        "spoken_language": spoken,
        "fallback_language": None if spoken == (language or DEFAULT_LANGUAGE) else spoken,
        "risk_level": level,
        "priority": PRIORITY_MAP.get(level, PRIORITY_MAP["LOW"]),
        "track_id": track_id,
        "speed_kmh": rs,
        "speed_valid": speed_valid,
        "speed_confidence": speed_confidence if include_speed else None,
        "direction": direction or "AHEAD",
        "ttc_seconds": ttc if (ttc is not None and ttc > 0 and ttc <= ttc_max_s) else None,
        "vehicle_class": vehicle_class,
    }