# Methodology

## Problem Statement

Indian roads feature highly heterogeneous mixed traffic including cars, motorcycles, buses, trucks, pedestrians, and bicycles. Existing collision avoidance systems are designed for structured Western traffic and fail in Indian conditions.

## Proposed Approach

### 1. Multi-Modal Sensing via Dashcam Video
- Uses a single forward-facing camera (dashcam) as the primary sensor
- Processes recorded Indian mixed-traffic videos as simulated input
- Detects and classifies diverse road user types

### 2. Temporal Tracking with ByteTrack
- Assigns stable IDs to detected objects across frames
- Maintains continuous identity even with partial occlusions
- Builds position history for trajectory analysis

### 3. Motion State Estimation
- Computes instantaneous velocity and heading from position history
- Classifies objects as approaching or receding
- Smooths noisy measurements using moving average filters

### 4. Multi-Horizon Trajectory Prediction
- Predicts future positions at 0.5s, 1s, and 2s horizons
- Uses constant-velocity linear extrapolation
- Assigns confidence scores based on trajectory quality

### 5. Collision Conflict Detection
- Analyzes trajectory intersections between ego and other road users
- Identifies points of potential path conflict
- Validates temporal proximity of arrivals

### 6. Time-to-Collision Estimation
- Calculates TTC using velocity-based projection
- Accounts for closing speed and relative position
- Provides graded TTC levels (CRITICAL/HIGH/MEDIUM/LOW)

### 7. Multi-Factor Risk Scoring
- Combines TTC, distance, closing speed, path intersection, and prediction confidence
- Weighted composite scoring for balanced risk assessment
- Produces 0.0-1.0 normalized risk scores

### 8. Directional Reasoning
- Classifies threat direction as LEFT, AHEAD, or RIGHT
- Uses angular offset from ego vehicle heading
- Enables spatially meaningful alerts

### 9. Inaction Gate Logic
- Monitors driver response state
- Suppresses alerts when driver is already responding
- Escalates alerts when driver shows no response to high risk

### 10. Smart Alert Generation
- Produces human-readable directional alerts
- Combines risk level, direction, and recommended action
- Prevents alert fatigue through intelligent gating

## Key Innovation: Inaction Gate

The inaction gate represents a novel approach to alert management:

```
IF (Risk Level >= HIGH) AND (Driver NOT Responding):
    -> Generate Alert
    -> Escalate Warning

IF (Risk Level >= HIGH) AND (Driver IS Responding):
    -> Suppress Alert
    -> Reduce Warning Level

IF (Risk Level < HIGH):
    -> Monitor Only
```

This prevents redundant alerts and respects driver autonomy while ensuring critical warnings are delivered when needed.

## Prototype Scope

This software-only simulation prototype demonstrates the complete processing pipeline using recorded traffic videos. Physical hardware integration (CAN bus, real sensors, actuators) is reserved for future development.
