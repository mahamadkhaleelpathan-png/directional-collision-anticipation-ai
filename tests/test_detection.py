"""Unit tests for the object detection module."""

import unittest
import numpy as np


class TestObjectDetector(unittest.TestCase):
    """Tests for ObjectDetector class."""

    def test_detection_imports(self):
        from src.detection.object_detector import ObjectDetector
        self.assertTrue(hasattr(ObjectDetector, "detect"))

    def test_detection_classes_list(self):
        from config.settings import settings
        expected_classes = {"car", "motorcycle", "bus", "truck", "person", "bicycle"}
        self.assertTrue(expected_classes.issubset(set(settings.DETECTION_CLASSES)))

    def test_detection_confidence_range(self):
        from config.settings import settings
        self.assertGreater(settings.DETECTION_CONFIDENCE, 0.0)
        self.assertLessEqual(settings.DETECTION_CONFIDENCE, 1.0)

    def test_settings_directories_exist(self):
        from config.settings import _ensure_dirs, settings
        _ensure_dirs()
        self.assertTrue(settings.DATA_DIR.exists())
        self.assertTrue(settings.OUTPUT_DIR.exists())
        self.assertTrue(settings.UPLOAD_DIR.exists())


class TestSettingsPart2(unittest.TestCase):
    """Tests for Part 2 settings."""

    def test_motion_settings(self):
        from config.settings import settings
        self.assertGreater(settings.MOTION_HISTORY_LENGTH, 0)
        self.assertGreater(settings.STATIONARY_SPEED_THRESHOLD, 0)

    def test_ego_path_settings(self):
        from config.settings import settings
        self.assertLess(settings.EGO_PATH_LEFT_RATIO, settings.EGO_PATH_RIGHT_RATIO)

    def test_risk_thresholds(self):
        from config.settings import settings
        self.assertLess(settings.RISK_SCORE_SAFE_MAX, settings.RISK_SCORE_LOW_MAX)
        self.assertLess(settings.RISK_SCORE_LOW_MAX, settings.RISK_SCORE_MEDIUM_MAX)
        self.assertLess(settings.RISK_SCORE_MEDIUM_MAX, settings.RISK_SCORE_HIGH_MAX)

    def test_risk_weights_sum(self):
        from config.settings import settings
        total = (
            settings.RISK_WEIGHT_MOTION +
            settings.RISK_WEIGHT_DIRECTION +
            settings.RISK_WEIGHT_PROXIMITY +
            settings.RISK_WEIGHT_CONFLICT +
            settings.RISK_WEIGHT_TTC +
            settings.RISK_WEIGHT_PET +
            settings.RISK_WEIGHT_TRAJECTORY
        )
        self.assertAlmostEqual(total, 1.0, places=1)

    def test_ttc_thresholds(self):
        from config.settings import settings
        self.assertLess(settings.TTC_CRITICAL_THRESHOLD, settings.TTC_HIGH_THRESHOLD)
        self.assertLess(settings.TTC_HIGH_THRESHOLD, settings.TTC_MEDIUM_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
