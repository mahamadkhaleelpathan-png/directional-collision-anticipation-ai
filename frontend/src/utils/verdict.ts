import type { PipelineResultPayload, AnalysisVerdict } from '../types';

/**
 * SINGLE centralized verdict for the whole frontend (FIX 2).
 *
 * Meaning (from backend `compute_analysis_verdict`, whole-video evidence):
 * - HIGH_COLLISION_RISK: a HIGH CONFLICT frame occurred, or max risk >= 60.
 * - POTENTIAL_COLLISION_RISK: a POTENTIAL CONFLICT frame occurred, or max >= 40.
 * - LOW_RISK: max risk 20-39, no conflict frames.
 * - NO_SIGNIFICANT_RISK: max risk < 20, no conflict frames.
 * - UNKNOWN: backend did not provide a verdict (legacy payloads).
 *
 * "Current Threat" (primary_threat) is DIFFERENT: it is the threat state at
 * the FINAL analyzed frame only, and may be null when the last frame has no
 * tracked objects — even if an earlier frame had risk. Both are shown with
 * captions so they can never look contradictory.
 */
export function getVerdict(result: PipelineResultPayload | null): AnalysisVerdict {
  if (result?.verdict && result.verdict.level && result.verdict.label) {
    return result.verdict;
  }
  // Legacy fallback: same bands, derived from stats only. Never invents data.
  const stats = result?.stats;
  if (!stats) {
    return {
      level: 'UNKNOWN',
      label: 'Verdict unavailable',
      collision_risk_detected: false,
      reason: 'no analysis result',
    };
  }
  const conflicts = stats.collision_count ?? 0;
  const high = stats.high_conflict_frames ?? 0;
  const maxRisk = stats.cumulative_max_risk ?? 0;
  if (high > 0 || maxRisk >= 60) {
    return {
      level: 'HIGH_COLLISION_RISK',
      label: 'High collision risk detected',
      collision_risk_detected: true,
      reason: `${high} high-conflict frame(s), max risk ${Math.round(maxRisk)}/100`,
    };
  }
  if (conflicts > 0 || maxRisk >= 40) {
    return {
      level: 'POTENTIAL_COLLISION_RISK',
      label: 'Potential collision risk detected',
      collision_risk_detected: true,
      reason: `${conflicts} conflict frame(s), max risk ${Math.round(maxRisk)}/100`,
    };
  }
  if (maxRisk >= 20) {
    return {
      level: 'LOW_RISK',
      label: 'Low risk detected',
      collision_risk_detected: false,
      reason: `max risk ${Math.round(maxRisk)}/100, no conflict frames`,
    };
  }
  return {
    level: 'NO_SIGNIFICANT_RISK',
    label: 'No significant collision risk detected',
    collision_risk_detected: false,
    reason: `max risk ${Math.round(maxRisk)}/100, no conflict frames`,
  };
}
