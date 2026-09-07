import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  X,
  Loader2,
  Play,
  Pause,
  Square,
  RotateCcw,
  SkipBack,
  SkipForward,
  ChevronLeft,
  ChevronRight,
  Maximize,
  Minimize,
  Info,
  AlertTriangle,
} from 'lucide-react';
import type { FrameMeta, FrameTrackMeta, JobSnapshot } from '../types';
import { api } from '../api';
import { hudRiskColor } from '../utils/hud';
import { SpeedCalibration } from './SpeedCalibration';

interface AIFrameInspectorProps {
  job: JobSnapshot | null;
  open: boolean;
  onClose: () => void;
  videoSrc: string | null;
  fps: number;
  totalFrames: number;
  autoPlay: boolean;
  sourcePath?: string | null;
}

const PIPELINE_STAGES = ['FRAME', 'YOLO', 'TRACK', 'MOTION', 'PREDICT', 'COLLISION', 'RISK', 'ALERT'] as const;
const SPEEDS = [0.25, 0.5, 1, 2];

function fmtClock(t: number): string {
  const safe = Number.isFinite(t) && t > 0 ? t : 0;
  const m = Math.floor(safe / 60);
  const s = Math.floor(safe % 60);
  const ms = Math.floor((safe - Math.floor(safe)) * 1000);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
}

function fmtFrame(n: number): string {
  const v = Math.max(1, Math.floor(n || 1));
  return v < 1000 ? String(v).padStart(3, '0') : v.toLocaleString();
}

function pct(v: number, max: number): number {
  return max > 0 ? (v / max) * 100 : 0;
}

