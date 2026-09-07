import { useEffect, useRef, useState } from 'react';
import type { PipelineResultPayload, RiskLevel } from '../types';

export const HUD_RISK_COLORS: Record<string, string> = {
  SAFE: '#34D399',
  LOW: '#34D399',
  MEDIUM: '#FBBF24',
  HIGH: '#FB923C',
  CRITICAL: '#F87171',
};

export function hudRiskColor(level: RiskLevel | undefined | null): string {
  if (!level) return '#64748B';
  return HUD_RISK_COLORS[level as string] ?? '#64748B';
}

export function isNum(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function fmtInt(value: number | null | undefined): string {
  if (!isNum(value)) return '—';
  return value.toLocaleString();
}

export function fmtTTC(value: number | null | undefined): string {
  if (!isNum(value)) return '—';
  return `${value.toFixed(2)}s`;
}

export function threatName(threat: PipelineResultPayload['primary_threat']): string {
  const t = threat;
  if (!t) return '—';
  const name = (t.object_type ?? t.class_name ?? '').toString();
  return name || '—';
}

export function classCounts(result: PipelineResultPayload | null): Record<string, number> {
  const counts = result?.class_counts ?? result?.stats?.class_counts ?? {};
  return counts;
}

export function trackMotorbikes(counts: Record<string, number>): {
  vehicles: number;
  motorbikes: number;
  pedestrians: number;
  tracks: number;
} {
  const sum = (keys: string[]) => keys.reduce((a, k) => a + (counts[k] ?? 0), 0);
  return {
    vehicles: sum(['car', 'bus', 'truck']),
    motorbikes: sum(['motorcycle', 'bicycle']),
    pedestrians: counts['person'] ?? 0,
    tracks: sum(Object.keys(counts)),
  };
}

/**
 * Count-up hook for HUD numeric readouts. Animates the displayed value from
 * its previous value toward `target` whenever `target` changes.
 */
export function useCountUp(target: number, duration = 700): number {
  const [display, setDisplay] = useState(target);
  const fromRef = useRef(target);
  const raf = useRef(0);

  useEffect(() => {
    const from = fromRef.current;
    const diff = target - from;
    if (diff === 0) return;
    let start: number | null = null;
    const tick = (ts: number) => {
      if (start === null) start = ts;
      const p = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(from + diff * eased);
      if (p < 1) raf.current = requestAnimationFrame(tick);
      else fromRef.current = target;
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);

  return display;
}