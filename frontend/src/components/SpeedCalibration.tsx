import { useCallback, useEffect, useRef, useState } from 'react';
import { Crosshair, Gauge, X } from 'lucide-react';
import type { CalibrationResponse, SpeedCalibrationStatus } from '../types';
import { api } from '../api';

const MS_TO_KMH = 3.6;

function fmtKmh(kmh: number | null | undefined): string {
  return typeof kmh === 'number' && Number.isFinite(kmh) ? `${kmh.toFixed(0)} km/h` : 'N/A';
}

interface SpeedCalibrationProps {
  sourcePath: string | null;
  statsSpeedCalibrated?: boolean;
}

/**
 * Optional speed-calibration panel (STEP 30). Lets the user map four road
 * points (A-B-C-D) on a real frame to known road dimensions. The homography
 * is validated on the backend before saving. Never fabricated: if the user
 * never calibrates, the dashboard shows km/h as NOT CALIBRATED.
 */
export function SpeedCalibration({ sourcePath, statsSpeedCalibrated }: SpeedCalibrationProps) {
  const [status, setStatus] = useState<SpeedCalibrationStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<{ url: string; width: number; height: number } | null>(null);
  const [points, setPoints] = useState<[number, number][]>([]);
  const [widthM, setWidthM] = useState(3.5);
  const [depthM, setDepthM] = useState(10);
  const [saving, setSaving] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  const refresh = useCallback(async () => {
    try {
      const res: CalibrationResponse = await api.calibrationStatus();
      setStatus(res.status);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load calibration status');
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const configured = status?.configured ?? false;
  const isCalibrated = configured || statsSpeedCalibrated === true;

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    setError(null);
    setMessage(null);
    if (next) {
      if (!sourcePath) {
        setError('Load a video first so you can click its road points.');
        return;
      }
      try {
        setLoading(true);
        const pv = await api.calibrationPreview(sourcePath);
        if (!pv.ok || !pv.preview_b64) {
          setMessage('Calibration is available, but the video preview could not be loaded here.');
          setOpen(false);
          return;
        }
        setPreview({
          url: `data:image/jpeg;base64,${pv.preview_b64}`,
          width: pv.width ?? 0,
          height: pv.height ?? 0,
        });
        setPoints([]);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load preview frame');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleClick = (e: React.MouseEvent<HTMLImageElement>) => {
    const img = imgRef.current;
    if (!img) return;
    const rect = img.getBoundingClientRect();
    const scaleX = (preview?.width ?? 1) / rect.width;
    const scaleY = (preview?.height ?? 1) / rect.height;
    const x = Math.max(0, Math.min((e.clientX - rect.left) * scaleX, preview?.width ?? 0));
    const y = Math.max(0, Math.min((e.clientY - rect.top) * scaleY, preview?.height ?? 0));
    setPoints((p) => (p.length >= 4 ? p : [...p, [x, y]]));
  };

  const apply = async () => {
    if (points.length !== 4 || widthM <= 0 || depthM <= 0) {
      setError('Select exactly 4 road points and enter positive width & distance.');
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const res: CalibrationResponse = await api.applyCalibration(points, widthM, depthM);
      setStatus(res.status);
      setMessage(res.status.note ?? 'Calibration saved.');
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save calibration');
    } finally {
      setSaving(false);
    }
  };

  const clear = async () => {
    setSaving(true);
    setError(null);
    try {
      const res: CalibrationResponse = await api.clearCalibration();
      setStatus(res.status);
      setMessage('Calibration removed. Speed now reports N/A / NOT CALIBRATED.');
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to clear calibration');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg border border-hud-border bg-hud-bg/40 p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Gauge className="h-3.5 w-3.5 text-hud-cyan" />
          <span className="hud-label">SPEED CALIBRATION</span>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 font-hud text-[9px] tracking-widest ${
            isCalibrated
              ? 'border-hud-green/40 bg-hud-green/15 text-hud-green'
              : 'border-hud-amber/40 bg-hud-amber/15 text-hud-amber'
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${isCalibrated ? 'bg-hud-green shadow-glowGreen' : 'bg-hud-amber'}`}
          />
          {isCalibrated ? 'CALIBRATED' : 'NOT CALIBRATED'}
        </span>
      </div>

      <p className="mt-1.5 font-hud text-[9px] leading-relaxed text-hud-dim">
        {isCalibrated ? (status?.note ?? 'CALIBRATED SPEED ESTIMATE') : 'N/A — CALIBRATION REQUIRED'}
      </p>
      <p className="mt-0.5 font-hud text-[8px] leading-relaxed text-hud-dim/70">
        {isCalibrated
          ? 'km/h shown on the HUD is a calibrated road-plane estimate, not a sensor measurement.'
          : 'Pixel movement is NOT converted to km/h until the scene is calibrated with a known road dimension.'}
      </p>

      {!isCalibrated && !open && (
        <button
          type="button"
          onClick={() => void toggle()}
          className="btn-hud mt-2 !py-1 !text-xs"
          disabled={!sourcePath}
        >
          <Crosshair className="h-3.5 w-3.5" /> CALIBRATE SPEED
        </button>
      )}
      {isCalibrated && !open && (
        <button
          type="button"
          onClick={() => void toggle()}
          className="btn-hud-secondary mt-2 !py-1 !text-xs"
        >
          RECALIBRATE
        </button>
      )}

      {open && (
        <div className="mt-3 space-y-3 border-t border-hud-border pt-3">
          {loading && <p className="font-hud text-[10px] text-hud-dim">LOADING PREVIEW FRAME…</p>}
          {preview && (
            <div>
              <p className="mb-1 font-hud text-[9px] text-hud-dim">
                CLICK THE 4 ROAD-PLANE CORNERS IN ORDER: A (top-left) → B (top-right) → C (bottom-right) → D (bottom-left)
              </p>
              <div className="relative inline-block max-w-full overflow-hidden rounded border border-hud-cyan/40">
                <img
                  ref={imgRef}
                  src={preview.url}
                  alt="Calibration frame"
                  className="max-h-56 w-full cursor-crosshair object-contain"
                  onClick={handleClick}
                />
                {points.map(([x, y], i) => (
                  <span
                    key={i}
                    className="absolute flex h-4 w-4 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-hud-green bg-hud-bg/80 text-[9px] font-bold text-hud-green"
                    style={{
                      left: `${(x / preview.width) * 100}%`,
                      top: `${(y / preview.height) * 100}%`,
                    }}
                  >
                    {['A', 'B', 'C', 'D'][i]}
                  </span>
                ))}
              </div>
              <div className="mt-1 font-hud text-[9px] text-hud-dim">
                {points.length}/4 SELECTED · {pointsFormatted(points)}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <label className="font-hud text-[9px] text-hud-dim">
              KNOWN ROAD WIDTH (m)
              <input
                type="number"
                min={0.5}
                max={20}
                step={0.1}
                value={widthM}
                onChange={(e) => setWidthM(Number(e.target.value))}
                className="mt-1 w-full rounded border border-hud-border bg-hud-bg px-2 py-1 font-mono text-sm text-hud-text"
              />
            </label>
            <label className="font-hud text-[9px] text-hud-dim">
              DISTANCE A→D (m)
              <input
                type="number"
                min={1}
                max={200}
                step={0.5}
                value={depthM}
                onChange={(e) => setDepthM(Number(e.target.value))}
                className="mt-1 w-full rounded border border-hud-border bg-hud-bg px-2 py-1 font-mono text-sm text-hud-text"
              />
            </label>
          </div>

          {error && <p className="rounded border border-hud-red/40 bg-hud-red/10 px-2 py-1 font-hud text-[9px] text-hud-red">{error}</p>}
          {message && <p className="rounded border border-hud-green/40 bg-hud-green/10 px-2 py-1 font-hud text-[9px] text-hud-green">{message}</p>}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void apply()}
              disabled={saving || points.length !== 4}
              className="btn-hud !py-1 !text-xs"
            >
              {saving ? 'SAVING…' : 'APPLY CALIBRATION'}
            </button>
            {configured && (
              <button type="button" onClick={() => void clear()} disabled={saving} className="btn-hud-secondary !py-1 !text-xs">
                <X className="h-3 w-3" /> CLEAR
              </button>
            )}
            <button type="button" onClick={() => setOpen(false)} className="btn-hud-secondary ml-auto !py-1 !text-xs">
              CLOSE
            </button>
          </div>
          <p className="font-hud text-[8px] leading-relaxed text-hud-dim/70">
            Save only uses real measurements (lane width / road markings / measured distance). It is validated
            (4 non-degenerate points, positive dimensions, numerically valid homography) or rejected.
          </p>
        </div>
      )}
    </div>
  );
}

function pointsFormatted(points: [number, number][]): string {
  return points
    .map(([x, y], i) => `${['A', 'B', 'C', 'D'][i]} (${Math.round(x)},${Math.round(y)})`)
    .join(' · ');
}

export const _fmtKmhForTest = fmtKmh;
export const _mpsToKmh = (mps: number) => mps * MS_TO_KMH;