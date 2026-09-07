"""Unit tests for the collision detection module."""

import unittest


class TestCollision(unittest.TestCase):
    """Tests for collision detection and TTC estimation."""

    def test_collision_imports(self):
        from src.collision.collision_engine import CollisionEngine, CollisionAssessment
        self.assertTrue(hasattr(CollisionEngine, "assess_all"))

    def test_collision_assessment_creation(self):
        from src.collision.collision_engine import CollisionAssessment
        assessment = CollisionAssessment(
            track_id=1,
            class_name="car",
            conflict_status="NO SIGNIFICANT CONFLICT",
            estimated_ttc=None,
            estimated_pet=None,
            estimated_drac_risk="LOW",
            estimated_act="N/A",
            proximity_to_ego=500.0,
            bbox_growth_rate=0.0,
            is_in_ego_zone=False,
        )
        self.assertEqual(assessment.track_id, 1)
        self.assertIsNone(assessment.estimated_ttc)
        self.assertEqual(assessment.estimated_drac_risk, "LOW")

    def test_collision_engine_assess(self):
        from src.collision.collision_engine import CollisionEngine
        from src.motion.motion_analysis import MotionState
        engine = CollisionEngine(frame_width=1280, frame_height=720)
        state = MotionState(track_id=1, class_name="car")
        state.positions = [(640, 400), (640, 420), (640, 440)]
        state.timestamps = [0.0, 0.033, 0.066]
        state.velocity = (0.0, 606.0)
        state.speed = 606.0
        state.is_approaching = True
        state.motion_state = "APPROACHING"
        state.bbox_history.append((620, 380, 660, 420))
        state.bbox_history.append((620, 400, 660, 440))
        state.bbox_history.append((620, 420, 660, 460))
        state.area_history.append(1600.0)
        state.area_history.append(1600.0)
        state.area_history.append(1600.0)

        assessments = engine.assess_all({1: state}, {1: "STABLE PATH"})
        self.assertIn(1, assessments)
        self.assertIsNotNone(assessments[1].conflict_status)

    def test_engine_init(self):
        from src.collision.collision_engine import CollisionEngine
        engine = CollisionEngine(frame_width=1280, frame_height=720)
        self.assertEqual(engine.frame_width, 1280)
        self.assertEqual(engine.frame_height, 720)

    def test_engine_conflict_constants(self):
        from src.collision.collision_engine import (
            CONFLICT_NO_SIGNIFICANT, CONFLICT_MONITOR,
            CONFLICT_POTENTIAL, CONFLICT_HIGH
        )
        self.assertEqual(CONFLICT_NO_SIGNIFICANT, "NO SIGNIFICANT CONFLICT")
        self.assertEqual(CONFLICT_HIGH, "HIGH CONFLICT")


if __name__ == "__main__":
    unittest.main()
