import type { ReactNode } from 'react';
import { Car, Bike, User, Fingerprint } from 'lucide-react';
import type { PipelineResultPayload } from '../types';
import { classCounts, trackMotorbikes, useCountUp } from '../utils/hud';

interface PerceptionPanelProps {
  result: PipelineResultPayload | null;
}

const CLASS_ICONS: Record<string, { icon: typeof Car; color: string }> = {
  car: { icon: Car, color: '#22D3EE' },
  bus: { icon: Car, color: '#3B82F6' },
  truck: { icon: Car, color: '#818CF8' },
  motorcycle: { icon: Bike, color: '#FBBF24' },
  bicycle: { icon: Bike, color: '#F97316' },
  person: { icon: User, color: '#34D399' },
};

export function PerceptionPanel({ result }: PerceptionPanelProps) {
  const counts = classCounts(result);
  const totals = trackMotorbikes(counts);

  const vehicles = useCountUp(totals.vehicles, 700);
  const motorbikes = useCountUp(totals.motorbikes, 700);
  const pedestrians = useCountUp(totals.pedestrians, 700);
  const tracks = useCountUp(totals.tracks, 700);

  const entries = Object.entries(counts).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);

  return (
    <section className="hud-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="hud-label flex items-center gap-2">
          <Fingerprint className="h-4 w-4 text-hud-cyan" />
          AI Perception
        </h3>
        <span className="font-hud text-[10px] tracking-widest text-hud-dim">
          {Object.keys(counts).length > 0 ? 'DETECTED CLASSES' : 'NO DETECTIONS'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Tile icon={<Car className="h-4 w-4 text-hud-cyan" />} label="Vehicles" value={Math.round(vehicles)} />
        <Tile icon={<Bike className="h-4 w-4 text-hud-amber" />} label="Motorbikes" value={Math.round(motorbikes)} />
        <Tile icon={<User className="h-4 w-4 text-hud-green" />} label="Pedestrians" value={Math.round(pedestrians)} />
        <Tile icon={<Fingerprint className="h-4 w-4 text-hud-blue" />} label="Unique Tracks" value={Math.round(tracks)} />
      </div>

      {entries.length > 0 ? (
        <div className="mt-3 space-y-1.5 border-t border-hud-border/60 pt-2.5">
          {entries.slice(0, 6).map(([cls, n]) => {
            const cfg = CLASS_ICONS[cls] ?? { icon: Fingerprint, color: '#64748B' };
            const Icon = cfg.icon;
            return (
              <div key={cls} className="flex items-center gap-2">
                <Icon className="h-3.5 w-3.5" style={{ color: cfg.color }} />
                <span className="font-hud text-xs capitalize text-hud-text">{cls}</span>
                <div className="ml-auto h-1.5 flex-1 overflow-hidden rounded-full bg-hud-border/70">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${entries[0][1] > 0 ? (n / entries[0][1]) * 100 : 0}%`, background: cfg.color, opacity: 0.7 }}
                  />
                </div>
                <span className="w-8 text-right font-hud text-xs font-bold text-hud-text">{n.toLocaleString()}</span>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="mt-3 border-t border-hud-border/60 pt-2.5 font-hud text-[10px] text-hud-dim">
          Process a video to populate the perception layer. Streamed detections are visualized on the annotated output.
        </p>
      )}
    </section>
  );
}

function Tile({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="rounded-lg border border-hud-border/70 bg-hud-bg/40 p-2.5 text-center">
      <div className="flex items-center justify-center gap-1.5">
        {icon}
        <span className="font-hud text-[9px] tracking-wider text-hud-dim uppercase">{label}</span>
      </div>
      <div className="mt-1 font-hud text-2xl font-bold leading-none text-hud-text">{value}</div>
    </div>
  );
}