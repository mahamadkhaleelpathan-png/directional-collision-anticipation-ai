"""
Dataset configuration for the collision anticipation system.

Defines dataset paths, supported formats, and label conventions.
Configurable via relative paths, environment variables, or defaults.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


SUPPORTED_VIDEO_FORMATS = [".mp4", ".avi", ".mov", ".mkv", ".webm"]

POSITIVE_LABELS = ["collision", "near_collision", "dangerous_conflict"]
NEGATIVE_LABELS = ["normal_traffic"]
INDIAN_TRAFFIC_LABELS = ["IDD", "I2WDD", "IDD_X", "IDD_Temporal", "other"]


@dataclass
class DatasetConfig:
    """Configuration for dataset discovery and management.

    E3 FIX: these paths previously pointed at a top-level ``dataset/``
    directory that does not exist in this repo, so
    ``GET /api/dataset/summary`` always returned zero videos. They now
    point at the real on-disk layout under ``data/`` (no duplicate
    folders created):
      positive       -> data/videos   (curated sample clips)
      negative       -> data/uploads  (uploaded + cached real videos)
      indian_traffic -> data/datasets (HuggingFace/local dataset cache)
    """

    DATASET_ROOT: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data")

    POSITIVE_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "videos")
    NEGATIVE_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "uploads")
    INDIAN_TRAFFIC_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "datasets")

    OUTPUT_BASE: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "output")
    DATASET_TEST_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "output" / "dataset_tests")

    SUPPORTED_FORMATS: List[str] = field(default_factory=lambda: list(SUPPORTED_VIDEO_FORMATS))

    MIN_VIDEO_FRAMES: int = 10
    MIN_VIDEO_FPS: float = 1.0

    def __post_init__(self):
        env_root = os.getenv("DATASET_ROOT")
        if env_root:
            self.DATASET_ROOT = Path(env_root)
        self._dirs_created = False

    def get_positive_subdirs(self) -> List[Path]:
        """Return all positive subdirectories."""
        if not self.POSITIVE_DIR.exists():
            return []
        return [d for d in self.POSITIVE_DIR.iterdir() if d.is_dir()]

    def get_negative_subdirs(self) -> List[Path]:
        """Return all negative subdirectories."""
        if not self.NEGATIVE_DIR.exists():
            return []
        return [d for d in self.NEGATIVE_DIR.iterdir() if d.is_dir()]

    def get_indian_traffic_subdirs(self) -> List[Path]:
        """Return all Indian traffic subdirectories."""
        if not self.INDIAN_TRAFFIC_DIR.exists():
            return []
        return [d for d in self.INDIAN_TRAFFIC_DIR.iterdir() if d.is_dir()]


dataset_config = DatasetConfig()


def _ensure_dataset_dirs():
    """Create dataset directories lazily on first access."""
    if not dataset_config._dirs_created:
        dataset_config.DATASET_ROOT.mkdir(parents=True, exist_ok=True)
        dataset_config.POSITIVE_DIR.mkdir(parents=True, exist_ok=True)
        dataset_config.NEGATIVE_DIR.mkdir(parents=True, exist_ok=True)
        dataset_config.INDIAN_TRAFFIC_DIR.mkdir(parents=True, exist_ok=True)
        dataset_config.DATASET_TEST_DIR.mkdir(parents=True, exist_ok=True)
        dataset_config._dirs_created = True
