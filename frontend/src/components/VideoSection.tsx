import { useEffect, useRef, useState } from 'react';
import {
  RotateCcw,
  Upload,
  Video as VideoIcon,
  Loader2,
  CheckCircle2,
  RefreshCw,
  Play,
  Database,
  Shuffle,
  Gauge,
  Eye,
  ScanSearch,
  MonitorPlay,
  X,
  ChevronRight,
} from 'lucide-react';
import type { JobSnapshot } from '../types';
import { api } from '../api';
import { getVerdict } from '../utils/verdict';
import { VideoOverlays } from './VideoOverlays';
import { FrameInspector } from './FrameInspector';
import { FrameControls } from './FrameControls';
import { AIPipeline } from './AIPipeline';
import { AIFrameInspector } from './AIFrameInspector';

interface VideoSectionProps {
  job: JobSnapshot | null;
  videoPath: string | null;
  selectedFilename: string | null;
  selectedDisplayName?: string | null;
  confidence: number;
  onConfidenceChange: (value: number) => void;
  onReset: () => void;
  onFileSelected: (file: File) => void;
  onSelectSourceVideo?: (video: { file_path: string; file_name: string; display_name?: string }) => void;
  onStartProcessing: () => void;
  processing: boolean;
}

const VERDICT_STYLE: Record<string, { color: string; glow: string }> = {
  HIGH_COLLISION_RISK: { color: '#F87171', glow: '0 0 20px rgba(248,113,113,0.6)' },
  POTENTIAL_COLLISION_RISK: { color: '#FBBF24', glow: '0 0 20px rgba(251,191,36,0.6)' },
  LOW_RISK: { color: '#FBBF24', glow: '0 0 18px rgba(251,191,36,0.5)' },
  NO_SIGNIFICANT_RISK: { color: '#34D399', glow: '0 0 18px rgba(52,211,153,0.5)' },
  UNKNOWN: { color: '#64748B', glow: '' },
};

