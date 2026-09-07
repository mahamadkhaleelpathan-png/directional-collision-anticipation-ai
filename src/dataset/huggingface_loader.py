"""
Dataset loader supporting multiple open-source sources.

Datasets:
  1. nexar-ai/nexar_collision_prediction — dashcam collision videos (HuggingFace)
  2. thirdeyelabs/indian-road-dataset — Indian road footage, Delhi NCR (HuggingFace)
  3. Drupad-DeV/Indian-Pedestrian-Intention-Dataset — Indian pedestrian clips (GitHub)
"""

import os
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

LOCAL_CACHE_DIR = settings.DATA_DIR / "datasets"

DATASETS = {
    "nexar": {
        "hf_name": "nexar-ai/nexar_collision_prediction",
        "description": "Nexar dashcam collision prediction (1500 videos, 1280x720, 30fps)",
        "type": "huggingface_video",
    },
    "indian_road": {
        "hf_name": "thirdeyelabs/indian-road-dataset",
        "description": "Indian road driving dataset — Delhi NCR dashcam (8441 clips, CC BY 4.0)",
        "type": "huggingface_webdataset",
    },
    "indian_pedestrian": {
        "github_url": "https://github.com/Drupad-DeV/Indian-Pedestrian-Intention-Dataset/archive/refs/heads/main.zip",
        "description": "Indian pedestrian intention — Kerala (17 clips, MIT license)",
        "type": "github_zip",
    },
}


@dataclass
class DatasetStats:
    source: str
    total: int = 0
    downloaded: int = 0
    local_dir: str = ""
    error: Optional[str] = None


def _extract_video_frame(video_reader, frame_idx: int):
    return video_reader[frame_idx].asnumpy()


def download_nexar(
    split: str = "train",
    max_samples: Optional[int] = None,
    on_progress=None,
) -> DatasetStats:
    """Download Nexar collision prediction dataset."""
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError("pip install datasets")

    video_dir = LOCAL_CACHE_DIR / "nexar" / split
    video_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading Nexar dataset (split=%s)...", split)
    if on_progress:
        on_progress(0, 0, "Loading Nexar metadata from HuggingFace...")

    ds = load_dataset("nexar-ai/nexar_collision_prediction", split=split)
    total = len(ds)
    if max_samples:
        total = min(total, max_samples)

    stats = DatasetStats(source="nexar", total=total, local_dir=str(video_dir))
    downloaded = 0

    for i in range(total):
        row = ds[i]
        label = row.get("label", 0)
        tag = "pos" if label == 1 else "neg"
        video_path = video_dir / f"nexar_{tag}_{i:05d}.mp4"

        if video_path.exists():
            downloaded += 1
            if on_progress and (i % 10 == 0 or i == total - 1):
                on_progress(i + 1, total, f"Nexar {i+1}/{total} (cached)")
            continue

        try:
            video_reader = row["video"]
            n_frames = len(video_reader)

            import cv2
            first_frame = _extract_video_frame(video_reader, 0)
            h, w = first_frame.shape[:2]

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(video_path), fourcc, 30, (w, h))
            if not writer.isOpened():
                video_path = video_path.with_suffix(".avi")
                writer = cv2.VideoWriter(str(video_path), fourcc, 30, (w, h))

            for f_idx in range(n_frames):
                frame = _extract_video_frame(video_reader, f_idx)
                writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            writer.release()
            downloaded += 1

            if on_progress and (i % 10 == 0 or i == total - 1):
                on_progress(i + 1, total, f"Nexar downloaded {i+1}/{total}")

        except Exception as e:
            logger.warning("Nexar video %d failed: %s", i, e)

    stats.downloaded = downloaded
    return stats


