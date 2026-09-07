# AI-Driven Directional Collision Anticipation System

> An intelligent driver assistance system that predicts and alerts drivers about potential collisions from multiple directions in real-time Indian mixed-traffic conditions.

---

## Problem Overview

Indian roads are among the most dangerous in the world, characterized by highly heterogeneous mixed traffic including cars, motorcycles, buses, trucks, pedestrians, and bicycles moving in unpredictable patterns. Existing collision avoidance systems are designed for structured Western traffic and fail to handle the complexity of Indian road conditions.

**Key Challenges:**
- Mixed traffic with diverse road user types
- Unpredictable lateral movements and lane violations
- High density of vulnerable road users (motorcycles, pedestrians)
- Lack of structured lane discipline
- Need for direction-aware collision anticipation

---

## Proposed Solution

The **AI-Driven Directional Collision Anticipation System** is a software-only simulation prototype that processes dashcam video to detect, track, predict, and warn about potential collisions from multiple directions.

The system implements a complete pipeline:

```
Traffic Video → Frame Processing → Object Detection → Multi-Object Tracking
→ Motion Analysis → Trajectory Generation → Future Prediction
→ Conflict Detection → TTC Calculation → Risk Scoring
→ Threat Ranking → Directional Reasoning → Driver Response Simulation
→ Inaction Gating → Smart Collision Alert → Dashboard
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Object Detection** | YOLO v11-based detection (yolo11n.pt) of cars, motorcycles, buses, trucks, pedestrians, bicycles |
| **Stable Tracking** | ByteTrack-based identity assignment and tracking across frames |
| **Motion Analysis** | Velocity, heading, and approach/recede classification |
| **Trajectory Prediction** | Multi-horizon future position prediction (0.5s, 1s, 2s) |
| **TTC Estimation** | Time-to-collision calculation using velocity projection |
| **Risk Scoring** | Multi-factor severity calculation (TTC, distance, speed, path intersection) |
| **Threat Ranking** | Priority-based threat identification and primary threat selection |
| **Directional Alerts** | LEFT / AHEAD / RIGHT threat classification |
| **Inaction Gate** | Intelligent alert suppression when driver is responding |
| **Modern Web Dashboard** | React + TypeScript interface with live video, metrics, and controls |

---

## System Architecture

```
+--------------------+     +-------------------+     +------------------+
|   Video Input      | --> |   Detection       | --> |   Tracking       |
|   (Dashcam)        |     |   (YOLO v11)      |     |   (ByteTrack)    |
+--------------------+     +-------------------+     +------------------+
                                                            |
                                                            v
+--------------------+     +-------------------+     +------------------+
|   React Web UI     | <-- |   FastAPI         | <-- |   Motion         |
|   (TypeScript /    |     |   Integration     |     |   Analysis       |
|    Vite / Tailwind)|     |   Layer           |     |                  |
+--------------------+     +-------------------+     +------------------+
                                                            |
                                                            v
+--------------------+     +-------------------+     +------------------+
|   Direction        | <-- |   Risk & Threat   | <-- |   Collision      |
|   Reasoning        |     |   Assessment      |     |   Detection      |
+--------------------+     +-------------------+     +------------------+
```

---

## Technology Stack

### Backend (Python AI)
| Technology | Purpose |
|------------|---------|
| **Python** | Core programming language |
| **OpenCV** | Video processing and frame manipulation |
| **Ultralytics YOLO** | Object detection (YOLOv11, yolo11n.pt) |
| **ByteTrack** | Multi-object tracking |
| **NumPy** | Numerical computations |
| **Pandas** | Data handling and manipulation |
| **SciPy** | Scientific computing utilities |
| **FastAPI** | HTTP/WebSocket API exposing the AI pipeline |

### Frontend (Web)
| Technology | Purpose |
|------------|---------|
| **React 18** | UI library |
| **TypeScript** | Type-safe source |
| **Vite** | Dev server / bundler |
| **Tailwind CSS** | Utility-first styling |
| **Lucide React** | Icon set |

---

## Project Structure

```
AI_Collision_Anticipation/
│
├── api/                     # FastAPI integration layer
│   ├── main.py              # HTTP + WebSocket endpoints
│   └── risk_color.py        # Risk-level color helper
│
├── frontend/                # React + TypeScript + Vite + Tailwind
│   ├── src/
│   │   ├── components/      # Header, VideoSection, CurrentThreat, etc.
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   ├── types.ts
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── config/                  # Centralized configuration
│   ├── settings.py          # Application settings
│   ├── thresholds.py        # Tunable collision thresholds
│   └── dataset_config.py
│
├── data/                    # Input data
│   ├── uploads/             # User-uploaded videos
│   ├── positive/            # Positive test videos
│   ├── negative/            # Negative test videos
│   └── indian_traffic/      # Indian traffic videos
│
├── models/                  # YOLO model weights
│
├── src/                     # Core AI processing modules (UNCHANGED)
│   ├── detection/           # Object detection (YOLO)
│   ├── tracking/            # Multi-object tracking (ByteTrack)
│   ├── motion/              # Motion analysis and trajectories
│   ├── prediction/          # Future position prediction
│   ├── collision/           # Conflict detection and TTC
│   ├── risk/                # Severity scoring and threat ranking
│   ├── direction/           # Directional reasoning
│   ├── driver_response/     # Driver simulation and inaction gate
│   ├── alerts/              # Alert generation and warning logic
│   ├── dataset/             # Dataset manager + test runner
│   ├── pipeline/            # Extracted pipeline orchestration
│   │   └── processor.py     # process_video() — no UI dependencies
│   └── utils/               # Utilities (video, geometry, viz, logging)
│
├── output/                  # Generated outputs
│   ├── processed_videos/
│   ├── screenshots/
│   ├── reports/
│   ├── dataset_tests/
│   └── logs/
│
├── tests/                   # Unit test suite
│
└── docs/                    # Documentation
```

---

## Installation

### Prerequisites

- Python 3.9 or higher
- Node.js 18+ and npm
- pip package manager
- Git

### Backend Setup

```bash
git clone <repository-url>
cd AI_Collision_Anticipation

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
# YOLO model file yolo11n.pt is already in the project root
```

### Frontend Setup

```bash
cd frontend
npm install
cd ..
```

---

## How to Run

You need **two processes** — one for the backend API and one for the frontend dev server.

### 1) Start the backend (FastAPI)

```bash
# From the project root
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

