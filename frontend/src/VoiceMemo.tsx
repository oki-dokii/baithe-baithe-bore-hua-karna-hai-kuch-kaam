import { FormEvent, useEffect, useRef, useState } from "react";
import "./voice-memo.css";

type Option = { wellbore_id: string; dataset_id: string; name: string; kind: string };

const SHIFT_TEMPLATES = [
  {
    label: "Barail Mud Loss",
    text: "Observed partial mud losses of 35 bbl/hr at 2,450 m MD in Barail sandstone. Reduced flow rate to 420 gpm; preparing 40 bbl high-viscosity LCM pill with mica and nutplug.",
  },
  {
    label: "Kopili Gas Kick",
    text: "Gas kick detected at 3,120 m MD in Kopili formation. Pit gain 14 bbl. Annular preventer closed. SIDPP 240 psi, SICP 310 psi. Commencing Driller's Method.",
  },
  {
    label: "Tight Hole / Drag",
    text: "High overpull and tight hole encountered while tripping out at 2,890 m MD. Maximum drag 35 klbf. Pumped 25 bbl lubricant pill and back-reamed to casing shoe.",
  },
  {
    label: "Drilling Optimization",
    text: "Drilling Tipam sandstone at 1,940 m MD. Parameters: WOB 18 klbf, RPM 110, Torque 11.5 kft-lb, ROP 22 m/hr. Mud weight maintained at 1.18 SG, zero fluid loss.",
  },
];

