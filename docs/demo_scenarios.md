# Demo Scenarios

## Scenario 1: Motorcycle Lane Cut-In

**Video**: `data/videos/motorcycle_lane_cut_in.mp4`

**Description**: A motorcycle approaches from the right and cuts into the ego vehicle's lane.

**Expected Behavior**:
- Detection identifies motorcycle
- Tracking assigns stable ID
- Motion analysis shows approaching state
- Direction: RIGHT
- TTC decreases rapidly
- Risk level escalates to HIGH/CRITICAL
- Alert: "HIGH RISK: Motorcycle approaching from RIGHT"
- Recommended action: "BRAKE NOW"

**Driver Response Options**:
- No action: Alert remains active
- Brake applied: Alert suppressed

---

## Scenario 2: Pedestrian Crossing

**Video**: `data/videos/pedestrian_crossing.mp4`

**Description**: A pedestrian crosses the road at an unmarked location in front of the ego vehicle.

**Expected Behavior**:
- Detection identifies person
- Tracking follows pedestrian trajectory
- Motion analysis shows lateral movement
- Direction: AHEAD
- Risk level increases as pedestrian enters path
- Alert: "CRITICAL RISK: Person approaching from AHEAD"

---

## Scenario 3: Vehicle Merge

**Video**: `data/videos/vehicle_merge.mp4`

**Description**: A car merges aggressively from an on-ramp, cutting in front of the ego vehicle.

**Expected Behavior**:
- Detection identifies car
- Tracking maintains identity during merge
- Motion analysis shows closing speed
- Direction: AHEAD or LEFT
- TTC calculation triggers warning
- Alert with appropriate severity level

---

## Scenario 4: Mixed Traffic Weaving

**Video**: `data/videos/mixed_traffic.mp4`

**Description**: Multiple road users (cars, motorcycles, bicycles) moving in close proximity in typical Indian traffic conditions.

**Expected Behavior**:
- Multiple simultaneous detections and tracks
- Each tracked object analyzed independently
- Threat ranker prioritizes the most dangerous
- Primary threat identified and alerted
- Other threats ranked in severity order

---

## Running Scenarios

### Option 1: Upload custom video
1. Open the web dashboard (<http://localhost:5173>)
2. Use the sidebar to upload a traffic video
3. The system processes it automatically

### Option 2: Select predefined scenario
1. Open the web dashboard (<http://localhost:5173>)
2. Switch to "Random" or "Auto" mode and pick a dataset video
3. System loads and processes the corresponding video

### Option 3: CLI processing
```python
from simulation.traffic_simulator import TrafficSimulator

simulator = TrafficSimulator("path/to/video.mp4")
# Process frames through the pipeline
```
