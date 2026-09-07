"""Unit tests for the risk assessment module."""

import unittest


class TestRisk(unittest.TestCase):
    """Tests for severity calculator, threat ranker, and risk engine."""

    def test_risk_imports(self):
        from src.risk.severity_calculator import SeverityCalculator
        from src.risk.threat_ranker import ThreatRanker, RankedThreat
        from src.risk.risk_engine import RiskEngine, RiskResult, PrimaryThreat
        self.assertTrue(hasattr(SeverityCalculator, "calculate"))
        self.assertTrue(hasattr(ThreatRanker, "rank"))
        self.assertTrue(hasattr(RiskEngine, "analyze"))

    def test_severity_range(self):
        from src.risk.severity_calculator import SeverityCalculator
        from src.collision.collision_engine import CollisionAssessment
        calc = SeverityCalculator()
        assessment = CollisionAssessment(
            track_id=1, class_name="car",
            conflict_status="HIGH CONFLICT",
            estimated_ttc=1.5, estimated_pet=None,
            estimated_drac_risk="HIGH", estimated_act="URGENT",
            proximity_to_ego=10.0, bbox_growth_rate=0.1,
            is_in_ego_zone=True,
        )
        score = calc.calculate(assessment)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_thresholds_risk_levels(self):
        from config.thresholds import thresholds
        self.assertEqual(thresholds.get_risk_level(90), "CRITICAL")
        self.assertEqual(thresholds.get_risk_level(70), "HIGH")
        self.assertEqual(thresholds.get_risk_level(50), "MEDIUM")
        self.assertEqual(thresholds.get_risk_level(30), "LOW")

    def test_risk_engine_analyze(self):
        from src.risk.risk_engine import RiskEngine
        from src.motion.motion_analysis import MotionState
        from src.collision.collision_engine import CollisionAssessment

        engine = RiskEngine()
        state = MotionState(track_id=1, class_name="car")
        state.motion_state = "APPROACHING"

        assessment = CollisionAssessment(
            track_id=1,
            class_name="car",
            conflict_status="POTENTIAL CONFLICT",
            estimated_ttc=2.5,
            estimated_pet=None,
            estimated_drac_risk="HIGH",
            estimated_act="URGENT",
            proximity_to_ego=100.0,
            bbox_growth_rate=0.05,
            is_in_ego_zone=True,
        )

        results = engine.analyze(
            motion_states={1: state},
            collision_assessments={1: assessment},
            directions={1: "AHEAD"},
            trajectory_status={1: "CONVERGING"},
        )

        self.assertIn(1, results)
        rr = results[1]
        self.assertGreater(rr.risk_score, 0)
        self.assertLessEqual(rr.risk_score, 100)
        self.assertIn(rr.risk_level, ["SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL"])

    def test_primary_threat_identification(self):
        from src.risk.risk_engine import RiskEngine
        from src.motion.motion_analysis import MotionState
        from src.collision.collision_engine import CollisionAssessment

        engine = RiskEngine()

        state1 = MotionState(track_id=1, class_name="car")
        state1.motion_state = "APPROACHING"
        assessment1 = CollisionAssessment(
            track_id=1, class_name="car", conflict_status="HIGH CONFLICT",
            estimated_ttc=1.5, estimated_pet=None, estimated_drac_risk="CRITICAL",
            estimated_act="IMMEDIATE", proximity_to_ego=50.0,
            bbox_growth_rate=0.1, is_in_ego_zone=True,
        )

        state2 = MotionState(track_id=2, class_name="person")
        state2.motion_state = "RECEDING"
        assessment2 = CollisionAssessment(
            track_id=2, class_name="person", conflict_status="NO SIGNIFICANT CONFLICT",
            estimated_ttc=None, estimated_pet=None, estimated_drac_risk="LOW",
            estimated_act="N/A", proximity_to_ego=400.0,
            bbox_growth_rate=-0.02, is_in_ego_zone=False,
        )

        engine.analyze(
            motion_states={1: state1, 2: state2},
            collision_assessments={1: assessment1, 2: assessment2},
            directions={1: "AHEAD", 2: "LEFT"},
            trajectory_status={1: "CONVERGING", 2: "MOVING AWAY"},
        )

        primary = engine.get_primary_threat()
        self.assertIsNotNone(primary)
        self.assertEqual(primary.tracking_id, 1)
        self.assertEqual(primary.object_type, "CAR")

    def test_risk_score_range(self):
        from src.risk.risk_engine import RiskEngine
        from src.motion.motion_analysis import MotionState

        engine = RiskEngine()
        state = MotionState(track_id=1, class_name="car")
        state.motion_state = "STATIONARY"

        results = engine.analyze(
            motion_states={1: state},
            collision_assessments={},
            directions={1: "AHEAD"},
            trajectory_status={1: "STABLE PATH"},
        )

        self.assertIn(1, results)
        self.assertGreaterEqual(results[1].risk_score, 0)
        self.assertLessEqual(results[1].risk_score, 100)

    def test_risk_summary(self):
        from src.risk.risk_engine import RiskEngine
        engine = RiskEngine()
        summary = engine.get_summary()
        self.assertEqual(summary["total_objects"], 0)
        self.assertEqual(summary["max_risk_score"], 0)

    def test_engine_init(self):
        from src.risk.risk_engine import RiskEngine
        engine = RiskEngine()
        self.assertIsNotNone(engine.risk_results)
        self.assertIsNone(engine.primary_threat)

    def test_risk_result_creation(self):
        from src.risk.risk_engine import RiskResult
        rr = RiskResult(
            track_id=1, class_name="car", risk_score=75.0, risk_level="HIGH",
            direction="AHEAD", motion_state="APPROACHING", trajectory_status="CONVERGING",
            conflict_status="HIGH CONFLICT", estimated_ttc=1.5, estimated_pet=None,
            estimated_drac_risk="HIGH", estimated_act="URGENT", risk_factors={}
        )
        self.assertEqual(rr.risk_score, 75.0)
        d = rr.to_dict()
        self.assertIn("risk_score", d)


if __name__ == "__main__":
    unittest.main()
