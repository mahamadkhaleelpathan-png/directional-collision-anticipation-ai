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
 * - Robustness against real browser bugs:
 *     * voices are pre-loaded (getVoices() may be empty at script load; we
 *       listen for `voiceschanged` and retry-poll a few times),
 *     * Chrome can silently stop firing `onend` (utterance "stuck") — a
 *       watchdog recovers the queue instead of freezing,
 *     * Chrome auto-pauses speech output after a while — the watchdog calls
 *       resume() while speaking,
 *     * an utterance that never starts (autoplay blocked / no usable voice)
 *       is reported as BLOCKED/NO_VOICE instead of staying SPEAKING forever.
 * - Mute, volume, enable/disable, live language and a self-test are exposed
 *   for the HUD, plus an honest ACTIVE VOICE status line.
 * - Threat-to-speech latency is measured (enqueue -> onstart) and logged.
 *
 * Single shared instance (see `voiceEngine` below) — React never creates a
 * second engine, so there are never duplicate speechSynthesis listeners.
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

/** Honest active-voice info for the HUD status line. */
export interface VoiceEngineInfo {
  available: boolean;
  provider: string;
  voicesCount: number;
  requestedLocale: string;
  /** Voice actually matched for the requested locale, if any. */
  selectedVoiceName: string | null;
  selectedVoiceLocale: string | null;
  /** true when a same-language fallback voice (e.g. ``hi``) was used. */
  fallbackVoiceAvailable: boolean;
  /** true when the active voice does NOT match the requested language. */
  isFallback: boolean;
  /** true when the requested language has an exact browser voice. */
  exactVoiceAvailable: boolean;
  /** true when a usable voice could be resolved for the requested language. */
  supported: boolean;
}

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