export function AIFrameInspector({ job, open, onClose, videoSrc, fps, totalFrames, autoPlay, sourcePath }: AIFrameInspectorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const framesRef = useRef<FrameMeta[]>([]);
  const idxOutRef = useRef(new Map<number, number>());
  const fetchFlagRef = useRef(false);
  const jobIdRef = useRef<string | null>(null);
  const frameErrRef = useRef<string | null>(null);

  const [frames, setFrames] = useState<FrameMeta[]>([]);
  const [framesAvailable, setFramesAvailable] = useState(false);
  const [framesLoading, setFramesLoading] = useState(false);
  const [framesError, setFramesError] = useState<string | null>(null);

  const [curOut, setCurOut] = useState(1);
  const [playing, setPlaying] = useState(false);
  const [streamEnded, setStreamEnded] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [videoDuration, setVideoDuration] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const [mediaError, setMediaError] = useState<string | null>(null);

  const result = job?.status === 'completed' ? job.result ?? null : null;
  const resultStats = result?.stats;

  // Clean local state each time the modal opens.
  useEffect(() => {
    if (!open) {
      const v = videoRef.current;
      if (v) v.pause();
      return;
    }
    setCurOut(1);
    setPlaying(false);
    setStreamEnded(false);
    setMediaError(null);
    setVideoDuration(0);
    if (!autoPlay) return;
    const v = videoRef.current;
    if (v) void v.play().catch(() => {});
  }, [open, autoPlay]);

  // Load per-frame records from the backend once the job completes.
  //
  // Hardened: the fetch is tied to a SPECIFIC job id, so switching videos
  // can never reuse a previous job's frames (stale-cache bug). If the frames
  // endpoint reports "not ready" yet (a real race right at job completion),
  // we transparently retry a few times instead of giving up and showing
  // "ANNOTATED VIDEO ONLY" forever. Overlays are never fabricated — if the
  // backend really has no per-frame records we keep showing the honest
  // whole-video fallback message.
  useEffect(() => {
    if (!open || !job) return;
    if (job.status !== 'completed' || !job.result) return;
    const jobId = job.job_id;

    // Switched job / first load: drop any other job's cached frame state.
    if (jobIdRef.current !== jobId) {
      jobIdRef.current = jobId;
      framesRef.current = [];
      idxOutRef.current = new Map();
      fetchFlagRef.current = false;
      frameErrRef.current = null;
      setFrames([]);
      setFramesAvailable(false);
      setFramesError(null);
      setFramesLoading(false);
    }

    // Already cached for THIS job → just re-apply to state.
    if (framesRef.current.length > 0) {
      setFrames(framesRef.current);
      setFramesAvailable(true);
      setFramesError(null);
      setFramesLoading(false);
      return;
    }
    // A fetch/retry pass is already in flight for this job → don't stack.
    if (fetchFlagRef.current) return;

    fetchFlagRef.current = true;
    let retries = 0;
    const MAX_RETRIES = 3;

    const attempt = () => {
      setFramesLoading(true);
      api
        .jobFrames(jobId)
        .then((payload) => {
          if (jobIdRef.current !== jobId) return; // user switched jobs mid-flight
          const usable =
            payload.available && Array.isArray(payload.frames) && payload.frames.length > 0;
          if (!usable) {
            if (retries < MAX_RETRIES) {
              retries += 1;
              window.setTimeout(attempt, 1000 * retries);
              return;
            }
            frameErrRef.current = 'no per-frame metadata for this job';
          } else {
            framesRef.current = payload.frames.slice().sort((a, b) => a.out - b.out);
            idxOutRef.current = new Map(framesRef.current.map((fm, i) => [fm.out, i]));
            frameErrRef.current = null;
          }
          setFrames(framesRef.current);
          setFramesAvailable(framesRef.current.length > 0);
          setFramesError(frameErrRef.current);
          setFramesLoading(false);
        })
        .catch((err: unknown) => {
          if (jobIdRef.current !== jobId) return;
          if (retries < MAX_RETRIES) {
            retries += 1;
            window.setTimeout(attempt, 1000 * retries);
            return;
          }
          frameErrRef.current = err instanceof Error ? err.message : 'failed to load per-frame data';
          setFrames([]);
          setFramesAvailable(false);
          setFramesError(frameErrRef.current);
          setFramesLoading(false);
        });
    };

    attempt();
  }, [open, job]);

  // Keyboard: ESC closes (when not fullscreen).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !document.fullscreenElement) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // Sync fullscreen state with the browser.
  useEffect(() => {
    const onFs = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', onFs);
    return () => document.removeEventListener('fullscreenchange', onFs);
  }, []);

  const videoW = resultStats?.width && resultStats.width > 0 ? resultStats.width : 1280;
  const videoH = resultStats?.height && resultStats.height > 0 ? resultStats.height : 720;
  const playFps = fps > 0 ? fps : 30;
  const outMax = Math.max(1, Math.round((videoDuration || totalFrames / playFps) * playFps));

  const idxByOut = idxOutRef.current;
  const meta = useMemo(() => {
    if (!framesAvailable) return undefined;
    const i = idxByOut.get(curOut);
    return i === undefined ? undefined : frames[i];
  }, [frames, framesAvailable, curOut, idxByOut]);

  const tracks = useMemo(() => {
    const t = meta?.tracks;
    if (!t || t.length === 0) return [];
    return t.slice().sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0));
  }, [meta]);

  // Real per-frame aggregate values (backend data for the CURRENT frame).
  const riskScore = useMemo(() => {
    if (tracks.length === 0) return null;
    return Math.max(...tracks.map((t) => t.risk_score ?? 0));
  }, [tracks]);
  const riskTrack = riskScore === null ? null : tracks.find((t) => t.risk_score === riskScore) ?? tracks[0];
  const ttc = useMemo(() => {
    const vals = tracks
      .map((t) => t.ttc)
      .filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
    return vals.length > 0 ? Math.min(...vals) : null;
  }, [tracks]);
  const frameDirection = riskTrack?.direction ?? null;
  const objectsCount = tracks.length;
  const tracksCount = useMemo(() => new Set(tracks.map((t) => t.id)).size, [tracks]);

  // Speed estimation: use the primary/threat track's calibrated speed when
  // available. Uncalibrated runs report null so the UI shows N/A / status.
  const threatSpeedKmh = useMemo(() => {
    if (!riskTrack) return null;
    if (typeof riskTrack.speed_kmh === 'number' && Number.isFinite(riskTrack.speed_kmh)) {
      return riskTrack.speed_kmh;
    }
    return null;
  }, [riskTrack]);
  const threatSpeedConf = riskTrack?.speed_confidence ?? null;
  const threatSpeedStatus = riskTrack?.speed_status ?? null;
  const calibrationConfigured =
    resultStats?.speed_calibrated === true ||
    resultStats?.speed_calibration?.configured === true;
  const cameraMotion = resultStats?.camera_motion_warning === true;
  const processingFps = resultStats?.processing_fps ?? null;
  const hazard = tracks.some(
    (t) => t.conflict === 'HIGH CONFLICT' || t.conflict === 'POTENTIAL CONFLICT' || (t.risk_score ?? 0) >= 60,
  );

  const handleTime = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    const out = Math.min(outMax, Math.max(1, Math.round(v.currentTime * playFps) + 1));
    setCurOut((prev) => (prev === out ? prev : out));
  }, [outMax, playFps]);

  // Motion trails for the top-risk objects: walk backward through the real
  // frames looking for each track's previous positions.
  const trails = useMemo(() => {
    if (!framesAvailable) return new Map<number, { points: { x: number; y: number }[] }>();
    const startIdx = idxByOut.get(curOut);
    if (startIdx === undefined) return new Map();
    const out: Map<number, { points: { x: number; y: number }[] }> = new Map();
    const targets = tracks.slice(0, 5).map((t) => t.id);
    const seen = new Map<number, number[]>();
    for (let i = startIdx; i >= Math.max(0, startIdx - 18); i--) {
      const fm = frames[i];
      for (const tr of fm?.tracks ?? []) {
        if (!targets.includes(tr.id)) continue;
        const list = seen.get(tr.id) ?? [];
        if (list.length < 18) list.push(i);
        seen.set(tr.id, list);
      }
    }
    for (const [id, idxs] of seen) {
      const points = idxs
        .sort((a, b) => a - b)
        .map((i) => frames[i].tracks.find((t) => t.id === id))
        .filter((t): t is FrameTrackMeta => Boolean(t))
        .map((t) => ({
          x: pct(t.center[0], videoW),
          y: pct(t.center[1], videoH),
        }));
      if (points.length > 0) out.set(id, { points });
    }
    return out;
  }, [frames, framesAvailable, curOut, tracks, idxByOut, videoW, videoH]);

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) void v.play().catch(() => {});
    else v.pause();
  };

  const stop = () => {
    const v = videoRef.current;
    if (!v) return;
    v.pause();
    v.currentTime = 0;
  };

  const restart = () => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = 0;
    void v.play().catch(() => {});
  };

  const stepFrame = (delta: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = Math.max(0, Math.min(v.duration || 0, v.currentTime + delta / playFps));
  };

  const seekTo = (out: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = Math.max(0, Math.min(v.duration || 0, (out - 1) / playFps));
  };

  const toggleFullscreen = () => {
    const el = containerRef.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => {});
    else void el.requestFullscreen?.().catch(() => {});
  };

  const selectVideo = () => {
    // From the inspector's empty state, guide the judge back to upload.
    onClose();
    document.getElementById('video-upload-btn')?.click();
  };

  if (!open) return null;

  const processingNow = job?.status === 'running' || job?.status === 'pending';
  const noVideo = !videoSrc;
  const frameNo = curOut;
  const streamStatus = mediaError
    ? { text: 'ERROR — DECODE FAILED', cls: 'border-hud-red/40 bg-hud-red/15 text-hud-red' }
    : processingNow
      ? { text: 'PROCESSING', cls: 'border-hud-amber/40 bg-hud-amber/15 text-hud-amber' }
      : framesLoading
        ? { text: 'BUFFERING — LOADING FRAME METADATA', cls: 'border-hud-amber/40 bg-hud-amber/15 text-hud-amber' }
        : streamEnded
          ? { text: 'COMPLETE — ALL FRAMES PLAYED', cls: 'border-hud-green/40 bg-hud-green/15 text-hud-green' }
          : playing
            ? { text: 'PLAYING — RECEIVING AI FRAMES', cls: 'border-hud-cyan/40 bg-hud-cyan/15 text-hud-cyan' }
            : { text: 'PAUSED', cls: 'border-hud-border/60 bg-hud-bg/70 text-hud-dim' };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-hud-bg/85 p-2 backdrop-blur-sm" onClick={onClose}>
      <div
        ref={containerRef}
        className="flex max-h-[96vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-hud-border bg-hud-panel shadow-hud"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-3 border-b border-hud-border px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-hud-cyan/60" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-hud-cyan" />
            </span>
            <span className="font-hud text-base font-bold tracking-widest text-hud-text">AI FRAME INSPECTOR</span>
            <span className="font-hud text-[10px] tracking-widest text-hud-dim">REAL PROCESSED FRAME STREAM</span>
          </div>
          {result && (
            <span
              className={`rounded border px-2 py-0.5 font-hud text-[9px] tracking-widest ${
                hazard ? 'border-hud-red/40 bg-hud-red/10 text-hud-red' : 'border-hud-green/40 bg-hud-green/10 text-hud-green'
              }`}
            >
              ● {hazard ? 'COLLISION RISK ACTIVE' : 'COLLISION RISK NOMINAL'}
            </span>
          )}
          <button type="button" onClick={onClose} className="btn-hud-secondary !px-2 !py-1 !text-xs">
            <X className="h-3.5 w-3.5" /> Close
          </button>
        </div>

        {noVideo ? (
          /* Empty state — no fabricated frames */
          <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
            <Info className="h-10 w-10 text-hud-dim" />
            <div className="font-hud text-lg font-bold tracking-widest text-hud-text">NO TRAFFIC VIDEO</div>
            <p className="max-w-sm text-xs text-hud-dim">Upload a traffic video to begin AI frame processing.</p>
            <button type="button" onClick={selectVideo} className="btn-hud !px-4 !py-2 !text-xs">
              Select Video
            </button>
          </div>
        ) : (
          <div className="grid flex-1 gap-3 p-3 lg:grid-cols-[1.55fr_1fr] lg:gap-4 lg:p-4">
            {/* --- Live processed frame surface --- */}
            <div className="min-w-0">
              <div className="relative overflow-hidden rounded-lg border border-hud-border bg-black">
                <div className="relative aspect-video w-full">
                  <video
                    key={`${videoSrc}|${job?.job_id ?? ''}`}
                    ref={videoRef}
                    src={videoSrc}
                    className="h-full w-full object-contain"
                    muted
                    playsInline
                    preload="auto"
                    onTimeUpdate={handleTime}
                    onPlay={() => {
                      setPlaying(true);
                      setStreamEnded(false);
                    }}
                    onPause={() => setPlaying(false)}
                    onEnded={() => setStreamEnded(true)}
                    onLoadedMetadata={(e) => setVideoDuration(e.currentTarget.duration || 0)}
                    onError={(e) => {
                      const el = e.currentTarget;
                      const code = el.error?.code ?? -1;
                      const why = el.error?.message ?? '';
                      console.error('[AIFrameInspector] processed video decode failed', {
                        code,
                        why,
                        src: videoSrc,
                        networkState: el.networkState,
                      });
                      setMediaError(
                        `VIDEO DECODE FAILED — MEDIA_ERR_${code}${why ? ` (${why})` : ''}. ` +
                          'THE OUTPUT FILE MUST BE H.264 FOR BROWSER PLAYBACK — RE-RUN ANALYSIS SO THE BACKEND RE-ENCODES IT.',
                      );
                    }}
                  />

                  {/* Real per-frame AI overlay (synchronized by `out` index) */}
                  {framesAvailable && tracks.length > 0 && (
                    <>
                      {/* Trails + predictions (SVG, % space) */}
                      <svg
                        className="pointer-events-none absolute inset-0 z-10 h-full w-full"
                        viewBox="0 0 100 100"
                        preserveAspectRatio="none"
                      >
                        {tracks.slice(0, 5).map((t) => {
                          const trail = trails.get(t.id);
                          const color = hudRiskColor(t.risk_level);
                          const cx = pct(t.center[0], videoW);
                          const cy = pct(t.center[1], videoH);
                          return (
                            <g key={t.id}>
                              {trail && trail.points.length > 1 && (
                                <polyline
                                  points={trail.points.map((p: { x: number; y: number }) => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ')}
                                  fill="none"
                                  stroke={color}
                                  strokeOpacity="0.55"
                                  strokeWidth="0.35"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  vectorEffect="non-scaling-stroke"
                                />
                              )}
                              {t.pred && (
                                <>
                                  <line
                                    x1={cx}
                                    y1={cy}
                                    x2={pct(t.pred[0], videoW)}
                                    y2={pct(t.pred[1], videoH)}
                                    stroke="rgba(34,211,238,0.65)"
                                    strokeDasharray="1.2 1"
                                    strokeWidth="0.3"
                                    vectorEffect="non-scaling-stroke"
                                  />
                                  <circle
                                    cx={pct(t.pred[0], videoW)}
                                    cy={pct(t.pred[1], videoH)}
                                    r="0.8"
                                    fill="none"
                                    stroke="#22D3EE"
                                    strokeWidth="0.35"
                                    vectorEffect="non-scaling-stroke"
                                  />
                                </>
                              )}
                            </g>
                          );
                        })}
                      </svg>

                      {/* Collision zone (only when backend reported it) */}
                      {hazard && (
                        <div className="pointer-events-none absolute inset-0 z-20">
                          <div className="absolute left-1/2 top-2 -translate-x-1/2">
                            <span className="hud-anim-blink inline-flex items-center gap-1.5 rounded border border-hud-red/50 bg-hud-bg/80 px-2 py-1 font-hud text-[10px] font-bold tracking-widest text-hud-red shadow-glowRed">
                              <AlertTriangle className="h-3 w-3" /> PREDICTED COLLISION
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Boxes + labels (HTML, % positions, real bboxes) */}
                      <div className="pointer-events-none absolute inset-0 z-20">
                        {tracks.slice(0, 8).map((t) => {
                          const [x1, y1, x2, y2] = t.bbox;
                          const color = hudRiskColor(t.risk_level);
                          return (
                            <div
                              key={t.id}
                              className="absolute"
                              style={{
                                left: `${pct(x1, videoW)}%`,
                                top: `${pct(y1, videoH)}%`,
                                width: `${pct(x2 - x1, videoW)}%`,
                                height: `${pct(y2 - y1, videoH)}%`,
                              }}
                            >
                              <div
                                className="absolute inset-0 rounded-[2px] border"
                                style={{ borderColor: color, boxShadow: `0 0 8px ${color}55`, borderWidth: '1.5px' }}
                              />
                              <span
                                className="absolute -top-[15px] left-0 whitespace-nowrap rounded-sm px-1 py-px font-hud text-[9px] font-bold tracking-wider"
                                style={{ backgroundColor: color, color: '#0B0F19' }}
                              >
                                {t.class.toUpperCase()} #{t.id}
                                {t.conf > 0 ? ` ${(t.conf * 100).toFixed(0)}%` : ''}
                              </span>
                              <span
                                className="absolute -top-[34px] left-0 whitespace-nowrap rounded-sm border border-hud-border bg-hud-bg/85 px-1 py-px font-hud text-[9px] tracking-wider"
                                style={{ color: typeof t.speed_kmh === 'number' ? '#34D399' : '#94A3B8' }}
                              >
                                {typeof t.speed_kmh === 'number'
                                  ? `${t.speed_kmh.toFixed(1)} km/h`
                                  : t.speed_status === 'CALCULATING'
                                    ? 'SPEED CALC…'
                                    : 'SPEED N/A'}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}

                  {/* Soft scanline */}
                  <div className="pointer-events-none absolute inset-0 z-30 overflow-hidden">
                    <div className="hud-anim-scanline-soft absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-transparent via-hud-cyan/25 to-transparent" />
                  </div>

                  {/* LEGEND chip */}
                  <div className="absolute right-2 top-2 z-30 rounded border border-hud-border bg-hud-bg/75 px-2 py-0.5 font-hud text-[8px] tracking-widest text-hud-dim backdrop-blur-sm">
                    {framesAvailable ? (
                      <span className="text-hud-cyan">● REAL PER-FRAME AI DATA</span>
                    ) : (
                      <span className="text-hud-amber">● ANNOTATED VIDEO ONLY</span>
                    )}
                  </div>

                  {/* Live stream status chip */}
                  <div
                    className={`absolute left-2 top-2 z-30 rounded border bg-hud-bg/75 px-2 py-0.5 font-hud text-[8px] tracking-widest backdrop-blur-sm ${streamStatus.cls}`}
                  >
                    ● {streamStatus.text}
                  </div>

                  {/* Processing in progress */}
                  {processingNow && (
                    <div className="absolute inset-0 z-40 flex items-center justify-center bg-hud-bg/80 backdrop-blur-sm">
                      <div className="flex flex-col items-center gap-2 text-center">
                        <Loader2 className="h-7 w-7 animate-spin text-hud-cyan" />
                        <div className="font-hud font-semibold text-hud-text">{job?.step ?? 'Processing frames…'}</div>
                        <div className="w-64">
                          <div className="h-1.5 overflow-hidden rounded-full bg-hud-border">
                            <div
                              className="h-full bg-gradient-to-r from-hud-cyan to-hud-blue"
                              style={{ width: `${Math.min(100, (job?.progress ?? 0) * 100)}%` }}
                            />
                          </div>
                          <div className="mt-1 flex justify-between font-hud text-[10px] text-hud-dim">
                            <span>
                              FRAME {(job?.frame ?? 0).toLocaleString()} /{(job?.total ?? 0).toLocaleString()}
                            </span>
                            <span className="text-hud-cyan">{Math.round((job?.progress ?? 0) * 100)}%</span>
                          </div>
                        </div>
                        <p className="font-hud text-[9px] tracking-widest text-hud-dim">
                          PROCESSED FRAME STREAM WILL JOG ONCE BACKEND ANALYSIS COMPLETES
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Media error */}
                  {mediaError && (
                    <div className="absolute inset-0 z-40 flex items-center justify-center bg-hud-bg/90">
                      <div className="max-w-sm rounded-lg border border-hud-red/40 bg-hud-red/10 p-4 text-center">
                        <AlertTriangle className="mx-auto mb-1 h-6 w-6 text-hud-red" />
                        <div className="font-hud text-sm font-bold tracking-widest text-hud-red">AI PROCESSING ERROR</div>
                        <p className="mt-1 text-xs text-hud-text">{mediaError}</p>
                      </div>
                    </div>
                  )}

                  {/* Per-frame AI readout on the frame surface */}
                  {framesAvailable && tracks.length > 0 && (
                    <div className="absolute bottom-2 left-2 z-30 flex flex-wrap gap-1.5 font-hud text-[9px] tracking-wider">
                      <span
                        className="rounded border px-1.5 py-0.5"
                        style={{
                          borderColor: hudRiskColor(riskTrack?.risk_level ?? 'SAFE'),
                          color: riskScore !== null && riskScore >= 40 ? '#F87171' : '#34D399',
                          background: '#0B0F19cc',
                        }}
                      >
                        RISK {riskScore !== null ? Math.round(riskScore) : '–'}/100
                      </span>
                      {ttc !== null && (
                        <span className="rounded border border-hud-border bg-hud-bg/80 px-1.5 py-0.5 text-hud-cyan">
                          TTC {ttc.toFixed(1)}s
                        </span>
                      )}
                      {frameDirection && (
                        <span className="rounded border border-hud-border bg-hud-bg/80 px-1.5 py-0.5 text-hud-amber">
                          {frameDirection}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Pipeline strip */}
              <div className="mt-2 rounded-lg border border-hud-border bg-hud-bg/40 p-2">
                <div className="flex items-center justify-between">
                  <span className="font-hud text-[9px] tracking-widest text-hud-dim">PIPELINE</span>
                  <span className="font-hud text-[9px] tracking-widest text-hud-cyan">
                    {processingNow ? 'LIVE PROCESSING' : 'REPLAY — POST-PROCESS VISUALIZATION'}
                  </span>
                </div>
                <div className="mt-1.5 grid grid-cols-4 gap-1 sm:grid-cols-8">
                  {PIPELINE_STAGES.map((s, i) => {
                    const prog = processingNow
                      ? job?.progress ?? 0
                      : outMax > 0
                        ? Math.min(1, curOut / outMax)
                        : 0;
                    const t = (i + 1) / PIPELINE_STAGES.length;
                    const done = prog >= t;
                    const active = !done && prog > i / PIPELINE_STAGES.length;
                    return (
                      <div
                        key={s}
                        className={`rounded border px-1 py-1 text-center font-hud text-[9px] font-semibold tracking-wider ${
                          done
                            ? 'border-hud-green/30 bg-hud-green/[0.06] text-hud-green'
                            : active
                              ? 'border-hud-amber/50 bg-hud-amber/10 text-hud-amber'
                              : 'border-hud-border/60 text-hud-dim/60'
                        }`}
                      >
                        {s}
                        <span className="ml-0.5">{done ? '✓' : active ? '◉' : '○'}</span>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-1 font-hud text-[8px] tracking-wider text-hud-dim/60">
                  STAGES IN BACKEND ORDER · REPLAY PROGRESS DRIVES THE INDICATORS (NOT FABRICATED TIMING)
                </p>
              </div>
            </div>

            {/* --- Right: real per-frame data + metrics --- */}
            <div className="min-w-0 space-y-3">
              <div className="rounded-lg border border-hud-border bg-hud-bg/40 p-3">
                <div className="flex items-center justify-between">
                  <span className="hud-label">FRAME DATA — LIVE</span>
                  {framesLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-hud-cyan" />}
                </div>

                <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2">
                  <KeyVal label="FRAME" value={fmtFrame(frameNo)} acc={1} plus={`/${totalFrames > 0 ? totalFrames.toLocaleString() : '—'}`} big />
                  <KeyVal label="TIMESTAMP" value={fmtClock(meta?.time ?? meta?.timestamp ?? (curOut - 1) / playFps)} acc={1} plus="/SRC FPS" />
                  <KeyVal label="SOURCE FPS" value={playFps.toFixed(1)} />
                  <KeyVal label="PROCESSING FPS" value={processingFps !== null && processingFps > 0 ? processingFps.toFixed(1) : 'N/A'} acc={0} />
                  <KeyVal label="OBJECTS" value={objectsCount > 0 ? String(objectsCount) : '0'} />
                  <KeyVal label="TRACKS" value={tracksCount > 0 ? String(tracksCount) : '0'} />
                  <KeyVal
                    label="RISK"
                    value={riskScore !== null ? `${Math.round(riskScore)}` : 'N/A'}
                    acc={riskScore !== null && riskScore >= 60 ? 3 : riskScore !== null && riskScore >= 40 ? 2 : 0}
                    plus="/100"
                  />
                  <KeyVal label="TTC" value={ttc !== null ? `${ttc.toFixed(2)}s` : 'N/A'} />
                  <KeyVal
                    label="THREAT SPEED"
                    value={threatSpeedKmh !== null ? `${threatSpeedKmh.toFixed(1)} km/h` : 'N/A'}
                    acc={threatSpeedKmh !== null ? 1 : 0}
                  />
                  <KeyVal
                    label="CONFIDENCE"
                    value={threatSpeedConf != null ? `${Math.round(threatSpeedConf * 100)}%` : '—'}
                    acc={threatSpeedStatus === 'LOW_CONFIDENCE' ? 2 : 0}
                  />
                  <KeyVal label="DIRECTION" value={frameDirection ?? 'N/A'} acc={2} />
                </div>

                {threatSpeedStatus === 'NOT_CALIBRATED' && (
                  <p className="mt-2 rounded border border-hud-amber/30 bg-hud-amber/10 px-2 py-1 font-hud text-[9px] text-hud-amber">
                    SPEED N/A — CALIBRATION REQUIRED. No km/h is shown because the scene is not calibrated.
                  </p>
                )}
                {threatSpeedStatus === 'CALCULATING' && (
                  <p className="mt-2 rounded border border-hud-border bg-hud-bg/60 px-2 py-1 font-hud text-[9px] text-hud-dim">
                    SPEED CALCULATING — not enough track history yet. Requires {''}a few more frames.
                  </p>
                )}
                {cameraMotion && (
                  <p className="mt-1 rounded border border-hud-amber/30 bg-hud-amber/10 px-2 py-1 font-hud text-[9px] text-hud-amber">
                    SPEED ESTIMATION — CAMERA MOTION MAY REDUCE ACCURACY. Speeds are relative/approach estimates.
                  </p>
                )}
                {!calibrationConfigured && threatSpeedStatus !== 'NOT_CALIBRATED' && (
                  <p className="mt-1 font-hud text-[8px] tracking-wider text-hud-dim/70">
                    CURRENT SCENE NOT CALIBRATED — km/h hidden until 4 road points + real dimensions are set.
                  </p>
                )}

                {framesError && (
                  <p className="mt-2 rounded border border-hud-amber/30 bg-hud-amber/10 px-2 py-1 font-hud text-[9px] text-hud-amber">
                    PER-FRAME METADATA {framesError.toUpperCase()} — SHOWING RESULT-WIDE DATA
                  </p>
                )}
              </div>

              {/* Processing metrics (backend does not measure per-stage ms → honest N/A) */}
              <div className="rounded-lg border border-hud-border bg-hud-bg/40 p-3">
                <div className="hud-label">FRAME PROCESSING</div>
                <div className="mt-2 space-y-1 font-hud text-[11px]">
                  {(['Capture', 'YOLO', 'Tracking', 'Prediction', 'Risk'] as const).map((s) => (
                    <div key={s} className="flex items-center justify-between">
                      <span className="text-hud-dim">{s.toUpperCase()}</span>
                      <span className="text-hud-dim/70">N/A</span>
                    </div>
                  ))}
                  <div className="flex items-center justify-between border-t border-hud-border/60 pt-1">
                    <span className="text-hud-dim">TOTAL / FRAME</span>
                    <span className="text-hud-dim/70">N/A</span>
                  </div>
                </div>
                {resultStats && (
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-hud-border/60 pt-2 font-hud text-[9px] text-hud-dim">
                    <span>PROCESSING {resultStats.processing_fps?.toFixed(1)} f/s</span>
                    <span>{resultStats.frames_processed?.toLocaleString()} FR</span>
                    <span>PLAYBACK {speed}×</span>
                    <span>{resultStats.processing_errors ?? 0} ERR</span>
                  </div>
                )}
                <p className="mt-1 font-hud text-[8px] tracking-wider text-hud-dim/70">
                  BACKEND DOES NOT MEASURE PER-STAGE TIMING — NOT FABRICATED
                </p>
              </div>

              <SpeedCalibration
                sourcePath={sourcePath ?? null}
                statsSpeedCalibrated={calibrationConfigured}
              />

              {framesError && (
                <div className="rounded-lg border border-hud-border bg-hud-bg/40 p-3 font-hud text-[9px] leading-relaxed text-hud-dim">
                  THIS RUN PREDATES PER-FRAME RECORDS — PLAYING THE REAL BACKEND-ANNOTATED VIDEO WITH WHOLE-VIDEO
                  METRICS. RUN A FRESH ANALYSIS TO ENABLE FRAME-SYNCED DETECTION OVERLAYS.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Transport bar */}
        {videoSrc && (
          <div className="border-t border-hud-border bg-hud-bg/60 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1">
                <button type="button" onClick={() => seekTo(1)} className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs" title="First frame">
                  <SkipBack className="h-3.5 w-3.5" />
                </button>
                <button type="button" onClick={() => stepFrame(-1)} className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs" title="Previous frame">
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <button type="button" onClick={togglePlay} disabled={processingNow} className="btn-hud !rounded-md !px-3 !py-1 !text-xs">
                  {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                  {playing ? 'Pause' : 'Play'}
                </button>
                <button type="button" onClick={stop} className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs" title="Stop">
                  <Square className="h-3.5 w-3.5" />
                </button>
                <button type="button" onClick={restart} className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs" title="Restart">
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
                <button type="button" onClick={() => stepFrame(1)} className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs" title="Next frame">
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
                <button type="button" onClick={() => seekTo(outMax)} className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs" title="Last frame">
                  <SkipForward className="h-3.5 w-3.5" />
                </button>
              </div>

              <div className="flex items-center gap-1">
                {SPEEDS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => {
                      setSpeed(s);
                      if (videoRef.current) videoRef.current.playbackRate = s;
                    }}
                    className={`rounded border px-2 py-1 font-hud text-[10px] font-semibold tracking-wider ${
                      speed === s
                        ? 'border-hud-cyan/50 bg-hud-cyan/15 text-hud-cyan shadow-glowCyan'
                        : 'border-hud-border bg-hud-panel text-hud-dim hover:text-hud-text'
                    }`}
                  >
                    {s}×
                  </button>
                ))}
              </div>

              <button type="button" onClick={toggleFullscreen} className="ml-auto btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs">
                {fullscreen ? <Minimize className="h-3.5 w-3.5" /> : <Maximize className="h-3.5 w-3.5" />}
                {fullscreen ? 'Exit' : 'Fullscreen'}
              </button>
            </div>

            {/* Timeline */}
            <div className="mt-2 flex items-center gap-2">
              <span className="min-w-[72px] text-right font-mono text-[11px] font-bold text-hud-cyan">
                FR {fmtFrame(curOut)}{meta && meta.frame && meta.frame !== curOut ? `·SRC ${meta.frame.toLocaleString()}` : ''}
              </span>
              <input
                type="range"
                min={0}
                max={outMax - 1}
                step={1}
                value={Math.max(0, Math.min(curOut - 1, outMax - 1))}
                onChange={(e) => seekTo(Number(e.target.value) + 1)}
                className="min-w-0 flex-1"
                aria-label="Frame timeline"
              />
              <span className="min-w-[62px] font-mono text-[11px] text-hud-dim">
                {fmtClock(videoRef.current?.currentTime ?? 0)} / {fmtClock(videoDuration)}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function KeyVal({
  label,
  value,
  acc = 0,
  plus,
  big = false,
}: {
  label: string;
  value: string;
  acc?: number;
  plus?: string;
  big?: boolean;
}) {
  const color = acc === 0 ? 'text-hud-text' : acc === 1 ? 'text-hud-cyan' : acc === 2 ? 'text-hud-amber' : 'text-hud-red';
  return (
    <div>
      <div className="font-hud text-[9px] tracking-widest text-hud-dim">{label}</div>
      <div className={`${big ? 'text-2xl font-bold' : 'text-base font-bold'} font-hud ${color}`}>
        {value}
        {plus && <span className="text-xs text-hud-dim">{plus}</span>}
      </div>
    </div>
  );
}