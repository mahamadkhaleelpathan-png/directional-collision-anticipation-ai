import { Shield, Activity, Gauge } from 'lucide-react';

interface HeaderProps {
  status: 'idle' | 'live' | 'processing';
  detail: string;
}

const CFG: Record<HeaderProps['status'], { label: string; dot: string; text: string; bar: string }> = {
  idle: { label: 'SYSTEM IDLE', dot: 'bg-hud-dim', text: 'text-hud-dim', bar: 'from-slate-500/40 to-transparent' },
  live: { label: 'SYSTEM ACTIVE', dot: 'bg-hud-green shadow-glowGreen', text: 'text-hud-green', bar: 'from-hud-green/60 to-transparent' },
  processing: { label: 'PROCESSING', dot: 'bg-hud-amber shadow-[0_0_10px_rgba(251,191,36,0.6)]', text: 'text-hud-amber', bar: 'from-hud-amber/60 to-transparent' },
};

export function Header({ status, detail }: HeaderProps) {
  const cfg = CFG[status];

  return (
    <header className="sticky top-0 z-50 border-b border-hud-border bg-hud-bg/90 backdrop-blur-md">
      {/* Animated status gradient bar across the very top */}
      <div className={`h-0.5 w-full bg-gradient-to-r ${cfg.bar}`} />
      <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-hud-cyan/30 to-hud-blue/30 border border-hud-cyan/40 shadow-glowCyan">
            <Shield className="h-5 w-5 text-hud-cyan" />
          </div>
          <div className="leading-tight">
            <h1 className="hud-title text-lg font-bold tracking-wide text-hud-text">
              AI COLLISION ANTICIPATION
            </h1>
            <p className="font-hud text-[11px] tracking-[0.2em] text-hud-dim">
              DIRECTIONAL DRIVER SAFETY SYSTEM
            </p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="hidden items-center gap-2 sm:flex">
            <Gauge className="h-4 w-4 text-hud-dim" />
            <span className="font-hud text-xs tracking-widest text-hud-dim">{detail.toUpperCase()}</span>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-hud-border bg-hud-panel px-3 py-1.5">
            <span className={`h-2 w-2 rounded-full ${cfg.dot}`} />
            <span className={`font-hud text-xs font-semibold tracking-widest ${cfg.text}`}>{cfg.label}</span>
          </div>
          <div className="hidden items-center gap-2 md:flex">
            <Activity className="h-4 w-4 text-hud-dim" />
            <span className="font-hud text-xs tracking-widest text-hud-dim">v2.0 · 6-STAGE / 9-STEP PIPELINE</span>
          </div>
        </div>
      </div>
    </header>
  );
}
