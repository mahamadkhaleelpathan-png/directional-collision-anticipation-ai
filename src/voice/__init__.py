"""
AI Voice Safety Assistant.

Additive layer that converts existing per-frame risk results produced by
`src.pipeline.processor` into natural spoken alerts. The backend pipeline
remains the single source of truth for risk/score/TTC/direction/track/
class/speed; this package only formats, debounces, priorities and delivers
them. It never alters detection, tracking, collision or risk logic.
"""

from src.voice.alert_templates import build_alert_text, build_voice_message
from src.voice.languages import DEFAULT_LANGUAGE, supported_languages
from src.voice.voice_events import PRIORITY_MAP, RISK_LEVELS, VoiceEvent
from src.voice.voice_manager import VoiceAlertManager

__all__ = [
    "PRIORITY_MAP",
    "RISK_LEVELS",
    "VoiceAlertManager",
    "VoiceEvent",
    "build_alert_text",
    "build_voice_message",
    "DEFAULT_LANGUAGE",
    "supported_languages",
]