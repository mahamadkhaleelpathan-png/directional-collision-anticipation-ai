"""Unit tests for the additive AI voice safety assistant (Part 4).

Covers: per-level alert emission (SAFE/MEDIUM/HIGH/CRITICAL), direction
phrases, cooldowns, duplicate suppression, escalation override, critical
interruption, invalid TTC, missing/non-confident speed, unavailable and
throwing providers, mute/disable, below-min-level filtering, stability
window debounce, the WebSocket payload shape, the state machine, and the
rules-based conversational answers (assistant_context).
"""

import unittest

from src.voice.alert_templates import build_alert_text, build_voice_message
from src.voice.assistant_context import answer_question, build_assistant_context
from src.voice.language_state import VoiceLanguageState
from src.voice.languages import (
    DEFAULT_LANGUAGE,
    supported_languages,
    test_text as language_test_text,
)
from src.voice.state_machine import (
    STATE_IDLE,
    STATE_LISTENING,
    STATE_MONITORING,
    STATE_MUTED,
    STATE_OFFLINE,
    STATE_SPEAKING,
    STATE_THINKING,
    VoiceStateMachine,
)
from src.voice.voice_events import PRIORITY_MAP, VoiceEvent
from src.voice.voice_manager import VoiceAlertManager
from src.voice.voice_provider import VoiceProvider


class RecorderProvider(VoiceProvider):
    name = "recorder"

    def __init__(self, available: bool = True) -> None:
        self.calls = []
        self.available = available

    def speak(self, text, interrupt=False, language=None):
        self.calls.append({"text": text, "interrupt": interrupt, "language": language})
        return True

    def stop(self) -> None:
        pass

    def is_available(self) -> bool:
        return self.available


class ThrowingProvider(VoiceProvider):
    name = "throwing"

    def speak(self, text, interrupt=False, language=None):
        raise RuntimeError("boom")

    def stop(self) -> None:
        pass

    def is_available(self) -> bool:
        return True


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def make_record(
    level="MEDIUM",
    direction="AHEAD",
    ttc=None,
    class_name="car",
    track_id=1,
    score=50.0,
    speed_kmh=None,
    speed_conf=0.0,
    speed_status="NOT_CALIBRATED",
    speed_timestamp_s=None,
):
    return {
        "risk_level": level,
        "risk_score": score,
        "direction": direction,
        "track_id": track_id,
        "class_name": class_name,
        "estimated_ttc": ttc,
        "speed_kmh": speed_kmh,
        "speed_confidence": speed_conf,
        "speed_status": speed_status,
        "speed_timestamp_s": speed_timestamp_s,
    }


def make_manager(
    provider=None,
    min_alert_level="MEDIUM",
    enabled=True,
    cooldown_safe_s=20.0,
    stability_window_frames=3,
    cooldown_medium_s=10.0,
    cooldown_high_s=5.0,
    cooldown_critical_s=1.5,
    speed_min_confidence=0.6,
    max_reasonable_speed_kmh=180.0,
    max_speed_data_age_s=1.0,
    speed_change_alert_threshold_kmh=10.0,
    language_source=None,
    language="en-IN",
    clock=None,
):
    return VoiceAlertManager(
        enabled=enabled,
        provider=provider or RecorderProvider(),
        min_alert_level=min_alert_level,
        cooldown_safe_s=cooldown_safe_s,
        cooldown_medium_s=cooldown_medium_s,
        cooldown_high_s=cooldown_high_s,
        cooldown_critical_s=cooldown_critical_s,
        stability_window_frames=stability_window_frames,
        speed_min_confidence=speed_min_confidence,
        max_reasonable_speed_kmh=max_reasonable_speed_kmh,
        max_speed_data_age_s=max_speed_data_age_s,
        speed_change_alert_threshold_kmh=speed_change_alert_threshold_kmh,
        language_source=language_source,
        language=language,
        clock=clock or FakeClock(),
    )


