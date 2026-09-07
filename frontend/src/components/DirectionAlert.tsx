import { ArrowLeft, ArrowRight, ArrowUp, AlertTriangle, ShieldCheck } from 'lucide-react';
import type { PrimaryThreat } from '../types';
import { hudRiskColor, threatName, isNum } from '../utils/hud';

interface DirectionAlertProps {
  threat: PrimaryThreat | null;
  verdictThreat: boolean;
}

function levelOf(threat: PrimaryThreat | null): string {
  if (!threat) return 'NONE';
  return (threat.risk_level ?? 'SAFE').toString();
}

export function DirectionAlert({ threat, verdictThreat }: DirectionAlertProps) {
  const level = levelOf(threat);
  const critical = level === 'CRITICAL';
  const high = level === 'HIGH';
  const medium = level === 'MEDIUM';
  const active = critical || high || medium;
  const dir = (threat?.direction ?? '').toUpperCase();
  const name = threatName(threat);
  const ttc = isNum(threat?.estimated_ttc) ? `${(threat?.estimated_ttc as number).toFixed(2)}s` : null;

  const Arrow =
    dir === 'LEFT' ? ArrowLeft : dir === 'RIGHT' ? ArrowRight : ArrowUp;
  const arrowAnim =
    dir === 'LEFT' ? 'hud-anim-arrow-l' : dir === 'RIGHT' ? 'hud-anim-arrow-r' : 'hud-anim-arrow-u';

  const accent = hudRiskColor(level);

  const message = critical
    ? `COLLISION ALERT — ${name.toUpperCase()} APPROACHING FROM ${dir || 'AHEAD'}`
    : high
      ? `HIGH THREAT — ${name.toUpperCase()} FROM ${dir || 'AHEAD'}`
      : medium
        ? `CAUTION — ${name.toUpperCase()} FROM ${dir || 'AHEAD'}`
        : 'NO ELEVATED THREAT — MONITORING ENVIRONMENT';

  return (
    <section
      className={`relative overflow-hidden rounded-xl border transition-colors ${
        critical ? 'hud-anim-screenpulse' : ''
      }`}
      style={{
        borderColor: `${accent}66`,
        background: `linear-gradient(90deg, ${accent}1a 0%, rgba(15,23,42,0.9) 35%, rgba(15,23,42,0.9) 65%, ${accent}1a 100%)`,
      }}
    >
      <div className="flex items-stretch gap-3 px-4 py-3">
        {/* Arrow cluster */}
        <div
          className={`flex w-16 items-center justify-center rounded-lg border`}
          style={{ borderColor: `${accent}44`, background: `${accent}14` }}
        >
          {active ? (
            <Arrow className={`h-8 w-8 ${arrowAnim}`} style={{ color: accent, filter: `drop-shadow(0 0 8px ${accent})` }} />
          ) : (
            <ShieldCheck className="h-8 w-8 text-hud-green" />
          )}
        </div>

        {/* Message */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {active && verdictThreat ? (
              <AlertTriangle className="h-4 w-4 flex-shrink-0" style={{ color: accent }} />
            ) : null}
            <span
              className="truncate font-hud text-sm font-bold uppercase tracking-widest sm:text-base"
              style={{ color: active ? accent : '#34D399', textShadow: active ? `0 0 10px ${accent}` : 'none' }}
            >
              {message}
            </span>
          </div>
          <div className="mt-0.5 font-hud text-[10px] tracking-widest text-hud-dim">
            {active ? (
              <>
                TRACK #{threat?.tracking_id ?? '—'} · DIRECTION {dir || 'AHEAD'}
                {ttc ? ` · TTC ${ttc}` : ''}
                {threat?.estimated_act && threat.estimated_act !== 'N/A' ? ` · ACTION: ${threat.estimated_act.toUpperCase()}` : ''}
              </>
            ) : (
              <>
                ALL TRACKED OBJECTS SAFE{verdictThreat ? ' · RESOLVED AFTER EARLIER RISK EVENT' : ''} · SYSTEM VIGILANT
              </>
            )}
          </div>
        </div>

        {/* Direction pill */}
        <div
          className="hidden flex-col items-center justify-center rounded-lg border px-3 sm:flex"
          style={{ borderColor: `${accent}44`, background: `${accent}14` }}
        >
          <span className="font-hud text-[9px] tracking-widest text-hud-dim">APPROACHING</span>
          <span className="font-hud text-sm font-bold tracking-widest" style={{ color: accent }}>
            {dir || 'AHEAD'}
          </span>
        </div>
      </div>
    </section>
  );
}