The API serves:
- `POST /api/upload` — upload a video (mp4, avi, mov, mkv, webm; validated via OpenCV probe)
- `POST /api/process` — start a processing job
- `GET /api/jobs/{id}` — poll a job (polling fallback when WebSocket is unavailable)
- `WS /ws/jobs/{id}` — live progress stream
- `GET /api/videos/{filename}` — annotated output video (also serves uploads by saved filename)
- `GET /api/source?path=<abs>` — original/source video playback (path must resolve inside `data/`)
- `POST /api/csv_report` — generate analysis CSV
- `GET /api/dataset/summary` — discover dataset
- `POST /api/dataset/random` — random pick
- `POST /api/dataset/test` — run dataset test (returns a job id)

### 2) Start the frontend (Vite dev server)

```bash
cd frontend
npm run dev
```

Open <http://localhost:5173>.

### Run Tests

```bash
pytest tests/ -v
```

### Production Build (frontend)

```bash
cd frontend
npm run build
```

---

## Current Prototype Scope

This is a **software-only simulation prototype** designed for SIH hackathon demonstration.

**Recorded traffic videos are used as simulated dashcam input in the current software prototype.**

| Aspect | Status |
|--------|--------|
| Object Detection | YOLO v11 on recorded video |
| Multi-Object Tracking | ByteTrack simulation |
| Driver Response | Simulated (manual/automatic) |
| Hardware Integration | NOT included |
| Real-time Sensors | NOT included |
| CAN Bus Access | NOT included |
| Actuator Control | NOT included |

---

## Future Hardware Deployment Scope

The system architecture is designed for future hardware deployment:

| Future Feature | Description |
|----------------|-------------|
| **Real Dashcam Input** | Live video from vehicle-mounted camera |
| **CAN Bus Integration** | Real-time vehicle speed and steering data |
| **GPS/IMU Integration** | Vehicle position and orientation |
| **ADAS Actuators** | Automatic braking and steering intervention |
| **V2X Communication** | Vehicle-to-infrastructure data exchange |
| **Edge Computing** | On-board NVIDIA Jetson or similar |
| **Multi-Camera Setup** | 360-degree situational awareness |
| **Night/Rain Vision** | Enhanced perception in adverse conditions |

---

## Demo Scenarios

See [docs/demo_scenarios.md](docs/demo_scenarios.md) for detailed scenario descriptions including:

1. **Motorcycle Lane Cut-In** - Right-side approach
2. **Pedestrian Crossing** - Ahead crossing
3. **Vehicle Merge** - Aggressive merge from on-ramp
4. **Mixed Traffic Weaving** - Multiple simultaneous threats

---

## License

This project is developed for SIH hackathon demonstration purposes.

---

## Acknowledgments

- **Smart India Hackathon** for the problem statement
- **Ultralytics** for YOLO v11
- **ByteTrack** for multi-object tracking
- **FastAPI** for the API framework
- **React + Vite + Tailwind** for the dashboard framework