import { FormEvent, useEffect, useState } from "react";
import ReportFacts from "./ReportFacts";
import VoiceMemo from "./VoiceMemo";

type Fields = {
  event_type: string;
  quote: string;
  description: string;
  depth_start: number | null;
  depth_end: number | null;
  depth_unit: string | null;
  depth_axis: string | null;
  depth_datum: string | null;
  formation_name: string | null;
  severity: string | null;
  mitigation: string | null;
  outcome: string | null;
  npt_hours: number | null;
};
type Candidate = {
  id: string;
  page_number: number;
  version: number;
  state: string;
  current_fields: Fields;
  issues: string[];
};
type Page = {
  id: string;
  page_number: number;
  raw_text: string;
  ocr_applied: boolean;
  ocr_confidence: number | null;
  has_preview: boolean;
  transcription_confidence: number | null;
  transcription_confidence_kind: string | null;
  transcription_language: string | null;
};
type Doc = {
  id: string;
  filename: string;
  doc_type: string;
  ingest_status: string;
  page_count: number | null;
  kind: string;
  qualification_status: string;
  origin_kind: string;
  authorization_state: string;
  applicability: string;
};
type Detail = Doc & {
  dataset_id: string;
  approval_allowed: boolean;
  review_version: number;
  candidates: Candidate[];
  pages: Page[];
  jobs: { status: string; error_message: string | null }[];
  audit: {
    actor_name: string;
    action: string;
    rationale: string;
    recorded_at: string;
  }[];
};
type Option = {
  wellbore_id: string;
  dataset_id: string;
  name: string;
  kind: string;
};
type Identity = { role: string; extraction_provider: string; document_max_pages: number; voice_local_asr_available: boolean };
const human = (value?: string) => (value ?? "unclassified").replaceAll("_", " ");
async function api<T>(
  token: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...init?.headers },
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error?.message ?? `Request failed (${response.status})`,
    );
  return data as T;
}

