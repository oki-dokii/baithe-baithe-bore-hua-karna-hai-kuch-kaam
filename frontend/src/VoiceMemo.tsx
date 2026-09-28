import { FormEvent, useEffect, useRef, useState } from "react";
import "./voice-memo.css";

type Option = { wellbore_id: string; dataset_id: string; name: string; kind: string };

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
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => { if (!wellbore && options.length) setWellbore(options[0].wellbore_id); }, [options, wellbore]);
  useEffect(() => {
    if (!audio) return;
    const url = URL.createObjectURL(audio);
    setAudioUrl(url);
    return () => { URL.revokeObjectURL(url); setAudioUrl(""); };
  }, [audio]);
  useEffect(() => () => {
    if (timeout.current) clearTimeout(timeout.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
    stream.current?.getTracks().forEach((track) => track.stop());
  }, []);
  async function start() {
    if (!consent) { setError("Confirm recording and 30-day audio retention first."); return; }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Microphone recording is unavailable in this browser or insecure context."); return;
    }
    setError(""); setAudio(null);
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = media;
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
        stream.current = null; setRecording(false);
      };
      current.start(); setRecording(true);
      timeout.current = setTimeout(stop, 60_000);
    } catch (e) { setError(`Microphone access failed: ${(e as Error).message}`); }
  }
  function stop() {
    if (timeout.current) clearTimeout(timeout.current);
    timeout.current = null;
    if (recorder.current?.state === "recording") recorder.current.stop();
  }
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!audio || !consent) return;
    const option = options.find((item) => item.wellbore_id === wellbore);
    if (!option) { setError("Choose a wellbore."); return; }
    if (!useAsr && !transcript.trim()) { setError("Type and check the transcript before uploading."); return; }
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
        method: "POST", headers: { Authorization: `Bearer ${token}`, "Idempotency-Key": crypto.randomUUID() }, body: form,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error?.message ?? `Upload failed (${response.status})`);
      setAudio(null); setTranscript(""); onSaved(result.id);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <section className="voice-memo-panel" aria-label="Voice memo capture">
    <p className="eyebrow">Optional / shift notes</p><h2>Capture a spoken note.</h2>
    <p>Audio stays in NWIS local storage for 30 days, then is purged. Its transcript is an unreviewed source passage; a reviewer must verify and approve any extracted claim.</p>
    <form onSubmit={upload}>
      <label>Wellbore<select value={wellbore} onChange={(e) => setWellbore(e.target.value)}>{options.map((item) => <option key={item.wellbore_id} value={item.wellbore_id}>{item.name} · {item.kind}</option>)}</select></label>
      <label>Spoken language<select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="en">English</option><option value="hi">Hindi</option><option value="as">Assamese</option></select></label>
      <label className="voice-consent"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}/> I have permission to record and retain this audio for 30 days.</label>
      <div className="voice-actions"><button type="button" onClick={start} disabled={recording || busy || !consent}>Record memo</button><button type="button" className="secondary" onClick={stop} disabled={!recording}>Stop</button><span>{recording ? "Recording · stops after 60 seconds" : audio ? "Recording ready" : "No recording"}</span></div>
      {audioUrl && <audio controls src={audioUrl} aria-label="Review recorded memo" />}
      <label className="voice-transcript">Checked transcript<textarea value={transcript} onChange={(e) => setTranscript(e.target.value)} disabled={useAsr} rows={5} maxLength={30000} placeholder="Write what was said, preserving the original language and uncertainty."/></label>
      <label className="voice-consent"><input type="checkbox" checked={useAsr} disabled={!asrAvailable} onChange={(e) => setUseAsr(e.target.checked)}/> Let the configured local Whisper model produce a draft instead</label>
      <p className="footnote">{asrAvailable ? "Local-host ASR is available. Its likelihood score is uncalibrated; verify the transcript against audio before approving a claim." : "Local ASR is not installed; a typed transcript is required. No browser or cloud speech service is used."}</p>
      {error && <p className="error" role="alert">{error}</p>}
      <button disabled={!audio || !consent || busy || recording}>{busy ? "Uploading…" : "Send to evidence review →"}</button>
    </form>
  </section>;
}
