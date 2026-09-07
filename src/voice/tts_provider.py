"""Text-to-speech facade.

Kept separate from :mod:`src.voice.voice_provider` so the backend has one
stable entry point for TTS while tests can swap the provider. Never raises:
failures are logged by the provider layer and reported as False.
"""

from __future__ import annotations

from typing import Optional

from src.voice.voice_provider import LogVoiceProvider, VoiceProvider


def text_to_speech(
    text: str,
    provider: Optional[VoiceProvider] = None,
    interrupt: bool = False,
    language: Optional[str] = None,
) -> bool:
    """Synthesize ``text`` through ``provider`` (log-only fallback by default).

    Returns True when a provider handled/announced the request, False when the
    text was empty or the provider raised. Never propagates exceptions.
    """
    if text is None or not str(text).strip():
        return False
    active = provider if provider is not None else LogVoiceProvider()
    try:
        return bool(active.speak(str(text), interrupt=interrupt, language=language))
    except Exception:  # noqa: BLE001
        return False