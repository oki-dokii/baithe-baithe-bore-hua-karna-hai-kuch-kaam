import { FormEvent, useEffect, useState } from "react";

type Question = {
  id: string;
  dataset_id: string;
  question: string;
  state: string;
  reason: string | null;
  kind: string;
  qualification_status: string;
  applicability: string;
};

type Citation = {
  document_id: string;
  filename: string;
  page_number: number;
  section_label?: string;
  quote: string;
  relevance_score?: number;
  verified_by?: string;
};

type RagAnswer = {
  question: string;
  status: "answered" | "no_evidence_found" | "conflict" | "no_answer";
  answer: string | null;
  confidence?: number;
  answer_kind?: string;
  reason?: string | null;
  citations: Citation[];
};

const SAMPLE_QUERIES = [
  "What mud weight was used during Tipam losses in NHK-302?",
  "How was differential sticking resolved in Kopili shale?",
  "What LCM pill cured lost circulation in Moran MOR-045?",
  "What depth was the gas kick observed in Barail sequence?",
  "What was the casing program for Nahorkatiya NHK-302?",
];

export default function ReportQuestions({ token }: { token: string }) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [selected, setSelected] = useState("");
  const [activeDatasetId, setActiveDatasetId] = useState("");
  
  // Free-form RAG Question state
  const [ragQuery, setRagQuery] = useState("");
  const [ragAnswer, setRagAnswer] = useState<RagAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Load datasets and existing questions
  useEffect(() => {
    let active = true;
    fetch("/api/v1/status", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((st) => {
        if (active && st.datasets && st.datasets.length > 0) {
          setActiveDatasetId(st.datasets[0]);
        }
      })
      .catch(() => {});

    fetch("/api/v1/report-facts/questions", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((rows) => {
        if (active && Array.isArray(rows)) {
          setQuestions(rows);
          if (rows[0]) setSelected(rows[0].id);
        }
      })
      .catch((e) => active && setError((e as Error).message));

    return () => {
      active = false;
    };
  }, [token]);

  async function handleRagSubmit(e?: FormEvent) {
    if (e) e.preventDefault();
    if (!ragQuery.trim()) return;

    setBusy(true);
    setError("");
    setRagAnswer(null);

    try {
      // Find fallback dataset ID if active is empty
      let dsId = activeDatasetId;
      if (!dsId) {
        const wellRes = await fetch("/api/v1/intelligence/wellbores", {
          headers: { Authorization: `Bearer ${token}` },
        });
        const wellData = await wellRes.json();
        if (wellData.items && wellData.items[0]) {
          dsId = wellData.items[0].dataset_id;
          setActiveDatasetId(dsId);
        }
      }

      const res = await fetch("/api/v1/report-facts/query-rag", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          dataset_id: dsId || "00000000-0000-0000-0000-000000000000",
          question: ragQuery.trim(),
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail ?? `RAG search failed (${res.status})`);
      }

      const data = await res.json();
      setRagAnswer(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function handleQuickQuery(q: string) {
    setRagQuery(q);
    // Programmatic trigger
    setBusy(true);
    setError("");
    setRagAnswer(null);

    let dsId = activeDatasetId;
    const fetchDataset = dsId
      ? Promise.resolve(dsId)
      : fetch("/api/v1/intelligence/wellbores", { headers: { Authorization: `Bearer ${token}` } })
          .then((r) => r.json())
          .then((w) => w.items?.[0]?.dataset_id ?? "00000000-0000-0000-0000-000000000000");

    fetchDataset
      .then((validDsId) => {
        setActiveDatasetId(validDsId);
        return fetch("/api/v1/report-facts/query-rag", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            dataset_id: validDsId,
            question: q,
          }),
        });
      })
      .then((res) => res.json())
      .then((data) => setRagAnswer(data))
      .catch((err) => setError((err as Error).message))
      .finally(() => setBusy(false));
  }

  async function askPreMapped(id: string) {
    setSelected(id);
    setRagAnswer(null);
    setError("");
    setBusy(true);
    try {
      const res = await fetch("/api/v1/report-facts/ask-question", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question_id: id }),
      });
      const data = await res.json();
      setRagAnswer(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workspace" aria-label="Reviewed report questions and intelligent RAG engine">
      <div className="workspace-header">
        <div>
          <p className="ws-eyebrow"><span className="plate-num">02</span> Investigate</p>
          <h1 className="ws-title">Intelligent Grounded Subsurface RAG</h1>
          <p className="ws-desc">
            Ask free-form questions against daily drilling logs, well completion reports, and offset incident archives.
          </p>
        </div>
        <span className="badge badge-success">EXTRACTIVE RAG ACTIVE</span>
      </div>

      <div className="workspace-body">
        {error && <div className="error-msg" role="alert">{error}</div>}

        {/* Search Bar & Quick Query Pills */}
        <div className="card" style={{ borderColor: "var(--border-teal)", marginBottom: "20px" }}>
          <div className="card-body">
            <form onSubmit={handleRagSubmit} style={{ display: "flex", gap: "12px", alignItems: "center" }}>
              <input
                type="text"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                placeholder="Ask any drilling question (e.g. mud weight during losses, stuck pipe resolution, LCM pill recipe)..."
                style={{
                  flex: 1,
                  padding: "12px 16px",
                  borderRadius: "var(--r-sm)",
                  background: "var(--glass-2)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                  fontSize: "0.9rem",
                }}
              />
              <button
                type="submit"
                className="btn btn-primary"
                disabled={busy || !ragQuery.trim()}
                style={{ padding: "12px 24px", whiteSpace: "nowrap" }}
              >
                {busy ? "Retrieving…" : "Ask Knowledge Base →"}
              </button>
            </form>

            {/* Quick Sample Queries */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "14px", alignItems: "center" }}>
              <span className="mono-sm" style={{ color: "var(--text-muted)", marginRight: "4px" }}>
                Suggested inquiries:
              </span>
              {SAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => handleQuickQuery(q)}
                  style={{
                    background: "rgba(23,106,112,0.12)",
                    border: "1px solid rgba(23,106,112,0.35)",
                    borderRadius: "16px",
                    color: "var(--teal-glow)",
                    padding: "4px 12px",
                    fontSize: "0.75rem",
                    cursor: "pointer",
                    transition: "all var(--dur-fast)",
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.background = "rgba(23,106,112,0.25)")}
                  onMouseOut={(e) => (e.currentTarget.style.background = "rgba(23,106,112,0.12)")}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div style={{ display: "grid", gridTemplateColumns: questions.length ? "280px 1fr" : "1fr", gap: "20px" }}>
          {/* Mapped Questions list if any exist */}
          {questions.length > 0 && (
            <div className="card" style={{ display: "flex", flexDirection: "column", maxHeight: "650px" }}>
              <div className="card-header">
                <span className="card-title">Curated Questions</span>
                <span className="mono-sm">{questions.length}</span>
              </div>
              <div style={{ flex: 1, overflowY: "auto" }}>
                {questions.map((item, idx) => (
                  <button
                    key={item.id}
                    onClick={() => askPreMapped(item.id)}
                    disabled={busy}
                    style={{
                      display: "block",
                      width: "100%",
                      textAlign: "left",
                      background: selected === item.id ? "rgba(23,106,112,0.12)" : "transparent",
                      border: "0",
                      borderBottom: "1px solid var(--border)",
                      borderLeft: `3px solid ${selected === item.id ? "var(--teal-glow)" : "transparent"}`,
                      padding: "12px 14px",
                      cursor: "pointer",
                    }}
                  >
                    <span className="mono-sm" style={{ display: "block", fontSize: "0.7rem", color: "var(--teal-glow)", marginBottom: "4px" }}>
                      #{idx + 1} · {item.kind.toUpperCase()}
                    </span>
                    <span style={{ fontSize: "0.78rem", color: "var(--text-primary)", display: "block", lineHeight: 1.4 }}>
                      {item.question}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* RAG Answer Display Card */}
          <div className="card" style={{ display: "flex", flexDirection: "column" }}>
            <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="card-title">Grounded Answer & Citation Evidence</span>
              {ragAnswer && (
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  {ragAnswer.confidence != null && (
                    <span className="mono-sm" style={{ color: "var(--teal-glow)" }}>
                      Confidence: {(ragAnswer.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  <span className={`badge ${ragAnswer.status === "answered" ? "badge-success" : "badge-warning"}`}>
                    {ragAnswer.status === "answered" ? "VERIFIED GROUND TRUTH" : ragAnswer.status.toUpperCase()}
                  </span>
                </div>
              )}
            </div>

            <div className="card-body" style={{ minHeight: "260px" }}>
              {busy ? (
                <div style={{ padding: "40px", textAlign: "center", color: "var(--teal-glow)" }}>
                  <span className="mono-sm">Searching ingested passages and extracting grounded evidence…</span>
                </div>
              ) : ragAnswer ? (
                <div>
                  <div style={{
                    padding: "18px 20px",
                    background: "var(--glass-2)",
                    borderRadius: "var(--r-md)",
                    border: "1px solid var(--border)",
                    marginBottom: "20px",
                  }}>
                    <span className="mono-sm" style={{ color: "var(--text-muted)", fontSize: "0.75rem", display: "block", marginBottom: "6px" }}>
                      Query: {ragAnswer.question}
                    </span>
                    <p style={{
                      fontSize: "1.05rem",
                      fontFamily: "var(--font-serif)",
                      color: "var(--text-primary)",
                      lineHeight: 1.5,
                      fontWeight: 500,
                    }}>
                      {ragAnswer.answer ?? "No direct answer found in verified passages."}
                    </p>
                    {ragAnswer.answer_kind && (
                      <span className="mono-sm" style={{ fontSize: "0.72rem", color: "var(--teal-glow)", marginTop: "8px", display: "block" }}>
                        Method: {ragAnswer.answer_kind.replaceAll("_", " ")}
                      </span>
                    )}
                  </div>

                  {/* Supporting Citations */}
                  <div>
                    <h4 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "12px", borderBottom: "1px solid var(--border)", paddingBottom: "6px" }}>
                      Supporting Source Passages ({ragAnswer.citations.length} cited)
                    </h4>

                    {ragAnswer.citations.length === 0 ? (
                      <p className="mono-sm" style={{ color: "var(--text-muted)" }}>
                        No passage citations attached to this response.
                      </p>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                        {ragAnswer.citations.map((c, i) => (
                          <div
                            key={i}
                            style={{
                              padding: "14px 16px",
                              borderRadius: "var(--r-sm)",
                              background: "rgba(13,27,42,0.6)",
                              border: "1px solid var(--border)",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                              <span className="mono-sm" style={{ color: "var(--teal-glow)" }}>
                                📄 {c.filename} · Page {c.page_number} {c.section_label ? `(${c.section_label})` : ""}
                              </span>
                              {c.relevance_score != null && (
                                <span className="mono-sm" style={{ color: "var(--text-muted)" }}>
                                  Score: {c.relevance_score.toFixed(2)}
                                </span>
                              )}
                            </div>
                            <blockquote style={{
                              fontStyle: "italic",
                              fontSize: "0.82rem",
                              color: "var(--text-primary)",
                              lineHeight: 1.55,
                              borderLeft: "2px solid var(--teal)",
                              paddingLeft: "12px",
                              margin: "6px 0 0",
                            }}>
                              "{c.quote}"
                            </blockquote>
                            {c.verified_by && (
                              <span className="mono-sm" style={{ fontSize: "0.7rem", color: "var(--green-bright)", display: "block", marginTop: "6px" }}>
                                Verified by: {c.verified_by}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div style={{ padding: "40px", textAlign: "center", color: "var(--text-secondary)" }}>
                  <p style={{ fontSize: "0.9rem", marginBottom: "8px" }}>
                    Select an inquiry above or type any question into the search bar to query the Assam subsurface archive.
                  </p>
                  <p className="mono-sm" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    Every answer is extracted strictly from Grounded Daily Drilling Reports and Well Completion Records.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
