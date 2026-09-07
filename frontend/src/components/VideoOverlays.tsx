import { useMemo } from 'react';
import type { PipelineResultPayload } from '../types';
import { hudRiskColor } from '../utils/hud';

interface VideoOverlaysProps {
  result: PipelineResultPayload | null;
  showSchematic: boolean;
}

export function VideoOverlays({ result, showSchematic }: VideoOverlaysProps) {
  const topThreats = useMemo(() => result?.top_threats.slice(0, 3) ?? [], [result]);
  const noneElevated = (result?.top_threats ?? []).length > 0 && (result?.top_threats ?? []).every((t) => (t.risk_score ?? 0) < 40);
  const activityLabel = result ? (showSchematic ? 'TRACKING' : 'AI-ANNOTATED OUTPUT') : 'AI-ANNOTATED OUTPUT';

  if (!result) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden">
      {/* Corner brackets */}
      <div className="absolute left-2 top-2 h-6 w-6 border-l-2 border-t-2 border-hud-cyan/80 hud-anim-bracket" />
      <div className="absolute right-2 top-2 h-6 w-6 border-r-2 border-t-2 border-hud-cyan/80 hud-anim-bracket" />
      <div className="absolute bottom-2 left-2 h-6 w-6 border-b-2 border-l-2 border-hud-cyan/80 hud-anim-bracket" />
      <div className="absolute bottom-2 right-2 h-6 w-6 border-b-2 border-r-2 border-hud-cyan/80 hud-anim-bracket" />

      {/* Scanline */}
      <div className="hud-anim-scanline absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-transparent via-hud-cyan/50 to-transparent" />

      {/* Top-left HUD readouts */}
      <div className="absolute left-4 top-4 space-y-1 font-hud text-[11px] leading-tight">
        <div className="text-hud-cyan" style={{ textShadow: '0 0 6px rgba(34,211,238,0.8)' }}>
          ● <span className="tracking-widest">{activityLabel}</span>
        </div>
        <div className="text-hud-dim">FRM {(result.stats?.frames_processed ?? 0).toLocaleString()}</div>
        <div className="text-hud-dim">TRACKS {(result.stats?.total_unique_tracks ?? 0)}</div>
      </div>

      {/* Threat chips */}
      {topThreats.length > 0 && (
        <div className="absolute right-4 top-4 space-y-1.5">
          {topThreats.map((t, i) => (
            <div
              key={`${t.tracking_id}-${i}`}
              className="flex items-center gap-2 rounded border border-hud-border bg-hud-bg/70 px-2 py-1 backdrop-blur-sm"
            >
              <span className="h-2 w-2 rounded-full" style={{ background: hudRiskColor(t.risk_level), boxShadow: `0 0 6px ${hudRiskColor(t.risk_level)}` }} />
              <span className="font-hud text-[10px] text-hud-text">
                #{i + 1} {t.class_name}#{t.tracking_id}
              </span>
              <span className="font-hud text-[9px] text-hud-dim">{Math.round(t.risk_score)}/100</span>
            </div>
          ))}
        </div>
      )}

      {/* Bottom note */}
      <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-2">
        <span className="rounded border border-hud-amber/40 bg-hud-bg/70 px-2 py-0.5 font-hud text-[9px] tracking-widest text-hud-amber">
          DETECTIONS & BOXES ARE DRAWN ON THE ANNOTATED OUTPUT
        </span>
        {noneElevated && (
          <span className="rounded border border-hud-green/40 bg-hud-bg/70 px-2 py-0.5 font-hud text-[9px] tracking-widest text-hud-green">
            NO ELEVATED THREAT
          </span>
        )}
      </div>
    </div>
  );
}