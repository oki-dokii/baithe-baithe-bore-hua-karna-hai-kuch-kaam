import { FormEvent, useEffect, useState } from "react";

type Page = { id: string; page_number: number; raw_text: string; ocr_applied: boolean };
type Fact = {
  id: string; fact_key: string; answer: string; quote: string; state: string;
  page_number: number; reviewer_name: string;
};
type Question = { id: string; question: string; state: string; reason: string | null };

async function request<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/report-facts${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...init?.headers },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message ?? `Request failed (${response.status})`);
  return data as T;
}

export default function ReportFacts({ token, documentId, datasetId, page, canReview, approvalAllowed }: {
  token: string; documentId: string; datasetId: string; page?: Page;
  canReview: boolean; approvalAllowed: boolean;
}) {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [factKey, setFactKey] = useState("");
  const [answer, setAnswer] = useState("");
  const [quote, setQuote] = useState("");
  const [rationale, setRationale] = useState("");
  const [ocrVerified, setOcrVerified] = useState(false);
  const [question, setQuestion] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([
      request<Fact[]>(token, `/documents/${documentId}`),
      request<Question[]>(token, `/questions?dataset_id=${datasetId}`),
    ]).then(([nextFacts, nextQuestions]) => {
      if (active) { setFacts(nextFacts); setQuestions(nextQuestions); }
    }).catch((e) => active && setError((e as Error).message));
    return () => { active = false; };
  }, [token, documentId, datasetId, revision]);

  async function addFact(event: FormEvent) {
    event.preventDefault();
    if (!page) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await request(token, "", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_id: datasetId, passage_id: page.id,
          fact_key: factKey.trim(), answer: answer.trim(), quote: quote.trim(),
          rationale: rationale.trim(), ocr_image_verified: ocrVerified }),
      });
      setAnswer(""); setQuote(""); setRationale(""); setOcrVerified(false); setRevision((r) => r + 1);
      setNotice("Reviewed fact recorded. Add a question mapping if readers should ask for it.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function addQuestion(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      await request(token, "/questions", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_id: datasetId, fact_key: factKey.trim(),
          question: question.trim(), state: blocked ? "conflict_blocked" : "ready",
          reason: blocked ? reason.trim() : null }),
      });
      setQuestion(""); setReason(""); setRevision((r) => r + 1);
      setNotice(blocked ? "Question recorded as blocked." : "Question mapped to reviewed facts.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function withdraw(id: string) {
    setBusy(true); setError("");
    try {
      await request(token, `/${id}/withdraw`, { method: "POST" });
      setRevision((r) => r + 1);
      setNotice("Fact withdrawn. The review decision remains in the ledger.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  return <section className="fact-workbench" aria-label="Report facts">
    <div className="fact-workbench-heading">
      <div><p className="eyebrow">02 / Beyond incidents</p><h2>Report facts.</h2>
        <p>One claim, one exact passage. No page-wide approval.</p></div>
      <span className="mono">{facts.filter((f) => f.state === "approved").length} REVIEWED</span>
    </div>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="notice" role="status">{notice}</p>}
    <div className="fact-workbench-grid">
      <div>
        <h3>Reviewed claims</h3>
        {facts.length ? facts.map((fact) => <article className="fact-card" key={fact.id}>
          <div className="fact-card-top"><code>{fact.fact_key}</code><span className={`state state-${fact.state}`}>{fact.state}</span></div>
          <strong>{fact.answer}</strong>
          <blockquote>{fact.quote}<cite>Page {fact.page_number} · {fact.reviewer_name}</cite></blockquote>
          {canReview && fact.state === "approved" && <button className="text-button danger"
            disabled={busy} onClick={() => withdraw(fact.id)}>Withdraw fact</button>}
        </article>) : <p className="footnote">No reviewed report facts in this document.</p>}
        {!!questions.length && <><h3>Question mappings</h3>
          {questions.map((q) => <p className="fact-question" key={q.id}>
            <span className={`state state-${q.state}`}>{q.state.replaceAll("_", " ")}</span> {q.question}
            {q.reason && <small>{q.reason}</small>}
          </p>)}</>}
      </div>
      {canReview && <div className="fact-entry">
        <h3>Record from the selected page</h3>
        {!approvalAllowed && <p className="quality-note">Source qualification is pending. Fact approval is locked; conflict questions may still be recorded.</p>}
        <label htmlFor="fact-key">Stable fact key</label>
        <input id="fact-key" value={factKey} onChange={(e) => setFactKey(e.target.value)}
          placeholder="well_31_2_6_circulation_recovery" pattern="[a-z][a-z0-9_]*" minLength={3} maxLength={120} />
        <p className="footnote">Include the report or well in the key so facts from different wells cannot mix.</p>
        <form onSubmit={addFact}>
          <p className="mono">SOURCE PAGE {page?.page_number ?? "—"}{page?.ocr_applied ? " · OCR: CHECK IMAGE" : ""}</p>
          <label htmlFor="fact-answer">Reviewed answer</label>
          <input id="fact-answer" value={answer} onChange={(e) => setAnswer(e.target.value)} maxLength={1000} required />
          <label htmlFor="fact-quote">Exact supporting quote</label>
          <textarea id="fact-quote" value={quote} onChange={(e) => setQuote(e.target.value)} maxLength={4000} rows={4} required />
          <label htmlFor="fact-rationale">Why this answer is supported</label>
          <textarea id="fact-rationale" value={rationale} onChange={(e) => setRationale(e.target.value)} minLength={3} maxLength={2000} rows={2} required />
          {page?.ocr_applied && <label className="check"><input type="checkbox" checked={ocrVerified}
            onChange={(e) => setOcrVerified(e.target.checked)} />I checked the quote against the page image.</label>}
          <button disabled={busy || !approvalAllowed || !page || factKey.length < 3 || (page.ocr_applied && !ocrVerified)}>Approve cited fact</button>
        </form>
        <form onSubmit={addQuestion}>
          <h3>Map a reader question</h3>
          <label htmlFor="fact-question">Question wording</label>
          <textarea id="fact-question" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500} minLength={5} required rows={2} />
          <label className="check"><input type="checkbox" checked={blocked} onChange={(e) => setBlocked(e.target.checked)} />Conflict-blocked</label>
          {blocked && <><label htmlFor="fact-block-reason">Why it is blocked</label>
            <textarea id="fact-block-reason" value={reason} onChange={(e) => setReason(e.target.value)} minLength={3} maxLength={1000} required /></>}
          <button disabled={busy || (!blocked && !approvalAllowed) || factKey.length < 3}>Register question</button>
        </form>
      </div>}
    </div>
  </section>;
}
