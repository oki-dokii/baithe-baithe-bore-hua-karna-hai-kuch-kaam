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
  alert_budget: {
    kind: string;
    shift_hours: number;
    shift_number: number;
    advisory_cap: number;
    issued_advisories: number;
    suppressed_count: number;
    safety_critical_bypass: boolean;
    notice: string;
    suppressed: {
      id: string; event_id: string; hazard_type: string; mapped_start_md_m: number;
      reason: string; source_well: string; filename: string; page_number: number;
    }[];
  };
  risk_reason: string;
  steps_total: number;
  replay_worker_ready: boolean;
  transport?: string;
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

function AlertCard({
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

  const isCritical = alert.relevance === "safety_critical" || alert.hazard_type.includes("KICK") || alert.hazard_type.includes("BLOWOUT");

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
    <article className={`alert-card${isCritical ? " critical" : " advisory"}`}>
      <div className="alert-header">
        <div className={`alert-icon${isCritical ? " critical" : " advisory"}`} aria-hidden="true" />
        <span className="alert-title-text">{human(alert.hazard_type)}</span>
        <span className={`badge ${isCritical ? "badge-error" : "badge-warn"}`}>
          {human(alert.lifecycle)}
        </span>
        <span className="badge badge-default">{human(alert.relevance)}</span>
        <span className="mono-sm">rev {alert.revision}</span>
      </div>

      <div className="alert-body">
        <p className="alert-footnote">
          Historical lookahead · {alert.seen_count} supporting ticks · revision {alert.revision}.
          Similar past events indicate a condition to review, not a prediction.
          Check the cited well, formation, depth datum, and current measurements before deciding any action.
        </p>

        {(alert.evidence_changed || alert.relevance === "review_required") && (
          <div className="error-msg" role="alert">
            Supporting evidence changed — this retained alert requires review.
          </div>
        )}

        <details>
          <summary>Evidence chain · {alert.evidence.length} source link{alert.evidence.length !== 1 ? "s" : ""}</summary>
          <div style={{ paddingTop: "10px", display: "flex", flexDirection: "column", gap: "10px" }}>
            {alert.evidence.map((e, i) => (
              <div className="alert-evidence" key={i}>
                <div className="alert-evidence-header">
                  {e.evidence_snapshot.source_well} · source MD {e.evidence_snapshot.source_start_md_m}–{e.evidence_snapshot.source_end_md_m} m
                  <span style={{ marginLeft: "8px", color: "var(--text-muted)" }}>→ mapped {e.evidence_snapshot.mapped_start_md_m}–{e.evidence_snapshot.mapped_end_md_m} m</span>
                </div>
                <blockquote className="alert-quote">
                  {e.evidence_snapshot.quote}
                  <cite className="alert-cite">
                    {e.evidence_snapshot.filename} · page {e.evidence_snapshot.page_number} · review: {human(e.current_review_state)}
                  </cite>
                </blockquote>
              </div>
            ))}
          </div>
        </details>

        {editable && (
          <fieldset disabled={busy} style={{ border: 0, padding: 0 }}>
            <div className="field" style={{ marginTop: "12px" }}>
              <label className="field-label" htmlFor={`reason-${alert.id}`}>Decision rationale</label>
              <textarea
                id={`reason-${alert.id}`}
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="What did you assess or verify?"
                rows={2}
              />
            </div>

            <div className="decision-actions">
              {(transitions[alert.lifecycle] ?? []).map((action) => (
                <button
                  key={action}
                  className={`btn btn-sm ${action === "resolve" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => act(action)}
                >
                  {human(action)}
                </button>
              ))}
            </div>

            <details style={{ marginTop: "12px" }}>
              <summary>Record engineer feedback</summary>
              <form onSubmit={feedback} style={{ paddingTop: "10px" }}>
                <div className="field">
                  <label className="field-label" htmlFor={`action-${alert.id}`}>Action actually taken</label>
                  <textarea
                    id={`action-${alert.id}`}
                    required
                    minLength={3}
                    value={actionTaken}
                    onChange={(e) => setActionTaken(e.target.value)}
                    rows={2}
                  />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor={`outcome-${alert.id}`}>Observed outcome</label>
                  <select
                    id={`outcome-${alert.id}`}
                    value={outcome}
                    onChange={(e) => setOutcome(e.target.value)}
                  >
                    <option value="unknown">Unknown / not yet observed</option>
                    <option value="incident_observed">Incident observed</option>
                    <option value="no_incident_observed">No incident observed</option>
                  </select>
                </div>
                <p className="mono-sm" style={{ marginBottom: "10px", lineHeight: 1.6 }}>
                  No incident observed does not automatically label this alert a false positive.
                </p>
                <button
                  className="btn btn-secondary btn-sm"
                  disabled={rationale.trim().length < 3}
                >
                  Save feedback
                </button>
              </form>
            </details>
          </fieldset>
        )}

        {error && <div className="error-msg" role="alert">{error}</div>}

        {!!alert.actions.length && (
          <details>
            <summary>Decision history · {alert.actions.length}</summary>
            <div style={{ paddingTop: "8px", display: "flex", flexDirection: "column", gap: "6px" }}>
              {alert.actions.map((a, i) => (
                <p key={i} className="mono-sm" style={{ lineHeight: 1.6 }}>
                  <span className="text-teal">{human(a.action)}</span> · {a.actor_name}: {a.rationale}
                </p>
              ))}
            </div>
          </details>
        )}

        {!!alert.feedback.length && (
          <details>
            <summary>Feedback history · {alert.feedback.length}</summary>
            <div style={{ paddingTop: "8px", display: "flex", flexDirection: "column", gap: "6px" }}>
              {alert.feedback.map((f, i) => (
                <p key={i} className="mono-sm" style={{ lineHeight: 1.6 }}>
                  {f.action_taken} · <span className="text-ochre">{human(f.observed_outcome)}</span> · {f.rationale}
                </p>
              ))}
            </div>
          </details>
        )}
      </div>
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
  const [streamConnected, setStreamConnected] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [clock, setClock] = useState(Date.now());
  const [speed, setSpeed] = useState("1");
  const [advisoryCap, setAdvisoryCap] = useState("3");

  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const canControl = ["engineer", "admin"].includes(role);

  useEffect(() => {
    let active = true;
    api<{ role: string }>(token, "/me")
      .then((me) => active && setRole(me.role))
      .catch((e) => active && setError(e.message));
    return () => { active = false; };
  }, [token]);

  useEffect(() => {
    if (!selected || !token || typeof WebSocket === "undefined") return;
    let active = true;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let watchdog: ReturnType<typeof setTimeout> | null = null;
    setStreamConnected(false);
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${location.host}/api/v1/replay-sessions/${selected}/stream`;

    function armWatchdog(current: WebSocket) {
      if (watchdog) clearTimeout(watchdog);
      watchdog = setTimeout(() => current.close(), 6000);
    }

    function connect() {
      if (!active) return;
      let current: WebSocket;
      try {
        current = new WebSocket(url);
        socket = current;
      } catch {
        retry = setTimeout(connect, 5000);
        return;
      }
      current.onopen = () => { current.send(JSON.stringify({ token })); armWatchdog(current); };
      current.onmessage = (event) => {
        try {
          const next = JSON.parse(event.data) as Snapshot;
          if (next.session?.id !== selected) return;
          armWatchdog(current);
          setData(next);
          setStreamConnected(true);
          setOffline(false);
          setError("");
        } catch { current.close(); }
      };
      current.onerror = () => current.close();
      current.onclose = () => {
        if (watchdog) clearTimeout(watchdog);
        if (!active) return;
        setStreamConnected(false);
        retry = setTimeout(connect, 5000);
      };
    }
    connect();
    return () => {
      active = false;
      if (retry) clearTimeout(retry);
      if (watchdog) clearTimeout(watchdog);
      socket?.close();
    };
  }, [token, selected]);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const list = await api<Session[]>(token, "/replay-sessions");
        if (!active) return;
        setSessions(list);
        if (!selected && list.length) setSelected(list[0].id);
        if (selected && !streamConnected) {
          const next = await api<Snapshot>(token, `/replay-sessions/${selected}`);
          if (active) setData(next);
        }
        if (active) setOffline(false);
      } catch (e) {
        if (active) { setOffline(true); setError((e as Error).message); }
      }
    }
    void load();
    const timer = setInterval(load, streamConnected ? 5000 : 1500);
    return () => { active = false; clearInterval(timer); };
  }, [token, selected, revision, streamConnected]);

  async function create() {
    setBusy(true);
    setError("");
    try {
      const next = await api<Session>(token, "/replay-sessions", {
        scenario_id: "golden-mud-loss-v1",
        speed: Number(speed),
        advisory_cap: Number(advisoryCap),
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
      const next = await api<Session>(token, `/replay-sessions/${selected}/control`, {
        action, expected_version: data.session.revision,
      });
      if (action === "reset") { setData(null); setSelected(next.id); }
      setRevision((x) => x + 1);
    } catch (e) {
      setError((e as Error).message);
      setRevision((x) => x + 1);
    } finally {
      setBusy(false);
    }
  }

  const isStale = !data?.telemetry ||
    data.stale ||
    clock - Date.parse(data.telemetry.received_at) > 15000;

  return (
    <div className="workspace">
      <div className="workspace-header">
        <div>
          <p className="ws-eyebrow"><span className="plate-num">00</span> Observe</p>
          <h1 className="ws-title">Before the next interval.</h1>
          <p className="ws-desc">
            Historical evidence ahead of the bit. Human judgment at every step.
          </p>
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", flexShrink: 0 }}>
          <span className="badge badge-simulated">SIMULATED · NOT LIVE eRTMAC</span>
          {offline && <span className="badge badge-error">Offline</span>}
        </div>
      </div>

      <div className="workspace-body">
        {error && <div className="error-msg" role="alert">{error}</div>}

        {/* Replay controls */}
        <div className="replay-panel">
          <div className="replay-field">
            <label className="field-label" htmlFor="replay-session-select">Replay session</label>
            <select
              id="replay-session-select"
              value={selected}
              onChange={(e) => { setSelected(e.target.value); setData(null); }}
            >
              <option value="">Select a session</option>
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {new Date(s.created_at).toLocaleString()} · {s.state} · {s.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </div>
          {canControl && (
            <>
              <div className="replay-field">
                <label className="field-label" htmlFor="replay-speed-select">New session speed</label>
                <select id="replay-speed-select" value={speed} onChange={(e) => setSpeed(e.target.value)}>
                  <option value="0.1">0.1× · 20 s/step</option>
                  <option value="1">1× · 2 s/step</option>
                  <option value="2">2× · 1 s/step</option>
                </select>
              </div>
              <div className="replay-field">
                <label className="field-label" htmlFor="advisory-cap-select">Advisory cap / 12-hr shift</label>
                <select id="advisory-cap-select" value={advisoryCap} onChange={(e) => setAdvisoryCap(e.target.value)}>
                  {[0, 1, 2, 3, 5].map((n) => (
                    <option key={n} value={n}>{n} low-priority advisories</option>
                  ))}
                </select>
              </div>
              <button
                className="btn btn-primary btn-sm"
                disabled={busy || offline}
                onClick={create}
              >
                + New replay
              </button>
            </>
          )}
        </div>

        {!data ? (
          <div className="notice">
            {selected
              ? "Loading replay snapshot…"
              : "Create a replay as an engineer/admin, or select a saved session. Approved SYN-B evidence is required to trigger the golden mud-loss alert."}
          </div>
        ) : (
          <>
            {/* Telemetry readout */}
            <div className="readout-strip">
              <div className="readout-cell">
                <span className="readout-eyebrow">SYN-A · Measured depth</span>
                <div className="readout-value">
                  {data.telemetry ? Number(data.telemetry.md_m).toFixed(0) : "—"}
                  <small>m MD</small>
                </div>
                <span className="readout-sub">Datum: synthetic_reference · MD = TVD</span>
              </div>

              <div className="readout-cell">
                <span className="readout-eyebrow">Receipt status</span>
                <div className="readout-value" style={{ fontSize: "1.4rem", color: isStale ? "var(--ochre-bright)" : "var(--teal-glow)" }}>
                  {offline
                    ? "Disconnected"
                    : isStale
                      ? "Stale / not received"
                      : "Fresh sample"}
                </div>
                <span className="readout-sub">
                  {data.telemetry
                    ? `Received ${new Date(data.telemetry.received_at).toLocaleString()}`
                    : "No sample yet"}
                </span>
                <span className="readout-sub">
                  State: <span className="text-teal">{data.session.state}</span> · step {data.session.next_sequence}/{data.steps_total}
                </span>
                <span className="readout-sub">
                  Transport: {streamConnected ? "WebSocket snapshots" : "HTTP reconnect fallback"}
                </span>
              </div>

              <div className="readout-cell">
                <span className="readout-eyebrow">Historical lookahead</span>
                <div className="readout-value">100<small>m</small></div>
                <span className="readout-sub">Formation: SYN-F1 · radius: 5 km</span>
                <span className="readout-sub">ML risk: <span style={{ color: "var(--text-muted)" }}>unavailable · no model</span></span>
                <span className="mono-sm" style={{ marginTop: "4px" }}>
                  No ML probability or drilling recommendation is available.
                </span>
              </div>
            </div>

            {!data.replay_worker_ready && (
              <div className="notice">
                Automatic replay worker is unavailable. Manual stepping remains available to engineers.
              </div>
            )}

            {/* Playback controls */}
            {canControl && (
              <div className="replay-panel" style={{ padding: "14px 18px" }}>
                <span className="field-label">Replay controls</span>
                <div className="replay-actions">
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={busy || offline || data.session.state !== "paused"}
                    onClick={() => control("step")}
                  >
                    ▶ Next depth sample
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={busy || offline || !data.replay_worker_ready || data.session.state !== "paused"}
                    onClick={() => control("resume")}
                  >
                    ▷ Play replay
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={busy || offline || data.session.state !== "running"}
                    onClick={() => control("pause")}
                  >
                    ⏸ Pause
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={busy || offline}
                    onClick={() => control("reset")}
                  >
                    ↺ Reset session
                  </button>
                </div>
                <p className="mono-sm" style={{ lineHeight: 1.6 }}>
                  Fixed depths: 2029 → 2030 → 2031 → 2141 m. New alerts evaluated only on fresh server-generated samples.
                </p>
              </div>
            )}

            {/* Alert budget */}
            <details open={data.alert_budget.suppressed_count > 0}>
              <summary>
                Alert budget · {data.alert_budget.issued_advisories}/{data.alert_budget.advisory_cap} advisories shown
                {data.alert_budget.suppressed_count > 0 && (
                  <span className="badge badge-warn" style={{ marginLeft: "8px" }}>
                    {data.alert_budget.suppressed_count} suppressed
                  </span>
                )}
              </summary>
              <div style={{ padding: "10px 0", display: "flex", flexDirection: "column", gap: "8px" }}>
                <p className="mono-sm" style={{ lineHeight: 1.6 }}>{data.alert_budget.notice}</p>
                {data.alert_budget.suppressed.map((item) => (
                  <p key={item.id} className="mono-sm" style={{ lineHeight: 1.6, color: "var(--ochre)" }}>
                    {human(item.hazard_type)} · {item.source_well} · mapped {Number(item.mapped_start_md_m).toFixed(0)} m MD
                    · suppressed (cap reached) · {item.filename} p.{item.page_number}
                  </p>
                ))}
              </div>
            </details>

            {/* Alerts section */}
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: "12px" }}>
              <h2 style={{ fontFamily: "var(--font-serif)", fontSize: "1.4rem", color: "var(--text-primary)" }}>
                Evidence-backed alerts
              </h2>
              <span className="mono-sm">{data.alerts.length} episode{data.alerts.length !== 1 ? "s" : ""} · acknowledgment ≠ resolution</span>
            </div>

            {data.alerts.length ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {data.alerts.map((a) => (
                  <AlertCard
                    key={a.id}
                    alert={a}
                    token={token}
                    editable={canControl && !offline}
                    refresh={() => setRevision((x) => x + 1)}
                  />
                ))}
              </div>
            ) : (
              <div className="notice">
                No alert has been triggered in this session. This does not establish that drilling is safe; check reviewed source coverage.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
