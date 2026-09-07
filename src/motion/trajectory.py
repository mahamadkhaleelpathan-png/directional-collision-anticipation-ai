"""
Trajectory generation module.

Generates smoothed trajectories from tracked position histories
for use in future position prediction.
"""

from typing import List, Optional, Tuple
import numpy as np
from collections import deque

from config.settings import settings
from config.thresholds import thresholds


class Trajectory:
    """Represents the trajectory of a single tracked object."""

    def __init__(self, track_id: int):
        self.track_id = track_id
        self.points: deque = deque(maxlen=200)
        self.timestamps: deque = deque(maxlen=200)

    def add_point(self, point: Tuple[float, float], timestamp: float):
        """Add a new position observation to the trajectory."""
        self.points.append(point)
        self.timestamps.append(timestamp)

    def get_points(self) -> np.ndarray:
        """Return trajectory as a numpy array of shape (N, 2)."""
        if len(self.points) == 0:
            return np.array([])
        return np.array(list(self.points))

    def get_timestamps(self) -> np.ndarray:
        """Return timestamps as numpy array."""
        if len(self.timestamps) == 0:
            return np.array([])
        return np.array(list(self.timestamps))

    def get_velocity_vector(self) -> Tuple[float, float]:
        """Compute the average velocity vector from the trajectory."""
        pts = self.get_points()
        if len(pts) < 2:
            return (0.0, 0.0)

        diffs = np.diff(pts, axis=0)
        times = self.get_timestamps()
        dt = np.diff(times)

        # Avoid division by zero
        dt[dt == 0] = 1e-6

        velocities = diffs / dt[:, np.newaxis]
        avg_velocity = np.mean(velocities, axis=0)
        return (float(avg_velocity[0]), float(avg_velocity[1]))

    def length(self) -> int:
        """Return number of points in the trajectory."""
        return len(self.points)


class TrajectoryGenerator:
    """
    Generates and manages trajectories for all tracked objects.

    Smooths raw position data and prepares trajectories for
    future position prediction.
    """

    def __init__(self):
        self.trajectories: dict = {}

    def update(self, track_id: int, position: Tuple[float, float], timestamp: float):
        """
        Update the trajectory for a tracked object.

        Args:
            track_id: Unique track identifier.
            position: (x, y) position in pixel coordinates.
            timestamp: Time in seconds.
        """
        if track_id not in self.trajectories:
            self.trajectories[track_id] = Trajectory(track_id)

        self.trajectories[track_id].add_point(position, timestamp)

    def get_trajectory(self, track_id: int) -> Optional[Trajectory]:
        """Get the trajectory for a specific track."""
        return self.trajectories.get(track_id)

    def get_all_trajectories(self) -> dict:
        """Get all active trajectories."""
        return self.trajectories

    def smooth_trajectory(self, trajectory: Trajectory) -> np.ndarray:
        """
        Apply a simple moving average smoothing to the trajectory.

        Args:
            trajectory: Trajectory object to smooth.

        Returns:
            Smoothed trajectory as numpy array of shape (N, 2).
        """
        points = trajectory.get_points()
        if len(points) < thresholds.trajectory_smoothing_window:
            return points

        window = thresholds.trajectory_smoothing_window
        kernel = np.ones(window) / window
        smoothed = np.zeros_like(points, dtype=float)

        for axis in range(2):
            smoothed[:, axis] = np.convolve(points[:, axis], kernel, mode="same")

        return smoothed

    def get_position_at_time(self, trajectory: Trajectory, target_time: float) -> Optional[Tuple[float, float]]:
        """
        Interpolate position at a specific time within the trajectory.

        Args:
            trajectory: Source trajectory.
            target_time: Time to interpolate to.

        Returns:
            Interpolated (x, y) position or None if insufficient data.
        """
        points = trajectory.get_points()
        times = trajectory.get_timestamps()

        if len(points) < 2:
            return None

        if target_time <= times[0]:
            return tuple(points[0])
        if target_time >= times[-1]:
            return tuple(points[-1])

        idx = np.searchsorted(times, target_time)
        if idx == 0:
            return tuple(points[0])

        t0, t1 = times[idx - 1], times[idx]
        p0, p1 = points[idx - 1], points[idx]

        alpha = (target_time - t0) / (t1 - t0) if t1 != t0 else 0.0
        interpolated = p0 + alpha * (p1 - p0)

        return (float(interpolated[0]), float(interpolated[1]))

    def reset(self):
        """Clear all trajectory data."""
        self.trajectories.clear()
