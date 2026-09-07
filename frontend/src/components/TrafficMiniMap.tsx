import { Radar } from 'lucide-react';
import type { PipelineResultPayload } from '../types';
import { isNum } from '../utils/hud';
import { riskColor } from '../utils/format';

interface TrafficMiniMapProps {
  result: PipelineResultPayload | null;
}

function riskFill(score: number | undefined): string {
  const s = score ?? 0;
  if (s >= 75) return '#F87171';
  if (s >= 50) return '#FB923C';
  if (s >= 25) return '#FBBF24';
  return '#34D399';
}

export function TrafficMiniMap({ result }: TrafficMiniMapProps) {
  const rows = result?.analysis_rows ?? [];
  const top = [...rows].sort((a, b) => b.max_risk_score - a.max_risk_score).slice(0, 8);

  return (
    <section className="hud-panel p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="hud-label flex items-center gap-2">
          <Radar className="h-4 w-4 text-hud-cyan" />
          Traffic Situation
        </h3>
        <span className="font-hud text-[9px] tracking-widest text-hud-amber">TRACKED OBJECTS</span>
      </div>

      {top.length === 0 ? (
        <p className="rounded-lg border border-hud-border bg-hud-bg/40 p-3 font-hud text-[10px] text-hud-dim">
          No tracked objects yet. Run analysis to populate.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {top.map((row) => {
            const risk = isNum(row.max_risk_score) ? row.max_risk_score : 0;
            const fill = riskFill(risk);
            const ttc = isNum(row.estimated_ttc) ? `${(row.estimated_ttc as number).toFixed(1)}s` : null;
            return (
              <li
                key={row.track_id}
                className="flex items-center gap-2 rounded-md border border-hud-border/60 bg-hud-bg/40 px-2.5 py-1.5"
              >
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: fill, boxShadow: `0 0 6px ${fill}` }}
                />
                <span className="font-hud text-xs capitalize text-hud-text">{row.class_name}#{row.track_id}</span>
                <span className="rounded px-1 py-0.5 text-[9px] uppercase" style={{ color: riskColor(row.risk_level), background: `${riskColor(row.risk_level)}1a` }}>
                  {row.direction}
                </span>
                {ttc && (
                  <span className="font-mono text-[9px] text-hud-dim">TTC {ttc}</span>
                )}
                <span className="ml-auto font-hud text-[10px] font-bold" style={{ color: fill }}>
                  {Math.round(risk)}/100
                </span>
                <span className="risk-pill" style={{ color: riskColor(row.risk_level) }}>{row.risk_level}</span>
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-2 font-hud text-[9px] leading-relaxed text-hud-dim">
        Real per-object analysis: class, track ID, approach direction, TTC and peak risk score from the backend. No map positions are shown because frame coordinates are not measured.
      </p>
    </section>
  );
}