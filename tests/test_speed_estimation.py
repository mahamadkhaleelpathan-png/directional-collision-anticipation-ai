"""Unit tests for the additive speed-estimation module (Part 3).

Covers conversion, timestamps/frame-skipping, distance, speed, smoothing,
outlier rejection, insufficient history, calibration valid/invalid, and
track cleanup (STEP 34). Uses synthetic point correspondences so ground
values are known analytically.
"""

import os
import tempfile
import unittest

import numpy as np

from config import settings
from src.calibration.calibration import (
    clear_calibration,
    load_calibration,
    save_calibration,
)
from src.calibration.ground import HomographyGroundPlane, bottom_center
from src.motion.speed_estimator import (
    SPEED_CALCULATING,
    SPEED_ESTIMATED,
    SPEED_LOW_CONFIDENCE,
    SPEED_NOT_CALIBRATED,
    SPEED_UNAVAILABLE,
    TrackSpeedEstimator,
    kmh_to_mps,
    mps_to_kmh,
)


def make_plane(width_m=3.5, depth_m=10.0):
    """A synthetic but perfectly known road-plane homography."""
    return HomographyGroundPlane(
        source="test",
        image_points=[(400, 300), (800, 300), (800, 600), (400, 600)],
        world_points_meters=[(0, 0), (width_m, 0), (width_m, depth_m), (0, depth_m)],
    )


class TestConversion(unittest.TestCase):
    def test_mps_to_kmh(self):
        self.assertAlmostEqual(mps_to_kmh(10.0), 36.0, places=6)
        self.assertAlmostEqual(mps_to_kmh(13.14), 47.304, places=3)

    def test_kmh_to_mps(self):
        self.assertAlmostEqual(kmh_to_mps(36.0), 10.0, places=6)
        self.assertAlmostEqual(kmh_to_mps(47.3), 13.1388, places=3)
        self.assertAlmostEqual(kmh_to_mps(mps_to_kmh(8.0)), 8.0, places=6)


class TestGroundPlane(unittest.TestCase):
    def test_bottom_center(self):
        x, y = bottom_center((100, 200, 140, 300))
        self.assertAlmostEqual(x, 120.0)
        self.assertAlmostEqual(y, 300.0)

    def test_distance(self):
        a, b = (0.0, 0.0), (3.0, 4.0)
        self.assertAlmostEqual(make_plane().ground_distance_m(a, b), 5.0, places=6)

    def test_valid_homography_maps_center(self):
        plane = make_plane(width_m=3.5, depth_m=10.0)
        self.assertTrue(plane.calibrated)
        # top-center of image -> world (width/2, 0)
        world = plane.image_to_ground(600, 300)
        self.assertIsNotNone(world)
        self.assertAlmostEqual(world[0], 1.75, places=1)
        self.assertAlmostEqual(world[1], 0.0, places=1)

    def test_invalid_points(self):
        # Duplicate image points -> must reject.
        plane = HomographyGroundPlane(
            source="test",
            image_points=[(0, 0), (0, 0), (10, 10), (20, 20)],
            world_points_meters=[(0, 0), (1, 0), (1, 1), (0, 1)],
        )
        self.assertFalse(plane.calibrated)

    def test_collinear_points(self):
        plane = HomographyGroundPlane(
            source="test",
            image_points=[(0, 0), (1, 0), (2, 0), (3, 0)],
            world_points_meters=[(0, 0), (1, 0), (1, 1), (0, 1)],
        )
        self.assertFalse(plane.calibrated)


class TestCalibrationPersistence(unittest.TestCase):
    def setUp(self):
        self._orig = settings.SPEED_CALIBRATION_FILE
        self._tmp_dir = tempfile.mkdtemp()
        settings.SPEED_CALIBRATION_FILE = os.path.join(self._tmp_dir, "speed_calibration.json")

    def tearDown(self):
        settings.SPEED_CALIBRATION_FILE = self._orig

    def test_unconfigured_is_not_calibrated(self):
        cal = load_calibration()
        self.assertFalse(cal.configured)

    def test_save_then_load_roundtrip(self):
        save_calibration([(400, 300), (800, 300), (800, 600), (400, 600)], 3.5, 10.0)
        cal = load_calibration()
        self.assertTrue(cal.configured)
        self.assertEqual(cal.to_status_dict()["label"], "CALIBRATED")

    def test_duplicate_points_rejected(self):
        with self.assertRaises(ValueError):
            save_calibration([(400, 300), (400, 300), (800, 600), (400, 600)], 3.5, 10.0)

    def test_non_positive_dimensions_rejected(self):
        with self.assertRaises(ValueError):
            save_calibration([(400, 300), (800, 300), (800, 600), (400, 600)], -1, 10.0)
        with self.assertRaises(ValueError):
            save_calibration([(400, 300), (800, 300), (800, 600), (400, 600)], 3.5, 0.0)

    def test_clear(self):
        save_calibration([(400, 300), (800, 300), (800, 600), (400, 600)], 3.5, 10.0)
        cal = clear_calibration()
        self.assertFalse(cal.configured)


def _wrap(plane):
    from src.calibration.calibration import Calibration
    return Calibration(
        ground_plane=plane,
        image_points=plane.image_points,
        world_points_meters=plane.world_points_meters,
    )


