"""Thread-safe holder for the live voice language selection.

The user can change the voice language from the HUD while a video is
processing (spec: "language switching during video without restart"). The
pipeline thread reads this state on every frame, so the change takes effect
on the next evaluated event without stopping/restarting the job.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional

from src.voice.languages import DEFAULT_LANGUAGE, LANGUAGE_LABELS, supported_languages


class VoiceLanguageState:
    """Small lock-guarded language selector shared between API and pipeline."""

    def __init__(self, language: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        chosen = (language or DEFAULT_LANGUAGE).strip()
        if chosen in LANGUAGE_LABELS:
            self._language = chosen
            self._valid = True
        else:
            self._language = DEFAULT_LANGUAGE
            self._valid = False

    def get_language(self) -> str:
        with self._lock:
            return self._language

    @property
    def valid(self) -> bool:
        with self._lock:
            return self._valid

    def set_language(self, code: str) -> bool:
        """Set a validated language code. Unsupported codes are rejected
        (the previous language stays active) so we never fake a language."""
        code = (code or "").strip()
        if code not in LANGUAGE_LABELS:
            return False
        with self._lock:
            changed = self._language != code
            self._language = code
            self._valid = True
        return changed

    def to_dict(self) -> Dict[str, str]:
        return {"language": self.get_language(), "valid": self._valid}