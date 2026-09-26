import { FormEvent, useEffect, useState } from "react";

type Session = {
  id: string;
  state: string;
  revision: number;
  next_sequence: number;
  created_at: string;
};
type Evidence = {
  event_id: string;
  evidence_snapshot: {
    source_well: string;
    quote: string;
    filename: string;
    page_number: number;
    source_start_md_m: number;
    source_end_md_m: number;
    mapped_start_md_m: number;
    mapped_end_md_m: number;
  };
  current_review_state: string;
};
type Alert = {
  id: string;
  lifecycle: string;
  relevance: string;
  hazard_type: string;
  revision: number;
  seen_count: number;
  evidence_changed: boolean;
  evidence: Evidence[];
  actions: { action: string; actor_name: string; rationale: string }[];
  feedback: {
    action_taken: string;
    observed_outcome: string;
    rationale: string;
  }[];
};
type Snapshot = {
  session: Session;
  telemetry: { md_m: number; sequence: number; received_at: string } | null;
  stale: boolean;
  alerts: Alert[];
  risk_reason: string;
  steps_total: number;
  replay_worker_ready: boolean;
};
const human = (s: string) => s.replaceAll("_", " ");
async function api<T>(token: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    signal: AbortSignal.timeout(10000),
    method: body ? "POST" : "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body
        ? {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          }
        : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error?.message ?? `Request failed (${response.status})`,
    );
  return data;
}

function AlertReview({
  alert,
  token,
  editable,
  refresh,
}: {
  alert: Alert;
  token: string;
  editable: boolean;
  refresh: () => void;
}) {
  const [rationale, setRationale] = useState("");
  const [actionTaken, setActionTaken] = useState("");
  const [outcome, setOutcome] = useState("unknown");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const transitions: Record<string, string[]> = {
    NEW: ["acknowledge", "review", "resolve", "dismiss"],
    ACKNOWLEDGED: ["review", "resolve", "dismiss"],
    UNDER_REVIEW: ["resolve", "dismiss"],
    RESOLVED: ["reopen"],
    DISMISSED: ["reopen"],
  };
  async function act(action: string) {
    if (rationale.trim().length < 3) {
      setError("A rationale is required.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(token, `/alerts/${alert.id}/actions`, {
        action,
        expected_version: alert.revision,
        rationale,
      });
      setRationale("");
      refresh();
    } catch (e) {
      setError((e as Error).message);
      refresh();
    } finally {
      setBusy(false);
    }
  }
  async function feedback(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(token, `/alerts/${alert.id}/feedback`, {
        action_taken: actionTaken,
        observed_outcome: outcome,
        rationale,
      });
      setActionTaken("");
      setRationale("");
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="operation-alert">
      <div className="alert-title">
        <h3>{human(alert.hazard_type)}</h3>
        <span className="state">{human(alert.lifecycle)}</span>
        <span className="state">{human(alert.relevance)}</span>
      </div>
      <p className="footnote">
        Historical lookahead · {alert.seen_count} supporting ticks · revision{" "}
        {alert.revision}. This is not a probability or operating instruction.
      </p>
      {(alert.evidence_changed || alert.relevance === "review_required") && (
        <p className="error">
          Supporting evidence changed. This retained alert requires review.
        </p>
      )}
      <details>
        <summary>
          Why this alert exists · {alert.evidence.length} source links
        </summary>
        {alert.evidence.map((e, i) => (
          <div className="alert-evidence" key={i}>
            <strong>
              {e.evidence_snapshot.source_well} · source MD{" "}
              {e.evidence_snapshot.source_start_md_m}–
              {e.evidence_snapshot.source_end_md_m} m
            </strong>
            <p>
              Mapped active MD {e.evidence_snapshot.mapped_start_md_m}–
              {e.evidence_snapshot.mapped_end_md_m} m
            </p>
            <blockquote>
              {e.evidence_snapshot.quote}
              <cite>
                {e.evidence_snapshot.filename} · page{" "}
                {e.evidence_snapshot.page_number} · current review:{" "}
                {human(e.current_review_state)}
              </cite>
            </blockquote>
          </div>
        ))}
      </details>
      {editable && (
        <fieldset disabled={busy}>
          <label htmlFor={`reason-${alert.id}`}>
            Decision / feedback rationale
          </label>
          <textarea
            id={`reason-${alert.id}`}
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            placeholder="What did you assess or verify?"
          />
          <div className="decision-actions">
            {(transitions[alert.lifecycle] ?? []).map((action) => (
              <button
                key={action}
                className="secondary"
                onClick={() => act(action)}
              >
                {human(action)}
              </button>
            ))}
          </div>
          <details className="feedback-form">
            <summary>Record engineer feedback</summary>
            <form onSubmit={feedback}>
              <label htmlFor={`action-${alert.id}`}>
                Action actually taken
              </label>
              <textarea
                id={`action-${alert.id}`}
                required
                minLength={3}
                value={actionTaken}
                onChange={(e) => setActionTaken(e.target.value)}
              />
              <label htmlFor={`outcome-${alert.id}`}>Observed outcome</label>
              <select
                id={`outcome-${alert.id}`}
                value={outcome}
                onChange={(e) => setOutcome(e.target.value)}
              >
                <option value="unknown">Unknown / not yet observed</option>
                <option value="incident_observed">Incident observed</option>
                <option value="no_incident_observed">
                  No incident observed
                </option>
              </select>
              <p className="footnote">
                No incident observed does not automatically label this alert a
                false positive. Adjudication remains unset.
              </p>
              <button disabled={rationale.trim().length < 3}>
                Save feedback
              </button>
            </form>
          </details>
        </fieldset>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!!alert.actions.length && (
        <details>
          <summary>Decision history · {alert.actions.length}</summary>
          {alert.actions.map((a, i) => (
            <p key={i}>
              {human(a.action)} · {a.actor_name}: {a.rationale}
            </p>
          ))}
        </details>
      )}
      {!!alert.feedback.length && (
        <details>
          <summary>Feedback history · {alert.feedback.length}</summary>
          {alert.feedback.map((f, i) => (
            <p key={i}>
              {f.action_taken} · {human(f.observed_outcome)} · {f.rationale}
            </p>
          ))}
        </details>
      )}
    </article>
  );
}

