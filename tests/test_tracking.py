"""Unit tests for the object tracking module."""

import unittest


class TestObjectTracker(unittest.TestCase):
    """Tests for ObjectTracker class."""

    def test_tracker_imports(self):
        from src.tracking.object_tracker import ObjectTracker, TrackedObject
        self.assertTrue(hasattr(ObjectTracker, "update"))
        self.assertTrue(hasattr(TrackedObject, "to_dict"))

    def test_tracked_object_creation(self):
        from src.tracking.object_tracker import TrackedObject
        obj = TrackedObject(track_id=1, class_name="car", bbox=(10, 20, 50, 60), frame_idx=1)
        self.assertEqual(obj.track_id, 1)
        self.assertEqual(obj.class_name, "car")
        self.assertEqual(obj.center, (30.0, 40.0))

    def test_tracked_object_update(self):
        from src.tracking.object_tracker import TrackedObject
        obj = TrackedObject(track_id=1, class_name="car", bbox=(10, 20, 50, 60), frame_idx=1)
        obj.update(bbox=(20, 30, 60, 70), frame_idx=2)
        self.assertEqual(obj.center, (40.0, 50.0))

    def test_tracked_object_to_dict(self):
        from src.tracking.object_tracker import TrackedObject
        obj = TrackedObject(track_id=5, class_name="motorcycle", bbox=(0, 0, 30, 40), frame_idx=10)
        d = obj.to_dict()
        self.assertEqual(d["track_id"], 5)
        self.assertEqual(d["class_name"], "motorcycle")


if __name__ == "__main__":
    unittest.main()