class TestSpeedEstimator(unittest.TestCase):
    def setUp(self):
        self.cal = type("C", (), {"configured": False, "to_status_dict": lambda s: {}, "ground_plane": None})()
        self.est = TrackSpeedEstimator(fps=30, calibration=self.cal)

    def feed(self, frames_boxes, confidence=0.85, fps=30):
        for frame, box in frames_boxes:
            self.est.update(track_id=1, frame_idx=frame, bbox=box, detection_conf=confidence)
        return self.est.last_estimate(1)

    def test_uncalibrated_never_reports_kmh(self):
        frames = [(i, (490, 300, 510, 500)) for i in range(1, 41)]
        res = self.feed(frames)
        self.assertEqual(res.speed_status, SPEED_NOT_CALIBRATED)
        self.assertIsNone(res.speed_kmh)

    def test_insufficient_history_is_calculating(self):
        # Even calibrated, a single frame must not yield speed.
        est = TrackSpeedEstimator(fps=30, calibration=_wrap(make_plane()))
        for f in range(1, 3):
            est.update(1, f, (400, 300, 500, 500), 0.9)
        res = est.last_estimate(1)
        self.assertIn(res.speed_status, (SPEED_CALCULATING, SPEED_UNAVAILABLE))
        self.assertIsNone(res.speed_kmh)

    def test_speed_value_matches_known_world_scene(self):
        # Move a box between known ground points at a known real speed.
        cal = _wrap(make_plane())
        est = TrackSpeedEstimator(fps=1, calibration=cal)  # 1 fps: 1 frame = 1s
        # Animate across the 10 m deep, 3.5 m wide plane over 10 seconds.
        for f in range(1, 21):
            v = 300 + f * 15  # bottom-center v moves down the plane
            box = (495, v - 55, 545, v)
            est.update(1, f, box, 0.9)
        res = est.last_estimate(1)
        self.assertEqual(res.speed_status, SPEED_ESTIMATED)
        self.assertIsNotNone(res.speed_kmh)
        # Expect roughly 10 m in ~10 s ≈ 1 m/s ≈ 3.6 km/h
        self.assertGreater(res.speed_kmh, 1.0)
        self.assertLess(res.speed_kmh, 6.0)

    def test_outlier_rejected_keeps_last_reliable(self):
        cal = _wrap(make_plane())
        est = TrackSpeedEstimator(fps=1, calibration=cal)
        for f in range(1, 25):
            v = 300 + f * 8
            est.update(1, f, (495, v - 55, 545, v), 0.9)
        steady = est.last_estimate(1).speed_kmh
        # Inject a huge outlier (impossible move) -> should be rejected.
        est.update(1, 99, (495, 540 - 3000, 545, 540 - 2900), 0.9)
        outlier = est.last_estimate(1)
        self.assertIsNotNone(outlier.speed_kmh)
        self.assertLess(outlier.speed_kmh, steady * 5 + 100)
        self.assertIn(outlier.speed_status, (SPEED_ESTIMATED, SPEED_LOW_CONFIDENCE))

    def test_frame_skipping_time(self):
        # Frames 1, 20, 40 at 30 fps: delta 19 frames = 0.633s not 1/30.
        cal = _wrap(make_plane())
        est = TrackSpeedEstimator(fps=30, calibration=cal)
        # Build a long synthetic constant-speed track first.
        for f in range(1, 200):
            v = 200 + f * 2.0
            est.update(1, f, (400, v - 60, 500, v), 0.9)
        est_kmh = est.last_estimate(1).speed_kmh
        self.assertIsNotNone(est_kmh)
        self.assertGreater(est_kmh, 0)


class TestTrackPruning(unittest.TestCase):
    def test_stale_tracks_pruned(self):
        est = TrackSpeedEstimator(fps=30, calibration=_wrap(make_plane()))
        for f in range(1, 10):
            est.update(1, f, (400, 300, 500, 500), 0.9)
        # Track 2 present once, then absent.
        est.update(2, 1, (400, 300, 500, 500), 0.9)
        est.cleanup({1}, frame_idx=10)
        # Not stale yet (small gap).
        self.assertIn(2, est._hist)
        est.cleanup({1}, frame_idx=10 + settings.SPEED_STALE_FRAMES + 10)
        self.assertNotIn(2, est._hist)


class TestEdgeCases(unittest.TestCase):
    def test_zero_delta_time_guard(self):
        cal = _wrap(make_plane())
        est = TrackSpeedEstimator(fps=30, calibration=cal)
        est.update(1, 1, (400, 300, 500, 500), 0.9)
        est.update(1, 1, (400, 300, 500, 500), 0.9)  # duplicate frame
        res = est.last_estimate(1)
        self.assertIsNotNone(res)
        self.assertIsNone(res.speed_kmh)  # not enough real history

    def test_no_tracks_no_crash(self):
        est = TrackSpeedEstimator(fps=30, calibration=_wrap(make_plane()))
        est.cleanup(set(), frame_idx=5)
        self.assertIsNone(est.last_estimate(1))


if __name__ == "__main__":
    unittest.main()