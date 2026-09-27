import { useEffect, useState } from "react";

type Question = {
  id: string; dataset_id: string; question: string; state: string;
  reason: string | null; kind: string; qualification_status: string; applicability: string;
};
type Citation = { id: string; document_id: string; filename: string; page_number: number;
  text_version: number; quote: string; ocr_applied: boolean; ocr_image_verified: boolean };
type Answer = { question: string; status: string; answer: string | null;
  reason: string | null; citations: Citation[] };

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
    request<Question[]>(token, "/questions").then((rows) => {
      if (active) { setQuestions(rows); setSelected(rows[0]?.id ?? ""); }
    }).catch((e) => active && setError((e as Error).message));
    return () => { active = false; };
  }, [token]);
  async function ask(id: string) {
    setSelected(id); setAnswer(null); setError(""); setBusy(true);
    try {
      setAnswer(await request<Answer>(token, "/ask-question", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_id: id }),
      }));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="question-room" aria-label="Reviewed report questions">
    <div className="archive-heading"><div><p className="eyebrow">02 / Ask the archive</p>
      <h1>Questions with a paper trail.</h1>
      <p>Only questions mapped by a reviewer appear here. Answers come from reviewed passages, not a generated summary.</p>
    </div></div>
    {error && <p className="error" role="alert">{error}</p>}
    {!questions.length ? <div className="ledger-empty"><h3>No mapped questions yet.</h3>
      <p>A reviewer can create one in the evidence room after checking a source page.</p></div> :
      <div className="question-grid"><div className="question-index">
        {questions.map((item, index) => <button key={item.id}
          className={`question-entry ${selected === item.id ? "selected" : ""}`}
          onClick={() => ask(item.id)} disabled={busy}>
          <span className="mono">{String(index + 1).padStart(2, "0")} / {item.kind.toUpperCase()} · {item.qualification_status.replaceAll("_", " ")}</span>
          <strong>{item.question}</strong>
          <span className={`state state-${item.state}`}>{item.state.replaceAll("_", " ")}</span>
        </button>)}
      </div><div className="question-answer" aria-live="polite">
        {busy ? <p role="status">Checking reviewed evidence…</p> : answer ? <>
          <p className="eyebrow">Review outcome / {answer.status.replaceAll("_", " ")}</p>
          <h2>{answer.answer ?? (answer.status === "conflict" ? "Still disputed." : "No approved answer.")}</h2>
          {answer.reason && <p className="quality-note">{answer.reason.replaceAll("_", " ")}</p>}
          {answer.citations.map((cite) => <blockquote key={cite.id}>{cite.quote}
            <cite>{cite.filename} · page {cite.page_number} · text v{cite.text_version}{cite.ocr_applied ? (cite.ocr_image_verified ? " · OCR image checked" : " · OCR source") : ""}</cite>
          </blockquote>)}
          <p className="footnote">Historical report evidence only. Not an operational recommendation.</p>
        </> : <><p className="eyebrow">Open a question</p><h2>Let the source answer.</h2>
          <p>Select a question to see its reviewed answer, citation, or explicit abstention.</p></>}
      </div></div>}
  </section>;
}
