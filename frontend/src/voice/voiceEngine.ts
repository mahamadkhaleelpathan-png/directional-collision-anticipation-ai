/**
 * Browser TTS playback engine for the voice safety assistant (Part 4).
 *
 * The backend is the single source of truth for WHAT is spoken (risk level,
 * direction, TTC, speed, language). This engine only decides WHEN/HOW audio is
 * played:
 * - A priority queue (mirror of the backend PRIORITY_MAP) where a higher
 *   priority utterance interrupts a lower one that is currently speaking.
 * - Honest connection to the Web Speech API: if the browser exposes no
 *   speechSynthesis, the engine reports `OFFLINE` instead of faking audio.
 * - Per-utterance language: the backend's message language is applied to each
 *   SpeechSynthesisUtterance and the best matching browser voice is selected
 *   for that locale (live language switching from the HUD).
 * - Mute, volume, enable/disable, live language and a self-test are exposed
 *   for the HUD.
 * - Threat-to-speech latency is measured (enqueue -> onstart) and logged.
 *
 * No new dependencies and no hard-coded secrets; everything runs client-side.
 */
import {
  VOICE_PRIORITIES as VOICE_PRIORITIES_,
  type VoiceAlert,
  type VoiceAssistantState,
} from '../types';
import {
  DEFAULT_VOICE_LANGUAGE,
  VOICE_TEST_TEXT_BY_LANG,
  type VoiceLanguageCode,
} from './languages';

export const VOICE_PRIORITIES = VOICE_PRIORITIES_;

export type VoiceEngineListener = (state: VoiceAssistantState, detail?: string) => void;

interface PlaybackItem {
  id: string;
  text: string;
  priority: number;
  kind: string;
  lang: string;
  enqueuedAt: number;
}

const MAX_QUEUE = 20;
const DEFAULT_LANG = DEFAULT_VOICE_LANGUAGE;
let instanceCounter = 0;

export class VoiceEngine {
  private enabled = true;
  private muted = false;
  private volume = 1.0;
  private queue: PlaybackItem[] = [];
  private speaking: PlaybackItem | null = null;
  private utter: SpeechSynthesisUtterance | null = null;
  private lang: string = DEFAULT_LANG;
  private state: VoiceAssistantState = 'IDLE';
  private listeners: Set<VoiceEngineListener> = new Set();
  private ttsAvailable = false;
  private lastSpokenText = '';
  private voices: SpeechSynthesisVoice[] = [];

  constructor() {
    this.ttsAvailable = this.detectTts();
    if (this.ttsAvailable) {
      try {
        this.voices = window.speechSynthesis.getVoices();
        window.speechSynthesis.onvoiceschanged = () => {
          this.voices = window.speechSynthesis.getVoices();
        };
      } catch {
        this.voices = [];
      }
    }
  }

  // ------------------------------------------------------------- utilities

  private detectTts(): boolean {
    try {
      return typeof window !== 'undefined' && 'speechSynthesis' in window;
    } catch {
      return false;
    }
  }

  isTtsAvailable(): boolean {
    return this.ttsAvailable;
  }

  getState(): VoiceAssistantState {
    return this.state;
  }

  getVolume(): number {
    return this.volume;
  }

  getLanguage(): string {
    return this.lang;
  }

  isEnabled(): boolean {
    return this.enabled;
  }

  isMuted(): boolean {
    return this.muted;
  }

  pendingCount(): number {
    return this.queue.length;
  }

  lastSpeakingText(): string {
    return this.lastSpokenText;
  }

