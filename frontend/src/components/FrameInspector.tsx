import { useEffect } from 'react';
import { X, ChevronLeft, ChevronRight, ScanSearch } from 'lucide-react';
import type { PipelineResultPayload } from '../types';
import { hudRiskColor, isNum } from '../utils/hud';

interface FrameInspectorProps {
  result: PipelineResultPayload | null;
  open: boolean;
  onClose: () => void;
  /** 0-based frame index of the currently displayed video position. */
  currentFrame: number;
  /** Total frames inferred from video duration × source fps. */
  totalFrames: number;
  videoFps: number;
  onSeek: (deltaFrames: number) => void;
}

export function FrameInspector({
  result,
  open,
  onClose,
  currentFrame,
  totalFrames,
  videoFps,
  onSeek,
}: FrameInspectorProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft') onSeek(-1);
      if (e.key === 'ArrowRight') onSeek(1);
      if (e.key === ' ') {
        e.preventDefault();
        onSeek(videoFps > 0 ? Math.round(videoFps) : 1);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose, onSeek, videoFps]);

  if (!open) return null;

  const rows = result?.analysis_rows ?? [];
  const top = [...rows].sort((a, b) => b.max_risk_score - a.max_risk_score).slice(0, 6);
  const stats = result?.stats;
  const frameNo = Math.max(0, Math.min(currentFrame + 1, Math.max(1, totalFrames)));

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-hud-bg/80 p-4 backdrop-blur-sm">
      <div className="hud-panel w-full max-w-3xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-hud-border/60 px-5 py-3">
          <h3 className="hud-label flex items-center gap-2">
            <ScanSearch className="h-4 w-4 text-hud-cyan" />
            Frame Inspector
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-hud-border bg-hud-bg/50 p-1.5 text-hud-dim transition hover:border-hud-cyan/40 hover:text-hud-cyan"
            aria-label="Close frame inspector"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5">
          {/* Frame navigation */}
          <div className="rounded-lg border border-hud-border bg-hud-bg/50 p-3 text-center">
            <div className="font-hud text-4xl font-bold text-hud-cyan" style={{ textShadow: '0 0 12px rgba(34,211,238,0.6)' }}>
              {frameNo.toLocaleString()}
            </div>
            <div className="mt-1 font-hud text-[10px] tracking-[0.3em] text-hud-dim">
              FRAME / {totalFrames.toLocaleString()}
            </div>
            <div className="mt-2 flex items-center justify-center gap-2">
              <button type="button" onClick={() => onSeek(-1)} className="btn-hud-secondary !px-2 !py-1 !text-xs" disabled={currentFrame <= 0}>
                <ChevronLeft className="h-3.5 w-3.5" /> PREV
              </button>
              <button type="button" onClick={() => onSeek(1)} className="btn-hud-secondary !px-2 !py-1 !text-xs" disabled={currentFrame >= totalFrames - 1}>
                NEXT <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="mx-auto mt-3 h-1.5 w-full overflow-hidden rounded-full bg-hud-border/70">
              <div
                className="h-full bg-gradient-to-r from-hud-cyan to-hud-blue transition-all"
                style={{ width: `${totalFrames > 0 ? (currentFrame / totalFrames) * 100 : 0}%` }}
              />
            </div>
            <p className="mt-2 font-hud text-[9px] text-hud-dim">
              ◀ ▶ step 1 frame · SPACE +1s · ESC close
            </p>
          </div>

          {/* Object summary table (real analysis data) */}
          <div className="mt-3">
            <div className="hud-label mb-1.5">Objects (real backend analysis)</div>
            {top.length === 0 ? (
              <p className="rounded-lg border border-hud-border bg-hud-bg/40 p-3 font-hud text-[10px] text-hud-dim">
                No object summaries available yet.
              </p>
            ) : (
              <ul className="space-y-1">
                {top.map((row) => (
                  <li
                    key={`${row.track_id}`}
                    className="flex items-center gap-2 rounded-md border border-hud-border/60 bg-hud-bg/40 px-2.5 py-1.5"
                  >
                    <span className="h-2 w-2 rounded-full" style={{ background: hudRiskColor(row.risk_level), boxShadow: `0 0 6px ${hudRiskColor(row.risk_level)}` }} />
                    <span className="font-hud text-xs capitalize text-hud-text">{row.class_name}#{row.track_id}</span>
                    <span className="font-hud text-[10px] text-hud-cyan">{row.direction}</span>
                    <span className="ml-auto font-hud text-[10px] text-hud-text">{Math.round(row.max_risk_score)}/100</span>
                    <span className="font-hud text-[10px] text-hud-dim">
                      {isNum(row.estimated_ttc) ? `TTC ${(row.estimated_ttc as number).toFixed(2)}s` : '—'}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <p className="mt-3 font-hud text-[9px] leading-relaxed text-hud-dim">
            Per-frame detection boxes are drawn by the YOLO/ByteTrack backend on the annotated video. This table summarizes each tracked object across the whole clip (real analysis data). Frame stepping here scrubs the video by {videoFps > 0 ? `${videoFps.toFixed(0)}` : '—'} fps.
          </p>
        </div>

        <div className="border-t border-hud-border/60 px-5 py-2.5 text-right font-hud text-[9px] tracking-widest text-hud-dim">
          VIDEO FPS {stats?.video_fps && stats.video_fps > 0 ? `${stats.video_fps.toFixed(1)}` : 'n/a'} ·{' '}
          {(stats?.frames_processed ?? 0) > 0 ? `${stats?.frames_processed?.toLocaleString() ?? '0'} frames processed` : 'no analysis yet'}
        </div>
      </div>
    </div>
  );
}