export function VideoSection({
  job,
  videoPath,
  selectedFilename,
  selectedDisplayName,
  confidence,
  onConfidenceChange,
  onReset,
  onFileSelected,
  onSelectSourceVideo,
  onStartProcessing,
  processing,
}: VideoSectionProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [showSources, setShowSources] = useState(false);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [sourceVideos, setSourceVideos] = useState<{ file_path: string; file_name: string }[]>([]);
  const [sourcesError, setSourcesError] = useState<string | null>(null);

  // New interactive state
  const [mode, setMode] = useState<'normal' | 'ai'>('ai');
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [aiInspectorOpen, setAiInspectorOpen] = useState(false);
  const [demoActive, setDemoActive] = useState(false);
  const [demoDone, setDemoDone] = useState(false);
  const [demoProgress, setDemoProgress] = useState(0);
  const [frameNo, setFrameNo] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [frameTick, setFrameTick] = useState(0);
  const demoNonce = useRef(0);

  useEffect(() => {
    if (selectedDisplayName) setSelectedFileName(selectedDisplayName);
  }, [selectedDisplayName]);

  // Reset local interactive state when the source/job changes
  useEffect(() => {
    setMode('ai');
    setInspectorOpen(false);
    setAiInspectorOpen(false);
    setDemoActive(false);
    setDemoDone(false);
    setDemoProgress(0);
    setFrameNo(0);
    setDuration(0);
  }, [videoPath, job?.job_id]);

  const result = job?.status === 'completed' ? (job.result ?? null) : null;
  const hasResult = result !== null;
  const verdict = hasResult ? getVerdict(result) : null;

  const processedSrc =
    hasResult && result.output_video_filename ? api.videoUrl(result.output_video_filename) : null;
  const originalSrc = videoPath ? api.sourceUrl(videoPath) : null;
  const displayName = selectedDisplayName ?? selectedFilename ?? 'Video';

  const sourceFps =
    result?.stats?.video_fps && result.stats.video_fps > 0 ? result.stats.video_fps : 30;
  const totalFrames =
    Math.round(duration * sourceFps) || result?.stats?.frames_processed || 0;

  const handleReplay = () => {
    const v = videoRef.current;
    if (v) {
      v.currentTime = 0;
      v.pause();
      v.play().catch(() => {});
    }
  };

  const handleFile = async (file: File) => {
    setIsUploading(true);
    setSelectedFileName(file.name);
    try {
      await onFileSelected(file);
    } finally {
      setIsUploading(false);
    }
  };

  const handleTime = () => {
    const v = videoRef.current;
    if (!v) return;
    const d = v.duration || 0;
    setDuration((prev) => (Math.abs(prev - d) < 0.05 ? prev : d));
    const f = Math.round(v.currentTime * sourceFps);
    setFrameNo((prev) => (prev === f ? prev : f));
    if (demoActive) {
      const p = d > 0 ? Math.min(1, v.currentTime / d) : 0;
      setDemoProgress(p);
    }
  };

  // Each real frame change advances the film-cell ticker + flashes the counter.
  useEffect(() => {
    setFrameTick((t) => t + 1);
  }, [frameNo]);

  const handleEnded = () => {
    if (demoActive) {
      setDemoDone(true);
      setDemoActive(false);
    }
  };

  const startDemo = () => {
    if (!processedSrc) return;
    demoNonce.current += 1;
    setDemoDone(false);
    setDemoActive(true);
    setDemoProgress(0);
    setMode('ai');
    setAiInspectorOpen(true);
  };

  const exitDemo = () => {
    setDemoActive(false);
    setDemoDone(false);
  };

  useEffect(() => {
    if (!demoActive) return;
    const v = videoRef.current;
    if (v) void v.play().catch(() => {});
  }, [demoActive, mode, demoNonce.current]);

  const handleSeek = (delta: number) => {
    const v = videoRef.current;
    if (!v) return;
    const step = delta / (sourceFps || 30);
    v.currentTime = Math.max(0, Math.min(v.duration || 0, v.currentTime + step));
  };

  const handleSeekFrame = (frame: number) => {
    const v = videoRef.current;
    if (!v || !(v.duration > 0)) return;
    const maxFrame = Math.max(0, Math.round(v.duration * sourceFps) - 1);
    v.currentTime = Math.max(0, Math.min(frame, maxFrame)) / (sourceFps || 30);
  };

  const showOverlays = hasResult && mode === 'normal';
  const currentSrc = hasResult && mode === 'ai' && processedSrc ? processedSrc : originalSrc;
  const videoKey = `${currentSrc}|${demoNonce.current}`;

  // Keep the video playback rate in sync with the slow-mo selector.
  useEffect(() => {
    const v = videoRef.current;
    if (v) v.playbackRate = speed;
  }, [speed, currentSrc, demoNonce.current]);

  const stats = result?.stats;
  const collisions = (stats?.collision_count ?? 0) > 0;

  const loadSources = async () => {
    setSourcesError(null);
    setSourcesLoading(true);
    try {
      const [summary, local] = await Promise.all([
        api.datasetSummary().catch(() => ({ videos: [] as never[] })),
        api.localVideos().catch(() => ({ videos: [] as never[] })),
      ]);
      const fromSummary = (summary.videos as { file_path: string; file_name: string }[]).map((v) => ({
        file_path: v.file_path,
        file_name: v.file_name,
      }));
      const fromLocal = (local.videos as { path: string; filename: string }[]).map((v) => ({
        file_path: v.path,
        file_name: v.filename,
      }));
      const seen = new Set<string>();
      const merged = [...fromSummary, ...fromLocal].filter((v) => {
        if (!v.file_path || seen.has(v.file_path)) return false;
        seen.add(v.file_path);
        return true;
      });
      setSourceVideos(merged);
      if (merged.length === 0) {
        setSourcesError('No source videos available yet. Upload a video or download a dataset.');
      }
    } catch (err) {
      setSourcesError(err instanceof Error ? err.message : 'Failed to load sources');
    } finally {
      setSourcesLoading(false);
    }
  };

  const toggleSources = () => {
    const next = !showSources;
    setShowSources(next);
    if (next && sourceVideos.length === 0) void loadSources();
  };

  const pickRandomSource = async () => {
    setSourcesError(null);
    setSourcesLoading(true);
    try {
      const res = await api.datasetRandom('all', 1, '');
      if (res.videos.length === 0) {
        setSourcesError('No source videos matched.');
        return;
      }
      const v = res.videos[0];
      onSelectSourceVideo?.({ file_path: v.file_path, file_name: v.file_name, display_name: v.file_name });
    } catch (err) {
      setSourcesError(err instanceof Error ? err.message : 'Random pick failed');
    } finally {
      setSourcesLoading(false);
    }
  };

  return (
    <section className="space-y-4">
      {/* Title bar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-hud text-lg font-bold tracking-wide text-hud-text">ROAD VIEW MONITOR</h2>
        {hasResult && mode === 'ai' && processedSrc ? (
          <span className="font-hud text-xs tracking-widest text-hud-cyan">● AI-ANNOTATED OUTPUT</span>
        ) : hasResult ? (
          <span className="font-hud text-xs tracking-widest text-hud-amber">● ORIGINAL — INFERENCE VIEW</span>
        ) : originalSrc ? (
          <span className="font-hud text-xs tracking-widest text-hud-green">● ORIGINAL — READY</span>
        ) : null}
      </div>

      {/* Video monitor */}
      <div className="overflow-hidden rounded-xl border border-hud-border bg-hud-panel shadow-hud">
        <div className="relative aspect-video w-full bg-hud-bg">
          {currentSrc ? (
            <>
              <video
                key={videoKey}
                ref={videoRef}
                src={currentSrc}
                className="h-full w-full object-contain"
                controls
                playsInline
                muted
                onTimeUpdate={handleTime}
                onLoadedMetadata={(e) => {
                  const d = e.currentTarget.duration || 0;
                  setDuration((prev) => (Math.abs(prev - d) < 0.05 ? prev : d));
                  if (demoActive && e.currentTarget.paused) void e.currentTarget.play().catch(() => {});
                }}
                onEnded={handleEnded}
              />
              {/* Soft frame scanline — makes the live image feel scanned frame-by-frame */}
              <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-t-xl">
                <div className="hud-anim-scanline-soft absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-hud-cyan/20 to-transparent" />
              </div>
              {hasResult && (
                <VideoOverlays result={result} showSchematic={showOverlays} />
              )}

              {/* Frame counter chip — film-cell ticker advances on every real frame change */}
              {hasResult && !demoActive && !demoDone && (
                <div className="absolute bottom-3 left-3 flex items-center gap-2 rounded border border-hud-border bg-hud-bg/70 px-2 py-1 backdrop-blur-sm">
                  <span key={frameTick} className="hud-anim-frameFlash font-mono text-[11px] font-bold text-hud-cyan">
                    FRM {frameNo.toLocaleString()}
                  </span>
                  {totalFrames > 0 && (
                    <span className="font-mono text-[10px] text-hud-dim">/ {totalFrames.toLocaleString()}</span>
                  )}
                  <span className="relative flex h-3 w-8 items-stretch gap-[2px] overflow-hidden">
                    {[0, 1, 2, 3].map((i) => (
                      <span key={i} className={`flex-1 rounded-[1px] ${i % 2 ? 'bg-hud-cyan/15' : 'bg-hud-cyan/25'}`} />
                    ))}
                    <span
                      className="absolute inset-y-[1px] w-1/4 rounded-[1px] bg-hud-cyan shadow-glowCyan transition-all duration-150"
                      style={{ left: `calc(${(frameTick % 4) * 25}% + 1px)` }}
                    />
                  </span>
                </div>
              )}

              {/* Demo-mode ribbon */}
              {demoActive && (
                <div className="absolute inset-x-0 bottom-0 bg-hud-bg/85 px-3 py-2 backdrop-blur-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 font-hud text-[10px] font-semibold tracking-widest text-hud-amber">
                      <span className="h-1.5 w-1.5 rounded-full bg-hud-amber hud-anim-blink" />
                      DEMO MODE — PLAYBACK OVERLAY
                    </span>
                    <span className="font-hud text-[10px] text-hud-dim">
                      {Math.round(demoProgress * 100)}% PLAYED
                    </span>
                  </div>
                  <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-hud-border">
                    <div
                      className="h-full bg-gradient-to-r from-hud-cyan to-hud-blue transition-all duration-200"
                      style={{ width: `${Math.min(100, demoProgress * 100)}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Demo completion card */}
              {demoDone && verdict && (
                <div className="absolute inset-0 flex items-center justify-center bg-hud-bg/85 backdrop-blur-sm">
                  <div className="w-full max-w-md rounded-xl border border-hud-border bg-hud-panel p-5 shadow-hud">
                    <div className="hud-label mb-1">WHOLE-VIDEO VERDICT</div>
                    <div
                      className="font-hud text-2xl font-bold uppercase leading-tight"
                      style={{ color: VERDICT_STYLE[verdict.level]?.color ?? '#64748B', textShadow: VERDICT_STYLE[verdict.level]?.glow }}
                    >
                      {verdict.label}
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-hud-dim">{verdict.reason}</p>
                    <div className="mt-3 grid grid-cols-3 gap-2 border-t border-hud-border/60 pt-3 text-center">
                      <MiniStat label="Frames" value={stats ? stats.frames_processed.toLocaleString() : '—'} />
                      <MiniStat label="Tracks" value={stats ? stats.total_unique_tracks.toLocaleString() : '—'} />
                      <MiniStat label="Conflicts" value={stats ? stats.collision_count?.toString() ?? '0' : '—'} accent={collisions ? 'text-hud-red' : 'text-hud-green'} />
                    </div>
                    <div className="mt-4 flex gap-2">
                      <button type="button" onClick={startDemo} className="btn-hud !py-2 !text-xs">
                        <RefreshCw className="h-3.5 w-3.5" /> Re-run Demo
                      </button>
                      <button type="button" onClick={exitDemo} className="btn-hud-secondary !py-2 !text-xs">
                        <X className="h-3.5 w-3.5" /> Exit
                      </button>
                    </div>
                    <p className="mt-2 font-hud text-[9px] tracking-wider text-hud-dim">REAL BACKEND VERDICT · FRONTEND PRESENTATION OVERLAY</p>
                  </div>
                </div>
              )}

              {/* Processing overlay */}
              {processing && (
                <div className="absolute inset-0 flex items-center justify-center bg-hud-bg/80 backdrop-blur-sm">
                  <div className="flex flex-col items-center gap-3">
                    <Loader2 className="h-8 w-8 animate-spin text-hud-cyan" />
                    <div className="font-hud font-semibold text-hud-text">{job?.step ?? 'Processing…'}</div>
                    {job && (
                      <div className="w-72">
                        <div className="h-2 overflow-hidden rounded-full bg-hud-border">
                          <div
                            className="h-full bg-gradient-to-r from-hud-cyan to-hud-blue transition-all shadow-glowCyan"
                            style={{ width: `${Math.round(job.progress * 100)}%` }}
                          />
                        </div>
                        <div className="mt-1 flex justify-between font-hud text-xs text-hud-dim">
                          <span>FRAME {job.frame.toLocaleString()} / {job.total.toLocaleString()}</span>
                          <span className="text-hud-cyan">{Math.round(job.progress * 100)}%</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center gap-3 text-center text-hud-dim">
              <VideoIcon className="h-12 w-12 text-hud-dim" />
              <p className="font-hud text-hud-text">
                {videoPath
                  ? `${displayName} ready. Click START ANALYSIS to begin.`
                  : 'Upload a traffic video to begin AI analysis.'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* "WHAT THE AI SEES" view-mode + demo bar */}
      {hasResult && (
        <div className="hud-panel flex flex-wrap items-center gap-2 p-3">
          <span className="hud-label mr-1">WHAT THE AI SEES</span>
          <button
            type="button"
            onClick={() => setMode('normal')}
            className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 font-hud text-xs font-semibold tracking-wider transition ${
              mode === 'normal'
                ? 'border-hud-cyan/50 bg-hud-cyan/15 text-hud-cyan shadow-glowCyan'
                : 'border-hud-border bg-hud-bg/50 text-hud-dim hover:text-hud-text'
            }`}
          >
            <Eye className="h-3.5 w-3.5" /> NORMAL VIEW
          </button>
          <button
            type="button"
            onClick={() => setMode('ai')}
            className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 font-hud text-xs font-semibold tracking-wider transition ${
              mode === 'ai'
                ? 'border-hud-green/50 bg-hud-green/15 text-hud-green shadow-glowGreen'
                : 'border-hud-border bg-hud-bg/50 text-hud-dim hover:text-hud-text'
            }`}
          >
            ● AI VIEW
          </button>

          <span className="mx-2 hidden h-6 w-px bg-hud-border sm:block" />

          <button
            type="button"
            onClick={startDemo}
            disabled={demoActive}
            className="btn-hud !px-3 !py-1.5 !text-xs"
          >
            {demoActive ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MonitorPlay className="h-3.5 w-3.5" />}
            Judge Demo Mode
          </button>
          <button
            type="button"
            onClick={() => setInspectorOpen(true)}
            className="btn-hud-secondary !px-3 !py-1.5 !text-xs"
          >
            <ScanSearch className="h-3.5 w-3.5" /> Frame Inspector
          </button>
          <span className="ml-auto hidden items-center gap-1 font-hud text-[10px] tracking-widest text-hud-dim lg:flex">
            <ChevronRight className="h-3 w-3 text-hud-cyan" /> NORMAL = real-time readouts · AI = backend-annotated boxes
          </span>
        </div>
      )}

      {/* Frame navigation & playback options */}
      {currentSrc && (
        <FrameControls
          currentFrame={frameNo}
          totalFrames={totalFrames}
          onSeekFrame={handleSeekFrame}
          speed={speed}
          onSpeedChange={setSpeed}
          onOpenInspector={() => setAiInspectorOpen(true)}
        />
      )}

      {/* Live AI pipeline tracker (real job stages, or demo-synced timeline) */}
      <AIPipeline job={job} processing={processing} demoActive={demoActive} demoProgress={demoProgress} />

      {/* Controls Deck */}
      <div className="hud-panel p-5">
        <div className="flex flex-wrap items-center gap-4">
          <div className="min-w-[220px] flex-1">
            <label className="hud-label mb-2 block">VIDEO SOURCE</label>
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="video/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    setSelectedFileName(file.name);
                    handleFile(file);
                    e.target.value = '';
                  }
                }}
              />
              <button
                type="button"
                id="video-upload-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading || processing}
                className="btn-hud"
              >
                {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                Upload Video
              </button>

              <button type="button" onClick={toggleSources} disabled={isUploading || processing} className="btn-hud-secondary">
                <Database className="h-4 w-4" />
                Sources
              </button>

              <button type="button" onClick={pickRandomSource} disabled={sourcesLoading || processing} className="btn-hud-secondary">
                {sourcesLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shuffle className="h-4 w-4" />}
                Random
              </button>

              {selectedFileName && (
                <span className="max-w-[200px] truncate font-hud text-xs text-hud-dim" title={selectedFileName}>
                  {selectedFileName}
                </span>
              )}
            </div>

            {showSources && (
              <div className="mt-3 rounded-lg border border-hud-border bg-hud-bg/50 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-hud text-xs tracking-wider text-hud-text">AVAILABLE SOURCE VIDEOS</span>
                  <button
                    type="button"
                    onClick={loadSources}
                    disabled={sourcesLoading}
                    className="rounded-md border border-hud-border bg-hud-panel px-2 py-1 text-xs text-hud-text hover:border-hud-cyan/40"
                  >
                    <RefreshCw className={`mr-1 inline h-3 w-3 ${sourcesLoading ? 'animate-spin' : ''}`} />
                    Refresh
                  </button>
                </div>
                {sourcesError && <p className="text-xs text-hud-red">{sourcesError}</p>}
                {sourceVideos.length > 0 && (
                  <ul className="max-h-40 space-y-1 overflow-y-auto">
                    {sourceVideos.map((v) => (
                      <li key={v.file_path}>
                        <button
                          type="button"
                          disabled={processing}
                          onClick={() =>
                            onSelectSourceVideo?.({
                              file_path: v.file_path,
                              file_name: v.file_name,
                              display_name: v.file_name,
                            })
                          }
                          className="w-full truncate rounded-md px-2 py-1 text-left font-hud text-xs text-hud-dim hover:bg-hud-panel hover:text-hud-cyan disabled:opacity-50"
                          title={v.file_path}
                        >
                          {v.file_name}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <div>
            <label className="hud-label mb-2 flex items-center gap-1.5">
              <Gauge className="h-3.5 w-3.5 text-hud-cyan" />
              DETECTION CONFIDENCE
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0.1}
                max={1.0}
                step={0.05}
                value={confidence}
                onChange={(e) => onConfidenceChange(Number(e.target.value))}
                className="w-36"
              />
              <span className="w-12 text-center font-hud text-xl font-bold text-hud-cyan">
                {confidence.toFixed(2)}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={!videoPath || processing}
              onClick={onStartProcessing}
              className="btn-hud !border-hud-green/40 !bg-hud-green/10 !text-hud-green hover:!bg-hud-green/20"
            >
              {processing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Start Analysis
            </button>
            <button type="button" disabled={!videoPath} onClick={onReset} className="btn-hud-secondary">
              <RotateCcw className="h-4 w-4" />
              Reset
            </button>
          </div>
        </div>
      </div>

      {/* Compact processing summary */}
      {hasResult && stats && (
        <div className="hud-panel p-4">
          <div className="hud-label mb-2">Processing Summary</div>
          <div className="grid grid-cols-2 gap-2 font-hud text-sm lg:grid-cols-4">
            <div><span className="text-hud-dim">Frames: </span><span className="font-bold text-hud-text">{stats.frames_processed.toLocaleString()}</span></div>
            <div><span className="text-hud-dim">Time: </span><span className="font-bold text-hud-text">{stats.processing_time}</span></div>
            <div><span className="text-hud-dim">FPS: </span><span className="font-bold text-hud-cyan">{stats.processing_fps.toFixed(1)}</span></div>
            <div><span className="text-hud-dim">Tracks: </span><span className="font-bold text-hud-text">{stats.total_unique_tracks}</span></div>
            <div><span className="text-hud-dim">Detections: </span><span className="font-bold text-hud-text">{stats.total_detections.toLocaleString()}</span></div>
            <div>
              <span className="text-hud-dim">Collisions: </span>
              <span className={`font-bold ${collisions ? 'text-hud-red' : 'text-hud-green'}`}>{stats.collision_count ?? 0}</span>
            </div>
            <div className="col-span-2">
              <span className="text-hud-dim">Types: </span>
              <span className="text-hud-text">{Object.keys(stats.class_counts ?? {}).map((k) => k).join(', ') || '—'}</span>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 border-t border-hud-border pt-3">
            {processedSrc && (
              <button type="button" onClick={handleReplay} className="btn-hud-secondary !py-1.5 !text-xs">
                <RefreshCw className="h-3.5 w-3.5" /> Replay
              </button>
            )}
            {processedSrc && (
              <button type="button" onClick={startDemo} className="btn-hud-secondary !py-1.5 !text-xs">
                <MonitorPlay className="h-3.5 w-3.5" /> Panel Demo
              </button>
            )}
            {verdict && verdict.collision_risk_detected && (
              <span className="ml-auto inline-flex items-center gap-1.5 rounded border border-hud-amber/40 bg-hud-amber/10 px-2 py-1 font-hud text-[10px] tracking-widest text-hud-amber">
                <CheckCircle2 className="h-3 w-3" /> {verdict.label.toUpperCase()} — SEE EVENT LOG
              </span>
            )}
          </div>
        </div>
      )}

      <FrameInspector
        result={result}
        open={inspectorOpen}
        onClose={() => setInspectorOpen(false)}
        currentFrame={frameNo}
        totalFrames={totalFrames}
        videoFps={sourceFps}
        onSeek={handleSeek}
      />

      <AIFrameInspector
        job={job}
        open={aiInspectorOpen}
        onClose={() => setAiInspectorOpen(false)}
        videoSrc={processedSrc}
        fps={sourceFps}
        totalFrames={totalFrames}
        autoPlay={demoActive}
        sourcePath={videoPath}
      />
    </section>
  );
}

function MiniStat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <div className="font-hud text-lg font-bold text-hud-text">{value}</div>
      <div className={`font-hud text-[9px] tracking-widest ${accent ?? 'text-hud-dim'}`}>{label}</div>
    </div>
  );
}