export default function VoiceMemo({ token, options, asrAvailable, onSaved }: {
  token: string; options: Option[]; asrAvailable: boolean; onSaved: (id: string) => void;
}) {
  const [consent, setConsent] = useState(false);
  const [wellbore, setWellbore] = useState(options[0]?.wellbore_id ?? "");
  const [language, setLanguage] = useState("en");
  const [transcript, setTranscript] = useState("");
  const [useAsr, setUseAsr] = useState(false);
  const [audio, setAudio] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [liveAsrActive, setLiveAsrActive] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);

  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speechRecognizer = useRef<any>(null);
  const animFrame = useRef<number | null>(null);
  const audioContext = useRef<AudioContext | null>(null);

  const browserAsrSupported = typeof window !== "undefined" &&
    Boolean((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

  useEffect(() => {
    if (!wellbore && options.length) setWellbore(options[0].wellbore_id);
  }, [options, wellbore]);

  useEffect(() => {
    if (!audio) return;
    const url = URL.createObjectURL(audio);
    setAudioUrl(url);
    return () => { URL.revokeObjectURL(url); setAudioUrl(""); };
  }, [audio]);

  useEffect(() => () => {
    if (timeout.current) clearTimeout(timeout.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
    if (speechRecognizer.current) {
      try { speechRecognizer.current.stop(); } catch { /* noop */ }
    }
    if (animFrame.current) cancelAnimationFrame(animFrame.current);
    if (audioContext.current) audioContext.current.close().catch(() => {});
    stream.current?.getTracks().forEach((track) => track.stop());
  }, []);

  function setupAudioMeter(mediaStream: MediaStream) {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      audioContext.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      const source = ctx.createMediaStreamSource(mediaStream);
      source.connect(analyser);
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const update = () => {
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;
        setAudioLevel(Math.min(100, Math.round((avg / 128) * 100)));
        animFrame.current = requestAnimationFrame(update);
      };
      update();
    } catch {
      // AudioContext meter fallback
    }
  }

  function startLiveSpeechRecognition() {
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) return;
    try {
      const recognizer = new SpeechRec();
      speechRecognizer.current = recognizer;
      recognizer.continuous = true;
      recognizer.interimResults = true;
      recognizer.lang = language === "hi" ? "hi-IN" : language === "as" ? "as-IN" : "en-IN";

      let finalSoFar = transcript ? transcript + " " : "";
      recognizer.onresult = (event: any) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalSoFar += event.results[i][0].transcript + " ";
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        setTranscript((finalSoFar + interim).trim());
      };
      recognizer.onerror = () => {
        setLiveAsrActive(false);
      };
      recognizer.onend = () => {
        setLiveAsrActive(false);
      };
      recognizer.start();
      setLiveAsrActive(true);
    } catch {
      setLiveAsrActive(false);
    }
  }

  function stopLiveSpeechRecognition() {
    if (speechRecognizer.current) {
      try { speechRecognizer.current.stop(); } catch { /* noop */ }
      speechRecognizer.current = null;
    }
    setLiveAsrActive(false);
  }

  async function start() {
    if (!consent) { setError("Confirm recording and 30-day audio retention first."); return; }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Microphone recording is unavailable in this browser or insecure context."); return;
    }
    setError(""); setAudio(null);
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = media;
      setupAudioMeter(media);

      const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find((type) => MediaRecorder.isTypeSupported(type));
      if (!mimeType) {
        media.getTracks().forEach((track) => track.stop()); stream.current = null;
        throw new Error("This browser cannot record WebM or MP4 audio for NWIS.");
      }
      const current = new MediaRecorder(media, { mimeType });
      recorder.current = current;
      const chunks: BlobPart[] = [];
      current.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      current.onstop = () => {
        setAudio(new Blob(chunks, { type: current.mimeType }));
        media.getTracks().forEach((track) => track.stop());
        stream.current = null;
        setRecording(false);
        setAudioLevel(0);
        if (animFrame.current) cancelAnimationFrame(animFrame.current);
        if (audioContext.current) { audioContext.current.close().catch(() => {}); audioContext.current = null; }
      };
      current.start();
      setRecording(true);
      timeout.current = setTimeout(stop, 60_000);

      // Trigger live speech recognition alongside recording if browser supports it
      if (browserAsrSupported && !useAsr) {
        startLiveSpeechRecognition();
      }
    } catch (e) { setError(`Microphone access failed: ${(e as Error).message}`); }
  }

  function stop() {
    if (timeout.current) clearTimeout(timeout.current);
    timeout.current = null;
    if (recorder.current?.state === "recording") recorder.current.stop();
    stopLiveSpeechRecognition();
  }

  function applyTemplate(tmplText: string) {
    setTranscript((prev) => (prev ? `${prev}\n\n${tmplText}` : tmplText));
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!audio || !consent) return;
    const option = options.find((item) => item.wellbore_id === wellbore);
    if (!option) { setError("Choose a wellbore."); return; }
    if (!useAsr && !transcript.trim()) { setError("Type or dictate and check the transcript before uploading."); return; }
    setBusy(true); setError("");
    const form = new FormData();
    const extension = audio.type.includes("mp4") ? "m4a" : audio.type.includes("wav") ? "wav" : "webm";
    form.append("audio", audio, `memo.${extension}`);
    form.append("dataset_id", option.dataset_id);
    form.append("wellbore_id", wellbore);
    form.append("language", language);
    form.append("consent", "true");
    form.append("transcript", useAsr ? "" : transcript.trim());
    try {
      const response = await fetch("/api/v1/voice-memos", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Idempotency-Key": crypto.randomUUID() },
        body: form,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error?.message ?? `Upload failed (${response.status})`);
      setAudio(null);
      setTranscript("");
      onSaved(result.id);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <section className="voice-memo-panel" aria-label="Voice memo capture">
      <div className="voice-memo-header">
        <p className="eyebrow">OIL Assam · Shift Verbal Logs</p>
        <h2>Capture Operational Spoken Note</h2>
      </div>
      <p>
        Audio stays in NWIS local storage for 30 days, then is purged. Its transcript serves as an
        unreviewed source passage; a drilling supervisor must verify and approve any extracted claim.
      </p>

      {/* Operational Template Presets */}
      <div className="voice-presets-row" style={{ marginBottom: "14px" }}>
        <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginRight: "8px", textTransform: "uppercase", letterSpacing: "0.05em", fontFamily: "var(--font-mono)" }}>
          Shift Templates:
        </span>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
          {SHIFT_TEMPLATES.map((tmpl) => (
            <button
              key={tmpl.label}
              type="button"
              className="secondary"
              style={{ fontSize: "0.75rem", padding: "4px 9px", borderRadius: "4px" }}
              onClick={() => applyTemplate(tmpl.text)}
            >
              + {tmpl.label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={upload}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          <label>
            Wellbore
            <select value={wellbore} onChange={(e) => setWellbore(e.target.value)}>
              {options.map((item) => (
                <option key={item.wellbore_id} value={item.wellbore_id}>
                  {item.name} · {item.kind}
                </option>
              ))}
            </select>
          </label>
          <label>
            Spoken language
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="en">English (India / General)</option>
              <option value="hi">Hindi (हिंदी)</option>
              <option value="as">Assamese (অসমীয়া)</option>
            </select>
          </label>
        </div>

        <label className="voice-consent">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          I have permission to record and retain this audio for 30 days under Oil India E&P operational policies.
        </label>

        {/* Live Audio Visualizer Bar */}
        {recording && (
          <div style={{
            background: "rgba(0,0,0,0.3)",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            padding: "8px 12px",
            display: "flex",
            alignItems: "center",
            gap: "10px"
          }}>
            <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--red-bright)", display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--red-bright)", animation: "pulse 1s infinite" }}></span>
              MIC LIVE
            </span>
            <div style={{ flex: 1, height: "8px", background: "var(--basin)", borderRadius: "4px", overflow: "hidden" }}>
              <div style={{
                height: "100%",
                width: `${audioLevel}%`,
                background: audioLevel > 70 ? "var(--red-bright)" : audioLevel > 30 ? "var(--teal-glow)" : "var(--slate-light)",
                transition: "width 0.1s ease"
              }} />
            </div>
            {liveAsrActive && (
              <span style={{ fontSize: "0.72rem", color: "var(--teal-glow)", fontFamily: "var(--font-mono)" }}>
                [Live Transcribing...]
              </span>
            )}
          </div>
        )}

        <div className="voice-actions">
          <button type="button" onClick={start} disabled={recording || busy || !consent} className={recording ? "recording" : ""}>
            {recording ? "● Recording Active" : "🎙 Record memo"}
          </button>
          <button type="button" className="secondary" onClick={stop} disabled={!recording}>
            ⏹ Stop Recording
          </button>
          {browserAsrSupported && !recording && (
            <button
              type="button"
              className="secondary"
              onClick={liveAsrActive ? stopLiveSpeechRecognition : startLiveSpeechRecognition}
              style={{ borderColor: liveAsrActive ? "var(--teal-glow)" : undefined }}
            >
              {liveAsrActive ? "⏹ Stop Dictation" : "🗣 Dictate Speech-to-Text"}
            </button>
          )}
          <span>
            {recording ? "Recording active · auto-stops after 60s" : audio ? "✓ Audio captured" : "Ready to record"}
          </span>
        </div>

        {audioUrl && (
          <div style={{ marginTop: "4px" }}>
            <audio controls src={audioUrl} aria-label="Review recorded memo" style={{ width: "100%" }} />
          </div>
        )}

        <label className="voice-transcript">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span>Verified transcript (Reviewer / Field Engineer)</span>
            {browserAsrSupported && (
              <span style={{ fontSize: "0.7rem", color: "var(--teal-glow)", fontFamily: "var(--font-mono)" }}>
                ✓ Web Speech API Available
              </span>
            )}
          </div>
          <textarea
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            disabled={useAsr}
            rows={5}
            maxLength={30000}
            placeholder="Write or dictate shift event details, preserving drilling depths, formation names, mud weights, and pressure numbers."
          />
        </label>

        <label className="voice-consent">
          <input
            type="checkbox"
            checked={useAsr}
            disabled={!asrAvailable}
            onChange={(e) => setUseAsr(e.target.checked)}
          />
          Let the configured local Whisper model produce a draft instead
        </label>

        <p className="footnote">
          {asrAvailable
            ? "Local-host ASR is available. Its likelihood score is uncalibrated; verify the transcript against audio before approving a claim."
            : browserAsrSupported
            ? "Browser Live Speech-to-Text is active for real-time dictation. Audio is preserved locally for verification."
            : "Local host ASR is not configured; typed or dictated transcript is required. No external cloud speech service is used."}
        </p>

        {error && <p className="error" role="alert">{error}</p>}

        <button disabled={!audio || !consent || busy || recording}>
          {busy ? "Uploading memo…" : "Send to evidence review →"}
        </button>
      </form>
    </section>
  );
}
