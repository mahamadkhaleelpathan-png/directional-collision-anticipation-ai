"""
Centralized application settings for the collision anticipation system.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    """Application-wide settings for the collision anticipation system."""

    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    DATA_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data")
    UPLOAD_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "uploads")
    MODEL_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "models")
    OUTPUT_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "output")

    VIDEO_FPS: int = 30
    FRAME_WIDTH: int = 1280
    FRAME_HEIGHT: int = 720

    YOLO_MODEL_PATH: str = "yolo11n.pt"
    DETECTION_CONFIDENCE: float = 0.45
    DETECTION_CLASSES: List[str] = field(default_factory=lambda: [
        "car", "motorcycle", "bus", "truck", "person", "bicycle"
    ])

    TRACK_BUFFER: int = 30
    MATCH_THRESH: float = 0.8

    PREDICTION_HORIZONS: List[float] = field(default_factory=lambda: [0.5, 1.0, 2.0])
    CONFIDENCE_DECAY: float = 0.15

    DIRECTION_LEFT_RATIO: float = 0.35
    DIRECTION_RIGHT_RATIO: float = 0.65

    RISK_SAFE: int = 20
    RISK_LOW: int = 40
    RISK_MEDIUM: int = 60
    RISK_HIGH: int = 80

    EGO_SPEED_KMH: float = 40.0
    EGO_LENGTH: float = 4.5
    EGO_WIDTH: float = 1.8

    DASHBOARD_PORT: int = 8501

    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    LOG_FILE: str = "output/logs/system.log"

    # --- Part 2: Motion Analysis ---
    MOTION_HISTORY_LENGTH: int = 15
    STATIONARY_SPEED_THRESHOLD: float = 2.0
    STATIONARY_DISPLACEMENT_THRESHOLD: float = 5.0
    APPROACHING_AREA_GROWTH_RATE: float = 0.02
    LATERAL_DOMINANCE_RATIO: float = 1.5
    MOTION_SMOOTHING_WINDOW: int = 5

    # --- Part 2: Ego Path / Reference Zone ---
    EGO_PATH_LEFT_RATIO: float = 0.30
    EGO_PATH_RIGHT_RATIO: float = 0.70
    EGO_PATH_TOP_RATIO: float = 0.0
    EGO_PATH_BOTTOM_RATIO: float = 1.0
    EGO_ZONE_APPROACHING_PRIORITY: float = 1.5

    # --- Part 2: Trajectory Prediction ---
    TRAJECTORY_HISTORY_LENGTH: int = 20
    TRAJECTORY_FUTURE_HORIZONS: List[float] = field(default_factory=lambda: [0.5, 1.0, 2.0])
    TRAJECTORY_CONVERGENCE_ANGLE_DEG: float = 15.0
    TRAJECTORY_CROSSING_LATERAL_OFFSET: float = 50.0

    # --- Part 2: Conflict Detection ---
    CONFLICT_PROXIMITY_PIXELS: float = 100.0
    CONFLICT_TIME_GAP_THRESHOLD: float = 2.0
    CONFLICT_APPROACHING_BONUS: float = 20.0
    CONFLICT_HIGH_RISK_TTC: float = 2.0
    CONFLICT_MEDIUM_RISK_TTC: float = 4.0

    # --- Part 2: TTC Thresholds ---
    TTC_CRITICAL_THRESHOLD: float = 1.5
    TTC_HIGH_THRESHOLD: float = 3.0
    TTC_MEDIUM_THRESHOLD: float = 5.0

    # --- Part 2: PET Thresholds ---
    PET_CRITICAL_THRESHOLD: float = 1.0
    PET_HIGH_THRESHOLD: float = 2.0
    PET_MEDIUM_THRESHOLD: float = 3.0

    # --- Part 2: Risk Scoring (0-100) ---
    RISK_SCORE_SAFE_MAX: int = 20
    RISK_SCORE_LOW_MAX: int = 40
    RISK_SCORE_MEDIUM_MAX: int = 60
    RISK_SCORE_HIGH_MAX: int = 80
    RISK_WEIGHT_MOTION: float = 0.15
    RISK_WEIGHT_DIRECTION: float = 0.10
    RISK_WEIGHT_PROXIMITY: float = 0.20
    RISK_WEIGHT_CONFLICT: float = 0.20
    RISK_WEIGHT_TTC: float = 0.20
    RISK_WEIGHT_PET: float = 0.10
    RISK_WEIGHT_TRAJECTORY: float = 0.05

    # --- Part 3: Speed Estimation (additive, calibration-gated) ---
    # Real-world km/h is ONLY produced when a valid road-plane homography
    # calibration exists in config/speed_calibration.json. Without it the
    # estimator reports NOT_CALIBRATED and exposes no km/h values.
    SPEED_CALIBRATION_FILE: str = field(
        default_factory=lambda: str(
            Path(__file__).resolve().parent.parent / "config" / "speed_calibration.json"
        )
    )
    SPEED_ESTIMATION_ENABLED: bool = True
    # Per-track position history window (source frames). Bounded to prevent leaks.
    SPEED_HISTORY_LENGTH: int = 60
    # Minimum valid ground observations before a speed is shown (not one frame).
    SPEED_MIN_HISTORY_FRAMES: int = 8
    # Speed is measured between the newest point and the oldest point that is at
    # least this many seconds older, so results are robust to per-frame jitter.
    SPEED_MEASUREMENT_WINDOW_S: float = 0.75
    # Configurable validation maximum. Anything above is rejected as an outlier,
    # the previous estimate is retained, and confidence is reduced.
    SPEED_MAX_KMH: float = 200.0
    # Exponential smoothing factor for the HUD-visible speed (STEP 8).
    SPEED_EMA_ALPHA: float = 0.30
    # Spike rejection relative to the running EMA (raw > ema*factor + offset).
    SPEED_SPIKE_FACTOR: float = 3.0
    SPEED_SPIKE_OFFSET_KMH: float = 60.0
    # A track that has not been observed for this many source frames is pruned.
    SPEED_STALE_FRAMES: int = 45
    # Camera-motion analysis samples the first N frames to decide whether to
    # warn that scene motion may bias speed estimates.
    CAMERA_MOTION_ANALYSIS_FRAMES: int = 10
    CAMERA_MOTION_SAMPLING_SKIP: int = 5

    # --- Part 4: AI Voice Assistant (additive) ---
    # Converts existing per-frame risk results into natural spoken alerts.
    # No secrets are stored here; optional provider keys come from env only.
    VOICE_ASSISTANT_ENABLED: bool = field(
        default_factory=lambda: os.getenv("VOICE_ASSISTANT_ENABLED", "true").lower()
        in ("1", "true", "yes", "on")
    )
    # Backend/TTS provider used by the server side (log | edge_tts | custom).
    # Actual audio playback for browser clients happens in the frontend via
    # the Web Speech API whenever ENABLE_BROWSER_FALLBACK is on.
    VOICE_PROVIDER: str = field(default_factory=lambda: os.getenv("VOICE_PROVIDER", "log"))
    VOICE_VOLUME: float = field(
        default_factory=lambda: float(os.getenv("VOICE_VOLUME", "1.0"))
    )
    VOICE_LANGUAGE: str = field(default_factory=lambda: os.getenv("VOICE_LANGUAGE", "en-IN"))
    VOICE_VOICE: str = field(default_factory=lambda: os.getenv("VOICE_VOICE", ""))
    # Alerts below this level produce no voice output (SAFE, LOW, MEDIUM, ...).
    VOICE_MIN_ALERT_LEVEL: str = field(
        default_factory=lambda: os.getenv("VOICE_MIN_ALERT_LEVEL", "MEDIUM").upper()
    )
    # Per-level repetition cooldowns (seconds). CRITICAL is intentionally short
    # and always interrupts whatever is being spoken.
    VOICE_COOLDOWN_SAFE_S: float = field(
        default_factory=lambda: float(os.getenv("VOICE_COOLDOWN_SAFE_S", "20"))
    )
    VOICE_COOLDOWN_MEDIUM_S: float = field(
        default_factory=lambda: float(os.getenv("VOICE_COOLDOWN_MEDIUM_S", "10"))
    )
    VOICE_COOLDOWN_HIGH_S: float = field(
        default_factory=lambda: float(os.getenv("VOICE_COOLDOWN_HIGH_S", "5"))
    )
    VOICE_COOLDOWN_CRITICAL_S: float = field(
        default_factory=lambda: float(os.getenv("VOICE_COOLDOWN_CRITICAL_S", "1.5"))
    )
    # A risk level must persist this many consecutive frames before it is
    # announced (debounce) - except CRITICAL which escalates immediately.
    RISK_STABILITY_WINDOW_FRAMES: int = field(
        default_factory=lambda: int(os.getenv("RISK_STABILITY_WINDOW_FRAMES", "5"))
    )
    # Maximum voice events kept per job (bounded queue, oldest dropped first).
    VOICE_MAX_QUEUE: int = field(
        default_factory=lambda: int(os.getenv("VOICE_MAX_QUEUE", "8"))
    )
    # TTC is spoken only when present, positive and no larger than this cap.
    VOICE_TTC_MAX_S: float = field(
        default_factory=lambda: float(os.getenv("VOICE_TTC_MAX_S", "10"))
    )
    # Speed is spoken only above this confidence and when speed_status==ESTIMATED.
    VOICE_SPEED_MIN_CONFIDENCE: float = field(
        default_factory=lambda: float(os.getenv("VOICE_SPEED_MIN_CONFIDENCE", "0.7"))
    )
    # Speed validation (items 8/28): the same-track speed is spoken only when
    # it is finite, positive, no larger than the reasonable maximum, and its
    # measurement is fresh enough (source seconds, not video frame).
    VOICE_MAX_REASONABLE_SPEED_KMH: float = field(
        default_factory=lambda: float(os.getenv("VOICE_MAX_REASONABLE_SPEED_KMH", "180"))
    )
    VOICE_MAX_SPEED_DATA_AGE_S: float = field(
        default_factory=lambda: float(os.getenv("VOICE_MAX_SPEED_DATA_AGE_S", "1.0"))
    )
    # A change this large (km/h) between consecutive SPEAKING speeds for the
    # SAME risk level triggers a fresh "speed changed" alert (non-spammy:
    # still gated by the level cooldown).
    VOICE_SPEED_CHANGE_ALERT_THRESHOLD_KMH: float = field(
        default_factory=lambda: float(os.getenv("VOICE_SPEED_CHANGE_ALERT_THRESHOLD_KMH", "10"))
    )
    # Text used by the frontend "Test voice" button.
    VOICE_TEST_TEXT: str = field(
        default_factory=lambda: os.getenv("VOICE_TEST_TEXT", "Voice assistant test.")
    )
    ENABLE_CONVERSATIONAL_MODE: bool = field(
        default_factory=lambda: os.getenv("ENABLE_CONVERSATIONAL_MODE", "true").lower()
        in ("1", "true", "yes", "on")
    )
    ENABLE_BROWSER_FALLBACK: bool = field(
        default_factory=lambda: os.getenv("ENABLE_BROWSER_FALLBACK", "true").lower()
        in ("1", "true", "yes", "on")
    )

    def __post_init__(self):
        """Mark as needing directory initialization."""
        self._dirs_created = False


settings = Settings()


def _ensure_dirs():
    """Create directories lazily on first access."""
    if not settings._dirs_created:
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        settings.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        (settings.OUTPUT_DIR / "processed_videos").mkdir(parents=True, exist_ok=True)
        (settings.OUTPUT_DIR / "screenshots").mkdir(parents=True, exist_ok=True)
        (settings.OUTPUT_DIR / "reports").mkdir(parents=True, exist_ok=True)
        (settings.OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
        settings._dirs_created = True
