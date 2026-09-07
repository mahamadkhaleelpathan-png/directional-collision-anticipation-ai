"""Core voice alert decision engine.

Receives the worst per-frame threat (already decided by the risk engine),
applies debounce (stability window), per-level cooldowns, duplicate
suppression, escalation override, critical interruption, track-change and
speed-change detection, then emits a :class:`~src.voice.voice_events.VoiceEvent`
that the transport layer pushes to connected clients over the existing
WebSocket, forwarding the same text to the backend voice provider.

Speed handling (items 8/28): the same-track ESTIMATED speed is spoken only
when finite, positive, below the configured maximum, above the confidence
threshold and fresh (source-seconds age <= max). Missing/freshness-rejected
speeds never produce a speed clause.

Failure policy: a voice outage must never break video analysis. All audible
work is wrapped so the manager can only raise for programmer errors, and the
pipeline wraps the whole evaluate() call as well.
"""

from __future__ import annotations

import math
import time as _time
from typing import Any, Callable, Dict, List, Optional, Tuple

from config.settings import settings
from src.utils.logger import get_logger
from src.voice.alert_templates import build_voice_message
from src.voice.languages import DEFAULT_LANGUAGE, is_supported_language, round_speed, test_text
from src.voice.state_machine import (
    STATE_IDLE,
    STATE_MONITORING,
    STATE_MUTED,
    STATE_OFFLINE,
    STATE_SPEAKING,
    VoiceStateMachine,
)
from src.voice.voice_events import (
    INTERRUPT_PRIORITY,
    PRIORITY_MAP,
    SEVERITY_ORDER,
    TEST_PRIORITY,
    VoiceEvent,
)
from src.voice.voice_provider import EdgeTTSProvider, LogVoiceProvider, VoiceProvider

logger = get_logger(__name__)


def severity_index(level: str) -> int:
    """Stable rank for a risk level token (unknown -> SAFE)."""
    return SEVERITY_ORDER.get((level or "SAFE").upper(), SEVERITY_ORDER["SAFE"])


def _provider_from_settings(provider_name: Optional[str] = None) -> VoiceProvider:
    name = (provider_name or settings.VOICE_PROVIDER or "log").lower()
    if name in ("edge_tts", "edge-tts", "edge"):
        return EdgeTTSProvider(voice=settings.VOICE_VOICE, language=settings.VOICE_LANGUAGE)
    return LogVoiceProvider()


