"""
Video processing pipeline.

Contains the core `process_video` orchestration extracted from the
original Streamlit UI. This module has no UI dependencies — it only
runs the AI pipeline and emits per-frame progress and final results.

The original AI logic is preserved verbatim from the previous
`app.py` implementation; only Streamlit-specific side effects
(progress_bar, st.error, st.session_state writes, rerun, etc.) have
been replaced with a callback interface.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np
import pandas as pd

try:
    import imageio_ffmpeg
    _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    _FFMPEG_EXE = None

from config.settings import settings
from src.calibration.calibration import load_calibration
from src.calibration.ego_motion import analyze_camera_motion
from src.collision.collision_engine import CollisionEngine
from src.direction.directional_reasoning import DirectionalReasoner
from src.motion.motion_analysis import MotionAnalyzer
from src.motion.speed_estimator import TrackSpeedEstimator
from src.motion.trajectory import TrajectoryGenerator
from src.prediction.future_position import FuturePositionPredictor
from src.risk.risk_engine import RiskEngine
from src.tracking.object_tracker import ObjectTracker
from src.utils.logger import get_logger
from src.voice.voice_manager import VoiceAlertManager

logger = get_logger(__name__)

_VOICE_SEVERITY = {"SAFE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _select_worst_threat(active_tracks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pick the highest-risk active track for the voice assistant.

    Ranks by (severity, risk_score), tipping ties toward the shorter
    estimated time-to-collision. Returns None when nothing is tracked.
    """
    if not active_tracks:
        return None
    ranked = sorted(
        active_tracks,
        key=lambda t: (
            _VOICE_SEVERITY.get(str(t.get("risk_level", "SAFE")).upper(), 0),
            float(t.get("risk_score") or 0.0),
            -(float(t["estimated_ttc"]) if t.get("estimated_ttc") is not None else float("inf")),
        ),
        reverse=True,
    )
    return ranked[0]


