"""Unit tests for the prediction module."""

import unittest


class TestPrediction(unittest.TestCase):
    """Tests for FuturePositionPredictor and MultiHorizonPredictor."""

    def test_prediction_imports(self):
        from src.prediction.future_position import FuturePositionPredictor, PredictionResult
        from src.prediction.multi_horizon import MultiHorizonPredictor
        self.assertTrue(hasattr(FuturePositionPredictor, "predict"))

    def test_prediction_horizons(self):
        from config.settings import settings
        self.assertEqual(settings.TRAJECTORY_FUTURE_HORIZONS, [0.5, 1.0, 2.0])

    def test_prediction_result_creation(self):
        from src.prediction.future_position import PredictionResult
        result = PredictionResult(track_id=1, horizon=1.0)
        self.assertEqual(result.horizon, 1.0)
        self.assertIsNone(result.predicted_position)
        self.assertEqual(result.trajectory_status, "STABLE PATH")

    def test_trajectory_status_classification(self):
        from src.prediction.future_position import FuturePositionPredictor
        from src.motion.trajectory import Trajectory
        import numpy as np

        predictor = FuturePositionPredictor()
        traj = Trajectory(track_id=1)
        # Object moving away (upward in image)
        for t in np.arange(0, 1.0, 0.033):
            traj.add_point((640.0, 500.0 - t * 100), float(t))

        results = predictor.predict(traj)
        self.assertTrue(len(results) > 0)
        self.assertIn(results[0].trajectory_status,
                      ["MOVING AWAY", "STABLE PATH", "CONVERGING", "POTENTIAL CROSSING"])

    def test_prediction_with_trajectory(self):
        from config.settings import settings
        from src.prediction.future_position import FuturePositionPredictor
        from src.motion.trajectory import Trajectory

        predictor = FuturePositionPredictor()
        traj = Trajectory(track_id=1)
        traj.add_point((100.0, 200.0), 0.0)
        traj.add_point((110.0, 220.0), 0.033)
        traj.add_point((120.0, 240.0), 0.066)
        traj.add_point((130.0, 260.0), 0.1)

        results = predictor.predict(traj)
        self.assertEqual(len(results), len(settings.TRAJECTORY_FUTURE_HORIZONS))
        for r in results:
            self.assertIsNotNone(r.predicted_position)
            self.assertGreater(r.confidence, 0)


class TestPredictionSettings(unittest.TestCase):
    """Tests for prediction-related settings."""

    def test_confidence_decay(self):
        from config.settings import settings
        self.assertGreater(settings.CONFIDENCE_DECAY, 0)

    def test_ego_path_ratios(self):
        from config.settings import settings
        self.assertLess(settings.EGO_PATH_LEFT_RATIO, settings.EGO_PATH_RIGHT_RATIO)


if __name__ == "__main__":
    unittest.main()
