"""Unit tests for the directional reasoning module."""

import unittest


class TestDirection(unittest.TestCase):
    """Tests for directional reasoning module."""

    def test_direction_imports(self):
        from src.direction.directional_reasoning import DirectionalReasoner, Direction
        self.assertTrue(hasattr(DirectionalReasoner, "determine_direction"))
        self.assertTrue(hasattr(Direction, "LEFT"))

    def test_direction_ahead(self):
        from src.direction.directional_reasoning import DirectionalReasoner, Direction
        reasoner = DirectionalReasoner()
        direction = reasoner.determine_direction(
            ego_center=(640, 360),
            threat_center=(640, 200),
        )
        self.assertEqual(direction, Direction.AHEAD)

    def test_direction_left(self):
        from src.direction.directional_reasoning import DirectionalReasoner, Direction
        reasoner = DirectionalReasoner()
        direction = reasoner.determine_direction(
            ego_center=(640, 360),
            threat_center=(200, 200),
        )
        self.assertEqual(direction, Direction.LEFT)

    def test_direction_right(self):
        from src.direction.directional_reasoning import DirectionalReasoner, Direction
        reasoner = DirectionalReasoner()
        direction = reasoner.determine_direction(
            ego_center=(640, 360),
            threat_center=(1000, 200),
        )
        self.assertEqual(direction, Direction.RIGHT)

    def test_direction_label(self):
        from src.direction.directional_reasoning import DirectionalReasoner, Direction
        reasoner = DirectionalReasoner()
        self.assertEqual(reasoner.get_direction_label(Direction.LEFT), "LEFT")
        self.assertEqual(reasoner.get_direction_label(Direction.AHEAD), "AHEAD")
        self.assertEqual(reasoner.get_direction_label(Direction.RIGHT), "RIGHT")


class TestInactionGate(unittest.TestCase):
    """Tests for inaction gate logic."""

    def test_inaction_gate_imports(self):
        from src.driver_response.inaction_gate import InactionGate
        self.assertTrue(hasattr(InactionGate, "evaluate"))

    def test_gate_should_alert_when_no_response(self):
        from src.driver_response.inaction_gate import InactionGate
        from src.driver_response.driver_simulator import DriverSimulator
        gate = InactionGate()
        sim = DriverSimulator()
        result = gate.evaluate("HIGH", sim.get_state(), current_time=5.0)
        self.assertTrue(result.should_alert)

    def test_gate_suppresses_when_responding(self):
        from src.driver_response.inaction_gate import InactionGate
        from src.driver_response.driver_simulator import DriverSimulator, DriverAction
        gate = InactionGate()
        sim = DriverSimulator()
        sim.set_action(DriverAction.BRAKE_APPLIED)
        result = gate.evaluate("HIGH", sim.get_state(), current_time=5.0)
        self.assertTrue(result.alert_suppressed)


if __name__ == "__main__":
    unittest.main()
