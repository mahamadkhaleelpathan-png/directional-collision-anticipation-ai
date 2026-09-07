# Vehicle Speed Estimation (Part 3)

An **additive, calibration-gated** real-world speed estimator for the AI
collision anticipation system. It consumes the **existing ByteTrack**
contained-boxes and introduces **no new detector, no new tracker, and no
re-processing of the video**. The collision, TTC, risk and direction logic
are untouched; speed is exposed for visualization only and is offered to
the HUD in real units.

## The core principle: pixel movement is NOT km/h

A camera looks at a 3D scene through a perspective projection. A vehicle
moving 20 pixels near the camera can be a completely different real
distance than 20 pixels far away (STEP 27). Converting raw pixel motion
into km/h requires either

* a **road-plane homography** (image pixels → ground meters), derived from
  calibration, or
* a known real-world reference (lane width, road markings, measured
  distance, or GPS ground truth).

This module refuses to produce `km/h` until a valid calibration exists. If
the scene is uncalibrated the estimator reports `NOT_CALIBRATED` and the
HUD shows `N/A` / `SPEED N/A — CALIBRATION REQUIRED`. **No fake values are
ever generated.**

## Four different measurements (never confused)

| Measurement | Source |
|---|---|
| SOURCE FPS | `video_fps` = OpenCV metadata of the input video |
| PROCESSING FPS | `processing_fps` = `frames_processed / elapsed_wall_time` |
| PLAYBACK SPEED | `speed` = browser `video.playbackRate` (UI only) |
| VEHICLE SPEED (km/h) | the new calibrated estimator below |

## Architecture

```
VIDEO → YOLO → ByteTrack → TRACK POSITION → SPEED ESTIMATION → MOTION/PREDICT → COLLISION → RISK → ALERT
                                                ^
                                          (new additive module)
```

New modules:

* `src/calibration/ground.py` — `GroundPlane`, `HomographyGroundPlane`
  (pinhole/homography ground mapping), `bottom_center(bbox)`.
* `src/calibration/calibration.py` — load / save / clear / validate the
  calibration file `config/speed_calibration.json`.
* `src/calibration/ego_motion.py` — camera-motion detection and an ego
  scene-flow estimate (only used for an honest warning, never for risk).
* `src/motion/speed_estimator.py` — per-track windowed, smoothed,
  outlier-rejected speed estimate + ESTIMATION CONFIDENCE.

## Calibration method (homography)

The UI lets the user click the four road-plane corners **A (top-left),
B (top-right), C (bottom-right), D (bottom-left)** on a real frame, then
enter the **known road width** (A→B, metres) and **distance ahead** (A→D,
metres). The backend builds `image_points = [A,B,C,D]` and
`world_points_meters = [(0,0), (width,0), (width,depth), (0,depth)]` and
computes the exact projective transform with `cv2.getPerspectiveTransform`.

Validation (STEP 26) rejects: fewer than 4 points, duplicated points,
collinear/degenerate polygons, non-positive world dimensions, and any
homography that is not numerically invertible / finite. Invalid input is
reported as `SPEED CALIBRATION ERROR` and is never persisted.

The ground-to-speed formula:

```
ground position = H @ bottom_center(bbox)     # (X, Z) metres
distance_m      = |ground_now - ground_anchor|
delta_time      = (frame_now - frame_anchor) / source_fps
speed_mps       = distance_m / delta_time
speed_kmh       = speed_mps * 3.6
```

## Timestamps and frame skipping (STEPS 12-13, 36)

Time always comes from the **SOURCE FPS and source frame number**:

```
timestamp = frame_number / source_fps
```

Never from the processing rate. Frame skipping is handled implicitly
because the estimator measures between the newest observation and an
anchor that is at least `SPEED_MEASUREMENT_WINDOW_S` seconds old, using
`(current_frame - anchor_frame) / source_fps`.