def warm_and_emit(manager, record, frames=None):
    """Feed `frames` consecutive frames of `record` and return last event."""
    frames = frames or manager._stability_window
    event = None
    for i in range(frames):
        event = manager.evaluate(record, frame_idx=i)
    return event


class VoiceAlertManagerTests(unittest.TestCase):
    def test_medium_alert_emits_after_stability(self):
        mgr = make_manager()
        event = warm_and_emit(mgr, make_record(level="MEDIUM"))
        self.assertIsNotNone(event)
        self.assertEqual(event.risk_level, "MEDIUM")
        self.assertEqual(mgr.alerts_emitted, 1)

    def test_high_alert_emits(self):
        mgr = make_manager()
        event = warm_and_emit(mgr, make_record(level="HIGH"))
        self.assertIsNotNone(event)
        self.assertEqual(event.risk_level, "HIGH")

    def test_critical_alert_emits_with_max_priority_and_interrupts(self):
        provider = RecorderProvider()
        mgr = make_manager(provider=provider)
        event = warm_and_emit(mgr, make_record(level="CRITICAL"))
        self.assertIsNotNone(event)
        self.assertEqual(event.risk_level, "CRITICAL")
        self.assertEqual(event.priority, PRIORITY_MAP["CRITICAL"])
        self.assertEqual(event.priority, 100)
        self.assertTrue(provider.calls[-1]["interrupt"])

    def test_safe_all_clear_emits_after_risk_subsides(self):
        mgr = make_manager(min_alert_level="SAFE", cooldown_safe_s=0.0)
        warm_and_emit(mgr, make_record(level="MEDIUM"))
        event = mgr.evaluate(make_record(level="SAFE"), frame_idx=99)
        self.assertIsNotNone(event)
        self.assertEqual(event.kind, "all_clear")
        self.assertEqual(event.risk_level, "SAFE")
        self.assertIn("Road ahead is clear.", event.text)

    def test_all_clear_not_emitted_below_minimum(self):
        mgr = make_manager(min_alert_level="MEDIUM", cooldown_safe_s=0.0)
        warm_and_emit(mgr, make_record(level="MEDIUM"))
        event = mgr.evaluate(make_record(level="SAFE"), frame_idx=99)
        self.assertIsNone(event)

    def test_left_direction_phrase(self):
        mgr = make_manager()
        event = warm_and_emit(mgr, make_record(level="HIGH", direction="LEFT", ttc=2.0))
        self.assertIn("left", event.text)

    def test_right_direction_phrase(self):
        mgr = make_manager()
        event = warm_and_emit(mgr, make_record(level="HIGH", direction="RIGHT", ttc=2.0))
        self.assertIn("right", event.text)

    def test_ahead_direction_phrase(self):
        mgr = make_manager()
        event = warm_and_emit(mgr, make_record(level="HIGH", direction="AHEAD", ttc=2.0))
        self.assertIn("ahead", event.text)

    def test_duplicate_within_cooldown_is_suppressed(self):
        mgr = make_manager()
        warm_and_emit(mgr, make_record(level="MEDIUM", track_id=7))
        again = mgr.evaluate(make_record(level="MEDIUM", track_id=7), frame_idx=50)
        self.assertIsNone(again)
        self.assertEqual(mgr.alerts_emitted, 1)

    def test_same_alert_emits_again_after_cooldown(self):
        clock = FakeClock()
        mgr = make_manager(clock=clock)
        warm_and_emit(mgr, make_record(level="MEDIUM"))
        self.assertEqual(mgr.alerts_emitted, 1)
        clock.advance(11.0)
        again = mgr.evaluate(make_record(level="MEDIUM"), frame_idx=60)
        self.assertIsNotNone(again)
        self.assertEqual(mgr.alerts_emitted, 2)

    def test_escalation_overrides_cooldown(self):
        mgr = make_manager()
        warm_and_emit(mgr, make_record(level="MEDIUM"))
        high_event = mgr.evaluate(make_record(level="HIGH"), frame_idx=5)
        self.assertIsNotNone(high_event)
        self.assertEqual(high_event.trigger, "escalation_override")
        critical_event = mgr.evaluate(make_record(level="CRITICAL"), frame_idx=6)
        self.assertIsNotNone(critical_event)
        self.assertEqual(critical_event.trigger, "critical_escalation")

    def test_invalid_ttc_omits_seconds_phrase(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr, make_record(level="HIGH", ttc=None, speed_kmh=None, speed_status="UNAVAILABLE")
        )
        self.assertIsNotNone(event)
        self.assertNotIn("seconds", event.text)
        self.assertNotIn("kilometers per hour", event.text)

    def test_uncalibrated_speed_never_included(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(level="MEDIUM", speed_kmh=80.0, speed_conf=0.9, speed_status="NOT_CALIBRATED"),
        )
        self.assertNotIn("kilometers per hour", event.text)

    def test_low_confidence_speed_never_included(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(level="MEDIUM", speed_kmh=80.0, speed_conf=0.4, speed_status="ESTIMATED"),
        )
        self.assertNotIn("kilometers per hour", event.text)

    def test_confident_estimated_speed_included(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM",
                speed_kmh=45.0,
                speed_conf=0.8,
                speed_status="ESTIMATED",
                speed_timestamp_s=0.0,
            ),
        )
        self.assertIn("45 kilometers per hour", event.text)

    def test_unavailable_provider_still_delivers_event(self):
        mgr = make_manager(provider=RecorderProvider(available=False))
        event = warm_and_emit(mgr, make_record(level="MEDIUM"))
        self.assertIsNotNone(event)
        self.assertEqual(mgr.alerts_emitted, 1)

    def test_throwing_provider_never_crashes(self):
        mgr = make_manager(provider=ThrowingProvider())
        event = warm_and_emit(mgr, make_record(level="MEDIUM"))
        self.assertIsNotNone(event)
        self.assertEqual(mgr.alerts_emitted, 1)

    def test_muted_suppresses_everything(self):
        mgr = make_manager()
        mgr.set_muted(True)
        self.assertIsNone(warm_and_emit(mgr, make_record(level="CRITICAL")))

    def test_disabled_suppresses_everything(self):
        mgr = make_manager(enabled=False)
        self.assertIsNone(warm_and_emit(mgr, make_record(level="CRITICAL")))

    def test_below_minimum_level_is_suppressed(self):
        mgr = make_manager(min_alert_level="HIGH")
        self.assertIsNone(warm_and_emit(mgr, make_record(level="MEDIUM")))

    def test_stability_window_debounce(self):
        mgr = make_manager(stability_window_frames=5)
        for i in range(4):
            self.assertIsNone(mgr.evaluate(make_record(level="MEDIUM"), frame_idx=i))
        event = mgr.evaluate(make_record(level="MEDIUM"), frame_idx=4)
        self.assertIsNotNone(event)
        self.assertEqual(mgr.alerts_emitted, 1)

    def test_event_payload_shape_for_websocket(self):
        mgr = make_manager()
        event = warm_and_emit(mgr, make_record(level="HIGH", ttc=2.0))
        payload = {"type": "voice_alert", **event.to_dict()}
        self.assertEqual(payload["type"], "voice_alert")
        for key in (
            "event_id", "kind", "risk_level", "direction", "text", "track_id",
            "class_name", "risk_score", "ttc", "speed_kmh", "priority",
            "timestamp", "trigger",
        ):
            self.assertIn(key, payload)
        self.assertIsInstance(payload["risk_score"], float)

    def test_latest_text_exposed(self):
        mgr = make_manager()
        warm_and_emit(mgr, make_record(level="MEDIUM", direction="LEFT"))
        self.assertIn("left", mgr.last_text)


