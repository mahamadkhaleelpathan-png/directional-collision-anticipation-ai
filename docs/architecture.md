# System Architecture

## Overview

The AI-Driven Directional Collision Anticipation System follows a modular pipeline architecture where each stage processes data and passes it to the next.

## Processing Pipeline

```
Traffic Video Input
        |
        v
+------------------+
|  Video Frame     |  Reads video frames using OpenCV
|  Processing      |  Resizes and preprocesses frames
+------------------+
        |
        v
+------------------+
|  Object          |  YOLO v11 (yolo11n.pt) detects road users:
|  Detection       |  car, motorcycle, bus, truck, person, bicycle
+------------------+
        |
        v
+------------------+
|  Multi-Object    |  ByteTrack assigns stable IDs
|  Tracking        |  Maintains identity across frames
+------------------+
        |
        v
+------------------+
|  Motion          |  Computes position, velocity, heading
|  Analysis        |  Determines approaching/receding state
+------------------+
        |
        v
+------------------+
|  Trajectory      |  Generates smoothed trajectories
|  Generation      |  Stores position history
+------------------+
        |
        v
+------------------+
|  Future Position |  Predicts positions at 0.5s, 1s, 2s
|  Prediction      |  Constant velocity extrapolation
+------------------+
        |
        v
+------------------+
|  Conflict        |  Detects path intersections
|  Detection       |  Identifies potential collisions
+------------------+
        |
        v
+------------------+
|  TTC             |  Estimates time-to-collision
|  Calculation     |  Based on closing speed
+------------------+
        |
        v
+------------------+
|  Risk &          |  Multi-factor severity scoring
|  Severity        |  Threat ranking and prioritization
+------------------+
        |
        v
+------------------+
|  Directional     |  Determines LEFT / AHEAD / RIGHT
|  Reasoning       |  Spatial threat classification
+------------------+
        |
        v
+------------------+
|  Driver Response |  Simulates brake / steer / no action
|  Simulation      |  For software-only prototype
+------------------+
        |
        v
+------------------+
|  Inaction Gate   |  HIGH RISK + NO RESPONSE = ALERT
|  Logic           |  HIGH RISK + RESPONDING = SUPPRESS
+------------------+
        |
        v
+------------------+
|  Smart Alert     |  Generates formatted warnings
|  Generation      |  Direction + action + severity
+------------------+
        |
        v
+------------------+
|  React Web UI    |  Interactive dashboard
|  (Vite + TS +    |  Video + metrics + alerts
|   Tailwind)      |
+------------------+
```

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `config/` | Centralized settings, thresholds, environment variables |
| `src/detection/` | YOLO-based object detection |
| `src/tracking/` | ByteTrack multi-object tracking |
| `src/motion/` | Kinematic state estimation and trajectory generation |
| `src/prediction/` | Multi-horizon future position prediction |
| `src/collision/` | Conflict detection and TTC calculation |
| `src/risk/` | Severity scoring and threat ranking |
| `src/direction/` | Directional reasoning (LEFT/AHEAD/RIGHT) |
| `src/driver_response/` | Driver simulation and inaction gating |
| `src/alerts/` | Alert generation and warning logic |
| `src/utils/` | Video, geometry, visualization, logging utilities |
| `simulation/` | Ego vehicle model and scenario management |
| `frontend/` | React + TypeScript + Vite + Tailwind web UI |
| `api/` | FastAPI integration layer (HTTP + WebSocket) |
| `tests/` | Unit test suite |
| `docs/` | Project documentation |

## Data Flow

1. **Input**: Recorded Indian mixed-traffic video (simulated dashcam)
2. **Processing**: Frame-by-frame analysis through the pipeline
3. **Output**: Annotated video frames, alerts, risk assessments
4. **Interface**: Real-time web dashboard served by the FastAPI backend
