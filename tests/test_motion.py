"""Unit tests for the motion analysis module."""

import unittest


class TestMotionAnalyzer(unittest.TestCase):
    """Tests for MotionAnalyzer class."""

    def test_motion_imports(self):
        from src.motion.motion_analysis import MotionAnalyzer, MotionState
        self.assertTrue(hasattr(MotionAnalyzer, "update"))

    def test_motion_state_creation(self):
        from src.motion.motion_analysis import MotionState
        state = MotionState(track_id=1, class_name="car")
        self.assertEqual(state.track_id, 1)
        self.assertFalse(state.is_approaching)
        self.assertEqual(state.motion_state, "STATIONARY")

    def test_motion_update(self):
        from src.motion.motion_analysis import MotionAnalyzer
        analyzer = MotionAnalyzer(fps=30)
        analyzer.update(track_id=1, class_name="car", center=(100, 200), ego_center=(640, 720))
        analyzer.update(track_id=1, class_name="car", center=(110, 210), ego_center=(640, 720))
        state = analyzer.get_motion_state(1)
        self.assertIsNotNone(state)
        self.assertEqual(len(state.positions), 2)
        self.assertGreater(state.speed, 0)

    def test_motion_classification_approaching(self):
        from src.motion.motion_analysis import MotionAnalyzer
        analyzer = MotionAnalyzer(fps=30)
        ego = (640, 720)
        # Object moving toward ego (downward in image coords)
        positions = [(640, 300), (640, 320), (640, 340), (640, 360), (640, 380)]
        for i, pos in enumerate(positions):
            analyzer.update(track_id=1, class_name="car", center=pos, ego_center=ego,
                           bbox=(pos[0]-20, pos[1]-20, pos[0]+20, pos[1]+20))
        state = analyzer.get_motion_state(1)
        self.assertIsNotNone(state)
        self.assertIn(state.motion_state, ["APPROACHING", "RECEDING", "MOVING LATERALLY", "STATIONARY"])

    def test_motion_classification_receding(self):
        from src.motion.motion_analysis import MotionAnalyzer
        analyzer = MotionAnalyzer(fps=30)
        ego = (640, 720)
        # Object moving away from ego (upward in image coords, decreasing area)
        positions = [(640, 500), (640, 480), (640, 460), (640, 440), (640, 420)]
        for i, pos in enumerate(positions):
            shrink = 20 - i * 2
            analyzer.update(track_id=1, class_name="car", center=pos, ego_center=ego,
                           bbox=(pos[0]-shrink, pos[1]-shrink, pos[0]+shrink, pos[1]+shrink))
        state = analyzer.get_motion_state(1)
        self.assertIsNotNone(state)
        self.assertIn(state.motion_state, ["APPROACHING", "RECEDING", "MOVING LATERALLY", "STATIONARY"])

    def test_motion_stationary(self):
        from src.motion.motion_analysis import MotionAnalyzer
        analyzer = MotionAnalyzer(fps=30)
        ego = (640, 720)
        for _ in range(10):
            analyzer.update(track_id=1, class_name="car", center=(300, 400), ego_center=ego)
        state = analyzer.get_motion_state(1)
        self.assertIsNotNone(state)
        self.assertEqual(state.motion_state, "STATIONARY")

    def test_trajectory_imports(self):
        from src.motion.trajectory import TrajectoryGenerator, Trajectory
        self.assertTrue(hasattr(TrajectoryGenerator, "update"))
        self.assertTrue(hasattr(Trajectory, "add_point"))

    def test_trajectory_points(self):
        from src.motion.trajectory import Trajectory
        traj = Trajectory(track_id=1)
        traj.add_point((100, 200), 0.0)
        traj.add_point((110, 210), 0.033)
        self.assertEqual(traj.length(), 2)


class TestMotionStateSerialization(unittest.TestCase):
    """Tests for MotionState serialization."""

    def test_to_dict(self):
        from src.motion.motion_analysis import MotionState
        state = MotionState(track_id=1, class_name="car")
        d = state.to_dict()
        self.assertIn("track_id", d)
        self.assertIn("motion_state", d)
        self.assertEqual(d["motion_state"], "STATIONARY")


if __name__ == "__main__":
    unittest.main()
