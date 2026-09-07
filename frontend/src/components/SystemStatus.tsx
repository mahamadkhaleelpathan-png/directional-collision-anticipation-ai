import { Shield, Camera, Activity, Cpu, CircleDot } from 'lucide-react';
import type { PipelineStats } from '../types';
import { fmtFloat, fmtInt } from '../utils/format';

interface SystemStatusProps {
  status: 'idle' | 'live' | 'processing';
  stats: PipelineStats | null;
  hasVideo: boolean;
}

const CFG = {
  idle: { label: 'IDLE', dot: 'bg-hud-dim', text: 'text-hud-dim' },
  live: { label: 'ACTIVE', dot: 'bg-hud-green shadow-glowGreen', text: 'text-hud-green' },
  processing: { label: 'PROCESSING', dot: 'bg-hud-amber', text: 'text-hud-amber' },
} as const;

export function SystemStatus({ status, stats, hasVideo }: SystemStatusProps) {
  const cfg = CFG[status];

  return (
    <div className="hud-panel p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="hud-label">Driver Status</h3>
        <div className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${cfg.dot}`} />
          <span className={`font-hud text-xs font-semibold tracking-widest ${cfg.text}`}>{cfg.label}</span>
        </div>
      </div>

      <div className="space-y-1">
        <Row
          icon={<Shield className="h-4 w-4 text-hud-cyan" />}
          label="SYSTEM"
          value={<span className={`font-hud text-sm font-semibold ${cfg.text}`}>{cfg.label}</span>}
        />
        <Row
          icon={<Camera className="h-4 w-4 text-hud-cyan" />}
          label="VIDEO INPUT"
          value={
            <span className={`font-hud text-sm font-semibold ${hasVideo ? 'text-hud-green' : 'text-hud-dim'}`}>
              {hasVideo ? 'LOADED' : 'NONE'}
            </span>
          }
        />
        <Row
          icon={<Activity className="h-4 w-4 text-hud-cyan" />}
          label="PROCESSING FPS"
          value={
            <span className="font-hud text-xl font-bold text-hud-cyan">
              {stats ? fmtFloat(stats.processing_fps, 1) : '—'}
            </span>
          }
        />
        <Row
          icon={<Cpu className="h-4 w-4 text-hud-cyan" />}
          label="DETECTIONS"
          value={
            <span className="font-hud text-xl font-bold text-hud-cyan">
              {stats ? fmtInt(stats.total_detections) : '—'}
            </span>
          }
        />
        <Row
          icon={<CircleDot className="h-4 w-4 text-hud-green" />}
          label="TRACKS"
          value={
            <span className="font-hud text-xl font-bold text-hud-green">
              {stats ? fmtInt(stats.total_unique_tracks) : '—'}
            </span>
          }
        />
      </div>
    </div>
  );
}

function Row({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between border-b border-hud-border/50 py-2.5 last:border-0">
      <div className="flex items-center gap-2.5">
        {icon}
        <span className="font-hud text-xs tracking-wider text-hud-dim">{label}</span>
      </div>
      {value}
    </div>
  );
}
