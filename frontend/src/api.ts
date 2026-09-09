import type {
  CalibrationPreview,
  CalibrationResponse,
  DatasetVideo,
  JobFramesPayload,
  JobSnapshot,
  PipelineResultPayload,
  VoiceAlert,
  VoiceQueryResponse,
} from './types';
import { API_BASE, wsUrl } from './config';

async function jsonFetch<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init);
  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = (body as { detail?: string }).detail ?? '';
    } catch {
      // ignore
    }
    throw new Error(detail || `Request failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export interface UploadResponse {
  filename: string;
  saved_filename: string;
  path: string;
  size_bytes: number;
}

export const api = {
  async uploadVideo(file: File): Promise<UploadResponse> {
    const fd = new FormData();
    fd.append('file', file);
    return jsonFetch<UploadResponse>(`${API_BASE}/upload`, {
      method: 'POST',
      body: fd,
    });
  },

  async startProcessing(videoPath: string, confidence: number): Promise<JobSnapshot> {
    return jsonFetch<JobSnapshot>(`${API_BASE}/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path: videoPath, confidence }),
    });
  },

  async jobStatus(jobId: string): Promise<JobSnapshot> {
    return jsonFetch<JobSnapshot>(`${API_BASE}/jobs/${jobId}`);
  },

  /** Per-frame AI records for a completed job (real backend output). */
  async jobFrames(jobId: string): Promise<JobFramesPayload> {
    return jsonFetch<JobFramesPayload>(`${API_BASE}/jobs/${jobId}/frames`);
  },

  /** Part 4: ask the voice assistant a natural-language question. */
  async voiceQuery(jobId: string, question: string): Promise<VoiceQueryResponse> {
    return jsonFetch<VoiceQueryResponse>(`${API_BASE}/voice/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, question }),
    });
  },

  /** Part 4: switch the live voice language for a job (no restart needed). */
  async voiceLanguage(
    jobId: string,
    language: string
  ): Promise<{ job_id: string; language: string; valid: boolean }> {
    return jsonFetch(`${API_BASE}/voice/language`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, language }),
    });
  },

  videoUrl(filename: string): string {
    return `${API_BASE}/videos/${encodeURIComponent(filename)}`;
  },

  /** E9: playable URL for any dataset/upload video by absolute server path. */
  sourceUrl(absPath: string): string {
    return `${API_BASE}/source?path=${encodeURIComponent(absPath)}`;
  },

  async localVideos(): Promise<{ count: number; videos: { source: string; path: string; filename: string }[] }> {
    return jsonFetch(`${API_BASE}/dataset/local_videos`);
  },

  downloadVideo(filename: string, outputFilename?: string): void {
    const url = `${API_BASE}/videos/${encodeURIComponent(filename)}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = outputFilename ?? filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  },

  async csvReport(rows: unknown[]): Promise<{ csv: string }> {
    return jsonFetch<{ csv: string }>(`${API_BASE}/csv_report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows }),
    });
  },

  async calibrationStatus(): Promise<CalibrationResponse> {
    return jsonFetch<CalibrationResponse>(`${API_BASE}/calibration`);
  },

  async applyCalibration(
    imagePoints: [number, number][],
    widthM: number,
    depthM: number
  ): Promise<CalibrationResponse> {
    return jsonFetch<CalibrationResponse>(`${API_BASE}/calibration`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_points: imagePoints, width_m: widthM, depth_m: depthM }),
    });
  },

  async clearCalibration(): Promise<CalibrationResponse> {
    return jsonFetch<CalibrationResponse>(`${API_BASE}/calibration`, { method: 'DELETE' });
  },

  async calibrationPreview(absPath: string): Promise<CalibrationPreview> {
    return jsonFetch<CalibrationPreview>(
      `${API_BASE}/calibration/preview?path=${encodeURIComponent(absPath)}`
    );
  },

  async datasetSummary(): Promise<{
    summary: Record<string, unknown>;
    videos: DatasetVideo[];
  }> {
    return jsonFetch(`${API_BASE}/dataset/summary`);
  },

  async datasetRandom(
    category: string,
    count: number,
    seed: string
  ): Promise<{ videos: DatasetVideo[] }> {
    return jsonFetch(`${API_BASE}/dataset/random`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category, count, seed }),
    });
  },

  async datasetTest(
    category: string,
    count: number,
    confidence: number,
    seed: string
  ): Promise<JobSnapshot> {
    return jsonFetch<JobSnapshot>(`${API_BASE}/dataset/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category, count, confidence, seed }),
    });
  },

  /**
   * E10: polling fallback for job progress. Used when the WebSocket is
   * unavailable, errors, or closes before the job finishes. Returns a
   * cancel function.
   */
  pollJob(
    jobId: string,
    handlers: {
      onUpdate: (snap: JobSnapshot) => void;
      onDone: (snap: JobSnapshot) => void;
      onError: (msg: string) => void;
    },
    intervalMs = 1500
  ): () => void {
    let cancelled = false;
    let consecutiveErrors = 0;
    let timer: ReturnType<typeof setInterval> | null = null;
    const tick = async () => {
      try {
        const snap = await api.jobStatus(jobId);
        if (cancelled) return;
        consecutiveErrors = 0;
        if (snap.status === 'completed' || snap.status === 'error') {
          if (timer) clearInterval(timer);
          if (snap.status === 'completed') handlers.onDone(snap);
          else handlers.onError(snap.error ?? 'Processing failed');
        } else {
          handlers.onUpdate(snap);
        }
      } catch (err) {
        if (cancelled) return;
        consecutiveErrors += 1;
        handlers.onError(err instanceof Error ? err.message : 'Polling failed');
        // Stop hammering a dead/unknown job instead of erroring forever.
        if (consecutiveErrors >= 5 && timer) {
          clearInterval(timer);
          timer = null;
        }
      }
    };
    void tick();
    timer = setInterval(() => void tick(), intervalMs);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  },

  openJobSocket(jobId: string, handlers: {
    onProgress: (snap: {
      type: 'progress';
      status: string;
      progress: number;
      step: string;
      stage?: string;
      frame: number;
      total: number;
      error: string | null;
      has_result: boolean;
    }) => void;
    onResult: (result: PipelineResultPayload) => void;
    onDone: () => void;
    onError: (msg: string) => void;
    /** Part 4: called for every backend-generated `voice_alert` message. */
    onVoiceAlert?: (alert: VoiceAlert) => void;
  }): WebSocket {
    const ws = new WebSocket(wsUrl(`/ws/jobs/${jobId}`));
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'progress') handlers.onProgress(payload);
        else if (payload.type === 'result') handlers.onResult(payload.result);
        else if (payload.type === 'done') handlers.onDone();
        else if (payload.type === 'error') handlers.onError(payload.message ?? 'Unknown error');
        else if (payload.type === 'voice_alert' && handlers.onVoiceAlert) {
          handlers.onVoiceAlert(payload as VoiceAlert);
        }
      } catch {
        // A malformed frame (e.g. non-strict JSON) must not silently drop
        // the result: route to onError so the polling fallback can fetch
        // the same job via REST.
        handlers.onError('progress message parse failed');
      }
    };
    return ws;
  },
};