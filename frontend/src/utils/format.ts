import type { RiskLevel } from '../types';

export const RISK_COLORS: Record<string, string> = {
  SAFE: '#16A34A',
  LOW: '#16A34A',
  MEDIUM: '#F59E0B',
  HIGH: '#F97316',
  CRITICAL: '#DC2626',
};

export function riskColor(level: RiskLevel | undefined): string {
  if (!level) return '#94A3B8';
  return RISK_COLORS[level as string] ?? '#94A3B8';
}

export function riskBadgeClasses(level: RiskLevel | undefined): string {
  switch ((level ?? '').toString()) {
    case 'CRITICAL':
      return 'bg-red-950 text-red-400 border-red-500/40';
    case 'HIGH':
      return 'bg-orange-950 text-orange-400 border-orange-500/40';
    case 'MEDIUM':
      return 'bg-amber-950 text-amber-400 border-amber-500/40';
    case 'LOW':
    case 'SAFE':
      return 'bg-emerald-950 text-emerald-400 border-emerald-500/40';
    default:
      return 'bg-slate-900 text-slate-400 border-slate-600';
  }
}

function isDisplayable(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function fmtSeconds(value: number | null | undefined, digits = 2): string {
  if (!isDisplayable(value)) return 'N/A';
  return `${value.toFixed(digits)} sec`;
}

export function fmtInt(value: number | null | undefined): string {
  if (!isDisplayable(value)) return 'N/A';
  return value.toLocaleString();
}

export function fmtFloat(value: number | null | undefined, digits = 1): string {
  if (!isDisplayable(value)) return 'N/A';
  return value.toFixed(digits);
}
