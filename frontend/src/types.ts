export type RiskLevel = 'SAFE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string;

export interface PrimaryThreat {
  object_type?: string;
  class_name?: string;
  tracking_id?: number;
  direction?: string;
  motion_state?: string;
  trajectory_status?: string;
  conflict_status?: string;
  risk_score?: number;
  risk_level?: RiskLevel;
  estimated_ttc?: number | null;
  estimated_pet?: number | null;
  estimated_drac_risk?: string;
  estimated_act?: string | null;
  color?: string;
}

export interface PipelineStats {
  frames_processed: number;
  processing_time: string;
  processing_time_raw: number;
  total_unique_tracks: number;
  total_detections: number;
  class_counts: Record<string, number>;
  processing_fps: number;
  total_frames: number;
  video_fps?: number;
  width?: number;
  height?: number;
  collision_count?: number;
  max_conflict?: string;
  processing_errors?: number;
  error_samples?: { frame: number; error: string }[];
  high_conflict_frames?: number;
  cumulative_max_risk?: number;
  max_risk_frame?: number;
  unique_track_ids?: number[];
  // --- Speed estimation (additive) ---
  speed_estimation_enabled?: boolean;
  speed_calibrated?: boolean;
  camera_motion_warning?: boolean;
  ego_speed_kmh?: number | null;
  speed_calibration?: SpeedCalibrationStatus;
}

export interface RiskSummary {
  max_risk_score?: number;
  total_objects?: number;
  highest_risk_object?: string;
  primary_threat?: string | null;
  risk_distribution?: Record<string, number>;
  overall_risk_level?: string;
}

export interface AnalysisRow {
  class_name: string;
  track_id: number;
  direction: string;
  motion: string;
  trajectory: string;
  conflict: string;
  estimated_ttc: number | null;
  estimated_pet: number | null;
  estimated_drac_risk: string;
  estimated_act: string | null;
  max_risk_score: number;
  risk_level: RiskLevel;
  // --- Speed estimation (additive, calibration-gated) ---
  estimated_speed_kmh?: number | null;
  estimated_speed_confidence?: number | null;
  speed_status?: string;
}

export interface TopThreat {
  rank: number;
  class_name: string;
  tracking_id: number;
  direction: string;
  risk_level: RiskLevel;
  risk_score: number;
}

export type VerdictLevel =
  | 'HIGH_COLLISION_RISK'
  | 'POTENTIAL_COLLISION_RISK'
  | 'LOW_RISK'
  | 'NO_SIGNIFICANT_RISK'
  | 'UNKNOWN';

export interface AnalysisVerdict {
  level: VerdictLevel | string;
  label: string;
  collision_risk_detected: boolean;
  reason: string;
}

export interface PipelineResultPayload {
  output_video_path: string;
  output_video_filename: string;
  stats: PipelineStats;
  risk_summary: RiskSummary;
  primary_threat: PrimaryThreat | null;
  analysis_rows: AnalysisRow[];
  top_threats: TopThreat[];
  unique_track_ids?: number[];
  class_counts?: Record<string, number>;
  frames_available?: boolean;
  frames_filename?: string;
  verdict?: AnalysisVerdict;
}

/** One tracked object inside one processed frame (real backend output). */
export interface FrameTrackMeta {
  id: number;
  class: string;
  conf: number;
  bbox: number[];
  center: number[];
  direction: string;
  motion: string;
  trajectory: string;
  conflict: string;
  ttc: number | null;
  pet: number | null;
  drac: string;
  act: string;
  risk_score: number;
  risk_level: RiskLevel;
  pred: number[] | null;
  // --- Speed estimation (additive, calibration-gated) ---
  speed_mps?: number | null;
  speed_kmh?: number | null;
  approach_kmh?: number | null;
  speed_confidence?: number | null;
  speed_status?: string;
}

/** One processed frame record. `out` is the synchronization key
    (position of the frame inside the processed output video). */
export interface FrameMeta {
  frame: number;
  out: number;
  timestamp: number;
  /** Source time = frame / source_fps (added to fix the -1:-1 timestamp bug). */
  time?: number;
  tracks: FrameTrackMeta[];
}

export interface SpeedCalibrationStatus {
  configured?: boolean;
  source?: string;
  label?: string;
  note?: string;
  image_points?: number[][];
  world_points_meters?: number[][];
}

export interface CalibrationResponse {
  status: SpeedCalibrationStatus;
  path: string;
}

export interface CalibrationPreview {
  ok: boolean;
  error?: string;
  width?: number;
  height?: number;
  preview_b64?: string | null;
}

export interface JobFramesPayload {
  available: boolean;
  fps?: number;
  total_frames?: number;
  processed_frames?: number;
  frames: FrameMeta[];
}

export type PipelineStage =
  | 'LOADING_VIDEO'
  | 'ANALYZING_FRAMES'
  | 'FINALIZING'
  | 'COMPLETED'
  | 'FAILED'
  | '';

export interface JobSnapshot {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  progress: number;
  step: string;
  stage?: PipelineStage | string;
  frame: number;
  total: number;
  error: string | null;
  video_filename: string | null;
  started_at: string;
  has_result: boolean;
  result?: PipelineResultPayload;
  stats?: PipelineStats;
  /** Part 4: voice assistant context (alerts count + worst threat). */
  voice?: {
    alerts?: number;
    worst?: VoiceWorstThreat | null;
  };
}

/** Worst-threat summary echoed back for the voice assistant (additive). */
export interface VoiceWorstThreat {
  risk_level?: string;
  direction?: string;
  track_id?: number | null;
  class_name?: string | null;
  ttc?: number | null;
  speed_kmh?: number | null;
  speed_confidence?: number | null;
  speed_status?: string | null;
}

/** A single backend-generated `voice_alert` WebSocket message (additive). */
export interface VoiceAlert {
  type: 'voice_alert';
  event_id: string;
  kind: string;
  risk_level: string;
  direction: string;
  text: string;
  message?: string;
  track_id?: number | null;
  class_name?: string | null;
  vehicle_class?: string | null;
  risk_score: number;
  ttc?: number | null;
  ttc_seconds?: number | null;
  speed_kmh?: number | null;
  speed_confidence?: number | null;
  speed_status?: string | null;
  /** Part 4 multilingual: language the TEXT was actually produced in. */
  language?: string;
  speed_valid?: boolean;
  speed_timestamp_s?: number | null;
  priority: number;
  timestamp?: string;
  trigger?: string;
}

/** Playback priority mirror of the backend PRIORITY_MAP (additive). */
export const VOICE_PRIORITIES = {
  SAFE: 10,
  LOW: 10,
  MEDIUM: 50,
  HIGH: 80,
  CRITICAL: 100,
  QUERY: 60,
  TEST: 75,
} as const;

export type VoiceAssistantState =
  | 'IDLE'
  | 'MONITORING'
  | 'LISTENING'
  | 'THINKING'
  | 'SPEAKING'
  | 'MUTED'
  | 'ERROR'
  | 'OFFLINE'
  | 'BLOCKED'
  | 'NO_VOICE';

export interface VoiceQueryResponse {
  job_id: string;
  answer: string;
  state: string;
}

export interface DatasetVideo {
  file_name: string;
  file_path: string;
  category: string;
  subcategory?: string;
  source_dataset?: string;
  width?: number;
  height?: number;
  fps?: number;
  frame_count?: number;
  duration?: number;
  is_valid?: boolean;
  error?: string;
}