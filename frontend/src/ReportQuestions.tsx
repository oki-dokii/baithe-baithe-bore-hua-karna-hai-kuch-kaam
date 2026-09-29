import { useEffect, useState } from "react";

type Question = {
  id: string; dataset_id: string; question: string; state: string;
  reason: string | null; kind: string; qualification_status: string; applicability: string;
};
type Citation = {
  id: string; document_id: string; filename: string; page_number: number;
  text_version: number; quote: string; ocr_applied: boolean; ocr_image_verified: boolean
};
type Answer = {
  question: string; status: string; answer: string | null;
  reason: string | null; citations: Citation[]
};

async function request<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/report-facts${path}`, {
    ...init, headers: { Authorization: `Bearer ${token}`, ...init?.headers },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message ?? `Request failed (${response.status})`);
  return data as T;
}

export default function ReportQuestions({ token }: { token: string }) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [selected, setSelected] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    request<Question[]>(token, "/questions")
      .then((rows) => {
        if (active) { setQuestions(rows); setSelected(rows[0]?.id ?? ""); }
      })
      .catch((e) => active && setError((e as Error).message));
    return () => { active = false; };
  }, [token]);

  async function ask(id: string) {
    setSelected(id);
    setAnswer(null);
    setError("");
    setBusy(true);
    try {
      setAnswer(await request<Answer>(token, "/ask-question", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_id: id }),
      }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workspace" aria-label="Reviewed report questions">
      <div className="workspace-header">
        <div>
          <p className="ws-eyebrow"><span className="plate-num">02</span> Investigate</p>
          <h1 className="ws-title">Questions with a paper trail.</h1>
          <p className="ws-desc">
            Only questions mapped by a reviewer appear here. Answers come from reviewed passages, not a generated summary.
          </p>
        </div>
      </div>

      <div className="workspace-body">
        {error && <div className="error-msg" role="alert">{error}</div>}

        {!questions.length ? (
          <div className="card">
            <div className="card-body">
              <h3 style={{ fontFamily: "var(--font-serif)", fontSize: "1.4rem", color: "var(--text-primary)", marginBottom: "12px" }}>
                No mapped questions yet.
              </h3>
              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                A reviewer can create one in the evidence room after checking a source page.
              </p>
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: "20px", flex: 1, minHeight: 0 }}>
            {/* Question index */}
            <div className="card" style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}>
              <div className="card-header">
                <span className="card-title">Questions</span>
                <span className="mono-sm">{questions.length}</span>
              </div>
              <div style={{ flex: 1, overflowY: "auto" }}>
                {questions.map((item, index) => (
                  <button
                    key={item.id}
                    style={{
                      display: "block",
                      width: "100%",
                      textAlign: "left",
                      background: "transparent",
                      border: "0",
                      borderBottom: "1px solid var(--border)",
                      borderLeft: `3px solid ${selected === item.id ? "var(--teal-glow)" : "transparent"}`,
                      padding: "14px 16px",
                      cursor: "pointer",
                      transition: "background var(--dur-fast), border-left-color var(--dur-fast)",
                      backgroundColor: selected === item.id ? "rgba(23,106,112,0.08)" : "transparent",
                    }}
                    onClick={() => ask(item.id)}
                    disabled={busy}
                  >
                    <span className="mono-sm" style={{ display: "block", marginBottom: "6px", color: "var(--teal)" }}>
                      {String(index + 1).padStart(2, "0")} / {item.kind.toUpperCase()} · {item.qualification_status.replaceAll("_", " ")}
                    </span>
                    <span style={{ display: "block", fontSize: "0.8rem", fontWeight: 500, color: "var(--text-primary)", lineHeight: 1.4, marginBottom: "8px" }}>
                      {item.question}
                    </span>
                    <span className={`badge badge-${item.state.toLowerCase()}`}>
                      {item.state.replaceAll("_", " ")}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Answer pane */}
            <div className="card" style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}>
              <div className="card-header">
                <span className="card-title">Answer</span>
                {answer && (
                  <span className={`badge badge-${answer.status === "answered" ? "ready" : answer.status === "conflict" ? "error" : "warn"}`}>
                    {answer.status.replaceAll("_", " ")}
                  </span>
                )}
              </div>
              <div style={{ flex: 1, overflowY: "auto", padding: "20px" }} aria-live="polite">
                {busy ? (
                  <div className="notice" role="status">Checking reviewed evidence…</div>
                ) : answer ? (
                  <>
                    <h2 style={{
                      fontFamily: "var(--font-serif)",
                      fontSize: "1.3rem",
                      color: "var(--text-primary)",
                      marginBottom: "16px",
                      lineHeight: 1.2,
                    }}>
                      {answer.answer ?? (answer.status === "conflict" ? "Still disputed." : "No approved answer.")}
                    </h2>
                    {answer.reason && (
                      <div className="notice" style={{ marginBottom: "16px" }}>
                        {answer.reason.replaceAll("_", " ")}
                      </div>
                    )}
                    {answer.citations.map((cite) => (
                      <div key={cite.id} style={{
                        background: "var(--basin)",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--r-sm)",
                        padding: "14px",
                        marginBottom: "10px",
                      }}>
                        <blockquote style={{
                          fontFamily: "var(--font-serif)",
                          fontSize: "0.88rem",
                          color: "var(--text-secondary)",
                          lineHeight: 1.65,
                          fontStyle: "italic",
                          borderLeft: "2px solid var(--teal-dim)",
                          paddingLeft: "12px",
                          margin: "0 0 10px",
                        }}>
                          {cite.quote}
                        </blockquote>
                        <cite className="mono-sm" style={{ fontStyle: "normal" }}>
                          {cite.filename} · page {cite.page_number} · text v{cite.text_version}
                          {cite.ocr_applied ? (cite.ocr_image_verified ? " · OCR image checked" : " · OCR source") : ""}
                        </cite>
                      </div>
                    ))}
                    <p className="mono-sm" style={{ marginTop: "16px", lineHeight: 1.6 }}>
                      Historical report evidence only. Not an operational recommendation.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="ws-eyebrow" style={{ marginBottom: "12px" }}>Open a question</p>
                    <h2 style={{ fontFamily: "var(--font-serif)", fontSize: "1.4rem", color: "var(--text-primary)", marginBottom: "12px" }}>
                      Let the source answer.
                    </h2>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                      Select a question from the list to see its reviewed answer, citation, or explicit abstention.
                    </p>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
