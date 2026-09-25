"""Voice/TTS provider abstraction.

The backend never renders audio unless a real provider is configured.
- ``LogVoiceProvider`` (default) records what would have been spoken and is
  always available.
- ``EdgeTTSProvider`` is an optional real synthesizer, enabled only when
  ``VOICE_PROVIDER=edge_tts`` and ``edge-tts`` is installed. It loads
  lazily; if the package is missing the provider reports unavailable and the
  pipeline keeps running (log fallback, never crash).

Browser clients render the actual audio with the Web Speech API (frontend
fallback) so no audio files are produced on the server by default.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Real Microsoft Edge neural voices for the supported Indian locales
# (item 35: true per-locale voices, with a safe fallback to the configured
# voice for locales where no Edge voice is published yet, e.g. Odia).
_INDIAN_VOICE_MAP = {
    "en-in": "en-IN-PrabhatNeural",
    "hi-in": "hi-IN-MadhurNeural",
    "te-in": "te-IN-MohanNeural",
    "ta-in": "ta-IN-ValluvarNeural",
    "kn-in": "kn-IN-GaganNeural",
    "ml-in": "ml-IN-MidhunNeural",
    "mr-in": "mr-IN-ManoharNeural",
    "gu-in": "gu-IN-NiranjanNeural",
    "bn-in": "bn-IN-BashkarNeural",
    "pa-in": "pa-IN-AbhishekNeural",
    "ur-in": "ur-IN-SalmanNeural",
}


class VoiceProvider:
    """Interface implemented by every backend voice provider."""

    name = "base"
    _lock = threading.Lock()

    def speak(self, text: str, interrupt: bool = False, language: Optional[str] = None) -> bool:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError

    def close(self) -> None:
        pass


class LogVoiceProvider(VoiceProvider):
    """Default provider: logs the exact payload that would be spoken."""

    name = "log"

    def speak(self, text: str, interrupt: bool = False, language: Optional[str] = None) -> bool:
        with self._lock:
            logger.info(
                "VOICE SPEAKING provider=%s interrupt=%s lang=%s text=%r",
                self.name, interrupt, language, text,
            )
        return True

    def stop(self) -> None:
        pass

    def is_available(self) -> bool:
        return True


class EdgeTTSProvider(VoiceProvider):
    """Optional real synthesizer built on microsoft ``edge-tts``.

    Requires ``pip install edge-tts`` AND ``VOICE_PROVIDER=edge_tts``.
    Synthesizes and discards the audio (the browser performs playback);
    failures log and return False rather than raising.
    """

    name = "edge_tts"

    def __init__(self, voice: str = "", language: str = "en-US", **_: Any) -> None:
        self._voice = voice or "en-US-ChristopherNeural"
        self._language = language
        self._mod: Optional[Any] = None
        try:
            import edge_tts  # type: ignore[import-not-found]

            self._mod = edge_tts
            logger.info("VOICE PROVIDER edge_tts module loaded")
        except Exception as exc:  # noqa: BLE001
            logger.warning("VOICE PROVIDER edge_tts unavailable: %s", exc)
            self._mod = None

    def is_available(self) -> bool:
        return self._mod is not None

    def speak(self, text: str, interrupt: bool = False, language: Optional[str] = None) -> bool:
        if self._mod is None:
            logger.error("VOICE PROVIDER ERROR edge_tts not installed")
            return False
        import asyncio

        voice = _INDIAN_VOICE_MAP.get((language or "").lower(), self._voice)
        if (language or "").lower() and (language or "").lower() not in _INDIAN_VOICE_MAP:
            logger.info(
                "VOICE FALLBACK lang=%s voice=%s (no published edge-tts voice for locale)",
                language, self._voice,
            )
        try:
            asyncio.run(self._stream(text, voice))
        except Exception as exc:  # noqa: BLE001
            logger.error("VOICE PROVIDER ERROR edge_tts: %s", exc)
            return False
        logger.info(
            "VOICE SPEAKING provider=%s interrupt=%s lang=%s text_len=%d",
            self.name, interrupt, language, len(text),
        )
        return True

    async def _stream(self, text: str, voice: str) -> None:
        communicate = self._mod.Communicate(text, voice)  # type: ignore[attr-defined]
        async for _ in communicate.stream():
            pass  # force synthesis, discard audio for browser playback

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass