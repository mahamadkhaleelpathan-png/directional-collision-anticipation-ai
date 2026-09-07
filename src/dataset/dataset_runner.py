"""
Dataset test runner module.

Processes videos through the collision anticipation pipeline
and records per-video results for dataset evaluation.
"""

import time
import datetime
import csv
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

import cv2
import numpy as np

from config.settings import settings
from config.dataset_config import dataset_config
from src.tracking.object_tracker import ObjectTracker
from src.motion.motion_analysis import MotionAnalyzer
from src.motion.trajectory import TrajectoryGenerator
from src.direction.directional_reasoning import DirectionalReasoner
from src.prediction.future_position import FuturePositionPredictor
from src.collision.collision_engine import CollisionEngine
from src.risk.risk_engine import RiskEngine
from src.dataset.dataset_manager import VideoMetadata


@dataclass
class VideoResult:
    """Results from processing a single video."""
    video_name: str
    dataset: str
    label: str
    frames_processed: int = 0
    fps: float = 0.0
    duration: float = 0.0
    width: int = 0
    height: int = 0
    unique_tracks: int = 0
    detection_events: int = 0
    max_risk: float = 0.0
    avg_risk: float = 0.0
    high_warnings: int = 0
    critical_warnings: int = 0
    conflict_events: int = 0
    min_ttc: Optional[float] = None
    alert_generated: bool = False
    false_positive: bool = False
    false_negative: bool = False
    processing_time: float = 0.0
    output_video_path: str = ""
    csv_report_path: str = ""
    error: str = ""
    primary_threat: str = "N/A"
    first_warning_frame: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "video_name": self.video_name,
            "dataset": self.dataset,
            "label": self.label,
            "frames_processed": self.frames_processed,
            "fps": round(self.fps, 1),
            "duration": round(self.duration, 2),
            "width": self.width,
            "height": self.height,
            "unique_tracks": self.unique_tracks,
            "detection_events": self.detection_events,
            "max_risk": round(self.max_risk, 1),
            "avg_risk": round(self.avg_risk, 1),
            "high_warnings": self.high_warnings,
            "critical_warnings": self.critical_warnings,
            "conflict_events": self.conflict_events,
            "min_ttc": round(self.min_ttc, 2) if self.min_ttc is not None else None,
            "alert_generated": self.alert_generated,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "processing_time": round(self.processing_time, 2),
            "output_video_path": self.output_video_path,
            "csv_report_path": self.csv_report_path,
            "error": self.error,
            "primary_threat": self.primary_threat,
            "first_warning_frame": self.first_warning_frame,
        }


@dataclass
class DatasetTestResult:
    """Aggregated results from a dataset test run."""
    run_id: str = ""
    run_timestamp: str = ""
    total_videos: int = 0
    processed_count: int = 0
    failed_count: int = 0
    positive_videos: int = 0
    negative_videos: int = 0
    positive_detected: int = 0
    positive_missed: int = 0
    negative_false_positives: int = 0
    avg_max_risk: float = 0.0
    max_observed_risk: float = 0.0
    avg_processing_fps: float = 0.0
    total_processing_time: float = 0.0
    video_results: List[VideoResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "run_timestamp": self.run_timestamp,
            "total_videos": self.total_videos,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "positive_videos": self.positive_videos,
            "negative_videos": self.negative_videos,
            "positive_detected": self.positive_detected,
            "positive_missed": self.positive_missed,
            "negative_false_positives": self.negative_false_positives,
            "avg_max_risk": round(self.avg_max_risk, 1),
            "max_observed_risk": round(self.max_observed_risk, 1),
            "avg_processing_fps": round(self.avg_processing_fps, 1),
            "total_processing_time": round(self.total_processing_time, 2),
        }


class DatasetTestRunner:
    """
    Runs the collision anticipation pipeline on dataset videos
    and records per-video results.
    """

    def __init__(self, confidence: float = 0.5):
        self.confidence = confidence
        self.output_base = dataset_config.DATASET_TEST_DIR
        self.results: List[VideoResult] = []

    def process_single_video(
        self,
        video_meta: VideoMetadata,
        output_dir: Optional[Path] = None,
        max_frames: Optional[int] = None,
    ) -> VideoResult:
        """
        Process a single video through the full pipeline.

        Args:
            video_meta: Metadata of the video to process.
            output_dir: Directory to save outputs.
            max_frames: Maximum frames to process (None = all).

        Returns:
            VideoResult with all measured metrics.
        """
        result = VideoResult(
            video_name=video_meta.file_name,
            dataset=video_meta.source_dataset,
            label=video_meta.category,
        )

        video_path = str(video_meta.file_path)

        if output_dir is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = self.output_base / f"run_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        start_time = time.time()

        try:
            tracker = ObjectTracker()
            motion_analyzer = MotionAnalyzer(fps=int(video_meta.fps))
            trajectory_gen = TrajectoryGenerator()
            direction_reasoner = DirectionalReasoner()
            collision_engine = CollisionEngine(frame_width=width, frame_height=height)
            risk_engine = RiskEngine()

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                result.error = "Cannot open video"
                return result

            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            result.fps = fps
            result.width = width
            result.height = height
            result.duration = total_frames / fps if fps > 0 else 0

            future_predictor = FuturePositionPredictor(frame_width=width, frame_height=height)
            ego_center = (width // 2, height)

            output_video_path = str(output_dir / f"processed_{video_meta.file_name}")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
            if not writer.isOpened():
                fourcc = cv2.VideoWriter_fourcc(*"XVID")
                output_video_path = str(output_dir / f"processed_{video_meta.file_name.rsplit('.', 1)[0]}.avi")
                writer = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))

            frame_idx = 0
            unique_track_ids = set()
            all_risk_scores = []
            all_class_counts = {}
            min_ttc_valid = None
            first_warning_frame = None

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_idx += 1
                if max_frames and frame_idx > max_frames:
                    break

                tracked_objects = tracker.update(frame)

                active_tracks = []
                directions_this_frame = {}
                motion_states_this_frame = {}

                for track in tracked_objects:
                    unique_track_ids.add(track.track_id)
                    all_class_counts[track.class_name] = all_class_counts.get(track.class_name, 0) + 1

                    motion_analyzer.update(
                        track_id=track.track_id,
                        class_name=track.class_name,
                        center=track.center,
                        ego_center=ego_center,
                        bbox=track.bbox,
                    )
                    trajectory_gen.update(
                        track_id=track.track_id,
                        position=track.center,
                        timestamp=frame_idx / fps,
                    )

                    direction = direction_reasoner.determine_direction(
                        ego_center=ego_center,
                        threat_center=track.center,
                    )
                    directions_this_frame[track.track_id] = direction.value

                    motion_state = motion_analyzer.get_motion_state(track.track_id)
                    if motion_state:
                        motion_states_this_frame[track.track_id] = motion_state

                    active_tracks.append({
                        "track_id": track.track_id,
                        "class_name": track.class_name,
                    })

                trajectory_status = {}
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

                for rr in risk_results.values():
                    all_risk_scores.append(rr.risk_score)
                    if rr.risk_level == "CRITICAL":
                        result.critical_warnings += 1
                        if first_warning_frame is None:
                            first_warning_frame = frame_idx
                    elif rr.risk_level == "HIGH":
                        result.high_warnings += 1
                        if first_warning_frame is None:
                            first_warning_frame = frame_idx
                    if rr.conflict_status in ("HIGH CONFLICT", "POTENTIAL CONFLICT"):
                        result.conflict_events += 1
                    if rr.estimated_ttc is not None:
                        if min_ttc_valid is None or rr.estimated_ttc < min_ttc_valid:
                            min_ttc_valid = rr.estimated_ttc

                primary = risk_engine.get_primary_threat()
                if primary:
                    result.primary_threat = f"{primary.object_type} #{primary.tracking_id}"

                active_track_ids = {t.track_id for t in tracked_objects}
                motion_analyzer.cleanup_stale_states(active_track_ids)

                writer.write(frame)

            cap.release()
            writer.release()

            result.frames_processed = frame_idx
            result.unique_tracks = len(unique_track_ids)
            result.detection_events = sum(all_class_counts.values())
            result.min_ttc = min_ttc_valid
            result.first_warning_frame = first_warning_frame
            result.alert_generated = result.high_warnings > 0 or result.critical_warnings > 0
            result.output_video_path = output_video_path

            if all_risk_scores:
                result.max_risk = max(all_risk_scores)
                result.avg_risk = sum(all_risk_scores) / len(all_risk_scores)

            if result.label == "negative":
                result.false_positive = result.high_warnings > 0 or result.critical_warnings > 0
            elif result.label == "positive":
                result.false_negative = not result.alert_generated

            csv_path = str(output_dir / f"report_{video_meta.file_name.rsplit('.', 1)[0]}.csv")
            self._save_csv_report(csv_path, video_meta, result)
            result.csv_report_path = csv_path

        except Exception as e:
            result.error = str(e)
            try:
                cap.release()
            except Exception:
                pass
            try:
                writer.release()
            except Exception:
                pass

        result.processing_time = time.time() - start_time
        return result

    def _save_csv_report(self, path: str, meta: VideoMetadata, result: VideoResult):
        """Save a per-video CSV report."""
        try:
            with open(path, "w", newline="") as f:
                writer_csv = csv.writer(f)
                writer_csv.writerow(["Metric", "Value"])
                writer_csv.writerow(["Video", result.video_name])
                writer_csv.writerow(["Dataset", result.dataset])
                writer_csv.writerow(["Label", result.label])
                writer_csv.writerow(["Frames Processed", result.frames_processed])
                writer_csv.writerow(["FPS", f"{result.fps:.1f}"])
                writer_csv.writerow(["Duration (s)", f"{result.duration:.2f}"])
                writer_csv.writerow(["Resolution", f"{result.width}x{result.height}"])
                writer_csv.writerow(["Unique Tracks", result.unique_tracks])
                writer_csv.writerow(["Detection Events", result.detection_events])
                writer_csv.writerow(["Max Risk", f"{result.max_risk:.1f}"])
                writer_csv.writerow(["Avg Risk", f"{result.avg_risk:.1f}"])
                writer_csv.writerow(["HIGH Warnings", result.high_warnings])
                writer_csv.writerow(["CRITICAL Warnings", result.critical_warnings])
                writer_csv.writerow(["Conflict Events", result.conflict_events])
                writer_csv.writerow(["Min TTC", f"{result.min_ttc:.2f}" if result.min_ttc else "N/A"])
                writer_csv.writerow(["Primary Threat", result.primary_threat])
                writer_csv.writerow(["Alert Generated", result.alert_generated])
                writer_csv.writerow(["False Positive", result.false_positive])
                writer_csv.writerow(["False Negative", result.false_negative])
                writer_csv.writerow(["Processing Time (s)", f"{result.processing_time:.2f}"])
                if result.error:
                    writer_csv.writerow(["Error", result.error])
        except Exception:
            pass

    def run_dataset_test(
        self,
        videos: List[VideoMetadata],
        run_id: Optional[str] = None,
        max_frames_per_video: Optional[int] = None,
    ) -> DatasetTestResult:
        """
        Process multiple videos and generate a dataset test summary.

        Args:
            videos: List of VideoMetadata to process.
            run_id: Unique identifier for this test run.
            max_frames_per_video: Max frames per video (None = all).

        Returns:
            DatasetTestResult with aggregated results.
        """
        if run_id is None:
            run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_base / f"run_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)

        dataset_result = DatasetTestResult(
            run_id=run_id,
            run_timestamp=timestamp,
            total_videos=len(videos),
        )

        self.results = []

        for i, video_meta in enumerate(videos):
            print(f"  Processing {i+1}/{len(videos)}: {video_meta.file_name} ({video_meta.category})")

            video_result = self.process_single_video(
                video_meta,
                output_dir=run_dir,
                max_frames=max_frames_per_video,
            )
            self.results.append(video_result)
            dataset_result.video_results.append(video_result)

            if video_result.error:
                dataset_result.failed_count += 1
            else:
                dataset_result.processed_count += 1

            if video_meta.category == "positive":
                dataset_result.positive_videos += 1
                if video_result.alert_generated:
                    dataset_result.positive_detected += 1
                else:
                    dataset_result.positive_missed += 1
            elif video_meta.category == "negative":
                dataset_result.negative_videos += 1
                if video_result.false_positive:
                    dataset_result.negative_false_positives += 1

        risk_scores = [r.max_risk for r in self.results if not r.error]
        processing_times = [r.processing_time for r in self.results if not r.error]
        frame_counts = [r.frames_processed for r in self.results if not r.error]

        if risk_scores:
            dataset_result.avg_max_risk = sum(risk_scores) / len(risk_scores)
            dataset_result.max_observed_risk = max(risk_scores)

        if processing_times:
            dataset_result.total_processing_time = sum(processing_times)
            total_frames = sum(frame_counts)
            if dataset_result.total_processing_time > 0:
                dataset_result.avg_processing_fps = total_frames / dataset_result.total_processing_time

        self._save_dataset_summary(run_dir, dataset_result)

        return dataset_result

    def _save_dataset_summary(self, run_dir: Path, result: DatasetTestResult):
        """Save the dataset test summary to CSV."""
        summary_path = run_dir / "dataset_summary.csv"
        try:
            with open(summary_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Metric", "Value"])
                for key, value in result.to_dict().items():
                    writer.writerow([key, value])
        except Exception:
            pass

        results_path = run_dir / "video_results.csv"
        try:
            with open(results_path, "w", newline="") as f:
                if result.video_results:
                    fieldnames = list(result.video_results[0].to_dict().keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for vr in result.video_results:
                        writer.writerow(vr.to_dict())
        except Exception:
            pass

    def get_results(self) -> List[VideoResult]:
        """Return all current results."""
        return self.results