def _recode_to_h264(path: str, ffmpeg_exe_fallback: bool = True) -> str:
    """Re-encode a video to browser-compatible H.264/yuv420p MP4.

    OpenCV's mp4v produces MPEG-4 Part 2 which Chrome/Edge reject.
    Uses the bundled ffmpeg from imageio-ffmpeg. Returns the same
    path replaced with the H.264 version, or raises RuntimeError
    if encoding fails so analysis is never reported complete with
    an unplayable video.
    """
    if not path.endswith(".mp4"):
        return path  # .avi fallback — not re-encoded here
    ffmpeg_exe = os.environ.get("FFMPEG_EXE") or _FFMPEG_EXE
    if not ffmpeg_exe or not os.path.exists(ffmpeg_exe):
        if ffmpeg_exe_fallback:
            logger.warning("No ffmpeg for H.264 re-encode; video may not play in browser")
            return path
        raise RuntimeError("ffmpeg required for browser-compatible video output")
    tmp_path = path + ".h264tmp.mp4"
    cmd = [
        ffmpeg_exe, "-y", "-i", path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "23", "-preset", "fast",
        "-movflags", "+faststart",
        tmp_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise RuntimeError("FFmpeg re-encoding timed out")
    if proc.returncode != 0:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise RuntimeError(f"FFmpeg re-encoding failed: {proc.stderr[:300]}")
    os.replace(tmp_path, path)
    logger.info("Re-encoded %s to H.264/yuv420p for browser playback", path)
    return path


ProgressCallback = Callable[[Dict[str, Any]], None]


@dataclass
class FrameSample:
    """Per-frame sample used for the on-screen frame series."""

    frame_index: int
    encoded_jpeg: Optional[bytes]


@dataclass
class PipelineResult:
    """Aggregated result returned by `process_video`."""

    output_video_path: str
    output_video_filename: str
    stats: Dict[str, Any]
    risk_summary: Dict[str, Any]
    primary_threat: Optional[Dict[str, Any]]
    analysis_rows: List[Dict[str, Any]] = field(default_factory=list)
    top_threats: List[Dict[str, Any]] = field(default_factory=list)
    verdict: Dict[str, Any] = field(default_factory=dict)
    # E16: optional JSON file with one record per processed frame (real
    # detections/tracks/risk for that frame). Empty string when disabled
    # or persistence failed. Never used by the AI logic itself.
    frames_path: str = ""


def compute_analysis_verdict(
    conflict_frames: int,
    high_conflict_frames: int,
    cumulative_max_risk: float,
) -> Dict[str, Any]:
    """Central whole-video verdict from cumulative evidence.

    Uses the existing risk-level thresholds from settings (HIGH>=60,
    MEDIUM>=40, LOW>=20) plus observed conflict severity. Meaning:
    - HIGH_COLLISION_RISK: a HIGH CONFLICT frame occurred, or max risk
      reached the HIGH band. A dangerous condition was estimated.
    - POTENTIAL_COLLISION_RISK: a POTENTIAL CONFLICT frame occurred, or
      max risk reached the MEDIUM band. A possible risk was estimated.
    - LOW_RISK: only LOW-band risk scores observed.
    - NO_SIGNIFICANT_RISK: nothing above the LOW band, no conflict frames.
    This is risk ESTIMATION from monocular video, not a record of a real
    crash. No claim is made that a collision occurred.
    """
    if high_conflict_frames > 0 or cumulative_max_risk >= settings.RISK_SCORE_MEDIUM_MAX:
        return {
            "level": "HIGH_COLLISION_RISK",
            "label": "High collision risk detected",
            "collision_risk_detected": True,
            "reason": (
                f"{high_conflict_frames} high-conflict frame(s), "
                f"max risk {cumulative_max_risk:.0f}/100"
            ),
        }
    if conflict_frames > 0 or cumulative_max_risk >= settings.RISK_SCORE_LOW_MAX:
        return {
            "level": "POTENTIAL_COLLISION_RISK",
            "label": "Potential collision risk detected",
            "collision_risk_detected": True,
            "reason": (
                f"{conflict_frames} conflict frame(s), "
                f"max risk {cumulative_max_risk:.0f}/100"
            ),
        }
    if cumulative_max_risk >= settings.RISK_SCORE_SAFE_MAX:
        return {
            "level": "LOW_RISK",
            "label": "Low risk detected",
            "collision_risk_detected": False,
            "reason": f"max risk {cumulative_max_risk:.0f}/100, no conflict frames",
        }
    return {
        "level": "NO_SIGNIFICANT_RISK",
        "label": "No significant collision risk detected",
        "collision_risk_detected": False,
        "reason": f"max risk {cumulative_max_risk:.0f}/100, no conflict frames",
    }


# Phase 5: structured pipeline stages. The per-frame loop runs the full
# AI chain (detect->track->motion->predict->collide->risk) on every frame,
# so per-module completion badges would be dishonest. Instead we emit the
# coarse stage the job has actually reached; the frontend renders only these.
STAGE_LOADING = "LOADING_VIDEO"
STAGE_ANALYZING = "ANALYZING_FRAMES"
STAGE_FINALIZING = "FINALIZING"
STAGE_COMPLETED = "COMPLETED"
STAGE_FAILED = "FAILED"


def _get_step_label(progress: float) -> str:
    if progress < 0.01:
        return "Initializing Pipeline..."
    elif progress < 0.10:
        return "Processing Frames..."
    elif progress < 0.50:
        return "Analyzing Traffic..."
    elif progress < 0.90:
        return "Computing Risk Scores..."
    else:
        return "Finalizing..."


def _get_stage(progress: float) -> str:
    if progress < 0.01:
        return STAGE_LOADING
    elif progress < 0.99:
        return STAGE_ANALYZING
    return STAGE_FINALIZING


def process_video(
    video_path: str,
    confidence: float = 0.5,
    on_progress: Optional[ProgressCallback] = None,
    on_voice_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    max_frames: Optional[int] = None,
    sample_every_n_frames: int = 30,
    frame_skip: int = 1,
    output_scale: float = 1.0,
    language_state: Optional[Any] = None,
) -> PipelineResult:
    """Run the full AI pipeline against a single video file.

    Parameters
    ----------
    video_path:
        Absolute path to the input video on disk.
    confidence:
        Detection confidence threshold forwarded to downstream
        modules.
    on_progress:
        Optional callback invoked with a dict containing keys
        ``frame``, ``total``, ``progress`` (0-1) and ``step`` on
        every processed frame so the UI layer can stream progress
        without depending on Streamlit.
    on_voice_event:
        Optional callback invoked with each emitted voice event
        dict (``VoiceEvent.to_dict()``) so the transport layer can
        forward it. Additive; never alters analysis.
    max_frames:
        Optional cap on the number of frames to process.
    sample_every_n_frames:
        Frequency at which an annotated JPEG frame is generated
        for the frontend preview timeline.
    frame_skip:
        Process every Nth frame for faster processing. Default 1 (all frames).
    output_scale:
        Output video resolution scale (0.25 to 1.0). Default 1.0 (original).
    language_state:
        Optional shared :class:`src.voice.language_state.VoiceLanguageState`
        so a language change from the HUD affects live speech without a
        pipeline restart. Additive; default is settings.VOICE_LANGUAGE.
    """

    logger.info("Starting pipeline: %s (conf=%.2f, skip=%d, scale=%.2f)",
                video_path, confidence, frame_skip, output_scale)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    output_dir = settings.OUTPUT_DIR / "processed_videos"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = str(output_dir / f"simulation_{timestamp_str}.mp4")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_w = int(width * output_scale)
    out_h = int(height * output_scale)
    writer = cv2.VideoWriter(output_path, fourcc, fps, (out_w, out_h))
    if not writer.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        output_path = str(output_dir / f"simulation_{timestamp_str}.avi")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (out_w, out_h))

    ego_center = (width // 2, height)

    # E2 FIX: forward the caller-selected confidence into the tracker so the
    # frontend slider actually changes YOLO detection behavior.
    tracker = ObjectTracker(conf_threshold=confidence)
    # E6 FIX: use the real video FPS (from OpenCV metadata) for all
    # motion/TTC/PET/prediction timing instead of hardcoded 30.
    motion_analyzer = MotionAnalyzer(fps=fps)
    trajectory_gen = TrajectoryGenerator()
    direction_reasoner = DirectionalReasoner()
    collision_engine = CollisionEngine(frame_width=width, frame_height=height)
    risk_engine = RiskEngine()
    future_predictor = FuturePositionPredictor(frame_width=width, frame_height=height)

    # --- Part 3: Speed estimation (additive, calibration-gated) ---
    # Never alters the pipeline above. Feed the ESTIMATOR the existing
    # ByteTrack boxes; it refuses to emit km/h while uncalibrated.
    speed_calibration = load_calibration()
    speed_estimator = TrackSpeedEstimator(
        fps=fps,
        calibration=speed_calibration,
        camera_moving=False,
    )
    cam_frames: List[Any] = []
    cam_frame_indices: List[int] = []
    cam_motion_analyzed = False
    camera_motion_warning = False
    ego_speed_kmh: Optional[float] = None

    # --- Part 4: Voice assistant (additive, failure-isolated) ---
    # The voice layer only consumes the pipeline's own risk results. If it
    # cannot start for any reason, video analysis proceeds normally.
    voice_manager: Optional[VoiceAlertManager] = None
    try:
        if settings.VOICE_ASSISTANT_ENABLED:
            voice_manager = VoiceAlertManager(fps=fps, language_source=language_state)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Voice assistant initialization failed (disabled): %s", exc)
        voice_manager = None

    frame_idx = 0
    output_frame_idx = 0
    start_time = time.time()
    all_class_counts: Dict[str, int] = {}
    unique_track_ids: set = set()
    frame_analyses: List[Dict[str, Any]] = []
    # E16: per-output-frame records (real per-frame AI results) persisted to
    # a JSON file so the frontend can replay the backend's own per-frame
    # output in sync with the annotated video. Contains only data the
    # pipeline already computed; no algorithm is changed.
    frame_records: List[Dict[str, Any]] = []
    # E7: cumulative collision/risk event tracking across the WHOLE video
    # (previously collision_count reflected only the final frame).
    conflict_frames = 0
    high_conflict_frames = 0
    max_conflict: str = "NONE"
    cumulative_max_risk = 0.0
    max_risk_frame = 0
    # E12: frame-level failure accounting (resilient: processing continues).
    error_count = 0
    error_samples: List[Dict[str, Any]] = []

    if on_progress:
        on_progress({
            "frame": 0,
            "total": total_frames,
            "progress": 0.0,
            "step": "Initializing AI pipeline...",
            "stage": STAGE_LOADING,
        })

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        if max_frames and frame_idx > max_frames:
            break
        if frame_skip > 1 and frame_idx % frame_skip != 0:
            if output_scale != 1.0:
                resized = cv2.resize(frame, (out_w, out_h))
                writer.write(resized)
            else:
                writer.write(frame)
            output_frame_idx += 1
            continue

        try:
            progress = frame_idx / max(total_frames, 1)
            if on_progress and (frame_idx % 3 == 0 or frame_idx == total_frames):
                on_progress({
                    "frame": frame_idx,
                    "total": total_frames,
                    "progress": min(progress, 1.0),
                    "step": _get_step_label(progress),
                    "stage": _get_stage(progress),
                })

            try:
                tracked_objects = tracker.update(frame)
            except Exception as track_exc:
                # E12: surface tracker failures with context instead of only a
                # generic warning; re-raise into the frame handler below so the
                # frame is counted as errored and processing continues.
                raise RuntimeError(f"detection/tracking failed: {type(track_exc).__name__}: {track_exc}") from track_exc

            # Camera-motion sampling (lightweight, once every few frames).
            if (
                not cam_motion_analyzed
                and len(cam_frames) < settings.CAMERA_MOTION_ANALYSIS_FRAMES
                and (frame_idx % max(int(settings.CAMERA_MOTION_SAMPLING_SKIP), 1)) == 0
            ):
                cam_frames.append(frame.copy())
                cam_frame_indices.append(frame_idx)

            active_tracks: List[Dict[str, Any]] = []
            directions_this_frame: Dict[int, str] = {}
            motion_states_this_frame: Dict[int, Any] = {}

            for track in tracked_objects:
                bbox_tuple = track.bbox
                motion_analyzer.update(
                    track_id=track.track_id,
                    class_name=track.class_name,
                    center=track.center,
                    ego_center=ego_center,
                    bbox=bbox_tuple,
                )
                trajectory_gen.update(
                    track_id=track.track_id,
                    position=track.center,
                    timestamp=frame_idx / fps,
                )
                unique_track_ids.add(track.track_id)

                # Part 3: per-track speed estimate from THIS track's ByteTrack
                # box. All fields are optional/additive.
                speed_est = speed_estimator.update(
                    track_id=track.track_id,
                    frame_idx=frame_idx,
                    bbox=tuple(bbox_tuple),
                    detection_conf=float(getattr(track, "confidence", 0.5)),
                )

                direction = direction_reasoner.determine_direction(
                    ego_center=ego_center,
                    threat_center=track.center,
                )
                directions_this_frame[track.track_id] = direction.value

                motion_state = motion_analyzer.get_motion_state(track.track_id)
                motion_label = "STATIONARY"
                if motion_state:
                    motion_label = motion_state.motion_state
                    motion_states_this_frame[track.track_id] = motion_state

                active_tracks.append({
                    "track_id": track.track_id,
                    "class_name": track.class_name,
                    "confidence": track.confidence,
                    "bbox": track.bbox,
                    "center": track.center,
                    "direction": direction.value,
                    "motion": motion_label,
                    "speed_mps": speed_est.speed_mps,
                    "speed_kmh": speed_est.speed_kmh,
                    "approach_kmh": speed_est.approach_kmh,
                    "speed_confidence": speed_est.speed_confidence,
                    "speed_status": speed_est.speed_status,
                    "speed_timestamp_s": getattr(speed_est, "timestamp_s", None),
                })

            for tobj in active_tracks:
                cname = tobj["class_name"]
                all_class_counts[cname] = all_class_counts.get(cname, 0) + 1

            trajectory_status: Dict[int, str] = {}
            for track_id, traj in trajectory_gen.get_all_trajectories().items():
                if traj.length() >= 3:
                    predictions = future_predictor.predict(traj)
                    if predictions:
                        trajectory_status[track_id] = predictions[0].trajectory_status
                    else:
                        trajectory_status[track_id] = "STABLE PATH"
                else:
                    trajectory_status[track_id] = "STABLE PATH"

            collision_assessments = collision_engine.assess_all(
                motion_states_this_frame, trajectory_status
            )

            risk_results = risk_engine.analyze(
                motion_states_this_frame,
                collision_assessments,
                directions_this_frame,
                trajectory_status,
            )

            for tobj in active_tracks:
                tid = tobj["track_id"]
                if tid in risk_results:
                    rr = risk_results[tid]
                    tobj["risk_score"] = rr.risk_score
                    tobj["risk_level"] = rr.risk_level
                    tobj["conflict_status"] = rr.conflict_status
                    tobj["estimated_ttc"] = rr.estimated_ttc
                    tobj["trajectory_status"] = rr.trajectory_status
                    tobj["estimated_drac_risk"] = rr.estimated_drac_risk
                    tobj["estimated_act"] = rr.estimated_act
                    tobj["estimated_pet"] = rr.estimated_pet
                elif tid in collision_assessments:
                    ca = collision_assessments[tid]
                    tobj["risk_score"] = 0.0
                    tobj["risk_level"] = "SAFE"
                    tobj["conflict_status"] = ca.conflict_status
                    tobj["estimated_ttc"] = ca.estimated_ttc
                    tobj["trajectory_status"] = trajectory_status.get(tid, "STABLE PATH")
                    tobj["estimated_drac_risk"] = ca.estimated_drac_risk
                    tobj["estimated_act"] = ca.estimated_act
                    tobj["estimated_pet"] = ca.estimated_pet
                else:
                    tobj["risk_score"] = 0.0
                    tobj["risk_level"] = "SAFE"
                    tobj["conflict_status"] = "NO SIGNIFICANT CONFLICT"
                    tobj["estimated_ttc"] = None
                    tobj["trajectory_status"] = trajectory_status.get(tid, "STABLE PATH")
                    tobj["estimated_drac_risk"] = "LOW"
                    tobj["estimated_act"] = "N/A"
                    tobj["estimated_pet"] = None

            # --- Part 4: voice safety assistant (additive) ---
            # The pipeline's own results are the single source of truth; the
            # voice layer only formats the worst threat. Failures here must
            # never affect analysis.
            if voice_manager is not None and on_voice_event is not None:
                try:
                    voice_event = voice_manager.evaluate(
                        _select_worst_threat(active_tracks), frame_idx=frame_idx
                    )
                    if voice_event is not None:
                        on_voice_event(voice_event.to_dict())
                except Exception as voice_exc:  # noqa: BLE001
                    logger.warning("Voice assistant error (non-fatal): %s", voice_exc)

            # E7: accumulate whole-video collision/risk events every frame.
            frame_conflicts = [
                r for r in risk_results.values()
                if r.conflict_status in ("HIGH CONFLICT", "POTENTIAL CONFLICT")
            ]
            if frame_conflicts:
                conflict_frames += 1
                if any(r.conflict_status == "HIGH CONFLICT" for r in frame_conflicts):
                    high_conflict_frames += 1
                    max_conflict = "HIGH CONFLICT"
                elif max_conflict == "NONE":
                    max_conflict = "POTENTIAL CONFLICT"
            if risk_results:
                frame_max = max(r.risk_score for r in risk_results.values())
                if frame_max > cumulative_max_risk:
                    cumulative_max_risk = frame_max
                    max_risk_frame = frame_idx

            if on_progress and (frame_idx % 3 == 0 or frame_idx == total_frames):
                live_stats = {
                    "frames_processed": frame_idx,
                    "total_unique_tracks": len(unique_track_ids),
                    "total_detections": sum(all_class_counts.values()),
                    "class_counts": dict(all_class_counts),
                    "processing_fps": frame_idx / max(time.time() - start_time, 0.001),
                    "total_frames": total_frames,
                    "video_fps": fps,
                    "width": width,
                    "height": height,
                    "collision_count": conflict_frames,
                    "high_conflict_frames": high_conflict_frames,
                    "max_conflict": max_conflict,
                    "cumulative_max_risk": round(cumulative_max_risk, 1),
                    "max_risk_frame": max_risk_frame,
                }
                voice_info = None
                if voice_manager is not None:
                    vw = voice_manager.current_worst
                    voice_info = {
                        "level": voice_manager.current_level,
                        "alerts": voice_manager.alerts_emitted,
                        "state": voice_manager.state_machine.state,
                        "worst": {k: vw.get(k) for k in (
                            "track_id", "class_name", "direction", "risk_level",
                            "risk_score", "ttc", "speed_kmh", "speed_confidence",
                            "speed_status",
                        )},
                    }
                live_stats["voice"] = voice_info
                on_progress({
                    "frame": frame_idx,
                    "total": total_frames,
                    "progress": min(frame_idx / max(total_frames, 1), 1.0),
                    "step": _get_step_label(frame_idx / max(total_frames, 1)),
                    "stage": _get_stage(frame_idx / max(total_frames, 1)),
                    "stats": live_stats,
                })

            for tobj in active_tracks:
                frame_analyses.append({
                    "frame": frame_idx,
                    "track_id": tobj["track_id"],
                    "class_name": tobj["class_name"],
                    "direction": tobj["direction"],
                    "motion": tobj["motion"],
                    "trajectory": tobj.get("trajectory_status", "STABLE PATH"),
                    "conflict": tobj.get("conflict_status", "NO SIGNIFICANT CONFLICT"),
                    "estimated_ttc": tobj.get("estimated_ttc"),
                    "estimated_pet": tobj.get("estimated_pet"),
                    "estimated_drac_risk": tobj.get("estimated_drac_risk", "LOW"),
                    "estimated_act": tobj.get("estimated_act", "N/A"),
                    "risk_score": tobj.get("risk_score", 0.0),
                    "risk_level": tobj.get("risk_level", "SAFE"),
                    "estimated_speed_kmh": tobj.get("speed_kmh"),
                    "estimated_speed_confidence": tobj.get("speed_confidence"),
                    "speed_status": tobj.get("speed_status"),
                })

            # --- Annotated frame drawing (same logic as original) ---
            annotated = frame.copy()

            ego_left = int(width * settings.EGO_PATH_LEFT_RATIO)
            ego_right = int(width * settings.EGO_PATH_RIGHT_RATIO)

            overlay_fill = annotated.copy()
            cv2.rectangle(overlay_fill, (ego_left, 0), (ego_right, height), (50, 50, 80), -1)
            cv2.addWeighted(overlay_fill, 0.08, annotated, 0.92, 0, annotated)

            overlay_lines = annotated.copy()
            cv2.line(overlay_lines, (ego_left, 0), (ego_left, height), (100, 100, 100), 1, cv2.LINE_AA)
            cv2.line(overlay_lines, (ego_right, 0), (ego_right, height), (100, 100, 100), 1, cv2.LINE_AA)
            cv2.putText(overlay_lines, "LEFT", (ego_left - 60, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 120, 120), 1)
            cv2.putText(overlay_lines, "AHEAD", (width // 2 - 30, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 120, 120), 1)
            cv2.putText(overlay_lines, "RIGHT", (ego_right + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 120, 120), 1)
            cv2.addWeighted(overlay_lines, 0.7, annotated, 0.3, 0, annotated)

            primary_threat = risk_engine.get_primary_threat()

            for tobj in active_tracks:
                x1, y1, x2, y2 = tobj["bbox"]
                cls = tobj["class_name"]
                tid = tobj["track_id"]
                direction = tobj["direction"]
                motion = tobj["motion"]
                risk_level = tobj.get("risk_level", "SAFE")
                risk_score = tobj.get("risk_score", 0.0)
                ttc = tobj.get("estimated_ttc")
                conflict = tobj.get("conflict_status", "NO SIGNIFICANT CONFLICT")
                traj_status = tobj.get("trajectory_status", "STABLE PATH")

                is_primary = (primary_threat is not None and
                              primary_threat.tracking_id == tid)

                if is_primary:
                    color = (0, 0, 255)
                    box_thickness = 3
                elif risk_level in ("CRITICAL", "HIGH"):
                    color = (0, 100, 255)
                    box_thickness = 2
                elif risk_level == "MEDIUM":
                    color = (0, 200, 255)
                    box_thickness = 2
                else:
                    class_colors = {
                        "car": (0, 255, 0),
                        "motorcycle": (0, 165, 255),
                        "bus": (255, 200, 0),
                        "truck": (200, 100, 0),
                        "person": (255, 0, 255),
                        "bicycle": (255, 255, 0),
                    }
                    color = class_colors.get(cls.lower(), (0, 255, 0))
                    box_thickness = 2

                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, box_thickness)

                label = f"{cls.upper()} #{tid}"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated, (x1, y1 - th - 14), (x1 + tw + 4, y1), color, -1)
                cv2.putText(annotated, label, (x1 + 2, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                # Explainability: every line below comes from this frame's real
                # backend output for this track. Conflict warnings appear ONLY
                # when collision_engine reported HIGH/POTENTIAL conflict for
                # this object in THIS frame; risk lines only for elevated
                # risk levels. Normal objects keep a clean ID + direction line.
                if conflict == "HIGH CONFLICT":
                    info_lines = ["!! HIGH CONFLICT !!"]
                elif conflict == "POTENTIAL CONFLICT":
                    info_lines = ["! POTENTIAL CONFLICT"]
                else:
                    info_lines = []
                if is_primary:
                    info_lines.append("** PRIMARY THREAT **")
                    info_lines.append(f"Dir: {direction}  Motion: {motion}")
                    info_lines.append(f"Risk: {risk_level} ({risk_score:.0f}/100)")
                    if ttc is not None:
                        info_lines.append(f"Est. TTC: {ttc:.1f}s")
                elif risk_level in ("CRITICAL", "HIGH", "MEDIUM"):
                    info_lines.append(f"Dir: {direction}  Motion: {motion}")
                    info_lines.append(f"Risk: {risk_level} ({risk_score:.0f}/100)")
                    if ttc is not None:
                        info_lines.append(f"Est. TTC: {ttc:.1f}s")
                else:
                    info_lines.append(f"Dir: {direction}  Motion: {motion}")

                y_offset = y1 - th - 16
                for line in info_lines:
                    (lw, lh), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
                    cv2.rectangle(annotated, (x1, y_offset - lh - 4), (x1 + lw + 4, y_offset), (0, 0, 0), -1)
                    cv2.putText(annotated, line, (x1 + 2, y_offset - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 220), 1)
                    y_offset -= lh + 5

                cx, cy = int(tobj["center"][0]), int(tobj["center"][1])
                cv2.circle(annotated, (cx, cy), 3, color, -1)

                # Predicted motion: markers come from FuturePositionPredictor for
                # THIS track's real horizons (0.5s/1.0s/2.0s constant-velocity
                # extrapolation). Labeled so the viewer can tell prediction
                # apart from detection. Nothing is drawn when no prediction
                # exists for this track in this frame.
                if tid in future_predictor.get_all_predictions():
                    preds = future_predictor.get_predictions(tid)
                    for pred in preds:
                        if pred.predicted_position is not None:
                            px, py = int(pred.predicted_position[0]), int(pred.predicted_position[1])
                            if 0 <= px < width and 0 <= py < height:
                                cv2.circle(annotated, (px, py), 3, (0, 255, 255), -1)
                                cv2.line(annotated, (cx, cy), (px, py), (0, 255, 255), 1, cv2.LINE_AA)
                                cv2.putText(annotated, f"{pred.horizon:.1f}s", (px + 5, py - 5),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

            # Past-motion trails: only for objects active in THIS frame, so
            # departed objects stop leaving ghost trails behind.
            active_ids = {t.track_id for t in tracked_objects}
            colors_list = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)]
            for track_id, traj in trajectory_gen.get_all_trajectories().items():
                if track_id not in active_ids:
                    continue
                points = traj.get_points()
                if len(points) < 2:
                    continue
                pts = points.astype(np.int32)
                traj_color = colors_list[track_id % len(colors_list)]
                for i in range(1, len(pts)):
                    thickness = max(1, min(2, i // 5))
                    cv2.line(annotated, tuple(pts[i - 1]), tuple(pts[i]), traj_color, thickness)

            if primary_threat is not None and primary_threat.risk_level in ("CRITICAL", "HIGH"):
                banner_h = 40
                banner_color = (0, 0, 200) if primary_threat.risk_level == "CRITICAL" else (0, 120, 200)
                cv2.rectangle(annotated, (0, height - banner_h), (width, height), banner_color, -1)
                banner_ttc = (f" | Est. TTC: {primary_threat.estimated_ttc:.1f}s"
                              if primary_threat.estimated_ttc is not None else "")
                threat_text = (f"PRIMARY THREAT: {primary_threat.object_type} #{primary_threat.tracking_id} "
                               f"| Risk: {primary_threat.risk_level} ({primary_threat.risk_score:.0f}/100){banner_ttc}")
                cv2.putText(annotated, threat_text, (20, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            info_lines = [
                "AI COLLISION ANTICIPATION SYSTEM",
                f"Active Tracks: {len(active_tracks)}",
                f"Frame: {frame_idx}/{total_frames}",
            ]
            x_info = width - 300
            for i, line in enumerate(info_lines):
                (tw_i, th_i), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(annotated, (x_info - 5, 25 + i * 22 - th_i - 2), (x_info + tw_i + 5, 25 + i * 22 + 4), (0, 0, 0), -1)
                cv2.putText(annotated, line, (x_info, 25 + i * 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)

            if output_scale != 1.0:
                annotated = cv2.resize(annotated, (out_w, out_h))
            writer.write(annotated)
            output_frame_idx += 1

            # E16: persist a compact record of THIS output frame using the
            # exact per-track values the pipeline computed for this frame.
            tracks_meta: List[Dict[str, Any]] = []
            for tobj in active_tracks:
                tid = tobj["track_id"]
                bbox = tobj.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue
                pred_point: Optional[List[int]] = None
                if tid in future_predictor.get_all_predictions():
                    for _p in future_predictor.get_predictions(tid):
                        if _p.predicted_position is not None:
                            pred_point = [
                                int(_p.predicted_position[0]),
                                int(_p.predicted_position[1]),
                            ]
                            break
                tracks_meta.append({
                    "id": tid,
                    "class": tobj.get("class_name", "unknown"),
                    "conf": round(float(tobj.get("confidence", 0.0)), 3),
                    "bbox": [int(v) for v in bbox],
                    "center": [int(v) for v in tobj["center"]],
                    "direction": tobj.get("direction", "AHEAD"),
                    "motion": tobj.get("motion", "STATIONARY"),
                    "trajectory": tobj.get("trajectory_status", "STABLE PATH"),
                    "conflict": tobj.get("conflict_status", "NO SIGNIFICANT CONFLICT"),
                    "ttc": tobj.get("estimated_ttc"),
                    "pet": tobj.get("estimated_pet"),
                    "drac": tobj.get("estimated_drac_risk", "LOW"),
                    "act": tobj.get("estimated_act", "N/A"),
                    "risk_score": round(float(tobj.get("risk_score", 0.0)), 1),
                    "risk_level": tobj.get("risk_level", "SAFE"),
                    "pred": pred_point,
                    "speed_mps": tobj.get("speed_mps"),
                    "speed_kmh": tobj.get("speed_kmh"),
                    "approach_kmh": tobj.get("approach_kmh"),
                    "speed_confidence": tobj.get("speed_confidence"),
                    "speed_status": tobj.get("speed_status"),
                })
            frame_records.append({
                "frame": frame_idx,
                "out": output_frame_idx,
                "timestamp": round(output_frame_idx / fps, 3) if fps else 0,
                "time": round(frame_idx / fps, 3) if fps else 0,
                "tracks": tracks_meta,
            })

            active_track_ids = {t.track_id for t in tracked_objects}
            motion_analyzer.cleanup_stale_states(active_track_ids)

            # Part 3: once enough early frames are sampled, decide whether the
            # camera is moving (reported as a warning, never affects risk).
            if not cam_motion_analyzed and len(cam_frames) >= settings.CAMERA_MOTION_ANALYSIS_FRAMES:
                cam_motion_analyzed = True
                try:
                    cam_moving, ego_est = analyze_camera_motion(
                        frames=cam_frames,
                        frame_indices=cam_frame_indices,
                        fps=fps,
                        plane=speed_calibration.ground_plane
                        if speed_calibration.configured
                        else None,
                    )
                    camera_motion_warning = bool(cam_moving)
                    ego_speed_kmh = ego_est
                    speed_estimator.camera_moving = cam_moving
                    if settings.SPEED_ESTIMATION_ENABLED:
                        logger.info(
                            "Camera-motion analysis: moving=%s ego_kmh_estimate=%s "
                            "calibration=%s",
                            cam_moving, ego_est, speed_calibration.to_status_dict().get("label"),
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Camera-motion analysis failed: %s", exc)

            speed_estimator.cleanup(active_track_ids, frame_idx)

        except Exception as e:
            # E12: keep resilience (write the raw frame so output stays in
            # sync) but record WHAT failed and WHERE instead of a bare
            # warning. Counts/samples are surfaced in the final stats.
            error_count += 1
            err_detail = f"{type(e).__name__}: {e}"
            if len(error_samples) < 5:
                error_samples.append({"frame": frame_idx, "error": err_detail[:200]})
            logger.warning("Error processing frame %d (frame_pipeline): %s", frame_idx, err_detail)
            if output_scale != 1.0:
                resized = cv2.resize(frame, (out_w, out_h))
                writer.write(resized)
            else:
                writer.write(frame)
            output_frame_idx += 1

    processing_time = time.time() - start_time
    cap.release()
    writer.release()

    # BROWSER COMPATIBILITY FIX: OpenCV writes mp4v (MPEG-4 Part 2)
    # which Chrome/Edge cannot decode. Re-encode to H.264/yuv420p
    # using the bundled ffmpeg from imageio-ffmpeg so the processed
    # video actually plays in the browser.
    output_path = _recode_to_h264(output_path, ffmpeg_exe_fallback=True)

    # E16: persist per-frame AI records next to the job's artifacts. The
    # file is written once per job, cleaned up when the job prunes, and is
    # purely additive — the pipeline's own results are unaffected.
    frames_path = ""
    try:
        frames_dir = settings.OUTPUT_DIR / "processed_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        frames_path = str(frames_dir / f"{Path(output_path).stem}_frames.json")
        with open(frames_path, "w", encoding="utf-8") as fh:
            json.dump({
                "fps": fps,
                "total_frames": total_frames,
                "processed_frames": frame_idx,
                "speed_calibration": speed_calibration.to_status_dict(),
                "frames": frame_records,
            }, fh)
    except Exception as exc:  # noqa: BLE001
        frames_path = ""
        logger.warning("Per-frame metadata persistence failed: %s", exc)

    if frame_analyses:
        df_all = pd.DataFrame(frame_analyses)
        df_summary = df_all.groupby("track_id").agg({
            "class_name": "first",
            "direction": lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],
            "motion": lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],
            "trajectory": lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],
            "conflict": lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],
            "estimated_ttc": "min",
            "estimated_pet": "min",
            "estimated_drac_risk": lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],
            "estimated_act": lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],
            "risk_score": "max",
            "risk_level": lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],
            "estimated_speed_kmh": "median",
            "estimated_speed_confidence": "mean",
            "speed_status": lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],
        }).reset_index()
        df_summary.rename(columns={"risk_score": "max_risk_score"}, inplace=True)
        df_summary["max_risk_score"] = df_summary["max_risk_score"].round(1)
        if "estimated_speed_kmh" in df_summary.columns:
            df_summary["estimated_speed_kmh"] = df_summary["estimated_speed_kmh"].round(1)
        if "estimated_speed_confidence" in df_summary.columns:
            df_summary["estimated_speed_confidence"] = df_summary["estimated_speed_confidence"].round(2)
        df_summary = df_summary.sort_values("max_risk_score", ascending=False)
    else:
        df_summary = pd.DataFrame()

    risk_summary = risk_engine.get_summary()
    primary = risk_engine.get_primary_threat()

    # E5 FIX: rank is the 1-based position in risk-sorted order (Rank 1 =
    # highest risk). Track ID stays a separate value.
    top_threats: List[Dict[str, Any]] = []
    if not df_summary.empty:
        for rank, (_, row) in enumerate(df_summary.head(3).iterrows(), start=1):
            top_threats.append({
                "rank": rank,
                "class_name": str(row["class_name"]),
                "tracking_id": int(row["track_id"]),
                "direction": str(row["direction"]),
                "risk_level": str(row["risk_level"]),
                "risk_score": float(row["max_risk_score"]),
            })

    # E7: final stats describe the entire simulation, not the last frame.
    stats = {
        "frames_processed": frame_idx,
        "processing_time": f"{processing_time:.1f}s",
        "processing_time_raw": processing_time,
        "total_unique_tracks": len(unique_track_ids),
        "total_detections": sum(all_class_counts.values()),
        "class_counts": all_class_counts,
        "processing_fps": frame_idx / max(processing_time, 0.001),
        "total_frames": total_frames,
        "video_fps": fps,
        "width": width,
        "height": height,
        "collision_count": conflict_frames,
        "high_conflict_frames": high_conflict_frames,
        "max_conflict": max_conflict,
        "cumulative_max_risk": round(cumulative_max_risk, 1),
        "max_risk_frame": max_risk_frame,
        "processing_errors": error_count,
        "error_samples": error_samples,
        "speed_estimation_enabled": settings.SPEED_ESTIMATION_ENABLED,
        "speed_calibration": speed_calibration.to_status_dict(),
        "speed_calibrated": bool(speed_calibration.configured),
        "camera_motion_warning": camera_motion_warning,
        "ego_speed_kmh": ego_speed_kmh,
    }

    # Part 4: final voice summary for the job result (additive).
    if voice_manager is not None:
        stats["voice"] = {
            "alerts": voice_manager.alerts_emitted,
            "last_level": voice_manager.current_level,
            "state": voice_manager.state_machine.state,
            "last_text": voice_manager.last_text,
        }

    verdict = compute_analysis_verdict(conflict_frames, high_conflict_frames, cumulative_max_risk)

    if on_progress:
        on_progress({
            "frame": frame_idx,
            "total": total_frames,
            "progress": 1.0,
            "step": f"Done. Processed {frame_idx} frames in {processing_time:.1f}s",
            "stage": STAGE_COMPLETED,
        })

    return PipelineResult(
        output_video_path=output_path,
        output_video_filename=Path(output_path).name,
        stats=stats,
        risk_summary=risk_summary,
        primary_threat=primary.to_dict() if primary else None,
        analysis_rows=df_summary.to_dict(orient="records") if not df_summary.empty else [],
        top_threats=top_threats,
        verdict=verdict,
        frames_path=frames_path,
    )