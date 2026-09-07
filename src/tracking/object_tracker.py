"""
Multi-object tracker using ByteTrack integration.

Assigns stable IDs to detected objects and maintains their movement
history across frames for trajectory analysis.
"""

from typing import Dict, List, Optional
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TrackedObject:
    """Represents a single tracked road user across frames."""

    def __init__(self, track_id: int, class_name: str, bbox: tuple, frame_idx: int, confidence: float = 0.0):
        self.track_id = track_id
        self.class_name = class_name
        self.bbox = bbox
        self.frame_idx = frame_idx
        self.confidence = confidence
        self.history: List[dict] = []

        # Compute center point
        x1, y1, x2, y2 = bbox
        self.center = ((x1 + x2) / 2, (y1 + y2) / 2)
        self.width = x2 - x1
        self.height = y2 - y1

    def update(self, bbox: tuple, frame_idx: int):
        """Update tracked object with new bounding box."""
        self.bbox = bbox
        self.frame_idx = frame_idx
        x1, y1, x2, y2 = bbox
        self.center = ((x1 + x2) / 2, (y1 + y2) / 2)
        self.width = x2 - x1
        self.height = y2 - y1

    def to_dict(self) -> dict:
        """Serialize tracked object to dictionary."""
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "bbox": self.bbox,
            "center": self.center,
            "frame_idx": self.frame_idx,
            "confidence": self.confidence,
        }


class ObjectTracker:
    """Multi-object tracker using YOLO + ByteTrack."""

    def __init__(self, model_path: Optional[str] = None, stale_threshold: int = 60,
                 conf_threshold: Optional[float] = None):
        """
        Initialize the tracker.

        Args:
            model_path: Path to the YOLO model file.
            stale_threshold: Number of frames after which a track is considered stale.
            conf_threshold: YOLO detection confidence threshold. Defaults to
                settings.DETECTION_CONFIDENCE. E2 FIX: previously the pipeline
                accepted a confidence value but never forwarded it here, so the
                frontend slider had no effect.
        """
        self.model_path = model_path or settings.YOLO_MODEL_PATH
        self.conf_threshold = conf_threshold if conf_threshold is not None else settings.DETECTION_CONFIDENCE
        self.model = None
        self.tracks: Dict[int, TrackedObject] = {}
        self.frame_count: int = 0
        self.stale_threshold = stale_threshold
        self._load_model()

    def _load_model(self):
        """Load the YOLO model with ByteTrack tracking."""
        if YOLO is None:
            raise ImportError("ultralytics package is not installed.")
        self.model = YOLO(self.model_path)

    def update(self, frame: np.ndarray) -> List[TrackedObject]:
        """
        Process a frame and update all tracked objects.

        Args:
            frame: BGR image as numpy array.

        Returns:
            List of currently active TrackedObject instances.
        """
        self.frame_count += 1

        results = self.model.track(
            frame,
            persist=True,
            conf=self.conf_threshold,
            tracker="bytetrack.yaml",
            verbose=False,
        )

        active_tracks = []
        active_ids = set()

        for result in results:
            boxes = result.boxes
            if boxes is None or boxes.id is None:
                continue

            for i in range(len(boxes)):
                track_id = int(boxes.id[i].cpu().numpy())
                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                cls_id = int(boxes.cls[i].cpu().numpy())
                cls_name = self.model.names.get(cls_id, "unknown")
                conf = float(boxes.conf[i].cpu().numpy())

                if cls_name.lower() not in settings.DETECTION_CLASSES:
                    continue

                bbox = (int(x1), int(y1), int(x2), int(y2))

                if track_id in self.tracks:
                    self.tracks[track_id].update(bbox, self.frame_count)
                    self.tracks[track_id].confidence = conf
                else:
                    self.tracks[track_id] = TrackedObject(
                        track_id=track_id,
                        class_name=cls_name,
                        bbox=bbox,
                        frame_idx=self.frame_count,
                        confidence=conf,
                    )

                active_ids.add(track_id)
                active_tracks.append(self.tracks[track_id])

        self._cleanup_stale_tracks()
        if active_tracks:
            logger.debug("Frame %d: tracking %d active objects", self.frame_count, len(active_tracks))
        return active_tracks

    def _cleanup_stale_tracks(self):
        """Remove tracks that haven't been updated for stale_threshold frames."""
        stale_ids = [
            tid for tid, track in self.tracks.items()
            if self.frame_count - track.frame_idx > self.stale_threshold
        ]
        for tid in stale_ids:
            del self.tracks[tid]

    def get_track_history(self, track_id: int) -> List[dict]:
        """Get the full history of a tracked object."""
        if track_id in self.tracks:
            return self.tracks[track_id].history
        return []

    def get_all_active_tracks(self) -> List[TrackedObject]:
        """Return all currently tracked objects."""
        return list(self.tracks.values())

    def reset(self):
        """Clear all tracking state."""
        self.tracks.clear()
        self.frame_count = 0