/** Utterance that never fired onstart within this window is treated as blocked. */
const BLOCKED_AFTER_MS = 2500;
/** Utterance whose onend never fires within this window is treated as stalled. */
const STALL_AFTER_MS = 1200;
/** Periodically resume(); defeats Chrome's automatic voice auto-pause. */
const RESUME_EVERY_MS = 1000;
/** Watchdog poll cadence. */
const WATCHDOG_MS = 300;

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
  private voices: SpeechSynthesisVoice[] = [];
  private voicesLoaded = false;
  private lastSpokenText = '';
  private activeVoice: SpeechSynthesisVoice | null = null;
  private started = false;
  private utterAt = 0;
  private blockedReported = false;
  private stalledReported = false;
  private lastResumeAt = 0;
  private voiceRetryTimer: number | null = null;
  private watchdogTimer: number | null = null;
  private _voicesReadyEmitted = false;

  constructor() {
    this.ttsAvailable = this.detectTts();
    if (this.ttsAvailable) {
      this.loadVoices();
      try {
        window.speechSynthesis.onvoiceschanged = () => {
          this.loadVoices();
        };
      } catch {
        /* older engines: retry-poll below */
      }
      this.startWatchdog();
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

  private loadVoices(): void {
    try {
      this.voices = window.speechSynthesis.getVoices();
    } catch {
      this.voices = [];
    }
    this.voicesLoaded = this.voices.length > 0;
    // Re-render the HUD diagnostics once voices become available.
    if (this.voicesLoaded && !this._voicesReadyEmitted) {
      this._voicesReadyEmitted = true;
      const first = this.voices[0];
      console.info(
        `VOICE VOICES READY count=${this.voices.length} sample="${first?.name ?? 'none'}" ${first?.lang ?? ''}`.trim(),
      );
      this.listeners.forEach((l) => l(this.state, this.lastSpokenText));
    }
    // Fallback for engines where `voiceschanged` never fires: probe a few times.
    if (!this.voicesLoaded && this.voiceRetryTimer === null) {
      let tries = 0;
      this.voiceRetryTimer = window.setInterval(() => {
        tries += 1;
        try {
          this.voices = window.speechSynthesis.getVoices();
        } catch {
          this.voices = [];
        }
        this.voicesLoaded = this.voices.length > 0;
        if (this.voicesLoaded || tries >= 8) {
          if (this.voiceRetryTimer !== null) window.clearInterval(this.voiceRetryTimer);
          this.voiceRetryTimer = null;
        }
        if (this.voicesLoaded) {
          const first = this.voices[0];
          console.info(
            `VOICE VOICES READY count=${this.voices.length} sample="${first?.name ?? 'none'}" ${first?.lang ?? ''}`.trim(),
          );
          if (!this._voicesReadyEmitted) {
            this._voicesReadyEmitted = true;
            this.listeners.forEach((l) => l(this.state, this.lastSpokenText));
          }
        }
      }, 250);
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

  /** Honest status: what voice is available/active vs what was requested. */
  getVoiceInfo(): VoiceEngineInfo {
    const voices = this.voices.length ? this.voices : [];
    let active = this.activeVoice;
    if (!active) active = this.pickVoice(this.lang, false) as SpeechSynthesisVoice | null;
    const requested = this.lang || DEFAULT_LANG;
    const target = requested.toLowerCase().replace('_', '-');
    const baseLang = target.split('-')[0];
    const exact = !!active && active.lang.toLowerCase().replace('_', '-') === target;
    const base =
      !!active && !exact && active.lang.toLowerCase().replace('_', '-').split('-')[0] === baseLang;
    return {
      available: this.ttsAvailable,
      provider: this.ttsAvailable ? 'Browser SpeechSynthesis' : 'Web Speech API unavailable',
      voicesCount: voices.length,
      requestedLocale: requested,
      selectedVoiceName: active ? active.name : null,
      selectedVoiceLocale: active ? active.lang : null,
      fallbackVoiceAvailable: base,
      isFallback: !!active && !exact && !base,
      exactVoiceAvailable: exact,
      supported: this.ttsAvailable && voices.length > 0 && (exact || base),
    };
  }

  /**
   * Diagnostics snapshot (Phase 19): requested locale, whether an exact or
   * same-language fallback voice was found, the chosen voice, provider and
   * supported flag. Used by the HUD status panel and dev console.
   */
  getVoiceDiagnostics(): VoiceEngineInfo {
    return this.getVoiceInfo();
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
      this.blockedReported = false;
      this.stalledReported = false;
      // Chrome requires a user gesture before audio may play; resume() here
      // (called from a click handler) unlocks the synthesis engine.
      if (this.ttsAvailable) {
        try {
          window.speechSynthesis.resume();
        } catch {
          /* ignore */
        }
      }
      if (this.queue.length) this.playNext();
      else this.setState('MONITORING');
    }
  }

  setMuted(on: boolean): void {
    this.muted = on;
    if (on) {
      this.cancelSpeakingOnly();
      this.setState('MUTED');
    } else if (this.state === 'MUTED') {
      if (this.ttsAvailable) {
        try {
          window.speechSynthesis.resume();
        } catch {
          /* ignore */
        }
      }
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
    if (!this.ttsAvailable) {
      this.setState('OFFLINE', 'Web Speech API unavailable');
      return;
    }
    try {
      window.speechSynthesis.resume();
    } catch {
      /* ignore */
    }
    // Unlock voices that were still loading.
    if (!this.voicesLoaded) this.loadVoices();
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

    if (this.queue.length >= MAX_QUEUE) {
      // Never drop the newest high-priority item: drop the LOWEST-priority
      // pending item instead of the newest (keeps CRITICAL/HIGH alive).
      const lowest = this.queue[this.queue.length - 1];
      if (full.priority <= lowest.priority && this.queue.length > 0) {
        return; // new item is not more important than what we already hold
      }
      this.queue.pop(); // remove the current lowest-priority pending item
    }
    this.queue.push(full);
    this.queue.sort((a, b) => b.priority - a.priority || b.id.localeCompare(a.id));

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
        // Chrome sometimes needs a resume() after cancel() before the next
        // speak() will produce audio.
        window.speechSynthesis.resume();
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
    this.started = false;
    this.activeVoice = null;
    this.blockedReported = false;
    this.stalledReported = false;
  }

  private pickVoice(lang: string, markActive = true): SpeechSynthesisVoice | null {
    try {
      const voices = this.voices.length ? this.voices : window.speechSynthesis.getVoices();
      if (!voices.length) return null;
      const target = lang.toLowerCase().replace('_', '-');
      const exact = voices.find((v) => v.lang.toLowerCase().replace('_', '-') === target);
      if (exact) {
        if (markActive) this.activeVoice = exact;
        return exact;
      }
      const base = target.split('-')[0];
      const baseMatch = voices.find((v) => v.lang.toLowerCase().startsWith(base)) ?? null;
      if (markActive) this.activeVoice = baseMatch;
      return baseMatch;
    } catch {
      return null;
    }
  }

  // ------------------------------------------------------------ watchdog

  private startWatchdog(): void {
    if (this.watchdogTimer !== null) return;
    this.watchdogTimer = window.setInterval(() => {
      if (!this.utter || !this.ttsAvailable) return;
      const now = Date.now();
      const synth = window.speechSynthesis;
      const age = now - this.utterAt;

      // A) Chrome auto-pause: keep the synthesis engine awake while speaking.
      if (this.started && synth.speaking && now - this.lastResumeAt >= RESUME_EVERY_MS) {
        this.lastResumeAt = now;
        try {
          synth.resume();
        } catch {
          /* ignore */
        }
        return;
      }

      // B) Utterance never started (autoplay blocked / no usable voice).
      if (!this.started && age >= BLOCKED_AFTER_MS) {
        if (!this.blockedReported) {
          this.blockedReported = true;
          const msg = this.voicesLoaded
            ? 'Audio blocked by the browser — click ENABLE VOICE once, then TEST VOICE'
            : 'No usable speech voice found for this browser — speech is unavailable';
          console.warn(`VOICE BLOCKED after ${age}ms (voices=${this.voices.length})`);
          this.setState(this.voicesLoaded ? 'BLOCKED' : 'NO_VOICE', msg);
        }
        this.cancelSpeakingOnly();
        // Keep the queue; the next real event (or user enable/re-test) retries.
        this.queue = [];
        this.setState(this.muted ? 'MUTED' : 'MONITORING');
        return;
      }

      // C) Started but Chrome never fired onend (stalled utterance).
      if (this.started && !synth.speaking && !synth.pending && age >= STALL_AFTER_MS) {
        if (!this.stalledReported) {
          this.stalledReported = true;
          console.warn(`VOICE STALLED: onend not fired after ${age}ms — recovering queue`);
        }
        const failed = this.utter;
        this.utter = null;
        if (failed) {
          failed.onend = null;
          failed.onerror = null;
        }
        if (this.speaking) {
          this.speaking = null;
          this.started = false;
          if (this.enabled && !this.muted) this.playNext();
          return;
        }
        this.started = false;
        this.setState(this.muted ? 'MUTED' : 'MONITORING');
      }
    }, WATCHDOG_MS);
  }

  // -------------------------------------------------------------- internal

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
      this.started = false;
      this.setState(this.muted ? 'MUTED' : 'MONITORING');
      return;
    }
    this.speaking = item;
    this.lastSpokenText = item.text;
    this.blockedReported = false;
    this.stalledReported = false;

    const utterance = new SpeechSynthesisUtterance(item.text);
    this.utter = utterance;
    this.started = false;
    this.utterAt = Date.now();
    utterance.lang = item.lang || this.lang;
    utterance.volume = this.volume;
    // Safety-alert pacing: not too fast, not too slow.
    utterance.rate = 1;
    utterance.pitch = 1;
    const voice = this.pickVoice(item.lang);
    if (voice) utterance.voice = voice;
    const enqueuedAt = item.enqueuedAt || Date.now();
    utterance.onstart = () => {
      this.started = true;
      this.utterAt = Date.now();
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

    try {
      window.speechSynthesis.resume();
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
    this.started = false;

    if (this.enabled && !this.muted) this.playNext();
    else this.setState(this.muted ? 'MUTED' : 'MONITORING');
  }
}

/** Shared singleton used by the HUD and the App's WebSocket handler. */
export const voiceEngine = new VoiceEngine();