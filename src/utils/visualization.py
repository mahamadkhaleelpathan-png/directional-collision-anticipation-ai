"""
Visualization utilities for rendering overlays on video frames.

Provides functions for drawing bounding boxes, trajectories,
predictions, alerts, and other visual indicators.
"""

from typing import List, Optional, Tuple
import numpy as np
import cv2

from src.alerts.alert_generator import CollisionAlert


# Color constants (BGR format for OpenCV)
COLOR_GREEN = (0, 255, 0)
COLOR_YELLOW = (0, 255, 255)
COLOR_ORANGE = (0, 165, 255)
COLOR_RED = (0, 0, 255)
COLOR_BLUE = (255, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)


def draw_detections(
    frame: np.ndarray,
    detections: list,
    color: Tuple[int, int, int] = COLOR_GREEN,
) -> np.ndarray:
    """Draw bounding boxes and class labels for detected objects."""
    annotated = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        label = f"{det['class_name']} {det.get('confidence', 0):.2f}"
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated, label, (x1, y1 - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1,
        )
    return annotated


def draw_trajectories(
    frame: np.ndarray,
    trajectories: dict,
    color: Tuple[int, int, int] = COLOR_BLUE,
) -> np.ndarray:
    """Draw trajectory lines for tracked objects."""
    annotated = frame.copy()
    for track_id, trajectory in trajectories.items():
        points = trajectory.get_points()
        if len(points) < 2:
            continue
        pts = points.astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(annotated, [pts], False, color, 2)
    return annotated


def draw_predictions(
    frame: np.ndarray,
    current_pos: Tuple[float, float],
    predicted_positions: list,
    color: Tuple[int, int, int] = COLOR_YELLOW,
) -> np.ndarray:
    """Draw predicted future positions as dashed lines."""
    annotated = frame.copy()
    curr = (int(current_pos[0]), int(current_pos[1]))

    for pred in predicted_positions:
        if pred is not None:
            pt = (int(pred[0]), int(pred[1]))
            cv2.line(annotated, curr, pt, color, 1, cv2.LINE_AA)
            cv2.circle(annotated, pt, 4, color, -1)

    return annotated


def draw_alert_overlay(
    frame: np.ndarray,
    alert: Optional[CollisionAlert],
) -> np.ndarray:
    """Draw alert banner at the top of the frame."""
    annotated = frame.copy()
    h, w = frame.shape[:2]

    if alert is None:
        return annotated

    # Alert banner
    color = tuple(int(alert.severity_color.lstrip("#")[i : i + 2], 16) for i in (4, 2, 0))
    cv2.rectangle(annotated, (0, 0), (w, 60), color, -1)
    cv2.putText(
        annotated,
        alert.message,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        COLOR_WHITE,
        2,
    )

    # Action indicator
    if alert.recommended_action:
        cv2.rectangle(annotated, (0, 60), (w, 100), COLOR_BLACK, -1)
        cv2.putText(
            annotated,
            f"ACTION: {alert.recommended_action}",
            (20, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2,
        )

    return annotated


def draw_risk_indicator(
    frame: np.ndarray,
    risk_score: float,
    position: Tuple[int, int] = (20, 700),
) -> np.ndarray:
    """Draw a risk score indicator on the frame."""
    annotated = frame.copy()
    bar_width = 200
    bar_height = 20

    x, y = position
    # Background
    cv2.rectangle(annotated, (x, y), (x + bar_width, y + bar_height), COLOR_BLACK, -1)
    # Fill based on risk
    fill_width = int(bar_width * risk_score)
    color = COLOR_GREEN if risk_score < 0.4 else COLOR_YELLOW if risk_score < 0.7 else COLOR_RED
    cv2.rectangle(annotated, (x, y), (x + fill_width, y + bar_height), color, -1)
    # Label
    cv2.putText(
        annotated,
        f"Risk: {risk_score:.2f}",
        (x, y - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        COLOR_WHITE,
        1,
    )
    return annotated