class VoiceEventTests(unittest.TestCase):
    def test_event_id_unique(self):
        self.assertNotEqual(VoiceEvent().event_id, VoiceEvent().event_id)

    def test_priority_map_complete(self):
        for level in ("SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
            self.assertIn(level, PRIORITY_MAP)


class AlertTemplateTests(unittest.TestCase):
    def test_ttc_above_cap_is_omitted(self):
        text = build_alert_text("HIGH", "AHEAD", ttc=99.0, ttc_max_s=10.0)
        self.assertNotIn("seconds", text)

    def test_zero_ttc_is_omitted(self):
        text = build_alert_text("HIGH", "AHEAD", ttc=0.0)
        self.assertNotIn("seconds", text)

    def test_unknown_direction_falls_back_to_nearby(self):
        text = build_alert_text("MEDIUM", "REAR")
        self.assertIn("nearby", text)


class StateMachineTests(unittest.TestCase):
    def test_invalid_transition_is_rejected(self):
        sm = VoiceStateMachine()
        self.assertFalse(sm.transition(STATE_SPEAKING))
        self.assertEqual(sm.state, STATE_IDLE)

    def test_full_monitoring_flow(self):
        sm = VoiceStateMachine()
        sm.transition(STATE_MONITORING)
        sm.transition(STATE_LISTENING)
        sm.transition(STATE_THINKING)
        sm.transition(STATE_SPEAKING)
        sm.transition(STATE_MONITORING)
        self.assertEqual(sm.state, STATE_MONITORING)

    def test_mute_and_offline_round_trip(self):
        sm = VoiceStateMachine(STATE_MONITORING)
        self.assertTrue(sm.transition(STATE_MUTED))
        self.assertTrue(sm.transition(STATE_MONITORING))
        self.assertTrue(sm.transition(STATE_OFFLINE))
        self.assertTrue(sm.transition(STATE_MONITORING))


class AssistantContextTests(unittest.TestCase):
    def test_risk_answer_uses_worst_threat(self):
        ctx = {"worst": {"risk_level": "HIGH", "direction": "LEFT", "ttc": 2.0}}
        answer = answer_question("what is the current risk?", ctx)
        self.assertIn("HIGH", answer)
        self.assertIn("left", answer)
        self.assertIn("2.0", answer)

    def test_safe_answer(self):
        answer = answer_question("is it safe?", {"worst": {"risk_level": "SAFE"}})
        self.assertIn("safe", answer)

    def test_speed_answer_without_estimate_is_honest(self):
        answer = answer_question("how fast is the car?", {})
        self.assertIn("I don't have a reliable speed estimate", answer)

    def test_speed_answer_with_confident_estimate(self):
        ctx = {
            "worst": {
                "class_name": "car",
                "speed_kmh": 45,
                "speed_confidence": 0.8,
                "speed_status": "ESTIMATED",
            }
        }
        answer = answer_question("what speed is the car?", ctx)
        self.assertIn("45 kilometers per hour", answer)

    def test_calibration_answer(self):
        self.assertIn("not configured", answer_question("is calibration active?", {"calibrated": False}))
        self.assertIn("active", answer_question("is calibration active?", {"calibrated": True}))

    def test_fallback_answer(self):
        answer = answer_question("tell me a joke", {})
        self.assertIn("I don't have an answer", answer)

    def test_build_context_keys(self):
        ctx = build_assistant_context(
            status="running",
            stats={"class_counts": {"car": 3}},
            worst={"risk_level": "MEDIUM"},
            calibrated=True,
        )
        self.assertEqual(ctx["status"], "running")
        self.assertEqual(ctx["class_counts"], {"car": 3})
        self.assertTrue(ctx["calibrated"])

    def test_counts_answer(self):
        ctx = {"class_counts": {"car": 4, "person": 2}}
        answer = answer_question("how many objects do you see?", ctx)
        self.assertIn("6 detections", answer)


class VoiceWebSocketTests(unittest.TestCase):
    """Integration: the WS loop drains queued events and sends voice_alert."""

    def test_ws_delivers_voice_alert(self):
        import api.main as m
        from fastapi.testclient import TestClient

        job = m._new_job()
        job.status = "running"
        payload = VoiceEvent(
            kind="risk_alert",
            risk_level="HIGH",
            direction="LEFT",
            text="Warning! Possible collision with Car approaching from your left. Reduce speed.",
            priority=PRIORITY_MAP["HIGH"],
            trigger="risk_level_changed",
        )
        job.voice_events.append(payload.to_dict())

        with TestClient(m.app) as client:
            with client.websocket_connect(f"/ws/jobs/{job.job_id}") as ws:
                types = []
                alert = None
                for _ in range(3):
                    msg = ws.receive_json()
                    t = msg.get("type")
                    types.append(t)
                    if t == "voice_alert":
                        alert = msg
                        break
                self.assertIn("progress", types)
                self.assertIsNotNone(alert)
                self.assertEqual(alert["type"], "voice_alert")
                self.assertEqual(alert["risk_level"], "HIGH")
                self.assertEqual(alert["direction"], "LEFT")
                self.assertEqual(alert["priority"], PRIORITY_MAP["HIGH"])
                # additive WS-payload fields (items 24/28)
                self.assertIn("message", alert)
                self.assertIn("vehicle_class", alert)
                self.assertIn("ttc_seconds", alert)
                self.assertIn("language", alert)
                self.assertIn("speed_valid", alert)


class MultilingualVoiceTests(unittest.TestCase):
    def test_default_language_is_telugu(self):
        msg = build_voice_message("HIGH", direction="AHEAD", ttc=2.0)
        self.assertEqual(msg["language"], DEFAULT_LANGUAGE)
        self.assertEqual(msg["language"], "te-IN")
        self.assertIn("తాకిడి", msg["text"])

    def test_hindi_message(self):
        msg = build_voice_message("HIGH", direction="LEFT", ttc=2.0, language="hi-IN")
        self.assertEqual(msg["language"], "hi-IN")
        self.assertEqual(msg["spoken_language"], "hi-IN")
        self.assertIn("जोखिम", msg["text"])

    def test_english_message_preserves_direction_substrings(self):
        msg = build_voice_message("HIGH", direction="RIGHT", ttc=2.0, language="en-IN")
        self.assertIn("right", msg["text"])
        self.assertIn("seconds", msg["text"])

    def test_unknown_language_falls_back_to_english(self):
        msg = build_voice_message("HIGH", direction="LEFT", language="pt-BR")
        self.assertEqual(msg["fallback_language"], "en-IN")
        self.assertEqual(msg["spoken_language"], "en-IN")
        self.assertIn("left", msg["text"])

    def test_language_switch_mid_video(self):
        mgr = make_manager(language_source=VoiceLanguageState("en-IN"))
        warm_and_emit(mgr, make_record(level="HIGH", direction="RIGHT"))
        mgr._language_source.set_language("hi-IN")
        event = mgr.evaluate(
            make_record(level="HIGH", direction="RIGHT", track_id=9), frame_idx=9
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.language, "hi-IN")
        self.assertIn("जोखिम", event.text)

    def test_supported_languages_include_indian_codes(self):
        codes = {lang["code"] for lang in supported_languages()}
        for code in (
            "en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "ml-IN",
            "mr-IN", "gu-IN", "bn-IN", "pa-IN", "or-IN", "ur-IN",
        ):
            self.assertIn(code, codes)

    def test_per_language_test_sentences(self):
        self.assertEqual(
            language_test_text("te-IN"),
            "వాయిస్ అసిస్టెంట్ పరీక్ష విజయవంతంగా పూర్తయింది.",
        )
        self.assertEqual(language_test_text("hi-IN"), "वॉइस असिस्टेंट परीक्षण सफल रहा।")
        self.assertEqual(language_test_text("en-IN"), "Voice assistant test successful.")


class VoiceMessageShapeTests(unittest.TestCase):
    def test_build_voice_message_shape(self):
        msg = build_voice_message(
            "CRITICAL",
            direction="LEFT",
            ttc=1.5,
            speed_kmh=46.2378,
            speed_confidence=0.9,
            include_speed=True,
            track_id=17,
            vehicle_class="car",
            language="en-IN",
        )
        for key in (
            "text", "language", "spoken_language", "fallback_language",
            "risk_level", "priority", "track_id", "speed_kmh", "speed_valid",
            "direction", "ttc_seconds", "vehicle_class", "speed_confidence",
        ):
            self.assertIn(key, msg)
        self.assertEqual(msg["risk_level"], "CRITICAL")
        self.assertEqual(msg["priority"], PRIORITY_MAP["CRITICAL"])
        self.assertTrue(msg["speed_valid"])
        self.assertEqual(msg["speed_kmh"], 46)
        self.assertEqual(msg["ttc_seconds"], 1.5)
        self.assertEqual(msg["vehicle_class"], "car")
        self.assertIn("46", msg["text"])


class SpeedGateTests(unittest.TestCase):
    def test_speed_rounds_to_nearest_kmh(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=46.2378, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
        )
        self.assertIn("approximately 46 kilometers per hour", event.text)

    def test_speed_rounds_up_to_next_kmh(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=46.8, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
        )
        self.assertIn("approximately 47 kilometers per hour", event.text)

    def test_event_speed_valid_flag(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=60.0, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
        )
        self.assertTrue(event.speed_valid)
        self.assertEqual(event.speed_kmh, 60)

    def test_nan_speed_never_spoken(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=float("nan"), speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
        )
        self.assertNotIn("kilometers per hour", event.text)

    def test_inf_speed_never_spoken(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=float("inf"), speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
        )
        self.assertNotIn("kilometers per hour", event.text)

    def test_negative_speed_never_spoken(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=-20.0, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
        )
        self.assertNotIn("kilometers per hour", event.text)

    def test_above_max_reasonable_speed_never_spoken(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=250.0, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
        )
        self.assertNotIn("kilometers per hour", event.text)

    def test_stale_speed_never_spoken(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=60.0, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=-5.0,
            ),
        )
        self.assertNotIn("kilometers per hour", event.text)

    def test_missing_speed_timestamp_never_spoken(self):
        mgr = make_manager()
        event = warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=60.0, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=None,
            ),
        )
        self.assertNotIn("kilometers per hour", event.text)

    def test_small_speed_change_within_cooldown_suppressed(self):
        mgr = make_manager(speed_change_alert_threshold_kmh=10.0)
        warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=40.0, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
        )
        event = mgr.evaluate(
            make_record(
                level="MEDIUM", speed_kmh=42.0, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
            frame_idx=5,
        )
        self.assertIsNone(event)

    def test_large_speed_change_triggers_alert(self):
        mgr = make_manager(speed_change_alert_threshold_kmh=10.0)
        warm_and_emit(
            mgr,
            make_record(
                level="MEDIUM", speed_kmh=40.0, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
        )
        event = mgr.evaluate(
            make_record(
                level="MEDIUM", speed_kmh=60.0, speed_conf=0.9,
                speed_status="ESTIMATED", speed_timestamp_s=0.0,
            ),
            frame_idx=5,
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.trigger, "speed_change_alert")


class TrackChangeTests(unittest.TestCase):
    def test_new_dangerous_track_emits_own_alert(self):
        mgr = make_manager()
        warm_and_emit(mgr, make_record(level="HIGH", track_id=17))
        event = mgr.evaluate(make_record(level="HIGH", track_id=18), frame_idx=5)
        self.assertIsNotNone(event)
        self.assertEqual(event.trigger, "track_change")
        self.assertEqual(event.track_id, 18)


class ThreatPriorityTests(unittest.TestCase):
    def test_worst_threat_priority(self):
        from src.pipeline.processor import _select_worst_threat

        tracks = [
            {"risk_level": "MEDIUM", "risk_score": 90.0, "estimated_ttc": 2.0, "track_id": 1},
            {"risk_level": "HIGH", "risk_score": 40.0, "estimated_ttc": 1.5, "track_id": 2},
        ]
        worst = _select_worst_threat(tracks)
        self.assertEqual(worst["risk_level"], "HIGH")
        self.assertEqual(worst["track_id"], 2)


if __name__ == "__main__":
    unittest.main()