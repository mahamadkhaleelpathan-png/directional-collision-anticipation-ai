"""
Dataset manager module.

Discovers, validates, and manages video datasets for automated testing.
Supports positive/negative/Indian-traffic categorization.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import random
import cv2

from config.dataset_config import dataset_config, SUPPORTED_VIDEO_FORMATS


@dataclass
class VideoMetadata:
    """Metadata for a single discovered video."""
    file_path: Path
    file_name: str
    category: str
    subcategory: str
    source_dataset: str
    width: int = 0
    height: int = 0
    fps: float = 0.0
    frame_count: int = 0
    duration: float = 0.0
    is_valid: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "file_path": str(self.file_path),
            "file_name": self.file_name,
            "category": self.category,
            "subcategory": self.subcategory,
            "source_dataset": self.source_dataset,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "duration": round(self.duration, 2),
            "is_valid": self.is_valid,
            "error": self.error,
        }


@dataclass
class DatasetSummary:
    """Summary of the discovered dataset."""
    total_videos: int = 0
    positive_count: int = 0
    negative_count: int = 0
    indian_traffic_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    by_subcategory: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_videos": self.total_videos,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "indian_traffic_count": self.indian_traffic_count,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "by_category": self.by_category,
            "by_subcategory": self.by_subcategory,
        }


class DatasetManager:
    """
    Manages video datasets for automated testing.

    Discovers videos recursively, validates them, categorizes them,
    and supports random selection for batch testing.
    """

    def __init__(self):
        self.config = dataset_config
        self.videos: List[VideoMetadata] = []
        self.summary = DatasetSummary()

    def discover_videos(self) -> List[VideoMetadata]:
        """
        Recursively discover all videos in the dataset directory.

        Returns:
            List of VideoMetadata for all discovered videos.
        """
        self.videos = []

        self._scan_directory(
            self.config.POSITIVE_DIR,
            category="positive",
            source_dataset="local"
        )

        self._scan_directory(
            self.config.NEGATIVE_DIR,
            category="negative",
            source_dataset="local"
        )

        self._scan_directory(
            self.config.INDIAN_TRAFFIC_DIR,
            category="indian_traffic",
            source_dataset="indian"
        )

        self._update_summary()
        return self.videos

    def _scan_directory(self, directory: Path, category: str, source_dataset: str):
        """Recursively scan a directory for video files."""
        if not directory.exists():
            return

        for item in directory.iterdir():
            if item.is_dir():
                subcategory = item.name
                self._scan_directory(item, category, subcategory)
            elif item.is_file() and item.suffix.lower() in self.config.SUPPORTED_FORMATS:
                metadata = self._create_metadata(item, category, source_dataset)
                self.videos.append(metadata)

    def _create_metadata(self, file_path: Path, category: str, source_dataset: str) -> VideoMetadata:
        """Create metadata for a video file, validating it if possible."""
        subcategory = file_path.parent.name if file_path.parent != self.config.DATASET_ROOT else "unknown"

        metadata = VideoMetadata(
            file_path=file_path,
            file_name=file_path.name,
            category=category,
            subcategory=subcategory,
            source_dataset=source_dataset,
        )

        try:
            cap = cv2.VideoCapture(str(file_path))
            if cap.isOpened():
                metadata.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                metadata.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                metadata.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                metadata.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                metadata.duration = metadata.frame_count / metadata.fps if metadata.fps > 0 else 0.0
                metadata.is_valid = (
                    metadata.frame_count >= self.config.MIN_VIDEO_FRAMES
                    and metadata.fps >= self.config.MIN_VIDEO_FPS
                    and metadata.width > 0
                    and metadata.height > 0
                )
                if not metadata.is_valid:
                    metadata.error = f"Insufficient frames ({metadata.frame_count}) or invalid dimensions"
                cap.release()
            else:
                metadata.error = "Cannot open video file"
        except Exception as e:
            metadata.error = str(e)

        return metadata

    def _update_summary(self):
        """Update the dataset summary from current video list."""
        self.summary = DatasetSummary()
        self.summary.total_videos = len(self.videos)

        for v in self.videos:
            if v.category == "positive":
                self.summary.positive_count += 1
            elif v.category == "negative":
                self.summary.negative_count += 1
            elif v.category == "indian_traffic":
                self.summary.indian_traffic_count += 1

            if v.is_valid:
                self.summary.valid_count += 1
            else:
                self.summary.invalid_count += 1

            self.summary.by_category[v.category] = self.summary.by_category.get(v.category, 0) + 1
            key = f"{v.category}/{v.subcategory}"
            self.summary.by_subcategory[key] = self.summary.by_subcategory.get(key, 0) + 1

    def get_valid_videos(self) -> List[VideoMetadata]:
        """Return only valid videos."""
        return [v for v in self.videos if v.is_valid]

    def get_videos_by_category(self, category: str) -> List[VideoMetadata]:
        """Return videos matching a category (positive/negative/indian_traffic)."""
        return [v for v in self.videos if v.category == category and v.is_valid]

    def get_positive_videos(self) -> List[VideoMetadata]:
        """Return all valid positive videos."""
        return self.get_videos_by_category("positive")

    def get_negative_videos(self) -> List[VideoMetadata]:
        """Return all valid negative videos."""
        return self.get_videos_by_category("negative")

    def get_indian_traffic_videos(self) -> List[VideoMetadata]:
        """Return all valid Indian traffic videos."""
        return self.get_videos_by_category("indian_traffic")

    def select_random(
        self,
        count: int = 1,
        category: str = "both",
        seed: Optional[int] = None,
        unique: bool = True,
    ) -> List[VideoMetadata]:
        """
        Select random videos from the dataset.

        Args:
            count: Number of videos to select.
            category: "positive", "negative", "indian_traffic", or "both" (positive+negative).
            seed: Random seed for reproducibility.
            unique: If True, avoid selecting the same video twice.

        Returns:
            List of selected VideoMetadata.
        """
        if seed is not None:
            random.seed(seed)

        if category == "both":
            pool = self.get_positive_videos() + self.get_negative_videos()
        elif category == "all":
            pool = self.get_valid_videos()
        else:
            pool = self.get_videos_by_category(category)

        if not pool:
            return []

        if unique:
            pool = list(set(id(v) for v in pool))
            pool = [v for v in self.videos if id(v) in pool and v.is_valid]

        selected = []
        available = list(pool)

        for _ in range(min(count, len(available))):
            if not available:
                break
            idx = random.randint(0, len(available) - 1)
            selected.append(available.pop(idx))

        return selected

    def select_balanced(
        self,
        total_count: int = 10,
        seed: Optional[int] = None,
    ) -> List[VideoMetadata]:
        """
        Select a balanced mix of positive and negative videos.

        Args:
            total_count: Total number of videos to select.
            seed: Random seed for reproducibility.

        Returns:
            List of selected VideoMetadata with balanced categories.
        """
        if seed is not None:
            random.seed(seed)

        positive = self.get_positive_videos()
        negative = self.get_negative_videos()

        if not positive and not negative:
            return self.get_valid_videos()[:total_count]

        pos_count = min(len(positive), total_count // 2)
        neg_count = min(len(negative), total_count - pos_count)

        if pos_count == 0 and neg_count > 0:
            neg_count = min(neg_count, total_count)
        elif neg_count == 0 and pos_count > 0:
            pos_count = min(pos_count, total_count)

        selected_pos = random.sample(positive, min(pos_count, len(positive))) if positive else []
        selected_neg = random.sample(negative, min(neg_count, len(negative))) if negative else []

        return selected_pos + selected_neg

    def validate_video(self, video_path: Path) -> VideoMetadata:
        """Validate a single video file and return its metadata."""
        category = "unknown"
        if self.config.POSITIVE_DIR in video_path.parents:
            category = "positive"
        elif self.config.NEGATIVE_DIR in video_path.parents:
            category = "negative"
        elif self.config.INDIAN_TRAFFIC_DIR in video_path.parents:
            category = "indian_traffic"

        return self._create_metadata(video_path, category, "local")

    def get_video_by_name(self, name: str) -> Optional[VideoMetadata]:
        """Find a video by its filename."""
        for v in self.videos:
            if v.file_name == name:
                return v
        return None

    def get_metadata_for_all(self) -> List[dict]:
        """Return metadata dictionaries for all discovered videos."""
        return [v.to_dict() for v in self.videos]

    def get_summary(self) -> dict:
        """Return the dataset summary as a dictionary."""
        return self.summary.to_dict()
