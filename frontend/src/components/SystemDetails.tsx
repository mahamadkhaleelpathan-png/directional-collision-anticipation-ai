import { useState } from 'react';
import { ChevronDown, Download, Table2, Film } from 'lucide-react';
import type {
  AnalysisRow,
  PipelineResultPayload,
  RiskSummary,
  PipelineStats,
} from '../types';
import { fmtFloat, fmtInt, fmtSeconds, riskBadgeClasses } from '../utils/format';
import { getVerdict } from '../utils/verdict';
import { api } from '../api';

interface SystemDetailsProps {
  result: PipelineResultPayload | null;
}

export function SystemDetails({ result }: SystemDetailsProps) {
  const [open, setOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleCsv = async () => {
    if (!result) return;
    setDownloading(true);
    try {
      const { csv } = await api.csvReport(result.analysis_rows);
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analysis_report_${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  const handleVideoDownload = () => {
    if (!result) return;
    const a = document.createElement('a');
    a.href = api.videoUrl(result.output_video_filename);
    a.download = result.output_video_filename;
    a.click();
  };

  return (
    <section className="hud-panel overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-5 py-3.5 text-left"
      >
        <span className="hud-label flex items-center gap-2">
          <Table2 className="h-4 w-4 text-hud-cyan" />
          System Details & Reports
        </span>
        <ChevronDown
          className={`h-4 w-4 text-hud-dim transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div className="space-y-6 border-t border-hud-border px-5 py-5">
          <SafetyMetrics
            riskSummary={result?.risk_summary ?? null}
            primary={result?.primary_threat ?? null}
            stats={result?.stats ?? null}
          />

          <Verdict stats={result?.stats ?? null} verdict={result ? getVerdict(result) : null} />

          <SpeedStatusPanel stats={result?.stats ?? null} />

          <PipelineStatus hasResult={!!result} />

          <ThreatPriority threats={result?.top_threats ?? []} />

          {result && result.analysis_rows.length > 0 && (
            <AnalysisTable rows={result.analysis_rows} />
          )}

          {result && (
            <div className="flex flex-wrap gap-3 border-t border-hud-border pt-4">
              <button
                type="button"
                onClick={handleVideoDownload}
                className="btn-hud !py-1.5 !text-xs"
              >
                <Film className="h-3.5 w-3.5" />
                Download Processed Video
              </button>
              <button
                type="button"
                onClick={handleCsv}
                disabled={downloading}
                className="btn-hud-secondary !py-1.5 !text-xs"
              >
                <Download className="h-3.5 w-3.5" />
                {downloading ? 'Preparing…' : 'Download Analysis Report (CSV)'}
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function MetricTile({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-lg border border-hud-border bg-hud-bg/50 p-3 text-center">
      <div className="hud-label">{label}</div>
      <div className={`mt-1 font-hud text-lg font-bold ${accent ?? 'text-hud-text'}`}>{value}</div>
    </div>
  );
}

function SafetyMetrics({
  riskSummary,
  primary,
  stats,
}: {
  riskSummary: RiskSummary | null;
  primary: PipelineResultPayload['primary_threat'];
  stats: PipelineStats | null;
}) {
  const ttc = primary?.estimated_ttc ?? null;
  const pet = primary?.estimated_pet ?? null;
  const drac = primary?.estimated_drac_risk ?? null;
  const act = primary?.estimated_act ?? null;

  return (
    <div>
      <h3 className="hud-label mb-3">Safety Metrics</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <MetricTile label="Est. TTC" value={fmtSeconds(ttc)} accent="text-hud-cyan" />
        <MetricTile label="Est. PET" value={fmtSeconds(pet)} accent="text-hud-cyan" />
        <MetricTile label="DRAC (heuristic)" value={drac ?? 'N/A'} accent="text-hud-amber" />
        <MetricTile label="Recommended Action" value={act && act !== 'N/A' ? act : 'N/A'} accent="text-hud-amber" />
        <MetricTile label="Frame" value={stats ? fmtInt(stats.frames_processed) : 'N/A'} />
      </div>
      <p className="mt-2 font-hud text-[11px] text-hud-dim">
        TTC/PET are monocular-video estimates, not sensor measurements. DRAC is a heuristic urgency category (not measured m/s²). Risk scores are 0–100 heuristic assessments.
      </p>
      {riskSummary && (
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <MetricTile label="Max Risk" value={`${fmtFloat(riskSummary.max_risk_score ?? 0, 0)} / 100`} accent="text-hud-red" />
          <MetricTile label="Highest Risk Object" value={riskSummary.highest_risk_object ?? 'N/A'} />
          <MetricTile label="Objects Analyzed" value={fmtInt(riskSummary.total_objects ?? 0)} accent="text-hud-green" />
        </div>
      )}
    </div>
  );
}

function PipelineStatus({ hasResult }: { hasResult: boolean }) {
  return (
    <div>
      <h3 className="hud-label mb-3">Pipeline</h3>
      {hasResult ? (
        <p className="font-hud text-xs text-hud-dim">
          <span className="rounded-md border border-hud-green/30 bg-hud-green/10 px-2.5 py-1 font-bold text-hud-green">
            ANALYSIS COMPLETE
          </span>{' '}
          <span className="ml-2">Detection → Tracking → Motion → Prediction → Collision → Risk → Output all ran per frame.</span>
        </p>
      ) : (
        <p className="font-hud text-xs text-hud-dim">
          No analysis has completed yet. Pipeline stages will be reported honestly after processing.
        </p>
      )}
    </div>
  );
}

function SpeedStatusPanel({ stats }: { stats: PipelineStats | null }) {
  if (!stats) return null;
  const calibrated = stats.speed_calibrated === true || stats.speed_calibration?.configured === true;
  const camMotion = stats.camera_motion_warning === true;
  const egoKmh = stats.ego_speed_kmh;
  const cal = stats.speed_calibration;
  return (
    <div>
      <h3 className="hud-label mb-3">Speed Estimation</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <MetricTile
          label="Calibration"
          value={calibrated ? '● CALIBRATED' : '○ NOT CALIBRATED'}
          accent={calibrated ? 'text-hud-green' : 'text-hud-amber'}
        />
        <MetricTile
          label="Ego (camera) Speed"
          value={typeof egoKmh === 'number' && Number.isFinite(egoKmh) ? `${egoKmh.toFixed(1)} km/h` : 'N/A'}
          accent={camMotion ? 'text-hud-amber' : 'text-hud-dim'}
        />
        <MetricTile
          label="Camera Motion"
          value={camMotion ? 'DETECTED' : 'STATIC / LOW'}
          accent={camMotion ? 'text-hud-amber' : 'text-hud-green'}
        />
      </div>
      <p className="mt-2 font-hud text-[11px] text-hud-dim">
        {stats.speed_estimation_enabled === false
          ? 'Speed estimation is disabled in configuration.'
          : calibrated
            ? (cal?.note ?? 'CALIBRATED VISION SPEED ESTIMATE — not a sensor measurement.')
            : 'N/A — CALIBRATION REQUIRED. No km/h values are reported because this scene has no road-plane calibration (real lane width / markings / measured distance).'}
      </p>
      {camMotion && (
        <p className="mt-1 font-hud text-[11px] text-hud-amber">
          SPEED ESTIMATION — CAMERA MOTION MAY REDUCE ACCURACY. Reported km/h are relative/approach estimates.
        </p>
      )}
    </div>
  );
}

function Verdict({ stats, verdict }: { stats: PipelineStats | null; verdict: ReturnType<typeof getVerdict> | null }) {
  if (!stats) return null;
  const collisions = stats.collision_count ?? 0;
  const counts = stats.class_counts ?? {};
  const entries = Object.entries(counts);
  const total = entries.reduce((a, [, c]) => a + (c as number), 0);
  return (
    <div>
      <h3 className="hud-label mb-3">Simulation Verdict (whole video)</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricTile label="Verdict" value={verdict?.label ?? 'N/A'} accent="text-hud-cyan" />
        <MetricTile label="Conflict Frames" value={fmtInt(collisions)} accent={collisions > 0 ? 'text-hud-red' : 'text-hud-green'} />
        <MetricTile
          label="Highest Risk"
          value={`${fmtFloat(stats.cumulative_max_risk ?? 0, 0)} / 100${stats.max_risk_frame ? ` @ ${fmtInt(stats.max_risk_frame)}` : ''}`}
          accent="text-hud-amber"
        />
        <MetricTile label="Unique Tracks" value={fmtInt(stats.total_unique_tracks)} accent="text-hud-green" />
      </div>
      {verdict && (
        <p className="mt-2 font-hud text-[11px] text-hud-dim">
          Basis: {verdict.reason}. A "conflict frame" means a HIGH/POTENTIAL conflict condition was estimated in that frame — not that a crash occurred. Strongest conflict: {stats.max_conflict ?? 'NONE'}.
        </p>
      )}
      <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-8">
        <MetricTile label="Cars" value={fmtInt((counts['car'] as number) ?? 0)} />
        <MetricTile label="Bikes" value={fmtInt((counts['motorcycle'] as number) ?? 0)} />
        <MetricTile label="Bicycles" value={fmtInt((counts['bicycle'] as number) ?? 0)} />
        <MetricTile label="Persons" value={fmtInt((counts['person'] as number) ?? 0)} />
        <MetricTile label="Buses" value={fmtInt((counts['bus'] as number) ?? 0)} />
        <MetricTile label="Trucks" value={fmtInt((counts['truck'] as number) ?? 0)} />
        <MetricTile label="Other" value={fmtInt(total - ['car','motorcycle','bicycle','person','bus','truck'].reduce((a,k)=>a+((counts[k] as number) ?? 0),0))} />
        <MetricTile label="Detection Events" value={fmtInt(stats.total_detections)} />
      </div>
      <p className="mt-2 font-hud text-[11px] text-hud-dim">
        Detection events count every per-frame detection. Unique tracks count distinct tracked objects. Per-class counts sum to detection events.
      </p>
      {(stats.processing_errors ?? 0) > 0 && (
        <p className="mt-2 text-xs text-hud-amber">
          {stats.processing_errors} frame(s) had processing errors and were passed through unannotated. See logs for details.
        </p>
      )}
    </div>
  );
}

function ThreatPriority({
  threats,
}: {
  threats: PipelineResultPayload['top_threats'];
}) {
  return (
    <div>
      <h3 className="hud-label mb-3">Threat Priority</h3>
      {threats.length === 0 ? (
        <p className="font-hud text-xs text-hud-dim">No ranked threats available. Process a video to view threat ranking.</p>
      ) : (
        <ol className="space-y-2">
          {threats.map((t, i) => (
            <li
              key={`${t.tracking_id}-${i}`}
              className="flex items-center justify-between rounded-lg border border-hud-border bg-hud-bg/50 px-3 py-2"
            >
              <div className="flex items-center gap-3">
                <span className="font-hud text-sm font-bold text-hud-dim">#{i + 1}</span>
                <span className="font-hud text-sm font-semibold text-hud-text">
                  {t.class_name} #{t.tracking_id}
                </span>
                <span className="font-hud text-xs text-hud-cyan">{t.direction}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-hud text-xs font-bold text-hud-text">{Math.round(t.risk_score)}/100</span>
                <span className={`risk-pill ${riskBadgeClasses(t.risk_level)}`}>{t.risk_level}</span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function AnalysisTable({ rows }: { rows: AnalysisRow[] }) {
  const headers = ['Object', 'Track', 'Direction', 'Speed', 'Risk', 'TTC', 'PET', 'DRAC', 'Level'];
  return (
    <div>
      <h3 className="hud-label mb-3">Per-Object Summary</h3>
      <div className="overflow-hidden rounded-lg border border-hud-border">
        <table className="w-full text-sm">
          <thead className="hud-label bg-hud-bg/60">
            <tr>
              {headers.map((h) => (
                <th key={h} className="px-3 py-2 text-left font-semibold">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 50).map((row, idx) => (
              <tr key={`${row.track_id}-${idx}`} className="border-t border-hud-border/40 hover:bg-hud-bg/30">
                <td className="px-3 py-2 font-hud text-hud-text">{row.class_name}</td>
                <td className="px-3 py-2 font-mono text-xs text-hud-dim">{row.track_id}</td>
                <td className="px-3 py-2 font-hud text-hud-cyan">{row.direction}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {typeof row.estimated_speed_kmh === 'number' ? (
                    <span className="text-hud-green">
                      {row.estimated_speed_kmh.toFixed(1)} km/h
                      {typeof row.estimated_speed_confidence === 'number'
                        ? ` · ${Math.round(row.estimated_speed_confidence * 100)}%`
                        : ''}
                    </span>
                  ) : (
                    <span className="text-hud-dim/70">
                      {row.speed_status === 'CALCULATING' ? 'CALCULATING…' : row.speed_status === 'NOT_CALIBRATED' ? 'N/A — NOT CALIBRATED' : 'N/A'}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-hud-text">{Math.round(row.max_risk_score)}/100</td>
                <td className="px-3 py-2 font-mono text-xs text-hud-dim">{row.estimated_ttc !== null ? row.estimated_ttc.toFixed(2) : 'N/A'}</td>
                <td className="px-3 py-2 font-mono text-xs text-hud-dim">{row.estimated_pet !== null ? row.estimated_pet.toFixed(2) : 'N/A'}</td>
                <td className="px-3 py-2 text-xs text-hud-dim">{row.estimated_drac_risk}</td>
                <td className="px-3 py-2">
                  <span className={`risk-pill ${riskBadgeClasses(row.risk_level)}`}>{row.risk_level}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