export default function Operations({ token }: { token: string }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selected, setSelected] = useState("");
  const [data, setData] = useState<Snapshot | null>(null);
  const [role, setRole] = useState("viewer");
  const [busy, setBusy] = useState(false);
  const [offline, setOffline] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const [speed, setSpeed] = useState("1");
  const canControl = ["engineer", "admin"].includes(role);
  useEffect(() => {
    let active = true;
    api<{ role: string }>(token, "/me")
      .then((me) => active && setRole(me.role))
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [token]);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const list = await api<Session[]>(token, "/replay-sessions");
        if (!active) return;
        setSessions(list);
        if (!selected && list.length) setSelected(list[0].id);
        if (selected) {
          const next = await api<Snapshot>(
            token,
            `/replay-sessions/${selected}`,
          );
          if (active) setData(next);
        }
        if (active) setOffline(false);
      } catch (e) {
        if (active) {
          setOffline(true);
          setError((e as Error).message);
        }
      }
    }
    void load();
    const timer = setInterval(load, 1500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [token, selected, revision]);
  async function create() {
    setBusy(true);
    setError("");
    try {
      const next = await api<Session>(token, "/replay-sessions", {
        scenario_id: "golden-mud-loss-v1",
        speed: Number(speed),
      });
      setSelected(next.id);
      setData(null);
      setRevision((x) => x + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function control(action: string) {
    if (!data) return;
    setBusy(true);
    setError("");
    try {
      const next = await api<Session>(
        token,
        `/replay-sessions/${selected}/control`,
        { action, expected_version: data.session.revision },
      );
      if (action === "reset") {
        setData(null);
        setSelected(next.id);
      }
      setRevision((x) => x + 1);
    } catch (e) {
      setError((e as Error).message);
      setRevision((x) => x + 1);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="operations">
      <div className="archive-heading">
        <div>
          <p className="eyebrow">Operations / Synthetic rehearsal</p>
          <h1>Before the next interval.</h1>
          <p>
            Historical evidence ahead of the bit. Human judgment at every step.
          </p>
        </div>
        <span className="state">SIMULATED · NOT LIVE eRTMAC</span>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="replay-controls">
        <div>
          <label htmlFor="replay-session">Replay history</label>
          <select
            id="replay-session"
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value);
              setData(null);
            }}
          >
            <option value="">Select a session</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {new Date(s.created_at).toLocaleString()} · {s.state} ·{" "}
                {s.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </div>
        {canControl && (
          <>
            <div>
              <label htmlFor="replay-speed">New session speed</label>
              <select
                id="replay-speed"
                value={speed}
                onChange={(e) => setSpeed(e.target.value)}
              >
                <option value="0.1">0.1× · 20 seconds / step</option>
                <option value="1">1× · 2 seconds / step</option>
                <option value="2">2× · 1 second / step</option>
              </select>
            </div>
            <button disabled={busy || offline} onClick={create}>
              New synthetic replay
            </button>
          </>
        )}
      </div>
      {!data ? (
        <p className="notice">
          {selected
            ? "Loading replay snapshot…"
            : "Create a replay as an engineer/admin, or select a saved session. Approved SYN-B evidence is required to trigger the golden mud-loss alert."}
        </p>
      ) : (
        <>
          <div className="operation-readout">
            <div>
              <span className="eyebrow">SYN-A / Measured depth</span>
              <strong>
                {data.telemetry ? Number(data.telemetry.md_m).toFixed(0) : "—"}
                <small> m MD</small>
              </strong>
              <span>Datum: synthetic_reference · MD = TVD in this fixture</span>
            </div>
            <div>
              <span className="eyebrow">Receipt status</span>
              <h2>
                {offline
                  ? "Disconnected · cached"
                  : data.stale ||
                      !data.telemetry ||
                      clock - Date.parse(data.telemetry.received_at) > 15000
                    ? "Stale / not received"
                    : "Fresh simulated sample"}
              </h2>
              <p>
                {data.telemetry
                  ? `Received ${new Date(data.telemetry.received_at).toLocaleString()}`
                  : "No sample yet"}
              </p>
              <p>
                State: {data.session.state} · step {data.session.next_sequence}/
                {data.steps_total}
              </p>
            </div>
            <div>
              <span className="eyebrow">Historical lookahead</span>
              <h2>100 m</h2>
              <p>Formation: SYN-F1 · radius: 5 km</p>
              <p>ML risk: unavailable · no model</p>
            </div>
          </div>
          {!data.replay_worker_ready && (
            <p className="notice">
              Automatic replay worker is unavailable. Manual stepping remains
              available to engineers while connected.
            </p>
          )}
          {canControl && (
            <div className="replay-buttons">
              <button
                disabled={busy || offline || data.session.state !== "paused"}
                onClick={() => control("step")}
              >
                Next depth sample
              </button>
              <button
                className="secondary"
                disabled={
                  busy ||
                  offline ||
                  !data.replay_worker_ready ||
                  data.session.state !== "paused"
                }
                onClick={() => control("resume")}
              >
                Play replay
              </button>
              <button
                className="secondary"
                disabled={busy || offline || data.session.state !== "running"}
                onClick={() => control("pause")}
              >
                Pause
              </button>
              <button
                className="text-button"
                disabled={busy || offline}
                onClick={() => control("reset")}
              >
                Reset into new session
              </button>
            </div>
          )}
          <p className="footnote">
            Fixed depths: 2029 → 2030 → 2030 → 2031 → 2141 m. New alerts are
            evaluated only on fresh, server-generated samples. Refreshing this
            page does not advance replay.
          </p>
          <div className="section-heading">
            <h2>Evidence-backed alerts</h2>
            <span>
              {data.alerts.length} episodes · acknowledgment ≠ resolution
            </span>
          </div>
          {data.alerts.length ? (
            data.alerts.map((a) => (
              <AlertReview
                key={a.id}
                alert={a}
                token={token}
                editable={canControl && !offline}
                refresh={() => setRevision((x) => x + 1)}
              />
            ))
          ) : (
            <p className="notice">
              No alert has been triggered in this session. This does not
              establish that drilling is safe; check reviewed source coverage.
            </p>
          )}
        </>
      )}
    </section>
  );
}
