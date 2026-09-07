import { ShieldCheck, AlertTriangle, Crosshair } from 'lucide-react';
import type { PipelineResultPayload } from '../types';
import { riskColor } from '../utils/format';
import { getVerdict } from '../utils/verdict';

interface CurrentThreatProps {
  result: PipelineResultPayload | null;
  live: boolean;
}

const VERDICT_STYLE: Record<string, { color: string; glow: string }> = {
  HIGH_COLLISION_RISK: { color: '#F87171', glow: '0 0 25px rgba(248,113,113,0.6)' },
  POTENTIAL_COLLISION_RISK: { color: '#FBBF24', glow: '0 0 25px rgba(251,191,36,0.6)' },
  LOW_RISK: { color: '#34D399', glow: '0 0 20px rgba(52,211,153,0.5)' },
  NO_SIGNIFICANT_RISK: { color: '#34D399', glow: '0 0 20px rgba(52,211,153,0.5)' },
  UNKNOWN: { color: '#64748B', glow: '' },
};

export function CurrentThreat({ result, live }: CurrentThreatProps) {
  const v = getVerdict(result);
  const vs = VERDICT_STYLE[v.level] ?? VERDICT_STYLE.UNKNOWN;
  const threat = result?.primary_threat ?? null;
  const stats = result?.stats;
  const hasEarlierRisk = v.collision_risk_detected || (stats?.cumulative_max_risk ?? 0) >= 20;
  const finalFrameSafe = !threat || (threat?.risk_level ?? 'SAFE') === 'SAFE';

  return (
    <div className="hud-panel p-5 hud-panel-hover">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="hud-label">Threat Analysis</h3>
        {live && (
          <span className="rounded-full border border-hud-green/30 bg-hud-green/10 px-2 py-0.5 font-hud text-[10px] font-semibold tracking-widest text-hud-green">
            FINAL FRAME
          </span>
        )}
      </div>

      {!result ? (
        <div className="flex items-center gap-3 py-2">
          <ShieldCheck className="h-6 w-6 text-hud-dim" />
          <div>
            <p className="font-hud text-sm font-semibold text-hud-text">No Analysis Yet</p>
            <p className="text-xs text-hud-dim">Upload a video and start analysis to view the threat assessment.</p>
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Whole-Video Verdict — big HUD readout */}
          <div className="rounded-lg border border-hud-border bg-hud-bg/50 p-4 text-center">
            <div className="hud-label mb-1">Whole-Video Verdict</div>
            <div
              className="font-hud text-2xl font-bold uppercase leading-tight"
              style={{ color: vs.color, ...(vs.glow ? { textShadow: vs.glow } : {}) }}
            >
              {v.label}
            </div>
            <p className="mt-2 text-xs text-hud-dim leading-relaxed">{v.reason}</p>
          </div>

          {/* Earlier Risk Warning */}
          {hasEarlierRisk && finalFrameSafe && (
            <div className="flex items-start gap-3 rounded-lg border border-hud-amber/30 bg-hud-amber/10 p-3">
              <AlertTriangle className="h-4 w-4 text-hud-amber flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-hud text-xs font-semibold text-hud-amber">EARLIER RISK EVENT</p>
                <p className="text-[11px] text-hud-dim leading-relaxed">
                  Final frame is safe, but risk was detected earlier in the video. See whole-video verdict above.
                </p>
              </div>
            </div>
          )}

          {/* Final Frame Threat */}
          {threat && (threat?.risk_level ?? 'SAFE') !== 'SAFE' && (
            <div className="space-y-3 rounded-lg border border-hud-border bg-hud-bg/50 p-4">
              <div className="flex items-center gap-2">
                <Crosshair className={`h-5 w-5 ${threat.risk_level === 'CRITICAL' ? 'text-hud-red' : 'text-hud-amber'}`} />
                <span className="hud-label">Final Frame Threat</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-3 w-3 rounded-full"
                  style={{ background: riskColor(threat?.risk_level), boxShadow: `0 0 10px ${riskColor(threat?.risk_level)}` }}
                />
                <span className="font-hud text-2xl font-bold uppercase" style={{ color: riskColor(threat?.risk_level) }}>
                  {threat?.risk_level ?? '—'}
                </span>
              </div>
              <div className="font-hud text-xl font-semibold capitalize text-hud-text">
                {threat?.object_type ?? threat?.class_name ?? '—'}
              </div>
              {threat?.direction && (
                <div className="font-hud text-sm tracking-widest text-hud-cyan">
                  APPROACHING FROM {threat.direction.toUpperCase()}
                </div>
              )}
              {typeof threat?.estimated_ttc === 'number' && Number.isFinite(threat.estimated_ttc) ? (
                <div className="font-hud text-sm text-hud-text">
                  EST. TTC <span className="font-bold text-hud-red">{threat.estimated_ttc.toFixed(2)}s</span>
                </div>
              ) : (
                <div className="font-hud text-sm text-hud-dim">EST. TTC —</div>
              )}
            </div>
          )}

          {threat && (threat?.risk_level ?? 'SAFE') === 'SAFE' && (
            <div className="flex items-center gap-2 py-1">
              <span className="h-3 w-3 rounded-full bg-hud-green shadow-glowGreen" />
              <p className="font-hud text-sm text-hud-text">Final frame: no elevated threat detected.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
