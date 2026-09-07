"""
Object detection module using Ultralytics YOLO.

Detects road users in each video frame and returns bounding boxes,
class labels, and confidence scores.
"""

from typing import List, Tuple, Optional
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

from config.settings import settings


class ObjectDetector:
    """YOLO-based object detector for traffic scene analysis."""

    def __init__(self, model_path: Optional[str] = None, confidence: Optional[float] = None):
        """
        Initialize the object detector.

        Args:
            model_path: Path to the YOLO model file.
            confidence: Minimum detection confidence threshold.
        """
        self.model_path = model_path or settings.YOLO_MODEL_PATH
        self.confidence = confidence or settings.DETECTION_CONFIDENCE
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load the YOLO model from disk."""
        if YOLO is None:
            raise ImportError("ultralytics package is not installed. Run: pip install ultralytics")
        self.model = YOLO(self.model_path)

    def detect(self, frame: np.ndarray) -> List[dict]:
        """
        Run object detection on a single video frame.

        Args:
            frame: BGR image as a numpy array (H, W, 3).

        Returns:
            List of detection dicts with keys:
                'bbox' (x1, y1, x2, y2),
                'class_name',
                'confidence',
                'class_id'
        """
        results = self.model(frame, conf=self.confidence, verbose=False)

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                cls_name = self.model.names.get(cls_id, "unknown")

                if cls_name.lower() in settings.DETECTION_CLASSES:
                    detections.append({
                        "bbox": (int(x1), int(y1), int(x2), int(y2)),
                        "class_name": cls_name,
                        "confidence": conf,
                        "class_id": cls_id,
                    })

        return detections

    def detect_batch(self, frames: List[np.ndarray]) -> List[List[dict]]:
        """
        Run detection on multiple frames.

        Args:
            frames: List of BGR images.

        Returns:
            List of detection lists, one per frame.
        """
        return [self.detect(frame) for frame in frames]
