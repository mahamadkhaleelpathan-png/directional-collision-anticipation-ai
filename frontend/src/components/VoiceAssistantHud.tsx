import { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Mic,
  MicOff,
  MessageSquare,
  Power,
  Radio,
  Volume2,
  VolumeX,
  Zap,
} from 'lucide-react';
import type { VoiceAlert, VoiceAssistantState } from '../types';
import {
  VOICE_LANGUAGE_CODES,
  VOICE_LANGUAGE_LABELS,
  languageLabel,
} from '../voice/languages';

interface VoiceAssistantHudProps {
  voiceState: VoiceAssistantState;
  lastText: string;
  alerts: number;
  enabled: boolean;
  muted: boolean;
  volume: number;
  jobId: string | null;
  listening: boolean;
  micAvailable: boolean;
  currentLanguage: string;
  lastAlert: VoiceAlert | null;
  onToggleEnabled: () => void;
  onToggleMuted: () => void;
  onVolumeChange: (v: number) => void;
  onTest: () => void;
  onAsk: (question: string) => void;
  onMic: () => void;
  onLanguageChange: (lang: string) => void;
}

const STATE_CFG: Record<VoiceAssistantState, { label: string; dot: string; text: string }> = {
  IDLE: { label: 'IDLE', dot: 'bg-hud-dim', text: 'text-hud-dim' },
  MONITORING: {
    label: 'MONITORING',
    dot: 'bg-hud-cyan shadow-glowCyan',
    text: 'text-hud-cyan',
  },
  LISTENING: { label: 'LISTENING', dot: 'bg-hud-amber shadow-glowCyan', text: 'text-hud-amber' },
  THINKING: { label: 'THINKING', dot: 'bg-hud-amber', text: 'text-hud-amber' },
  SPEAKING: {
    label: 'SPEAKING',
    dot: 'bg-hud-green shadow-glowGreen',
    text: 'text-hud-green',
  },
  MUTED: { label: 'MUTED', dot: 'bg-hud-dim', text: 'text-hud-dim' },
  ERROR: { label: 'ERROR', dot: 'bg-hud-red shadow-glowRed', text: 'text-hud-red' },
  OFFLINE: { label: 'OFFLINE', dot: 'bg-hud-red shadow-glowRed', text: 'text-hud-red' },
};

function AlertRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="font-hud text-[10px] tracking-widest text-hud-dim">{label}</span>
      <span className="font-hud text-xs text-hud-text">{value}</span>
    </div>
  );
}