class VoiceAlertManager:
    """Per-video decision engine. Instantiate once per processed job."""

    def __init__(
        self,
        fps: float = 30.0,
        enabled: bool = settings.VOICE_ASSISTANT_ENABLED,
        provider: Optional[VoiceProvider] = None,
        min_alert_level: str = settings.VOICE_MIN_ALERT_LEVEL,
        cooldown_medium_s: float = settings.VOICE_COOLDOWN_MEDIUM_S,
        cooldown_high_s: float = settings.VOICE_COOLDOWN_HIGH_S,
        cooldown_critical_s: float = settings.VOICE_COOLDOWN_CRITICAL_S,
        cooldown_safe_s: float = settings.VOICE_COOLDOWN_SAFE_S,
        stability_window_frames: int = settings.RISK_STABILITY_WINDOW_FRAMES,
        ttc_max_s: float = settings.VOICE_TTC_MAX_S,
        speed_min_confidence: float = settings.VOICE_SPEED_MIN_CONFIDENCE,
        max_reasonable_speed_kmh: float = settings.VOICE_MAX_REASONABLE_SPEED_KMH,
        max_speed_data_age_s: float = settings.VOICE_MAX_SPEED_DATA_AGE_S,
        speed_change_alert_threshold_kmh: float = settings.VOICE_SPEED_CHANGE_ALERT_THRESHOLD_KMH,
        language: str = settings.VOICE_LANGUAGE,
        language_source: Optional[Any] = None,
        max_queue: int = settings.VOICE_MAX_QUEUE,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._fps = max(float(fps or 30.0), 0.001)
        self._enabled = bool(enabled)
        self._provider = provider if provider is not None else _provider_from_settings()
        self._min_level = str(min_alert_level or "MEDIUM").upper()
        self._cooldowns = {
            "SAFE": float(cooldown_safe_s),
            "MEDIUM": float(cooldown_medium_s),
            "HIGH": float(cooldown_high_s),
            "CRITICAL": float(cooldown_critical_s),
        }
        self._stability_window = max(int(stability_window_frames or 0), 1)
        self._ttc_max_s = float(ttc_max_s)
        self._speed_min_confidence = float(speed_min_confidence)
        self._max_reasonable_speed_kmh = float(max_reasonable_speed_kmh)
        self._max_speed_data_age_s = float(max_speed_data_age_s)
        self._speed_change_threshold = float(speed_change_alert_threshold_kmh)
        self._language = language or DEFAULT_LANGUAGE
        self._language_source = language_source
        self._max_queue = max(int(max_queue or 1), 1)
        self._clock = clock or _time.monotonic

        self.state_machine = VoiceStateMachine(STATE_MONITORING if self._enabled else STATE_IDLE)
        self._muted = False
        self._muted_logged = False

        self._last_emit = 0.0
        self._last_emit_by_level: Dict[str, float] = {}
        self._last_emit_by_track: Dict[Any, float] = {}
        self._last_level: Optional[str] = None
        self._last_text: Optional[str] = None
        self._last_emit_track: Optional[Any] = None
        self._last_speed_kmh: Optional[int] = None
        self._provider_down = False
        self._track_flap_gap_s = 1.5
        self._eval_started: Optional[float] = None
        self._consecutive: Dict[str, int] = {}
        self._current_worst: Dict[str, Any] = {}
        self._recent: List[VoiceEvent] = []
        self._alerts_emitted = 0

    # ------------------------------------------------------------------ props

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def current_level(self) -> Optional[str]:
        return self._last_level

    @property
    def current_worst(self) -> Dict[str, Any]:
        return dict(self._current_worst)

    @property
    def last_text(self) -> Optional[str]:
        return self._last_text

    @property
    def recent_events(self) -> List[VoiceEvent]:
        return list(self._recent)

    @property
    def alerts_emitted(self) -> int:
        return self._alerts_emitted

    # ------------------------------------------------------------- control

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        self._muted_logged = False
        if muted:
            self.state_machine.transition(STATE_MUTED)
            logger.info("VOICE MUTED state=%s", self.state_machine.state)
        else:
            self.state_machine.transition(STATE_MONITORING)
            logger.info("VOICE UNMUTED state=%s", self.state_machine.state)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if self._enabled:
            self.state_machine.transition(STATE_MONITORING)
        else:
            self.state_machine.transition(STATE_IDLE)
        logger.info("VOICE STATE CHANGE enabled=%s state=%s", self._enabled, self.state_machine.state)

    def set_language(self, code: str) -> bool:
        """Change the static fallback language (the live ``language_source``,
        when provided, takes precedence during evaluate)."""
        if is_supported_language(code):
            self._language = code
            return True
        return False

    # --------------------------------------------------------------- logic

    def evaluate(self, record: Optional[Dict[str, Any]], frame_idx: int = 0) -> Optional[VoiceEvent]:
        """Decide whether to announce the worst threat of the frame.

        Returns the emitted event (if any) so the caller can transport it;
        returns None when nothing should be spoken.
        """
        if not self._enabled:
            return None
        if self._muted:
            if not self._muted_logged:
                logger.info("VOICE MUTED — alerts suppressed")
                self._muted_logged = True
            return None

        now = self._clock()
        self._eval_started = now
        event_time = frame_idx / self._fps

        self._track_provider_health()

        if not record:
            return None

        level = str(record.get("risk_level") or "SAFE").upper()
        if level not in PRIORITY_MAP:
            level = "SAFE"
        effective = "SAFE" if level in ("SAFE", "LOW") else level

        worst = {
            "track_id": record.get("track_id"),
            "class_name": record.get("class_name"),
            "direction": str(record.get("direction") or "AHEAD").upper(),
            "risk_level": effective,
            "risk_score": float(record.get("risk_score") or 0.0),
            "ttc": self._clean_ttc(record.get("estimated_ttc") or record.get("ttc")),
            "speed_kmh": record.get("speed_kmh"),
            "speed_confidence": record.get("speed_confidence"),
            "speed_status": str(record.get("speed_status") or "").upper(),
            "speed_timestamp_s": record.get("speed_timestamp_s"),
        }
        self._current_worst = worst

        logger.info(
            "RISK DETECTED level=%s track=%s frame=%d risk_score=%.1f",
            effective, worst.get("track_id"), frame_idx, worst.get("risk_score"),
        )

        self._consecutive[effective] = self._consecutive.get(effective, 0) + 1
        for other in list(self._consecutive):
            if other != effective:
                self._consecutive[other] = 0
        consecutive = self._consecutive[effective]

        speed_valid, speed_kmh, speed_reason = self._validate_speed(worst, event_time)
        if speed_valid:
            logger.info("VOICE SPEED VALID track=%s speed_kmh=%s", worst.get("track_id"), speed_kmh)
        elif effective != "SAFE":
            logger.info(
                "VOICE SPEED INVALID track=%s reason=%s", worst.get("track_id"), speed_reason,
            )
        include_speed = effective != "SAFE" and speed_valid

        if effective == "SAFE":
            return self._maybe_all_clear(now=now, worst=worst)

        if severity_index(effective) < severity_index(self._min_level):
            self._log_suppressed("below_min_level", effective, worst)
            return None

        track_id = worst.get("track_id")
        escalated = (
            self._last_level is not None
            and severity_index(effective) > severity_index(self._last_level)
        )
        track_changed = (
            track_id is not None
            and self._last_emit_track is not None
            and track_id != self._last_emit_track
        )

        trigger = "stability_satisfied"
        if escalated:
            # CRITICAL escalates immediately regardless of stability/cooldown.
            trigger = "critical_escalation" if effective == "CRITICAL" else "escalation_override"
        elif track_changed:
            # Item 19: a NEW dangerous track deserves its own warning. Still
            # debounced and throttled so repeated per-track flapping cannot
            # build an audio queue of dozens of messages.
            last_track_t = self._last_emit_by_track.get(track_id)
            if last_track_t is not None and now - last_track_t < self._track_flap_gap_s:
                self._log_suppressed("track_flap", effective, worst)
                return None
            if consecutive < self._stability_window:
                self._log_suppressed("stability_window", effective, worst)
                return None
            trigger = "track_change"
        else:
            if consecutive < self._stability_window:
                self._log_suppressed("stability_window", effective, worst)
                return None
            cooldown = self._cooldowns.get(effective, 5.0)
            last_t = self._last_emit_by_level.get(effective)
            if last_t is not None and now - last_t < cooldown:
                # Item 18: only a large, confident speed change on the SAME
                # risk level is worth re-announcing (still cooldown-gated so
                # it cannot spam).
                speed_changed = (
                    include_speed
                    and self._last_speed_kmh is not None
                    and speed_kmh is not None
                    and abs(int(speed_kmh) - int(self._last_speed_kmh))
                    >= self._speed_change_threshold
                )
                if not speed_changed:
                    self._log_suppressed("cooldown_duplicate", effective, worst)
                    return None
                trigger = "speed_change_alert"
            else:
                trigger = "risk_level_changed" if self._last_level != effective else "cooldown_elapsed"

        event = self._build_event(
            worst, effective, trigger, include_speed, speed_kmh, speed_valid,
        )
        self._emit(event, now=now, speed_kmh=speed_kmh if include_speed else None)
        return event

    # ------------------------------------------------------------- helpers

    def _maybe_all_clear(self, now: float, worst: Dict[str, Any]) -> Optional[VoiceEvent]:
        if severity_index(self._min_level) > severity_index("SAFE"):
            return None  # all-clear is below the configured announcement floor
        if self._last_level in (None, "SAFE"):
            return None
        last_safe = self._last_emit_by_level.get("SAFE")
        if last_safe is not None and now - last_safe < self._cooldowns.get("SAFE", 20.0):
            self._log_suppressed("cooldown_safe", "SAFE", worst)
            return None
        event = self._build_event(
            worst, "SAFE", "all_clear", include_speed=False, speed_kmh=None, speed_valid=False,
        )
        event.kind = "all_clear"
        self._emit(event, now=now, speed_kmh=None)
        return event

    def _build_event(
        self,
        worst: Dict[str, Any],
        level: str,
        trigger: str,
        include_speed: bool,
        speed_kmh: Optional[int],
        speed_valid: bool,
    ) -> VoiceEvent:
        language = self._current_language()
        msg = build_voice_message(
            risk_level=level,
            direction=worst.get("direction"),
            ttc=worst.get("ttc"),
            speed_kmh=speed_kmh if include_speed else None,
            speed_confidence=worst.get("speed_confidence") if include_speed else None,
            ttc_max_s=self._ttc_max_s,
            include_speed=include_speed,
            vehicle_class=worst.get("class_name"),
            track_id=worst.get("track_id"),
            language=language,
        )
        if msg.get("fallback_language"):
            logger.info(
                "VOICE FALLBACK lang=%s spoken=%s", language, msg.get("spoken_language"),
            )
        return VoiceEvent(
            kind="risk_alert",
            risk_level=level,
            direction=worst.get("direction") or "AHEAD",
            text=msg["text"],
            track_id=worst.get("track_id"),
            class_name=worst.get("class_name"),
            risk_score=float(worst.get("risk_score") or 0.0),
            ttc=worst.get("ttc"),
            speed_kmh=msg["speed_kmh"],
            speed_confidence=worst.get("speed_confidence") if include_speed else None,
            speed_status=str(worst.get("speed_status") or "").upper(),
            priority=msg["priority"],
            trigger=trigger,
            language=msg["spoken_language"],
            speed_valid=speed_valid,
            speed_timestamp_s=worst.get("speed_timestamp_s"),
        )

    def _emit(self, event: VoiceEvent, now: Optional[float] = None,
              speed_kmh: Optional[int] = None) -> None:
        now = now or self._clock()
        self._last_level = event.risk_level
        self._last_text = event.text
        self._last_emit = now
        self._last_emit_by_level[event.risk_level] = now
        if event.track_id is not None:
            self._last_emit_track = event.track_id
            self._last_emit_by_track[event.track_id] = now
        if speed_kmh is not None:
            self._last_speed_kmh = int(speed_kmh)
        self._alerts_emitted += 1
        self._recent.append(event)
        if len(self._recent) > self._max_queue:
            self._recent = self._recent[-self._max_queue:]
        self._deliver_speech(event)
        latency_ms = 0.0
        if self._eval_started is not None:
            latency_ms = (now - self._eval_started) * 1000.0
        logger.info(
            "VOICE EVENT CREATED level=%s direction=%s trigger=%s track=%s priority=%d "
            "lang=%s speed_valid=%s latency_ms=%.1f",
            event.risk_level, event.direction, event.trigger, event.track_id, event.priority,
            event.language, event.speed_valid, latency_ms,
        )

    def _deliver_speech(self, event: VoiceEvent) -> None:
        if self._provider is None or not self._provider.is_available():
            return
        try:
            interrupt = event.priority >= INTERRUPT_PRIORITY
            if interrupt:
                logger.info("VOICE INTERRUPTED priority=%d", event.priority)
            self.state_machine.transition(STATE_SPEAKING)
            t0 = self._clock()
            ok = self._provider.speak(
                event.text, interrupt=interrupt, language=event.language or self._current_language(),
            )
            tts_latency_ms = (self._clock() - t0) * 1000.0
            logger.info(
                "VOICE TTS STARTED provider=%s interrupt=%s lang=%s tts_latency_ms=%.1f ok=%s",
                self._provider.name, interrupt, event.language, tts_latency_ms, ok,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("VOICE TTS ERROR %s: %s", self._provider.name, exc)
        finally:
            self.state_machine.transition(STATE_MONITORING)

    def _track_provider_health(self) -> None:
        """Reflect provider availability in the state machine (OFFLINE vs
        MONITORING) with automatic recovery logging."""
        provider_available = self._provider is not None and self._provider.is_available()
        if self._provider_down and provider_available:
            self._provider_down = False
            if self.state_machine.can_transition(STATE_MONITORING):
                self.state_machine.transition(STATE_MONITORING)
            logger.info("VOICE RECOVERED provider=%s", self._provider.name)
        elif not provider_available and not self._provider_down:
            self._provider_down = True
            if self.state_machine.can_transition(STATE_OFFLINE):
                self.state_machine.transition(STATE_OFFLINE)
            logger.info(
                "VOICE FALLBACK provider=%s unavailable state=OFFLINE (events still delivered)",
                self._provider.name,
            )

    def _validate_speed(
        self, worst: Dict[str, Any], event_time: float,
    ) -> Tuple[bool, Optional[int], str]:
        """Full speed gate (items 8/28).

        Requires status ESTIMATED, finite positive value, confidence above the
        configured floor, value <= max reasonable, and a fresh source timestamp
        (age in real frames-vs-physics seconds <= VOICE_MAX_SPEED_DATA_AGE_S).
        """
        status = str(worst.get("speed_status") or "").upper()
        if status != "ESTIMATED":
            return False, None, f"status={status or 'UNKNOWN'}"
        kmh = worst.get("speed_kmh")
        conf = worst.get("speed_confidence")
        if not isinstance(kmh, (int, float)) or not isinstance(conf, (int, float)):
            return False, None, "non_numeric"
        kmh_f = float(kmh)
        conf_f = float(conf)
        if math.isnan(kmh_f) or math.isinf(kmh_f) or math.isnan(conf_f) or math.isinf(conf_f):
            return False, None, "non_finite"
        if conf_f < self._speed_min_confidence:
            return False, None, f"low_confidence_{conf_f:.2f}"
        if kmh_f <= 0:
            return False, None, "non_positive"
        if kmh_f > self._max_reasonable_speed_kmh:
            return False, None, f"unreasonable_{kmh_f:.1f}"
        ts = worst.get("speed_timestamp_s")
        if not isinstance(ts, (int, float)):
            return False, None, "no_timestamp"
        age = event_time - float(ts)
        if age < 0 or age > self._max_speed_data_age_s:
            return False, None, f"stale_age_{age:.2f}s"
        rs = round_speed(kmh_f)
        if rs is None or rs <= 0:
            return False, None, "rounding_failed"
        return True, rs, "ok"

    def _current_language(self) -> str:
        if self._language_source is not None:
            try:
                lang = self._language_source.get_language()
                if lang:
                    return lang
            except Exception:  # noqa: BLE001 - live source never blocks the pipeline
                pass
        return self._language or DEFAULT_LANGUAGE

    def _log_suppressed(self, reason: str, level: str, worst: Dict[str, Any]) -> None:
        logger.info(
            "VOICE EVENT SUPPRESSED reason=%s level=%s track=%s",
            reason, level, worst.get("track_id"),
        )

    @staticmethod
    def _clean_ttc(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            f = float(value)
        except (TypeError, ValueError):
            return None
        return f if f > 0 else None

    # -------------------------------------------------------------- actions

    def test_speech(self, text: Optional[str] = None) -> Optional[VoiceEvent]:
        """Produce a test voice event (used by the frontend "Test voice");
        speaks the per-language test sentence and depends on NO collision
        event (item 48)."""
        if not self._enabled or self._muted:
            return None
        language = self._current_language()
        payload = text or test_text(language)
        event = VoiceEvent(
            kind="test",
            risk_level="SAFE",
            direction="AHEAD",
            text=payload,
            priority=TEST_PRIORITY,
            trigger="test",
            language=language,
            speed_valid=False,
        )
        self._deliver_speech(event)
        logger.info("VOICE EVENT CREATED level=SAFE trigger=test kind=test lang=%s", language)
        return event