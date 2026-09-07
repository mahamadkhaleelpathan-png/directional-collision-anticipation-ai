import { Timer } from 'lucide-react';
import { isNum, useCountUp, threatName } from '../utils/hud';
import type { PipelineResultPayload } from '../types';

interface TTCDisplayProps {
  threat: PipelineResultPayload['primary_threat'];
}

export function TTCDisplay({ threat }: TTCDisplayProps) {
  const ttc = isNum(threat?.estimated_ttc) ? (threat?.estimated_ttc as number) : null;
  const pet = isNum(threat?.estimated_pet) ? (threat?.estimated_pet as number) : null;
  const action = threat?.estimated_act && threat.estimated_act !== 'N/A' ? threat.estimated_act : null;

  const acc = ttc === null ? '#64748B' : ttc < 1 ? '#F87171' : ttc < 2 ? '#FB923C' : ttc < 3 ? '#FBBF24' : '#34D399';
  const anim = useCountUp(ttc === null ? 0 : ttc, 600);
  const frac = ttc === null ? 0 : Math.max(0, Math.min(1, ttc / 5));

  return (
    <section className="hud-panel p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="hud-label flex items-center gap-2">
          <Timer className="h-4 w-4 text-hud-cyan" />
          Time to Collision
        </h3>
        <span className="font-hud text-xs font-semibold uppercase text-hud-cyan">{threatName(threat)}</span>
      </div>

      <div className="rounded-lg border border-hud-border bg-hud-bg/50 px-4 py-3 text-center">
        <div className="font-hud text-4xl font-bold leading-none" style={{ color: acc, textShadow: `0 0 14px ${acc}` }}>
          {ttc === null ? '—' : `${anim.toFixed(2)}s`}
        </div>
        <div className="mt-1 font-hud text-[10px] tracking-[0.3em] text-hud-dim">
          {ttc === null ? 'NO THREAT ACTIVE' : 'ESTIMATED TIME TO IMPACT'}
        </div>
      </div>

      {/* Time scale */}
      <div className="mt-3">
        <div className="relative h-2 overflow-hidden rounded-full bg-hud-border/70">
          <div
            className="absolute left-1/2 top-1/2 h-px w-full bg-hud-border"
            style={{ transform: 'translateY(-50%)' }}
          />
          <div className="absolute inset-y-0 left-0 rounded-full transition-all duration-300" style={{ width: `${frac * 100}%`, background: acc, boxShadow: `0 0 10px ${acc}` }} />
          <div className="absolute inset-y-0" style={{ left: '20%', width: '1px', background: '#334155' }} />
          <div className="absolute inset-y-0" style={{ left: '40%', width: '1px', background: '#334155' }} />
          <div className="absolute inset-y-0" style={{ left: '60%', width: '1px', background: '#334155' }} />
          <div className="absolute inset-y-0" style={{ left: '80%', width: '1px', background: '#334155' }} />
        </div>
        <div className="mt-1 flex justify-between font-hud text-[9px] tracking-wider text-hud-dim">
          <span>0s IMPACT</span>
          <span>2.5s</span>
          <span>5s SAFE</span>
        </div>
      </div>

      {(pet !== null || action) && (
        <div className="mt-3 space-y-1.5 border-t border-hud-border/60 pt-2.5">
          {pet !== null && (
            <div className="flex items-center justify-between font-hud text-[11px]">
              <span className="text-hud-dim">EST. PET</span>
              <span className="font-semibold text-hud-text">{pet.toFixed(2)}s</span>
            </div>
          )}
          {action ? (
            <div className="flex items-center justify-between gap-2 font-hud text-[11px]">
              <span className="text-hud-dim">RECOMMENDED ACTION</span>
              <span className="text-right font-semibold text-hud-amber">{action}</span>
            </div>
          ) : null}
        </div>
      )}

      <p className="mt-2 font-hud text-[9px] leading-relaxed text-hud-dim">
        TTC from monocular-video motion analysis (SCHEMATIC visualization of backend estimate).
      </p>
    </section>
  );
}