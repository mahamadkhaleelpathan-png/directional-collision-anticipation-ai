import { useMemo, useRef } from 'react';
import { Film, CheckCircle2, XCircle } from 'lucide-react';
import type { JobSnapshot } from '../types';

interface AIPipelineProps {
  job: JobSnapshot | null;
  processing: boolean;
  /** When true, the pipeline display is driven by demoProgress (frontend-only visualization). */
  demoActive: boolean;
  /** 0..1 playback fraction of the annotated video. */
  demoProgress: number;
}

export function AIPipeline({ job, processing, demoActive, demoProgress }: AIPipelineProps) {
  const isDemo = demoActive;
  const failed = job?.status === 'error';
  const completedAll = !failed && job?.status === 'completed';

  const total = job?.total ?? 0;
  const cur = useMemo(() => {
    if (isDemo) return Math.round(demoProgress * Math.max(total, Math.max(job?.result?.stats?.frames_processed ?? 0, 1)));
    if (completedAll) {
      return (
        job?.result?.stats?.frames_processed ??
        job?.stats?.frames_processed ??
        job?.frame ??
        0
      );
    }
    return job?.frame ?? 0;
  }, [isDemo, demoProgress, total, completedAll, job]);

  const stage = (job?.stage ?? '').toString();
  const step = job?.step ?? null;

  const progress = isDemo
    ? Math.min(1, demoProgress * 1.1)
    : failed
      ? job?.progress
      : completedAll
        ? 1
        : (job?.progress ?? 0);

  // Observed frame feed rate (real mode only) — computed from progress polls.
  const rateRef = useRef(0);
  const lastFrameRef = useRef<number | null>(null);
  const lastTimeRef = useRef(0);
  useMemo(() => {
    if (!processing || isDemo || job?.status !== 'running') return;
    const now = Date.now();
    const f = job.frame ?? 0;
    if (lastFrameRef.current !== null && f !== lastFrameRef.current) {
      const dt = (now - lastTimeRef.current) / 1000;
      if (dt > 0.05) {
        const inst = (f - lastFrameRef.current) / dt;
        rateRef.current = inst > 0 ? rateRef.current * 0.6 + inst * 0.4 : rateRef.current;
      }
    }
    lastFrameRef.current = f;
    lastTimeRef.current = now;
  }, [processing, isDemo, job?.frame, job?.status]);
  const observedRate = Math.round(rateRef.current);

  const showFlow = !!job || isDemo;

  return (
    <section className="hud-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-hud-border/60 px-4 py-3">
        <h3 className="hud-label flex items-center gap-2">
          <Film className="h-4 w-4 text-hud-cyan" />
          AI Perception Pipeline
        </h3>
        {processing ? (
          <span className="flex items-center gap-1.5 rounded-full border border-hud-amber/30 bg-hud-amber/10 px-2.5 py-0.5 font-hud text-[10px] font-semibold tracking-widest text-hud-amber">
            <span className="h-1.5 w-1.5 rounded-full bg-hud-amber hud-anim-blink" />
            LIVE
          </span>
        ) : completedAll ? (
          <span className="flex items-center gap-1.5 rounded-full border border-hud-green/30 bg-hud-green/10 px-2.5 py-0.5 font-hud text-[10px] font-semibold tracking-widest text-hud-green">
            <CheckCircle2 className="h-3 w-3" />
            COMPLETE
          </span>
        ) : failed ? (
          <span className="flex items-center gap-1.5 rounded-full border border-hud-red/30 bg-hud-red/10 px-2.5 py-0.5 font-hud text-[10px] font-semibold tracking-widest text-hud-red">
            <XCircle className="h-3 w-3" />
            FAILED
          </span>
        ) : (
          <span className="rounded-full border border-hud-border bg-hud-bg/50 px-2.5 py-0.5 font-hud text-[10px] font-semibold tracking-widest text-hud-dim">
            STANDBY
          </span>
        )}
      </div>

      <div className="px-4 py-4">
        {showFlow && (
          <div className="mb-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="flex items-center gap-2 font-hud text-[10px] tracking-widest text-hud-dim">
                <span className={`h-2 w-2 rounded-full ${processing ? 'bg-hud-amber hud-anim-blink' : completedAll ? 'bg-hud-green' : 'bg-hud-dim'}`} />
                {isDemo ? 'DEMO REPLAY — FRONTEND TIMELINE' : completedAll ? 'FRAME STREAM — COMPLETE' : 'FRAME STREAM'}
              </span>
              <span className="font-hud text-sm font-bold text-hud-cyan" style={{ textShadow: '0 0 8px rgba(34,211,238,0.5)' }}>
                {completedAll ? 'ALL FRAMES' : cur.toLocaleString()}
                <span className="text-hud-dim"> / {total > 0 ? total.toLocaleString() : '—'}</span>
              </span>
              {processing && !isDemo && observedRate > 0 && (
                <span className="font-hud text-[9px] tracking-widest text-hud-dim">~{observedRate} f/s FEED</span>
              )}
            </div>

            {/* Progress bar */}
            <div className="mt-2">
              <div className="h-2 overflow-hidden rounded-full bg-hud-border/70">
                <div
                  className={`h-full transition-all duration-300 ${
                    failed ? 'bg-hud-red' : 'bg-gradient-to-r from-hud-cyan to-hud-blue shadow-glowCyan'
                  }`}
                  style={{ width: `${Math.max(0, Math.min(100, (progress ?? 0) * 100))}%` }}
                />
              </div>
              <div className="mt-1 flex justify-between font-hud text-[9px] tracking-wider text-hud-dim">
                <span>{Math.round((progress ?? 0) * 100)}%</span>
                {!isDemo && (
                  <span>
                    FRAME {job?.frame?.toLocaleString() ?? 0} / {total.toLocaleString()}
                    {step ? ` · STEP ${step}` : ''}
                  </span>
                )}
              </div>
            </div>

            {/* Honest stage readout */}
            {!isDemo ? (
              <div className="mt-3 rounded-lg border border-hud-border/60 bg-hud-bg/40 px-3 py-2.5">
                {failed ? (
                  <p className="font-hud text-[11px] font-semibold tracking-widest text-hud-red">
                    PROCESSING FAILED — {job?.error ?? 'unknown error'}
                  </p>
                ) : completedAll ? (
                  <p className="flex items-center gap-2 font-hud text-[11px] font-semibold tracking-widest text-hud-green">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    ALL PIPELINE STAGES COMPLETE — {job?.result?.stats?.frames_processed?.toLocaleString() ?? '—'} FRAMES, {job?.result?.stats?.total_unique_tracks ?? '—'} TRACKS
                  </p>
                ) : processing ? (
                  <p className="flex flex-wrap items-center justify-between gap-2 font-hud text-[11px] tracking-widest">
                    <span className="text-hud-cyan">
                      {stage ? `CURRENT STAGE ▸ ${stage}` : 'INITIALIZING…'}
                    </span>
                    {job?.progress !== undefined && (
                      <span className="text-hud-dim">{Math.round(job.progress * 100)}% COMPLETE</span>
                    )}
                  </p>
                ) : (
                  <p className="font-hud text-[11px] tracking-widest text-hud-dim">
                    PIPELINE STANDBY — UPLOAD A VIDEO AND START ANALYSIS
                  </p>
                )}
              </div>
            ) : (
              <p className="mt-3 font-hud text-[9px] tracking-wider text-hud-dim">
                PLAYBACK SYNCHRONIZED VISUALIZATION · FRONTEND TIMELINE (DEMO)
              </p>
            )}
          </div>
        )}

        {!showFlow && (
          <p className="font-hud text-[10px] tracking-widest text-hud-dim">
            PIPELINE STANDBY — UPLOAD A VIDEO AND START ANALYSIS
          </p>
        )}
      </div>
    </section>
  );
}