The frontend timestamp bug (`-1:-1.966`, negative) is fixed: the frame
record now includes a `time = frame / source_fps` field and the inspector
clamps non-finite/negative values.

## Smoothing, outliers, confidence, lifecycle

* **History bound:** per-track rolling window `SPEED_HISTORY_LENGTH` (60).
* **Minimum history:** `SPEED_MIN_HISTORY_FRAMES` (8) before any speed is
  shown — otherwise `CALCULATING`.
* **Smoothing:** exponential moving average, factor `SPEED_EMA_ALPHA (0.30)`.
* **Outlier rejection:** any sample above `SPEED_MAX_KMH (200)` or a spike
  vs. the running EMA (`> ema*factor + offset`) is rejected, the last
  reliable estimate is retained, and confidence is reduced.
* **ESTIMATION CONFIDENCE** (0-1, explicitly a heuristic, STEP 10/29):
  blends history sufficiency, detection confidence, measurement
  consistency, track age, recent outliers, and is scaled down when the
  camera is moving.
* **Cleanup:** tracks not observed for `SPEED_STALE_FRAMES` are pruned to
  bound memory (STEP 33).

## Backend / API changes

* `src/pipeline/processor.py` — additive per-track fields in the per-frame
  records (`tracks_meta`), analysis rows, summary `analysis_rows`, final
  `stats`; camera-motion sampling; `time` field embedded in frame records.
* `api/main.py` — `/api/calibration` (GET status, POST apply, DELETE
  clear), `/api/calibration/preview` (representative frame for the UI),
  speed columns in the CSV report.

New per-track serialized fields (backward compatible / optional):

```
speed_mps, speed_kmh, approach_kmh, speed_confidence, speed_status
```

Status values: `NOT_CALIBRATED`, `CALCULATING`, `ESTIMATED`,
`LOW_CONFIDENCE`, `TRACK_LOST`, `UNAVAILABLE` (STEP 24).

## Frontend changes

* `frontend/src/components/SpeedCalibration.tsx` — status chip
  (● CALIBRATED / ○ NOT CALIBRATED) + the 4-click point selector +
  width/distance inputs + apply/clear; never opens without a video.
* `frontend/src/components/AIFrameInspector.tsx` — FRAME DATA now shows
  THREAT SPEED (km/h) + ESTIMATION CONFIDENCE + PROCESSING FPS, separate
  from SOURCE FPS and PLAYBACK; the per-box overlay shows
  `47.3 km/h` (or `SPEED N/A`); the calibration panel and camera-motion
  warning render alongside.
* `frontend/src/components/SystemDetails.tsx` — per-object Speed column and
  a Speed Estimation panel (calibration status, ego speed, camera-motion).
* `frontend/src/components/VideoSection.tsx` — forwards the source path to
  the inspector so calibration can use the real frame.

## Testing

`pytest tests/ -q` covers (see `tests/test_speed_estimation.py`): m/s↔km/h
conversion, timestamp/`(-1)`-guard, frame-skipping time, distance, speed,
smoothing, outlier rejection, insufficient history, calibration
valid/invalid (duplicate/collinear/non-positive), track cleanup, and
uncalibrated-never-km/h.

## Known limitations

* **The current video is NOT calibrated** until a calibration is applied:
  it reports `○ NOT CALIBRATED` and no km/h.
* For genuinely accurate km/h you must provide a **real-world reference** —
  a known lane width or measured road segment — via the CALIBRATE SPEED
  flow. Without it the project cannot claim absolute accuracy.
* The camera-motion check is a heuristic. If motion is detected the UI
  warns `CAMERA MOTION MAY REDUCE ACCURACY`; reported speeds are best
  treated as relative/approach estimates.
* ESTIMATION CONFIDENCE is a transparent heuristic, not a calibrated
  statistical uncertainty.
* Lateral speed near the horizon is poorly conditioned; the homography is
  bounded to a sane neighbourhood of the calibrated region.
