import { SkipBack, SkipForward, ChevronLeft, ChevronRight, Info } from 'lucide-react';

interface FrameControlsProps {
  currentFrame: number;
  totalFrames: number;
  onSeekFrame: (frame: number) => void;
  speed: number;
  onSpeedChange: (s: number) => void;
  onOpenInspector: () => void;
}

const SPEEDS = [1, 0.5, 0.25, 0.125];

export function FrameControls({ currentFrame, totalFrames, onSeekFrame, speed, onSpeedChange, onOpenInspector }: FrameControlsProps) {
  const max = Math.max(1, totalFrames - 1);
  const atStart = currentFrame <= 0;
  const atEnd = totalFrames > 0 && currentFrame >= totalFrames - 1;

  return (
    <section className="hud-panel p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="hud-label mr-1">FRAME</span>
        <span className="min-w-[130px] rounded-md border border-hud-border bg-hud-bg/60 px-2 py-1 text-center font-mono text-sm font-bold text-hud-cyan">
          {currentFrame.toLocaleString()}
          <span className="text-hud-dim"> / {totalFrames > 0 ? totalFrames.toLocaleString() : '—'}</span>
        </span>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onSeekFrame(0)}
            disabled={atStart}
            className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs"
            aria-label="Seek to first frame"
          >
            <SkipBack className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => onSeekFrame(currentFrame - 1)}
            disabled={atStart}
            className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs"
            aria-label="Previous frame"
          >
            <ChevronLeft className="h-3.5 w-3.5" /> PREV
          </button>
          <button
            type="button"
            onClick={() => onSeekFrame(currentFrame + 1)}
            disabled={atEnd}
            className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs"
            aria-label="Next frame"
          >
            NEXT <ChevronRight className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={onOpenInspector}
            className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs"
            aria-label="Open AI frame inspector"
            title="Open the live AI frame-by-frame player"
          >
            <Info className="h-3.5 w-3.5 text-hud-cyan" />
          </button>
          <button
            type="button"
            onClick={() => onSeekFrame(Math.max(0, totalFrames - 1))}
            disabled={atEnd}
            className="btn-hud-secondary !rounded-md !px-2 !py-1 !text-xs"
            aria-label="Seek to last frame"
          >
            <SkipForward className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Frame scrubber */}
      <div className="mt-2">
        <input
          type="range"
          min={0}
          max={max}
          step={1}
          value={Math.max(0, Math.min(currentFrame, max))}
          onChange={(e) => onSeekFrame(Number(e.target.value))}
          className="w-full"
          aria-label="Scrub frames"
        />
      </div>

      {/* Playback speed */}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <span className="hud-label">PLAYBACK SLOW-MO</span>
        <div className="flex items-center gap-1">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onSpeedChange(s)}
              className={`rounded border px-2 py-1 font-hud text-[10px] font-semibold tracking-wider transition ${
                speed === s
                  ? 'border-hud-cyan/50 bg-hud-cyan/15 text-hud-cyan shadow-glowCyan'
                  : 'border-hud-border bg-hud-bg/50 text-hud-dim hover:text-hud-text'
              }`}
            >
              {s === 1 ? '1×' : s.toFixed(3).replace(/0+$/, '').replace(/\.$/, '') + '×'}
            </button>
          ))}
        </div>
        <span className="font-hud text-[9px] tracking-widest text-hud-dim">
          {speed === 1 ? 'FULL SPEED' : 'SLOW MOTION'}
        </span>
      </div>
    </section>
  );
}