  subscribe(listener: VoiceEngineListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private setState(next: VoiceAssistantState, detail?: string): void {
    this.state = next;
    this.listeners.forEach((l) => l(next, detail));
  }

  private nextItemId(): string {
    instanceCounter += 1;
    return `vb-${Date.now()}-${instanceCounter}`;
  }

  // ---------------------------------------------------------------- control

  setEnabled(on: boolean): void {
    this.enabled = on;
    if (!on) {
      this.cancelAll();
      this.setState('IDLE');
    } else if (this.muted) {
      this.setState('MUTED');
    } else {
      this.setState('MONITORING');
    }
  }

  setMuted(on: boolean): void {
    this.muted = on;
    if (on) {
      this.cancelSpeakingOnly();
      this.setState('MUTED');
    } else if (this.state === 'MUTED') {
      if (this.queue.length) this.playNext();
      else this.setState('MONITORING');
    }
  }

  setVolume(v: number): void {
    this.volume = Math.min(1, Math.max(0, v));
    if (this.utter && this.ttsAvailable) this.utter.volume = this.volume;
  }

  /** Live language selection (affects the next utterance only). */
  setLanguage(code: string): void {
    this.lang = code || DEFAULT_LANG;
  }

  stop(): void {
    this.cancelAll();
    this.setState('MONITORING');
  }

  // ------------------------------------------------------------- playback

  /** Speak a backend `voice_alert` (priority + language come from backend). */
  speakAlert(alert: VoiceAlert): void {
    const fallback =
      VOICE_PRIORITIES[alert.risk_level as keyof typeof VOICE_PRIORITIES] ?? VOICE_PRIORITIES.SAFE;
    this.enqueue({
      id: alert.event_id || this.nextItemId(),
      text: alert.text || alert.message || '',
      priority: typeof alert.priority === 'number' ? alert.priority : fallback,
      kind: alert.kind || 'risk_alert',
      lang: alert.language || this.lang,
    });
  }

  speakText(text: string, priority: number, kind: string, lang?: string): void {
    this.enqueue({
      id: this.nextItemId(),
      text,
      priority,
      kind,
      lang: lang || this.lang,
    });
  }

  /** "Test voice" button: plays the per-language test line (item 48). */
  test(text?: string): void {
    const lang = this.lang as VoiceLanguageCode;
    this.enqueue({
      id: this.nextItemId(),
      text: text || VOICE_TEST_TEXT_BY_LANG[lang] || 'Voice assistant test successful.',
      priority: VOICE_PRIORITIES.TEST,
      kind: 'test',
      lang: this.lang,
    });
  }

  private enqueue(item: Omit<PlaybackItem, 'enqueuedAt'>): void {
    if (!this.enabled || this.muted) return;
    if (!item.text || !item.text.trim()) return;

    if (!this.ttsAvailable) {
      this.setState('OFFLINE', 'Web Speech API unavailable');
      return;
    }

    const full: PlaybackItem = { ...item, enqueuedAt: Date.now() };

    // Precedence: a higher-priority utterance preempts a lower one that is
    // currently speaking (backend CRITICAL/HIGH naturally win this way).
    const speakingPriority = this.speaking ? this.speaking.priority : -1;
    if (full.priority > speakingPriority) this.cancelSpeakingOnly();

    this.queue.push(full);
    this.queue.sort((a, b) => b.priority - a.priority || b.id.localeCompare(a.id));
    if (this.queue.length > MAX_QUEUE) this.queue = this.queue.slice(0, MAX_QUEUE);

    if (!this.speaking) this.playNext();
  }

  private cancelAll(): void {
    this.cancelSpeakingOnly();
    this.queue = [];
  }

  private cancelSpeakingOnly(): void {
    if (this.utter && this.ttsAvailable) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // browser quirks are harmless: handlers are still detached below
      }
    }
    if (this.utter) {
      const u = this.utter;
      u.onend = null;
      u.onerror = null;
    }
    this.utter = null;
    this.speaking = null;
  }

  private pickVoice(lang: string): SpeechSynthesisVoice | null {
    try {
      const voices = this.voices.length ? this.voices : window.speechSynthesis.getVoices();
      if (!voices.length) return null;
      const target = lang.toLowerCase().replace('_', '-');
      const exact = voices.find((v) => v.lang.toLowerCase().replace('_', '-') === target);
      if (exact) return exact;
      const base = target.split('-')[0];
      return voices.find((v) => v.lang.toLowerCase().startsWith(base)) ?? null;
    } catch {
      return null;
    }
  }

  private playNext(): void {
    if (this.muted || !this.enabled) {
      this.setState(this.muted ? 'MUTED' : 'MONITORING');
      return;
    }
    if (!this.ttsAvailable) {
      this.setState('OFFLINE', 'Web Speech API unavailable');
      return;
    }
    const item = this.queue.shift();
    if (!item) {
      this.speaking = null;
      this.setState(this.muted ? 'MUTED' : 'MONITORING');
      return;
    }
    this.speaking = item;
    this.lastSpokenText = item.text;

    const utterance = new SpeechSynthesisUtterance(item.text);
    this.utter = utterance;
    utterance.lang = item.lang || this.lang;
    utterance.volume = this.volume;
    utterance.rate = 1;
    utterance.pitch = 1;
    const voice = this.pickVoice(item.lang);
    if (voice) utterance.voice = voice;
    const enqueuedAt = item.enqueuedAt || Date.now();
    utterance.onstart = () => {
      const latencyMs = Date.now() - enqueuedAt;
      console.info(`VOICE PLAYBACK START latency_ms=${latencyMs} lang=${item.lang}`);
      this.setState('SPEAKING', item.text);
    };
    utterance.onend = () => this.finishPlayback(item);
    utterance.onerror = (ev: SpeechSynthesisErrorEvent) => {
      // A single failed utterance must not stop the whole assistant.
      this.setState('ERROR', `TTS utterance error: ${ev.error || 'error'}`);
      this.finishPlayback(item);
    };

    this.setState('SPEAKING', item.text);
    try {
      window.speechSynthesis.speak(utterance);
    } catch {
      this.setState('ERROR', 'TTS speak failed');
      this.finishPlayback(item);
    }
  }

  private finishPlayback(item: PlaybackItem): void {
    if (this.utter) {
      const ended = this.utter;
      this.utter = null;
      ended.onend = null;
      ended.onerror = null;
    }
    if (this.speaking && this.speaking.id !== item.id) return; // stale callback
    this.speaking = null;

    if (this.enabled && !this.muted) this.playNext();
    else this.setState(this.muted ? 'MUTED' : 'MONITORING');
  }
}

/** Shared singleton used by the HUD and the App's WebSocket handler. */
export const voiceEngine = new VoiceEngine();