function Review({
  candidate,
  token,
  documentId,
  onSaved,
  canReview,
  approvalBlocked,
  qualificationStatus,
  voiceMemo,
}: {
  candidate: Candidate;
  token: string;
  documentId: string;
  onSaved: () => void;
  canReview: boolean;
  approvalBlocked: boolean;
  qualificationStatus: string;
  voiceMemo: boolean;
}) {
  const [fields, setFields] = useState(candidate.current_fields);
  const [rationale, setRationale] = useState("");
  const [acknowledge, setAcknowledge] = useState(false);
  const [voiceVerified, setVoiceVerified] = useState(false);
  const [onsetBasis, setOnsetBasis] = useState("unspecified");
  const [onsetEarliest, setOnsetEarliest] = useState("");
  const [onsetLatest, setOnsetLatest] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const locked = !canReview || candidate.state !== "needs_review" || busy || saved;
  const set = (key: keyof Fields, value: string) =>
    setFields((previous) => ({
      ...previous,
      [key]: ["depth_start", "depth_end", "npt_hours"].includes(key)
        ? value === ""
          ? null
          : Number(value)
        : value || null,
    }));
  async function decide(decision: string) {
    if (rationale.trim().length < 3) {
      setError("Add a rationale before recording your decision.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(token, `/documents/${documentId}/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          candidate_id: candidate.id,
          expected_version: candidate.version,
          decision,
          rationale,
          fields,
          acknowledge_issues: acknowledge,
          voice_audio_verified: voiceVerified,
          onset: {
            basis: onsetBasis,
            earliest: onsetBasis === "unspecified" ? null : onsetEarliest || null,
            latest: onsetBasis === "unspecified" ? null : onsetLatest || null,
          },
        }),
      });
      setSaved(true);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="evidence-form">
      <div className="evidence-heading">
        <span className={`state state-${candidate.state}`}>
          {human(candidate.state)}
        </span>
        <span className="mono">REV {candidate.version}</span>
      </div>
      <blockquote>
        {candidate.current_fields.quote}
        <cite>Source · page {candidate.page_number}</cite>
      </blockquote>
      <fieldset disabled={locked}>
        <label htmlFor="event-type">Recorded event</label>
        <select
          id="event-type"
          value={fields.event_type}
          onChange={(e) => set("event_type", e.target.value)}
        >
          {[
            "mud_loss",
            "kick",
            "stuck_pipe",
            "overpressure",
            "torque_spike",
            "tight_hole",
            "fishing",
            "cementing_issue",
            "other",
          ].map((x) => (
            <option key={x} value={x}>
              {human(x)}
            </option>
          ))}
        </select>
        <label htmlFor="description">Interpretation</label>
        <textarea
          id="description"
          value={fields.description}
          onChange={(e) => set("description", e.target.value)}
          rows={3}
        />
        <div className="field-pair">
          {(
            [
              ["depth_start", "From"],
              ["depth_end", "To"],
            ] as const
          ).map(([key, label]) => (
            <div key={key}>
              <label htmlFor={key}>{label}</label>
              <input
                id={key}
                type="number"
                step="any"
                min="0"
                value={fields[key] ?? ""}
                onChange={(e) => set(key, e.target.value)}
                placeholder="Not stated"
              />
            </div>
          ))}
        </div>
        <div className="field-pair">
          <div>
            <label htmlFor="depth_unit">Source unit</label>
            <input
              id="depth_unit"
              value={fields.depth_unit ?? ""}
              onChange={(e) => set("depth_unit", e.target.value)}
              placeholder="e.g. ft"
            />
          </div>
          <div>
            <label htmlFor="axis">Depth axis</label>
            <select
              id="axis"
              value={fields.depth_axis ?? ""}
              onChange={(e) => set("depth_axis", e.target.value)}
            >
              <option value="">Not stated</option>
              <option>MD</option>
              <option>TVD</option>
            </select>
          </div>
        </div>
        {(
          [
            ["depth_datum", "Depth datum"],
            ["formation_name", "Formation"],
            ["mitigation", "Recorded mitigation"],
          ] as const
        ).map(([key, label]) => (
          <div key={key}>
            <label htmlFor={key}>{label}</label>
            <input
              id={key}
              value={fields[key] ?? ""}
              onChange={(e) => set(key, e.target.value)}
              placeholder="Not stated"
            />
          </div>
        ))}
        <div className="field-pair">
          <div>
            <label htmlFor="severity">Severity</label>
            <select
              id="severity"
              value={fields.severity ?? ""}
              onChange={(e) => set("severity", e.target.value)}
            >
              <option value="">Not stated</option>
              {["low", "medium", "high", "critical"].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="outcome">Outcome</label>
            <select
              id="outcome"
              value={fields.outcome ?? ""}
              onChange={(e) => set("outcome", e.target.value)}
            >
              <option value="">Not stated</option>
              {["successful", "partial", "unsuccessful", "unknown"].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </div>
        </div>
        <label htmlFor="npt_hours">NPT · hours</label>
        <input
          id="npt_hours"
          type="number"
          min="0"
          step="any"
          value={fields.npt_hours ?? ""}
          onChange={(e) => set("npt_hours", e.target.value)}
          placeholder="Not stated"
        />
        {!!candidate.issues.length && (
          <div className="quality-note">
            <strong>Requires attention</strong>
            <ul>
              {candidate.issues.map((x) => (
                <li key={x}>{human(x)}</li>
              ))}
            </ul>
          </div>
        )}
        {canReview && candidate.state === "needs_review" && (
          <>
            {approvalBlocked && (
              <p className="quality-note">
                {qualificationStatus === "staged_unreviewed"
                  ? "Benchmark staging"
                  : "Source qualification"} · approval is locked. Inspect the source,
                record corrections or reject unsupported drafts; do not treat
                these as operational evidence.
              </p>
            )}
            <label htmlFor="onset-basis">Incident onset timing · optional</label>
            <select
              id="onset-basis"
              value={onsetBasis}
              onChange={(e) => setOnsetBasis(e.target.value)}
            >
              <option value="unspecified">Not established</option>
              <option value="exact_timelog">Exact timelog</option>
              <option value="day_only_ddr">Reporting day only</option>
              <option value="shift_report">Shift or bounded interval</option>
            </select>
            {onsetBasis !== "unspecified" && (
              <>
                <label htmlFor="onset-earliest">Earliest plausible onset · ISO 8601 with offset</label>
                <input
                  id="onset-earliest"
                  type="text"
                  value={onsetEarliest}
                  onChange={(e) => setOnsetEarliest(e.target.value)}
                  placeholder="2026-01-01T00:00:00+05:30"
                />
                <label htmlFor="onset-latest">Latest plausible onset · ISO 8601 with offset</label>
                <input
                  id="onset-latest"
                  type="text"
                  value={onsetLatest}
                  onChange={(e) => setOnsetLatest(e.target.value)}
                  placeholder="2026-01-01T23:59:59.999999+05:30"
                />
              </>
            )}
            <p className="footnote">
              Use only source-supported bounds and explain them in the rationale.
              Date-only or uncertain timing does not imply a precise pre-event ML label.
            </p>
            <label htmlFor="rationale">Review rationale · required</label>
            <textarea
              id="rationale"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              rows={2}
              placeholder="What did you verify or change?"
            />
            <label className="check">
              <input
                type="checkbox"
                checked={acknowledge}
                onChange={(e) => setAcknowledge(e.target.checked)}
              />
              I verified the source and acknowledge unresolved quality issues,
              including those introduced by my edits.
            </label>
            {voiceMemo && <label className="check">
              <input type="checkbox" checked={voiceVerified} onChange={(e) => setVoiceVerified(e.target.checked)} />
              I listened to the retained audio and verified this transcript against it. I am not the uploader.
            </label>}
            <p className="footnote">
              Approval records a historical claim, not an operational
              recommendation.
            </p>
            <div className="decision-actions">
              {!approvalBlocked && (
                <button type="button" onClick={() => decide("approve")}>
                  {busy ? "Saving…" : "Approve evidence"}
                </button>
              )}
              <button
                type="button"
                className="secondary"
                onClick={() => decide("correct")}
              >
                Save correction
              </button>
              <button
                type="button"
                className="text-button danger"
                onClick={() => decide("reject")}
              >
                Reject
              </button>
            </div>
          </>
        )}
      </fieldset>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export default function Documents({ token }: { token: string }) {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [options, setOptions] = useState<Option[]>([]);
  const [documents, setDocuments] = useState<Doc[]>([]);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [candidateId, setCandidateId] = useState("");
  const [pageNumber, setPageNumber] = useState(1);
  const [image, setImage] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [correctedTranscript, setCorrectedTranscript] = useState("");
  const [correctionRationale, setCorrectionRationale] = useState("");
  const [showImage, setShowImage] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [wellbore, setWellbore] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [manualQuote, setManualQuote] = useState("");
  const [manualRationale, setManualRationale] = useState("");
  const [activeTab, setActiveTab] = useState<"workbench" | "facts" | "voice">("workbench");
  const [docFilter, setDocFilter] = useState("");
  const canReview = identity?.role === "reviewer" || identity?.role === "admin";
  const canUpload = identity && identity.role !== "viewer";
  useEffect(() => {
    let active = true;
    api<Identity>(token, "/me")
      .then(async (me) => {
        if (!active) return;
        setIdentity(me);
        if (me.role !== "viewer") {
          const data = await api<Option[]>(token, "/document-options");
          if (active) {
            setOptions(data);
            setWellbore(data[0]?.wellbore_id ?? "");
          }
        }
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [token]);
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const docs = await api<Doc[]>(token, "/documents");
        if (!active) return;
        setDocuments(docs);
        if (!selected && docs.length) setSelected(docs[0].id);
        if (selected) {
          const data = await api<Detail>(token, `/documents/${selected}`);
          if (active) {
            setDetail(data);
            if (["needs_review", "reviewed", "failed"].includes(data.ingest_status)) {
              setNotice(previous => previous.startsWith("Report received.")
                ? (data.ingest_status === "failed" ? "Extraction failed. Inspect the error before retrying." : "Extraction finished. Verify the source before approving evidence.")
                : previous);
            }
          }
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    void refresh();
    const interval = window.setInterval(refresh, 5000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [token, selected, revision]);
  const candidate =
    detail?.candidates.find((c) => c.id === candidateId) ??
    detail?.candidates[0];
  useEffect(() => {
    if (candidate) setPageNumber(candidate.page_number);
  }, [candidate?.id]);
  const page =
    detail?.pages.find((p) => p.page_number === pageNumber) ?? detail?.pages[0];
  useEffect(() => { setCorrectedTranscript(page?.raw_text ?? ""); }, [detail?.id, page?.id]);
  useEffect(() => {
    let active = true;
    let url = "";
    setImage("");
    if (page?.has_preview && detail)
      fetch(`/api/v1/documents/${detail.id}/pages/${page.id}/preview`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => {
          if (!r.ok)
            throw new Error(
              "Page image unavailable. Use the extracted text view.",
            );
          return r.blob();
        })
        .then((blob) => {
          if (active) {
            url = URL.createObjectURL(blob);
            setImage(url);
          }
        })
        .catch((e) => active && setError(e.message));
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [page?.id, page?.has_preview, detail?.id, token]);
  useEffect(() => {
    let active = true;
    let url = "";
    setAudioUrl("");
    if (detail?.doc_type === "voice_memo")
      fetch(`/api/v1/documents/${detail.id}/audio`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => response.ok ? response.blob() : null)
        .then((blob) => { if (blob && active) { url = URL.createObjectURL(blob); setAudioUrl(url); } });
    return () => { active = false; if (url) URL.revokeObjectURL(url); };
  }, [detail?.id, detail?.doc_type, token]);
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) {
      setError("Choose a report smaller than 25 MB.");
      return;
    }
    const option = options.find((o) => o.wellbore_id === wellbore);
    if (!option) return;
    setBusy(true);
    setError("");
    setNotice("");
    const form = new FormData();
    form.append("file", file);
    form.append("dataset_id", option.dataset_id);
    form.append("wellbore_id", wellbore);
    try {
      const result = await api<{ id: string; duplicate: boolean }>(
        token,
        "/documents",
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: form,
        },
      );
      setDetail(null);
      setSelected(result.id);
      setCandidateId("");
      setPageNumber(1);
      setShowUpload(false);
      setRevision((r) => r + 1);
      setNotice(
        result.duplicate
          ? "This report is already archived. Opened the existing record."
          : "Report received. Extraction is queued; this view updates automatically.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function retry() {
    if (!detail) return;
    setBusy(true);
    setError("");
    try {
      await api(token, `/documents/${detail.id}/retry`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      setRevision((r) => r + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function saveTranscriptCorrection(event: FormEvent) {
    event.preventDefault();
    if (!detail || correctionRationale.trim().length < 3) {
      setError("Explain why the transcript needs correction."); return;
    }
    setBusy(true); setError("");
    try {
      await api(token, `/voice-memos/${detail.id}/transcript`, {
        method: "POST", headers: { "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ expected_review_version: detail.review_version,
          text: correctedTranscript, rationale: correctionRationale }),
      });
      setCorrectionRationale(""); setCandidateId("");
      setRevision((value) => value + 1);
      setNotice("A new transcript version was created. Earlier drafts were rejected; review the new evidence.");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function addCandidate(event: FormEvent) {
    event.preventDefault();
    if (!detail || !page) return;
    setBusy(true);
    setError("");
    const fields: Fields = {
      event_type: "other",
      quote: manualQuote,
      description: manualQuote,
      depth_start: null,
      depth_end: null,
      depth_unit: null,
      depth_axis: null,
      depth_datum: null,
      formation_name: null,
      severity: null,
      mitigation: null,
      outcome: null,
      npt_hours: null,
    };
    try {
      const result = await api<{ id: string }>(
        token,
        `/documents/${detail.id}/candidates`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({
            page_number: page.page_number,
            expected_version: detail.review_version,
            fields,
            rationale: manualRationale,
          }),
        },
      );
      setCandidateId(result.id);
      setManualQuote("");
      setManualRationale("");
      setRevision((r) => r + 1);
      setNotice(
        "Candidate added. Classify the event and verify its details before approval.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const filteredDocuments = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(docFilter.toLowerCase()) ||
    doc.kind.toLowerCase().includes(docFilter.toLowerCase())
  );

  return (
    <section aria-label="Document evidence workspace" className="documents-workspace">
      {/* Workspace Header */}
      <div className="archive-heading">
        <div>
          <p className="eyebrow">04 / Validation & Source Studio</p>
          <h1>The evidence room.</h1>
          <p>Read the record. Verify the detail. Carry the lesson forward.</p>
        </div>
        <div className="header-actions">
          {canUpload && (
            <button
              className="secondary"
              onClick={() => {
                setShowUpload((v) => !v);
                setActiveTab("workbench");
              }}
            >
              {showUpload ? "Close upload" : "+ Upload report"}
            </button>
          )}
          {canUpload && (
            <button
              className="text-button"
              onClick={() => setActiveTab("voice")}
            >
              🎙️ Record shift note
            </button>
          )}
        </div>
      </div>

      <div className="archive-meta">
        <span>{String(documents.length).padStart(2, "0")} REPORTS IN ARCHIVE</span>
        <span>
          {identity
            ? identity.extraction_provider === "local_rules"
              ? "RULE-BASED EXTRACTION"
              : "MODEL-ASSISTED EXTRACTION"
            : "CONNECTING"}{" "}
          · HUMAN REVIEW REQUIRED
        </span>
        <span>ROLE: {identity?.role?.toUpperCase()}</span>
      </div>

      {error && (
        <div role="alert" className="error">
          {error}
          <button className="text-button" onClick={() => setError("")}>
            Dismiss
          </button>
        </div>
      )}
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}

      {/* Subview Tabs Bar */}
      <div className="subview-tab-bar" role="tablist" aria-label="Validation workspaces">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "workbench"}
          className={`subview-tab-btn ${activeTab === "workbench" ? "active" : ""}`}
          onClick={() => setActiveTab("workbench")}
        >
          <span className="tab-num">01</span>
          <span className="tab-title">Review Studio</span>
          <span className="tab-desc">Queue, source viewer & claim decision</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "facts"}
          className={`subview-tab-btn ${activeTab === "facts" ? "active" : ""}`}
          onClick={() => setActiveTab("facts")}
        >
          <span className="tab-num">02</span>
          <span className="tab-title">Structured Facts</span>
          <span className="tab-desc">Drilling parameters & casing logs</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "voice"}
          className={`subview-tab-btn ${activeTab === "voice" ? "active" : ""}`}
          onClick={() => setActiveTab("voice")}
        >
          <span className="tab-num">03</span>
          <span className="tab-title">Shift Voice Memo</span>
          <span className="tab-desc">Spoken field note capture & audio</span>
        </button>
      </div>

      {/* Tab 1: Document Review Workbench */}
      {activeTab === "workbench" && (
        <>
          {showUpload && (
            <div className="upload-banner">
              <div className="upload-banner-header">
                <h3>Upload New Source Report</h3>
                <button className="text-button" onClick={() => setShowUpload(false)}>✕ Close</button>
              </div>
              <form className="upload-form" onSubmit={upload}>
                <div>
                  <label htmlFor="report-file">
                    Source report · PDF or UTF-8 text
                  </label>
                  <input
                    id="report-file"
                    type="file"
                    accept=".pdf,.txt"
                    required
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                  <p className="footnote">
                    25 MB maximum · {identity?.document_max_pages ?? 50} pages · English OCR
                  </p>
                </div>
                <div>
                  <label htmlFor="upload-well">Link to wellbore</label>
                  <select
                    id="upload-well"
                    value={wellbore}
                    onChange={(e) => setWellbore(e.target.value)}
                  >
                    {options.map((o) => (
                      <option key={o.wellbore_id} value={o.wellbore_id}>
                        {o.name} · {o.kind}
                      </option>
                    ))}
                  </select>
                  {!options.length && (
                    <p>No wellbores available. Load the foundation fixture first.</p>
                  )}
                </div>
                <button disabled={busy || !file || !wellbore}>
                  {busy ? "Uploading…" : "Upload & extract →"}
                </button>
              </form>
            </div>
          )}

          <div className="review-layout">
            {/* Column 1: Report Queue */}
            <aside className="report-index">
              <div className="report-index-header">
                <h2>
                  Review Queue <span>{String(documents.length).padStart(2, "0")}</span>
                </h2>
                {canUpload && (
                  <button
                    className="text-button"
                    onClick={() => setShowUpload((v) => !v)}
                    title="Upload report"
                  >
                    + Upload
                  </button>
                )}
              </div>
              <div className="report-search-box">
                <input
                  type="text"
                  placeholder="Filter reports by name..."
                  value={docFilter}
                  onChange={(e) => setDocFilter(e.target.value)}
                />
              </div>
              <div className="report-index-body">
                {filteredDocuments.length ? (
                  filteredDocuments.map((doc, i) => (
                    <button
                      className={`report-entry ${selected === doc.id ? "selected" : ""}`}
                      key={doc.id}
                      onClick={() => {
                        setSelected(doc.id);
                        setDetail(null);
                        setCandidateId("");
                        setPageNumber(1);
                        setNotice("");
                      }}
                    >
                      <div className="report-entry-id">
                        REPORT {String(i + 1).padStart(2, "0")}
                        {doc.doc_type === "voice_memo" ? " · 🎙️ VOICE" : " · 📄 DOC"}
                      </div>
                      <div className="report-entry-name" title={doc.filename}>{doc.filename}</div>
                      <div className="report-entry-meta">
                        {doc.origin_kind
                          ? `${human(doc.origin_kind)} · ${human(doc.applicability)}`
                          : doc.kind} · {doc.page_count ?? "—"} p.
                      </div>
                      <span className={`state state-${doc.ingest_status}`}>
                        {human(doc.ingest_status)}
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="index-empty">
                    <span className="folio-icon" aria-hidden="true">
                      ≡
                    </span>
                    <p>
                      {docFilter ? "No reports match your filter." : "The archive starts with a report."}
                    </p>
                    <small>
                      {canUpload
                        ? "Add a drilling report to begin."
                        : "Approved evidence will appear here when available."}
                    </small>
                  </div>
                )}
              </div>
              <p className="index-note">
                Historical evidence, not operating instructions.
              </p>
            </aside>

            {/* Column 2: Source Record Viewer */}
            <section className="source-panel" aria-label="Source report">
              <div className="panel-heading">
                <h2>Source record</h2>
                <span className="mono">
                  {detail ? human(detail.ingest_status) : "NO RECORD SELECTED"}
                </span>
              </div>
              {detail ? (
                <>
                  {detail.origin_kind && (
                    <p className="quality-note">
                      Source: {human(detail.origin_kind)} · authorization: {human(detail.authorization_state)}
                      · use: {human(detail.applicability)} · qualification: {human(detail.qualification_status)}.
                    </p>
                  )}
                  <div className="source-toolbar">
                    <strong title={detail.filename}>{detail.filename}</strong>
                    {detail.pages.length > 0 && (
                      <div>
                        <label className="sr-only" htmlFor="page-selector">
                          Source page
                        </label>
                        <select
                          id="page-selector"
                          value={page?.page_number ?? 1}
                          onChange={(e) => setPageNumber(Number(e.target.value))}
                        >
                          {detail.pages.map((p) => (
                            <option key={p.id} value={p.page_number}>
                              Page {p.page_number} of {detail.pages.length}
                            </option>
                          ))}
                        </select>
                        {page?.has_preview && (
                          <button
                            className="text-button"
                            onClick={() => setShowImage((v) => !v)}
                          >
                            {showImage ? "Text view" : "Page image"}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                  {detail.doc_type === "voice_memo" && (
                    <div className="voice-source-note">
                      <p className="footnote">
                        Voice transcript is untrusted until a reviewer checks the audio and approves a cited claim. Audio access is limited to the uploader and reviewers; expires in 30 days.
                      </p>
                      {audioUrl ? (
                        <audio controls src={audioUrl} aria-label="Original voice memo" />
                      ) : (
                        <p>Audio unavailable or access restricted.</p>
                      )}
                      {audioUrl && canUpload && page && (
                        <form onSubmit={saveTranscriptCorrection} className="voice-correction">
                          <label htmlFor="corrected-voice-text">Correct transcript before claim review</label>
                          <textarea
                            id="corrected-voice-text"
                            rows={4}
                            value={correctedTranscript}
                            onChange={(e) => setCorrectedTranscript(e.target.value)}
                          />
                          <label htmlFor="voice-correction-reason">Correction rationale</label>
                          <input
                            id="voice-correction-reason"
                            value={correctionRationale}
                            onChange={(e) => setCorrectionRationale(e.target.value)}
                          />
                          <button disabled={busy || correctedTranscript.trim() === page.raw_text.trim()}>
                            Save new transcript version
                          </button>
                        </form>
                      )}
                    </div>
                  )}
                  {page ? (
                    <div className="source-sheet">
                      {page.ocr_applied && (
                        <p className="ocr-note">
                          OCR transcription ·{" "}
                          {page.ocr_confidence == null
                            ? "confidence unavailable"
                            : `${Math.round(page.ocr_confidence * 100)}% mean word confidence`}{" "}
                          · verify against image
                        </p>
                      )}
                      {detail.doc_type === "voice_memo" && (
                        <p className="ocr-note">
                          {human(page.transcription_language ?? "language unknown")} voice transcript ·{" "}
                          {page.transcription_confidence == null
                            ? "confidence unavailable (typed or corrected)"
                            : `${Math.round(page.transcription_confidence * 100)}% uncalibrated token likelihood`}{" "}
                          · verify against audio
                        </p>
                      )}
                      {showImage && image ? (
                        <img
                          className="page-image"
                          src={image}
                          alt={`Original report page ${page.page_number}`}
                        />
                      ) : (
                        <pre className="source-text">
                          {page.raw_text || "No readable text found on this page."}
                        </pre>
                      )}
                      <div className="page-folio">
                        NWIS / SOURCE ARCHIVE{" "}
                        <span>{String(page.page_number).padStart(2, "0")}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="empty-source">
                      <span className="large-folio">
                        {detail.ingest_status === "failed" ? "!" : "…"}
                      </span>
                      <h3>
                        {detail.ingest_status === "failed"
                          ? "This report needs another look."
                          : canReview
                            ? "Preparing the source record."
                            : "Source access is limited."}
                      </h3>
                      <p>
                        {detail.jobs[0]?.error_message ??
                          (canReview
                            ? "The worker is reading the report. Extracted pages will appear here."
                            : "Full source pages are reserved for reviewers. Approved claims appear in the evidence column.")}
                      </p>
                      {detail.ingest_status === "failed" && canReview && (
                        <button onClick={retry} disabled={busy}>
                          Retry extraction
                        </button>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <div className="empty-source">
                  <div className="document-outline" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                    <i />
                  </div>
                  <p className="eyebrow">Every lesson has a source</p>
                  <h3>
                    Open a report from the queue.
                    <br />
                    Start with what happened.
                  </h3>
                  <p>
                    The original page stays beside each extracted claim, so nothing
                    loses its context.
                  </p>
                </div>
              )}
            </section>

            {/* Column 3: Evidence Ledger & Review Studio */}
            <aside className="evidence-panel">
              <div className="panel-heading">
                <h2>Evidence ledger</h2>
                <span className="mono">
                  {String(detail?.candidates.length ?? 0).padStart(2, "0")}
                </span>
              </div>
              <div className="evidence-panel-body">
                {candidate && detail ? (
                  <>
                    <label className="sr-only" htmlFor="candidate-selector">
                      Select extracted event
                    </label>
                    <select
                      className="candidate-selector"
                      id="candidate-selector"
                      value={candidate.id}
                      onChange={(e) => {
                        setCandidateId(e.target.value);
                        const next = detail.candidates.find(
                          (c) => c.id === e.target.value,
                        );
                        if (next) setPageNumber(next.page_number);
                      }}
                    >
                      {detail.candidates.map((c, i) => (
                        <option key={c.id} value={c.id}>
                          {i + 1}. {human(c.current_fields.event_type)} · p.
                          {c.page_number} · {human(c.state)}
                        </option>
                      ))}
                    </select>
                    <Review
                      key={`${candidate.id}:${candidate.version}`}
                      candidate={candidate}
                      token={token}
                      documentId={detail.id}
                      canReview={canReview}
                      approvalBlocked={!(detail.approval_allowed ??
                        (detail.qualification_status !== "staged_unreviewed"))}
                      qualificationStatus={detail.qualification_status}
                      voiceMemo={detail.doc_type === "voice_memo"}
                      onSaved={() => {
                        setRevision((r) => r + 1);
                        setNotice("Review decision recorded with your rationale.");
                      }}
                    />
                  </>
                ) : (
                  <div className="ledger-empty">
                    <span className="eyebrow">Nothing assumed.</span>
                    <h3>
                      Facts first.
                      <br />
                      Judgment second.
                    </h3>
                    <p>
                      {detail?.ingest_status === "needs_review"
                        ? "No candidates are visible. This does not establish that the report contains no incidents."
                        : "Extracted events appear here with their source quote, depth reference and review status."}
                    </p>
                    <ol>
                      <li>Identify the recorded event</li>
                      <li>Verify depth and formation</li>
                      <li>Record a review decision</li>
                    </ol>
                  </div>
                )}

                {canReview &&
                  page &&
                  detail &&
                  ["needs_review", "reviewed"].includes(detail.ingest_status) && (
                    <details className="manual-entry">
                      <summary>
                        Missing an incident? Add claim from p. {page.page_number}
                      </summary>
                      <form className="manual-entry-form" onSubmit={addCandidate}>
                        <div>
                          <label htmlFor="manual-quote">
                            Exact quote from page {page.page_number}
                          </label>
                          <textarea
                            id="manual-quote"
                            required
                            rows={3}
                            maxLength={2000}
                            value={manualQuote}
                            onChange={(e) => setManualQuote(e.target.value)}
                            placeholder="Quote the exact sentence..."
                          />
                        </div>
                        <div>
                          <label htmlFor="manual-rationale">
                            Rationale for adding
                          </label>
                          <textarea
                            id="manual-rationale"
                            required
                            rows={2}
                            minLength={3}
                            maxLength={2000}
                            value={manualRationale}
                            onChange={(e) => setManualRationale(e.target.value)}
                            placeholder="Why is this claim safety or operationally critical?"
                          />
                        </div>
                        <button disabled={busy} className="secondary">Add for review</button>
                      </form>
                    </details>
                  )}

                {!!detail?.audit.length && (
                  <details className="review-history">
                    <summary>Review history · {detail.audit.length}</summary>
                    {detail.audit.map((a, i) => (
                      <div key={i}>
                        <strong>
                          {human(a.action)} · {a.actor_name}
                        </strong>
                        <p>{a.rationale}</p>
                        <time>{new Date(a.recorded_at).toLocaleString()}</time>
                      </div>
                    ))}
                  </details>
                )}
              </div>
            </aside>
          </div>
        </>
      )}

      {/* Tab 2: Structured Report Facts */}
      {activeTab === "facts" && (
        <div className="tab-content-panel">
          <div className="tab-section-intro">
            <h2>Structured Report Facts & Well Parameters</h2>
            <p className="footnote">
              Deterministic parameters, casing seats, mud weight records, and formation tops extracted from the active report.
            </p>
          </div>
          {detail ? (
            <ReportFacts
              key={detail.id}
              token={token}
              documentId={detail.id}
              datasetId={detail.dataset_id}
              page={page}
              canReview={canReview}
              approvalAllowed={Boolean(detail.approval_allowed)}
            />
          ) : (
            <div className="empty-source" style={{ minHeight: "300px" }}>
              <h3>No Report Selected</h3>
              <p>Select a report in the Review Studio to inspect its extracted parameters.</p>
              <button className="secondary" onClick={() => setActiveTab("workbench")}>
                Return to Review Studio →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Shift Voice Memo */}
      {activeTab === "voice" && canUpload && (
        <div className="tab-content-panel">
          <div className="tab-section-intro">
            <h2>Capture Field Audio Shift Note</h2>
            <p className="footnote">
              Record a spoken shift note for verification. The transcript will enter the evidence review queue for human sign-off. Audio is stored locally for 30 days.
            </p>
          </div>
          <VoiceMemo
            token={token}
            options={options}
            asrAvailable={Boolean(identity?.voice_local_asr_available)}
            onSaved={(id) => {
              setSelected(id);
              setDetail(null);
              setRevision((value) => value + 1);
              setActiveTab("workbench");
              setNotice("Voice memo received. The transcript has entered the evidence-review queue.");
            }}
          />
        </div>
      )}
    </section>
  );
}
