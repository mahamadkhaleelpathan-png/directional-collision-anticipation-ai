import { useEffect, useRef, useState } from 'react';
import { Terminal } from 'lucide-react';
import type { JobSnapshot } from '../types';
import { getVerdict } from '../utils/verdict';

interface EventLogProps {
  job: JobSnapshot | null;
}

type Kind = 'info' | 'cyan' | 'green' | 'amber' | 'red' | 'dim';

interface Line {
  id: number;
  time: string;
  kind: Kind;
  text: string;
}

const KIND_COLOR: Record<Kind, string> = {
  info: '#94A3B8',
  cyan: '#22D3EE',
  green: '#34D399',
  amber: '#FBBF24',
  red: '#F87171',
  dim: '#64748B',
};

function now() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
}

export function EventLog({ job }: EventLogProps) {
  const [lines, setLines] = useState<Line[]>([]);
  const [muted, setMuted] = useState(false);
  const seen = useRef<Set<string>>(new Set());
  const idRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    seen.current.clear();
    idRef.current = 0;
    setLines([]);
  }, [job?.job_id]);

  useEffect(() => {
    if (!job) return;
    const jobId = job.job_id;
    const push = (key: string, kind: Kind, text: string) => {
      if (seen.current.has(key)) return;
      seen.current.add(key);
      idRef.current += 1;
      setLines((prev) => [...prev.slice(-49), { id: idRef.current, time: now(), kind, text }]);
    };

    const keyA = (s: string) => `${jobId}-${s}`;

    if (job.status === 'running' || job.status === 'pending') {
      push(keyA('start'), 'cyan', `JOB ${jobId.slice(0, 8)} — AI pipeline started`);
      if (job.stage) push(keyA(`stage-${job.stage}`), 'amber', `STAGE ▸ ${job.stage}`);
      const p = Math.round((job.progress ?? 0) * 100);
      if (p >= 25) push(keyA('p25'), 'info', `PROGRESS ${p}% — FRAME ${job.frame.toLocaleString()}/${job.total.toLocaleString()}`);
      if (p >= 50) push(keyA('p50'), 'info', `PROGRESS ${p}% — half of frames analyzed`);
      if (p >= 75) push(keyA('p75'), 'info', `PROGRESS ${p}% — finishing analysis`);
      if (job.step && job.step !== job.stage) push(keyA(`step-${job.step}`), 'dim', `STEP ${job.step}`);
    }

    if (job.status === 'completed') {
      const result = job.result;
      const stats = result?.stats;
      push(keyA('done'), 'green', `JOB ${jobId.slice(0, 8)} — analysis complete`);
      if (result) {
        const v = getVerdict(result);
        push(keyA('verdict'), v.collision_risk_detected ? 'red' : 'green', `VERDICT ${v.label}`);
        push(keyA('vreason'), 'info', `REASON ${v.reason}`);
      }
      if (stats) {
        push(keyA('frames'), 'cyan', `FRAMES PROCESSED ${stats.frames_processed.toLocaleString()} @ ${stats.processing_fps.toFixed(1)} FPS`);
        push(keyA('tracks'), 'info', `UNIQUE TRACKS ${stats.total_unique_tracks} · DETECTIONS ${stats.total_detections.toLocaleString()}`);
        const col = stats.collision_count ?? 0;
        if (col > 0) push(keyA('col'), 'red', `COLLISION FLAGS ${col} — see frame inspector`);
        else push(keyA('nocol'), 'green', 'NO CONFLICT FRAMES FLAGGED');
      }
    }

    if (job.status === 'error') {
      push(keyA('err'), 'red', `PROCESSING FAILED — ${job.error ?? 'unknown error'}`);
    }
  }, [job]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  return (
    <section className="hud-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-hud-border/60 px-4 py-2.5">
        <h3 className="hud-label flex items-center gap-2">
          <Terminal className="h-4 w-4 text-hud-cyan" />
          Event Log
        </h3>
        <button
          type="button"
          onClick={() => setMuted((m) => !m)}
          className="rounded border border-hud-border bg-hud-bg/50 px-2 py-0.5 font-hud text-[9px] tracking-widest text-hud-dim hover:text-hud-cyan"
        >
          {muted ? 'UNMUTE' : 'MUTE'}
        </button>
      </div>

      <div ref={scrollRef} className="h-44 overflow-y-auto px-3 py-2 font-mono text-[10px] leading-relaxed">
        {lines.length === 0 ? (
          <p className="py-6 text-center text-hud-dim">SYSTEM LOG EMPTY — AWAITING ANALYSIS</p>
        ) : (
          lines.map((l) => (
            <div key={l.id} className="flex gap-2" style={{ color: muted && l.kind === 'dim' ? '#1E293B' : KIND_COLOR[l.kind] }}>
              <span className="shrink-0 text-hud-dim/60">[{l.time}]</span>
              <span className="break-words">{l.text}</span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}