import { useEffect, useMemo, useRef, useState } from 'react';
import { Header } from './components/Header';
import { VideoSection } from './components/VideoSection';
import { SystemStatus } from './components/SystemStatus';
import { CurrentThreat } from './components/CurrentThreat';
import { SystemDetails } from './components/SystemDetails';
import { DirectionAlert } from './components/DirectionAlert';
import { RiskGauge } from './components/RiskGauge';
import { TTCDisplay } from './components/TTCDisplay';
import { PerceptionPanel } from './components/PerceptionPanel';
import { TrafficMiniMap } from './components/TrafficMiniMap';
import { EventLog } from './components/EventLog';
import { VoiceAssistantHud } from './components/VoiceAssistantHud';
import { api } from './api';
import { API_BASE } from './config';
import { ErrorBoundary } from './components/ErrorBoundary';
import { getVerdict } from './utils/verdict';
import { voiceEngine } from './voice/voiceEngine';
import { VOICE_PRIORITIES } from './voice/voiceEngine';
import { DEFAULT_VOICE_LANGUAGE, isSupportedLanguage } from './voice/languages';
import type { JobSnapshot, VoiceAlert, VoiceAssistantState } from './types';

interface SelectedVideo {
  file_path: string;
  file_name: string;
  display_name: string;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function getRecognizer(): any {
  const w = window as any;
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export default function App() {
  const [confidence, setConfidence] = useState(0.5);
  const [selectedVideo, setSelectedVideo] = useState<SelectedVideo | null>(null);
  const [job, setJob] = useState<JobSnapshot | null>(null);
  const [apiUp, setApiUp] = useState(true);
  const socketRef = useRef<WebSocket | null>(null);

  // Part 4: voice safety assistant UI state (mirrors the shared voiceEngine).
  const [voiceState, setVoiceState] = useState<VoiceAssistantState>(() => voiceEngine.getState());
  const [lastSpoken, setLastSpoken] = useState('');
  const [voiceAlertCount, setVoiceAlertCount] = useState(0);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [voiceMuted, setVoiceMuted] = useState(false);
  const [voiceVolume, setVoiceVolume] = useState(1);
  const [lastVoiceAlert, setLastVoiceAlert] = useState<VoiceAlert | null>(null);
  const [listening, setListening] = useState(false);
  const [micAvailable, setMicAvailable] = useState(false);
  const recognizerRef = useRef<any>(null);

  const [voiceLanguage, setVoiceLanguageState] = useState<string>(() => {
    try {
      const saved = localStorage.getItem('voice.language');
      if (saved && isSupportedLanguage(saved)) {
        voiceEngine.setLanguage(saved);
        return saved;
      }
    } catch {
      // ignore storage errors
    }
    return voiceEngine.getLanguage() || DEFAULT_VOICE_LANGUAGE;
  });

  const handleLanguageChange = (lang: string) => {
    setVoiceLanguageState(lang);
    voiceEngine.setLanguage(lang);
    try {
      localStorage.setItem('voice.language', lang);
    } catch {
      // ignore storage errors
    }
    if (job?.job_id) {
      api.voiceLanguage(job.job_id, lang).catch((err) =>
        console.error('voice language sync failed', err)
      );
    }
  };

  useEffect(() => {
    const unsubscribe = voiceEngine.subscribe((state, detail) => {
      setVoiceState(state);
      if (detail) setLastSpoken(detail);
    });
    // Keep the shared engine enabled/monitoring once the HUD is mounted.
    voiceEngine.setEnabled(true);
    return unsubscribe;
  }, []);

  useEffect(() => {
    setMicAvailable(!!getRecognizer());
    return () => {
      try {
        recognizerRef.current?.stop();
      } catch {
        // ignore
      }
      recognizerRef.current = null;
    };
  }, []);

  const submitQuestion = async (question: string) => {
    const jobId = job?.job_id;
    if (!jobId || !question.trim()) return;
    try {
      const res = await api.voiceQuery(jobId, question.trim());
      if (res.answer) {
        voiceEngine.speakText(res.answer, VOICE_PRIORITIES.QUERY, 'answer');
        setLastSpoken(res.answer);
      }
    } catch (err) {
      console.error('voice query failed', err);
    }
  };

  const stopListening = () => {
    try {
      recognizerRef.current?.stop();
    } catch {
      // ignore
    }
    recognizerRef.current = null;
    setListening(false);
  };

  const handleMic = () => {
    if (listening) {
      stopListening();
      return;
    }
    const recognizer = getRecognizer();
    if (!recognizer) {
      setMicAvailable(false);
      return;
    }
    recognizer.lang = 'en-US';
    recognizer.interimResults = false;
    recognizer.onresult = (ev: any) => {
      const transcript = ev?.results?.[0]?.[0]?.transcript ?? '';
      if (transcript) void submitQuestion(transcript);
    };
    recognizer.onerror = () => setListening(false);
    recognizer.onend = () => setListening(false);
    recognizerRef.current = recognizer;
    try {
      recognizer.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  };

  const voiceAlertTotal = Math.max(voiceAlertCount, job?.voice?.alerts ?? 0);

  // Surface a clear banner when the backend is unreachable instead of silently 502-ing video fetches.
  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (alive) setApiUp(res.ok);
      } catch {
        if (alive) setApiUp(false);
      }
    };
    void check();
    const t = setInterval(() => void check(), 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const headerStatus: 'idle' | 'live' | 'processing' = useMemo(() => {
    if (job?.status === 'running') return 'processing';
    if (job?.status === 'completed') return 'live';
    return 'idle';
  }, [job]);

  const handleUpload = async (file: File) => {
    try {
      const res = await api.uploadVideo(file);
      setSelectedVideo({
        file_path: res.path,
        file_name: res.saved_filename,
        display_name: res.filename,
      });
      setJob(null);
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handleSelectSourceVideo = (video: { file_path: string; file_name: string; display_name?: string }) => {
    setSelectedVideo({
      file_path: video.file_path,
      file_name: video.file_name,
      display_name: video.display_name ?? video.file_name,
    });
    setJob(null);
  };

  const handleStartProcessing = async () => {
    if (!selectedVideo) return;
    try {
      const newJob = await api.startProcessing(selectedVideo.file_path, confidence);
      setJob(newJob);
      setVoiceAlertCount(0);
      openSocket(newJob.job_id);
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : 'Failed to start processing');
    }
  };

  const pollCancelRef = useRef<(() => void) | null>(null);

  const stopPolling = () => {
    if (pollCancelRef.current) {
      pollCancelRef.current();
      pollCancelRef.current = null;
    }
  };

  const openSocket = (jobId: string) => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    stopPolling();
    let finished = false;
    let gotResult = false;

    const startPollFallback = () => {
      if (pollCancelRef.current) return;
      if (finished && gotResult) return;
      pollCancelRef.current = api.pollJob(jobId, {
        onUpdate: (snap) => {
          setJob((prev) =>
            prev
              ? {
                  ...prev,
                  status: snap.status,
                  progress: snap.progress,
                  step: snap.step,
                  stage: snap.stage ?? prev.stage,
                  frame: snap.frame,
                  total: snap.total,
                  error: snap.error,
                  has_result: snap.has_result,
                }
              : prev
          );
        },
        onDone: (snap) => {
          finished = true;
          gotResult = true;
          stopPolling();
          setJob((prev) =>
            prev ? { ...prev, result: snap.result, has_result: true, status: 'completed' } : prev
          );
        },
        onError: (msg) => {
          console.error('polling fallback error', msg);
        },
      });
    };

    const ws = api.openJobSocket(jobId, {
      onProgress: (p) => {
        setJob((prev) =>
          prev
            ? {
                ...prev,
                status: p.status as JobSnapshot['status'],
                progress: p.progress,
                step: p.step,
                stage: p.stage ?? prev.stage,
                frame: p.frame,
                total: p.total,
                error: p.error,
                has_result: p.has_result,
              }
            : prev
        );
      },
      onResult: (result) => {
        finished = true;
        gotResult = true;
        stopPolling();
        setJob((prev) =>
          prev ? { ...prev, result, has_result: true, status: 'completed' } : prev
        );
      },
      onDone: () => {
        finished = true;
        ws.close();
        socketRef.current = null;
        if (!gotResult) startPollFallback();
        else stopPolling();
      },
      onError: (msg) => {
        console.error('socket error', msg);
        startPollFallback();
      },
      onVoiceAlert: (alert) => {
        voiceEngine.speakAlert(alert);
        setLastVoiceAlert(alert);
        setVoiceAlertCount((count) => count + 1);
      },
    });
    ws.onclose = () => {
      if (!finished || !gotResult) startPollFallback();
    };
    const openTimer = setTimeout(() => {
      if (!finished && ws.readyState !== WebSocket.OPEN) startPollFallback();
    }, 4000);
    const origClose = ws.close.bind(ws);
    ws.close = (...args: Parameters<typeof origClose>) => {
      clearTimeout(openTimer);
      return origClose(...args);
    };
    socketRef.current = ws;
  };

  const handleReset = () => {
    stopListening();
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    stopPolling();
    setSelectedVideo(null);
    setJob(null);
  };

  useEffect(() => {
    return () => {
      if (socketRef.current) socketRef.current.close();
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const processing = job?.status === 'running';
  const result = job?.status === 'completed' ? job.result ?? null : null;

  const headerDetail = processing
    ? 'Processing video…'
    : job?.status === 'error'
      ? 'Processing failed'
      : result
        ? 'Analysis complete'
        : selectedVideo
          ? 'Video ready'
          : 'No video selected';

  const verdict = result ? getVerdict(result) : null;
  const threat = result?.primary_threat ?? null;
  const riskValue =
    result?.stats?.cumulative_max_risk ??
    result?.risk_summary?.max_risk_score ??
    null;

  return (
    <div className="min-h-screen bg-hud-bg">
      {/* Ambient background glow */}
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute -top-32 left-1/4 h-96 w-96 rounded-full bg-hud-cyan/5 blur-3xl" />
        <div className="absolute top-1/2 right-0 h-96 w-96 rounded-full bg-hud-blue/5 blur-3xl" />
      </div>

      <div className="relative z-10">
        <Header status={headerStatus} detail={headerDetail} />

        {!apiUp && (
          <div className="relative z-20 border-b border-hud-red/40 bg-hud-red/10 px-4 py-2 text-center font-hud text-xs font-semibold tracking-widest text-hud-red">
            ⚠ API OFFLINE — START THE BACKEND (uvicorn on port 8000) TO FETCH &amp; ANALYZE VIDEOS
          </div>
        )}

        <main className="mx-auto max-w-[1700px] px-4 py-5 sm:px-6">
          {/* Directional alert — full width at top */}
          <div className="mb-5">
            <ErrorBoundary section="directional alert">
              <DirectionAlert threat={threat} verdictThreat={verdict?.collision_risk_detected ?? false} />
            </ErrorBoundary>
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
            {/* Left / Main Column */}
            <div className="space-y-5">
              <ErrorBoundary section="video analysis">
                <VideoSection
                  job={job}
                  videoPath={selectedVideo?.file_path ?? null}
                  selectedFilename={selectedVideo?.file_name ?? null}
                  selectedDisplayName={selectedVideo?.display_name ?? null}
                  confidence={confidence}
                  onConfidenceChange={setConfidence}
                  onReset={handleReset}
                  onFileSelected={handleUpload}
                  onSelectSourceVideo={handleSelectSourceVideo}
                  onStartProcessing={handleStartProcessing}
                  processing={processing}
                />
              </ErrorBoundary>

              <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
                <ErrorBoundary section="perception">
                  <PerceptionPanel result={result} />
                </ErrorBoundary>
                <ErrorBoundary section="traffic map">
                  <TrafficMiniMap result={result} />
                </ErrorBoundary>
                <ErrorBoundary section="event log">
                  <EventLog job={job} />
                </ErrorBoundary>
              </div>
            </div>

            {/* Right Column — Instruments */}
            <div className="space-y-5">
              <ErrorBoundary section="risk gauge">
                <RiskGauge
                  value={riskValue}
                  label="RISK GAUGE"
                  hint={result ? 'PEAK COLLISION RISK ACROSS ANALYSIS · REAL BACKEND METRIC' : 'ANALYSIS REQUIRED — RUN THE PIPELINE TO POPULATE RISK'}
                />
              </ErrorBoundary>
              <ErrorBoundary section="time to collision">
                <TTCDisplay threat={threat} />
              </ErrorBoundary>
              <ErrorBoundary section="voice assistant">
                <VoiceAssistantHud
                  voiceState={voiceState}
                  lastText={lastSpoken}
                  alerts={voiceAlertTotal}
                  enabled={voiceEnabled}
                  muted={voiceMuted}
                  volume={voiceVolume}
                  jobId={job?.job_id ?? null}
                  listening={listening}
                  micAvailable={micAvailable}
                  currentLanguage={voiceLanguage}
                  lastAlert={lastVoiceAlert}
                  onToggleEnabled={() => {
                    const next = !voiceEnabled;
                    setVoiceEnabled(next);
                    voiceEngine.setEnabled(next);
                  }}
                  onToggleMuted={() => {
                    const next = !voiceMuted;
                    setVoiceMuted(next);
                    voiceEngine.setMuted(next);
                  }}
                  onVolumeChange={(v) => {
                    setVoiceVolume(v);
                    voiceEngine.setVolume(v);
                  }}
                  onTest={() => voiceEngine.test()}
                  onAsk={(q) => void submitQuestion(q)}
                  onMic={() => handleMic()}
                  onLanguageChange={handleLanguageChange}
                />
              </ErrorBoundary>
              <ErrorBoundary section="driver status">
                <SystemStatus
                  status={headerStatus}
                  stats={result?.stats ?? null}
                  hasVideo={!!selectedVideo}
                />
              </ErrorBoundary>
            </div>
          </div>

          {/* Bottom — Threat + System Details */}
          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <ErrorBoundary section="threat analysis">
              <CurrentThreat result={result} live={!!result && job?.status === 'completed'} />
            </ErrorBoundary>
            <ErrorBoundary section="system details">
              <SystemDetails result={result} />
            </ErrorBoundary>
          </div>

          <footer className="pt-4 pb-2 text-center font-hud text-[11px] tracking-widest text-hud-dim">
            AI COLLISION ANTICIPATION SYSTEM · SOFTWARE SIMULATION PROTOTYPE · DETECTION | TRACKING | PREDICTION | ALERT
          </footer>
        </main>
      </div>
    </div>
  );
}