def download_indian_road(
    max_samples: Optional[int] = None,
    on_progress=None,
) -> DatasetStats:
    """Download Indian Road Driving Dataset from HuggingFace (WebDataset shards).

    This extracts keyframes as MP4s for the pipeline.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError("pip install datasets")

    video_dir = LOCAL_CACHE_DIR / "indian_road"
    video_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading Indian Road Dataset from HuggingFace...")
    if on_progress:
        on_progress(0, 0, "Loading Indian Road Dataset metadata...")

    try:
        ds = load_dataset("thirdeyelabs/indian-road-dataset", split="train")
    except Exception as e:
        logger.warning("Could not load Indian Road Dataset: %s", e)
        return DatasetStats(source="indian_road", error=str(e))

    total = len(ds)
    if max_samples:
        total = min(total, max_samples)

    stats = DatasetStats(source="indian_road", total=total, local_dir=str(video_dir))
    downloaded = 0

    import cv2

    for i in range(total):
        video_path = video_dir / f"indian_road_{i:05d}.mp4"
        if video_path.exists():
            downloaded += 1
            if on_progress and (i % 10 == 0 or i == total - 1):
                on_progress(i + 1, total, f"Indian Road {i+1}/{total} (cached)")
            continue

        try:
            row = ds[i]
            frame = row.get("image")
            if frame is None:
                continue

            import numpy as np
            img = np.array(frame)
            h, w = img.shape[:2]

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(video_path), fourcc, 10, (w, h))
            if not writer.isOpened():
                continue

            bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            writer.write(bgr)
            writer.release()
            downloaded += 1

            if on_progress and (i % 10 == 0 or i == total - 1):
                on_progress(i + 1, total, f"Indian Road {i+1}/{total}")

        except Exception as e:
            logger.warning("Indian Road video %d failed: %s", i, e)

    stats.downloaded = downloaded
    return stats


def download_indian_pedestrian(on_progress=None) -> DatasetStats:
    """Download Indian Pedestrian Intention Dataset clips from GitHub."""
    import urllib.request
    import zipfile
    import io

    video_dir = LOCAL_CACHE_DIR / "indian_pedestrian" / "clips"
    video_dir.mkdir(parents=True, exist_ok=True)

    existing = list(video_dir.glob("*.mp4"))
    if existing:
        logger.info("Indian Pedestrian clips already cached (%d files)", len(existing))
        return DatasetStats(
            source="indian_pedestrian",
            total=len(existing),
            downloaded=len(existing),
            local_dir=str(video_dir),
        )

    url = DATASETS["indian_pedestrian"]["github_url"]
    logger.info("Downloading Indian Pedestrian dataset from GitHub...")
    if on_progress:
        on_progress(0, 1, "Downloading Indian Pedestrian clips from GitHub...")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as response:
            zip_data = response.read()

        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            for member in zf.namelist():
                if member.endswith(".mp4"):
                    data = zf.read(member)
                    filename = Path(member).name
                    (video_dir / filename).write_bytes(data)

        clips = list(video_dir.glob("*.mp4"))
        if on_progress:
            on_progress(1, 1, f"Downloaded {len(clips)} Indian pedestrian clips")

        return DatasetStats(
            source="indian_pedestrian",
            total=len(clips),
            downloaded=len(clips),
            local_dir=str(video_dir),
        )
    except Exception as e:
        logger.error("Failed to download Indian Pedestrian dataset: %s", e)
        return DatasetStats(source="indian_pedestrian", error=str(e))


def download_all(
    sources: Optional[List[str]] = None,
    max_samples: Optional[int] = None,
    on_progress=None,
) -> Dict[str, DatasetStats]:
    """Download from one or more sources.

    Parameters
    ----------
    sources:
        List of source keys: "nexar", "indian_road", "indian_pedestrian".
        Defaults to all three.
    max_samples:
        Cap per HuggingFace dataset (ignored for GitHub zip).
    on_progress:
        Callback: on_progress(source, current, total, message)
    """
    if sources is None:
        sources = ["nexar", "indian_road", "indian_pedestrian"]

    results = {}

    for src in sources:
        if src == "nexar":
            def nexar_prog(cur, tot, msg):
                if on_progress:
                    on_progress("nexar", cur, tot, msg)
            results["nexar"] = download_nexar(
                max_samples=max_samples, on_progress=nexar_prog
            )

        elif src == "indian_road":
            def indian_prog(cur, tot, msg):
                if on_progress:
                    on_progress("indian_road", cur, tot, msg)
            results["indian_road"] = download_indian_road(
                max_samples=max_samples, on_progress=indian_prog
            )

        elif src == "indian_pedestrian":
            def ped_prog(cur, tot, msg):
                if on_progress:
                    on_progress("indian_pedestrian", cur, tot, msg)
            results["indian_pedestrian"] = download_indian_pedestrian(on_progress=ped_prog)

    return results


def list_all_local_videos() -> List[Dict]:
    """List all locally cached videos from any source."""
    results = []

    for source_dir in LOCAL_CACHE_DIR.iterdir():
        if not source_dir.is_dir():
            continue
        for video_path in source_dir.rglob("*.mp4"):
            results.append({
                "source": source_dir.name,
                "path": str(video_path),
                "filename": video_path.name,
            })
        for video_path in source_dir.rglob("*.avi"):
            results.append({
                "source": source_dir.name,
                "path": str(video_path),
                "filename": video_path.name,
            })

    return results
