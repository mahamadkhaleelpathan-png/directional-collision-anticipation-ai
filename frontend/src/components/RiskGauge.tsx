import { useMemo } from 'react';
import { Gauge as GaugeIcon } from 'lucide-react';
import { isNum, useCountUp } from '../utils/hud';

interface RiskGaugeProps {
  value: number | null | undefined;
  label?: string;
  hint?: string;
}

function polar(deg: number, radius: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: 100 + radius * Math.cos(rad), y: 100 - radius * Math.sin(rad) };
}

const ARC_R = 78;
const START = polar(180, ARC_R);
const END = polar(0, ARC_R);
const ARC_D = `M ${START.x} ${START.y} A ${ARC_R} ${ARC_R} 0 0 1 ${END.x} ${END.y}`;

const BANDS = [
  { from: 0, to: 25, label: 'SAFE', color: '#34D399' },
  { from: 25, to: 50, label: 'CAUTION', color: '#FBBF24' },
  { from: 50, to: 75, label: 'WARNING', color: '#FB923C' },
  { from: 75, to: 100, label: 'CRITICAL', color: '#F87171' },
] as const;

const TICKS = [0, 25, 50, 75, 100];

function bandFor(value: number) {
  if (value >= 75) return BANDS[3];
  if (value >= 50) return BANDS[2];
  if (value >= 25) return BANDS[1];
  return BANDS[0];
}

export function RiskGauge({ value, label = 'RISK GAUGE', hint }: RiskGaugeProps) {
  const clamped = useMemo(() => (isNum(value) ? Math.max(0, Math.min(100, value as number)) : 0), [value]);
  const band = bandFor(clamped);
  const display = useCountUp(clamped, 800);
  const frac = clamped / 100;
  const angle = 180 - clamped * 1.8;
  const tip = polar(angle, ARC_R - 12);
  const critical = band.color === '#F87171';

  return (
    <section
      className={`hud-panel p-4 ${critical ? 'hud-anim-screenpulse' : ''}`}
      style={critical ? { borderColor: 'rgba(248,113,113,0.5)' } : undefined}
    >
      <div className="mb-1 flex items-center justify-between">
        <h3 className="hud-label flex items-center gap-2">
          <GaugeIcon className="h-4 w-4 text-hud-cyan" />
          {label}
        </h3>
        <span
          className="font-hud text-xs font-bold tracking-widest"
          style={{ color: band.color, textShadow: `0 0 8px ${band.color}` }}
        >
          {band.label}
        </span>
      </div>

      <svg viewBox="0 0 200 116" className="mx-auto w-full max-w-[240px]">
        {/* Band arcs */}
        {BANDS.map((b) => {
          const offset = -(b.from / 100);
          return (
            <path
              key={b.label}
              d={ARC_D}
              fill="none"
              stroke={b.color}
              strokeOpacity={0.22}
              strokeWidth={9}
              pathLength={1}
              strokeDasharray={`${(b.to - b.from) / 100} ${1 - (b.to - b.from) / 100}`}
              strokeDashoffset={offset}
            />
          );
        })}
        {/* Track */}
        <path d={ARC_D} fill="none" stroke="#1E293B" strokeWidth={2} strokeLinecap="round" />
        {/* Colored fill up to value */}
        <path
          d={ARC_D}
          fill="none"
          stroke={band.color}
          strokeWidth={9}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={`${frac} ${1 - frac}`}
          style={{ transition: 'stroke-dasharray 0.3s, stroke 0.3s', filter: `drop-shadow(0 0 4px ${band.color})` }}
        />
        {/* Ticks */}
        {TICKS.map((t) => {
          const inner = polar(180 - t * 1.8, ARC_R - 9);
          const outer = polar(180 - t * 1.8, ARC_R + 2);
          return (
            <g key={t}>
              <line x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} stroke="#334155" strokeWidth={1.5} />
              <text
                x={polar(180 - t * 1.8, ARC_R + 7).x}
                y={polar(180 - t * 1.8, ARC_R + 7).y + 3}
                textAnchor="middle"
                fontSize={7}
                fill="#64748B"
                fontFamily="Rajdhani, sans-serif"
              >
                {t}
              </text>
            </g>
          );
        })}
        {/* Needle */}
        <line
          x1={100}
          y1={100}
          x2={tip.x}
          y2={tip.y}
          stroke={band.color}
          strokeWidth={2.5}
          strokeLinecap="round"
          style={{ transition: 'stroke 0.3s' }}
        />
        <circle cx={100} cy={100} r={4} fill="#0F172A" stroke={band.color} strokeWidth={1.5} />
        {/* Ego marker below arc */}
        <rect x={97} y={102} width={6} height={8} rx={1} fill="#22D3EE" opacity={0.85} />
      </svg>

      <div className="-mt-2 text-center">
        <div
          className="font-hud text-4xl font-bold leading-none"
          style={{ color: band.color, textShadow: `0 0 12px ${band.color}` }}
        >
          {Math.round(display)}
        </div>
        <div className="font-hud text-[10px] tracking-[0.3em] text-hud-dim">/ 100</div>
      </div>

      <div className="mt-2 grid grid-cols-4 gap-1">
        {BANDS.map((b) => (
          <div key={b.label} className="text-center">
            <div className="h-1 rounded-full" style={{ background: b.color, opacity: band === b ? 1 : 0.25 }} />
            <div className={`mt-0.5 font-hud text-[8px] tracking-wider ${band === b ? 'text-hud-text' : 'text-hud-dim'}`}>
              {b.label}
            </div>
          </div>
        ))}
      </div>

      {hint && <p className="mt-2 font-hud text-[10px] leading-relaxed text-hud-dim">{hint}</p>}
    </section>
  );
}