export function VoiceAssistantHud(props: VoiceAssistantHudProps) {
  const [question, setQuestion] = useState('');
  const cfg = STATE_CFG[props.voiceState] ?? STATE_CFG.IDLE;
  const speaking = props.voiceState === 'SPEAKING';

  const submitAsk = () => {
    const q = question.trim();
    if (!q) return;
    props.onAsk(q);
    setQuestion('');
  };

  const alert = props.lastAlert;
  const alertRisk = alert?.risk_level ?? '—';
  const alertSpeed = alert?.speed_valid ? `${alert.speed_kmh ?? '?'} km/h` : 'n/a';

  return (
    <div className="hud-panel p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="hud-label flex items-center gap-2">
          <Radio className="h-4 w-4 text-hud-cyan" />
          VOICE SAFETY ASSISTANT
        </h3>
        <div className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${cfg.dot}`} />
          <span className={`font-hud text-xs font-semibold tracking-widest ${cfg.text}`}>
            {cfg.label}
          </span>
        </div>
      </div>

      {/* Language selector + current language (item 21/47) */}
      <div className="mb-4 rounded-lg border border-hud-border/60 bg-hud-panel2/60 p-3">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="font-hud text-[10px] tracking-widest text-hud-dim">CURRENT LANGUAGE</span>
          <span className="font-hud text-xs font-semibold text-hud-cyan">
            {languageLabel(props.currentLanguage)}
          </span>
        </div>
        <select
          value={props.currentLanguage}
          onChange={(e) => props.onLanguageChange(e.target.value)}
          className="w-full rounded-lg border border-hud-border bg-hud-panel2 px-3 py-2 font-hud text-xs text-hud-text outline-none focus:border-hud-cyan/50"
          aria-label="Voice assistant language"
        >
          {VOICE_LANGUAGE_CODES.map((code) => (
            <option key={code} value={code}>
              {VOICE_LANGUAGE_LABELS[code]}
            </option>
          ))}
        </select>
      </div>

      {/* Waveform — reflects the REAL audio state (item 27) */}
      <div
        className={`mb-4 flex h-10 items-center justify-center gap-[3px] rounded-lg border border-hud-border/60 bg-hud-panel2/60 ${
          speaking ? 'hud-anim-voice' : ''
        }`}
        aria-hidden="true"
      >
        {Array.from({ length: 12 }).map((_, i) => (
          <span
            key={i}
            className={`w-[3px] rounded-full ${speaking ? 'voice-bar' : 'bg-hud-dim/60'} ${
              speaking ? 'bg-hud-green' : ''
            }`}
            style={speaking ? { animationDelay: `${i * 0.08}s` } : undefined}
          />
        ))}
        <span className="ml-2 font-hud text-[10px] tracking-widest text-hud-dim">
          {speaking ? '))) SPEAKING (((' : props.muted ? '● MUTED' : '● MONITORING'}
        </span>
      </div>

      {/* Last uttered sentence */}
      <div className="mb-4 min-h-[3rem] rounded-lg border border-hud-border/60 bg-hud-panel2/60 p-3">
        <p className="mb-1 font-hud text-[10px] tracking-widest text-hud-dim">LAST UTTERANCE</p>
        <p className="font-hud text-sm leading-snug text-hud-text">
          {props.lastText || 'No voice output yet. Run an analysis to hear risk alerts.'}
        </p>
      </div>

      {/* Live threat info from the SAME authoritative event (item 28) */}
      <div className="mb-4 rounded-lg border border-hud-border/60 bg-hud-panel2/60 p-3">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="flex items-center gap-1 font-hud text-[10px] tracking-widest text-hud-dim">
            <AlertTriangle className="h-3 w-3 text-hud-amber" />
            CURRENT ALERT
          </span>
          <span className="font-hud text-xs font-semibold text-hud-amber">{alertRisk}</span>
        </div>
        <div className="space-y-1">
          <AlertRow label="DIRECTION" value={alert?.direction ?? '—'} />
          <AlertRow label="VEHICLE" value={alert?.vehicle_class ?? alert?.class_name ?? '—'} />
          <AlertRow label="TRACK" value={alert?.track_id != null ? String(alert.track_id) : '—'} />
          <AlertRow label="SPEED" value={alertSpeed} />
          <AlertRow
            label="TTC"
            value={alert?.ttc_seconds ?? alert?.ttc != null ? `${alert?.ttc_seconds ?? alert?.ttc}s` : '—'}
          />
          <AlertRow label="LANG" value={alert?.language ?? props.currentLanguage} />
        </div>
      </div>

      {/* Controls */}
      <div className="mb-4 grid grid-cols-2 gap-2">
        <button
          type="button"
          className={props.enabled ? 'btn-hud' : 'btn-hud-secondary'}
          onClick={props.onToggleEnabled}
          title={props.enabled ? 'Disable the voice assistant' : 'Enable the voice assistant'}
        >
          <Power className="h-4 w-4" />
          {props.enabled ? 'ON' : 'OFF'}
        </button>
        <button
          type="button"
          className={props.muted ? 'btn-hud-secondary' : 'btn-hud'}
          onClick={props.onToggleMuted}
          title={props.muted ? 'Unmute the voice assistant' : 'Mute the voice assistant'}
        >
          {props.muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          {props.muted ? 'UNMUTE' : 'MUTE'}
        </button>
      </div>

      <div className="mb-4">
        <div className="mb-1 flex items-center justify-between">
          <span className="hud-label">VOICE VOLUME</span>
          <span className="font-hud text-xs text-hud-cyan">{Math.round(props.volume * 100)}%</span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={props.volume}
          onChange={(e) => props.onVolumeChange(parseFloat(e.target.value))}
          className="w-full accent-hud-cyan"
          aria-label="Voice assistant volume"
        />
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2">
        <button type="button" className="btn-hud-secondary" onClick={props.onTest}>
          <Zap className="h-4 w-4" />
          TEST VOICE
        </button>
        <button
          type="button"
          className={props.listening ? 'btn-hud' : 'btn-hud-secondary'}
          onClick={props.onMic}
          disabled={!props.micAvailable}
          title={
            props.micAvailable
              ? 'Ask a question with your microphone'
              : 'Microphone unavailable in this browser'
          }
        >
          {props.micAvailable ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
          {props.listening ? 'LISTENING…' : 'ASK'}
        </button>
      </div>

      {/* Conversational ask */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submitAsk();
          }}
          placeholder={
            props.jobId ? 'Ask the assistant… e.g. "is it safe?"' : 'Run an analysis to ask questions'
          }
          disabled={!props.jobId}
          className="w-full rounded-lg border border-hud-border bg-hud-panel2/60 px-3 py-2 text-sm text-hud-text outline-none placeholder:text-hud-dim/70 focus:border-hud-cyan/50 disabled:cursor-not-allowed disabled:opacity-50"
        />
        <button
          type="button"
          className="btn-hud px-3"
          onClick={submitAsk}
          disabled={!props.jobId || !question.trim()}
          title="Send question"
        >
          <MessageSquare className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-hud-border/50 pt-2">
        <span className="flex items-center gap-1.5 font-hud text-[10px] tracking-widest text-hud-dim">
          <Activity className="h-3 w-3 text-hud-cyan" />ALERTS: {props.alerts}
        </span>
        <span className="font-hud text-[10px] tracking-widest text-hud-dim">
          {props.micAvailable ? 'MIC READY' : 'MIC UNAVAILABLE'}
        </span>
      </div>
    </div>
  );
}