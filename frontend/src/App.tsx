import { FormEvent, ReactElement, Suspense, lazy, useEffect, useState } from "react";
import Documents from "./Documents";
const Intelligence = lazy(() => import("./Intelligence"));
import Operations from "./Operations";
import Prediction from "./Prediction";
import ReportQuestions from "./ReportQuestions";
import "./styles.css";

type Component = { state: string; detail: string | null };
type Status = {
  environment: string;
  source_mode: string;
  database: Component;
  spatial: Component;
  vector: Component;
  ingestion: Component;
  replay: Component;
  prediction: Component;
  datasets: string[];
  checked_at: string;
};
type Well = {
  id: string;
  external_id: string;
  name: string;
  basin_name: string | null;
  data_kind: string;
  longitude: number;
  latitude: number;
  surface_distance_m: number | null;
};
type WellPage = { items: Well[]; next_cursor: string | null };

async function getJson<T>(path: string, token: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      data.error?.message ?? `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

function StateBadge({ state }: { state: string }) {
  const cls = `badge badge-${state.toLowerCase()}`;
  return <span className={cls}>{state.replaceAll("_", " ")}</span>;
}

// ── SVG Icons ──────────────────────────────────────────────────
const IconObserve = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="8" r="3" />
    <path d="M8 1v2M8 13v2M1 8h2M13 8h2" strokeLinecap="round" />
    <path d="M3.5 3.5l1.5 1.5M11 11l1.5 1.5M11 3.5L9.5 5M3.5 12.5L5 11" strokeLinecap="round" />
  </svg>
);
const IconExplore = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="7" r="4.5" />
    <path d="M8 11.5V15M5.5 15h5" strokeLinecap="round" />
    <circle cx="8" cy="7" r="1.5" fill="currentColor" stroke="none" />
  </svg>
);
const IconInvestigate = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="6.5" cy="6.5" r="4" />
    <path d="M9.5 9.5L14 14" strokeLinecap="round" />
  </svg>
);
const IconValidate = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="1.5" width="10" height="13" rx="1" />
    <path d="M5 5.5h6M5 8h6M5 10.5h4" strokeLinecap="round" />
    <path d="M13 11l1.5 1.5L16 10" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const IconDirectory = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="1" y="4" width="14" height="10" rx="1" />
    <path d="M1 7h14M5 4V2.5h4.5" strokeLinecap="round" />
    <circle cx="8" cy="11" r="1.5" />
  </svg>
);
const IconEvaluate = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="1" y="11" width="3" height="4" rx="0.5" />
    <rect x="6" y="7" width="3" height="8" rx="0.5" />
    <rect x="11" y="3" width="3" height="12" rx="0.5" />
    <path d="M2.5 9l4-4 4-2" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="1.5 1" />
  </svg>
);
const IconDisconnect = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M5.5 10.5l5-5M6 4l-4 4 2 2 4-4M10 12l4-4-2-2-4 4" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M13 3l-2 2" strokeLinecap="round" />
  </svg>
);

type View = "operations" | "documents" | "intelligence" | "foundation" | "prediction" | "questions";

const NAV_ITEMS: { id: View; label: string; plate: string; Icon: () => ReactElement }[] = [
  { id: "operations",  label: "Observe",     plate: "00", Icon: IconObserve },
  { id: "intelligence",label: "Explore",     plate: "01", Icon: IconExplore },
  { id: "questions",   label: "Investigate", plate: "02", Icon: IconInvestigate },
  { id: "documents",   label: "Validate",    plate: "03", Icon: IconValidate },
  { id: "foundation",  label: "Directory",   plate: "04", Icon: IconDirectory },
  { id: "prediction",  label: "Evaluate",    plate: "05", Icon: IconEvaluate },
];

// ── Landing ────────────────────────────────────────────────────
function Landing({
  onConnect,
  loading,
  error,
}: {
  onConnect: (token: string) => void;
  loading: boolean;
  error: string;
}) {
  const [token, setToken] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    onConnect(token.trim());
    setToken("");
  }

  const depthTicks = [
    { depth: "1,800 m", major: false },
    { depth: "2,000 m", major: true },
    { depth: "2,100 m", major: false },
    { depth: "2,141 m", major: true },
    { depth: "2,200 m", major: false },
    { depth: "2,300 m", major: false },
  ];

  return (
    <div className="landing">
      <div className="landing-ruler" aria-hidden="true">
        {depthTicks.map((t) => (
          <div key={t.depth} className={`ruler-tick${t.major ? " major" : ""}`}>
            <span>{t.depth}</span>
          </div>
        ))}
      </div>

      <div className="landing-main">
        <div className="landing-hero">
          <p className="landing-plate">
            OIL · SIH Prototype · Nearby Wells Intelligence System
          </p>
          <h1 className="landing-title">
            What one well teaches,
            <br />
            the <em>next</em> should know.
          </h1>
          <p className="landing-sub">
            A subsurface observatory connecting historical drilling experience,
            nearby well analogues, formation correlation, and proactive hazard
            alerts — source-led, human-reviewed, evidence-backed.
          </p>
          <div className="landing-features">
            {[
              ["00", "Observe live telemetry and evidence-backed alerts"],
              ["01", "Explore nearby wells by map and depth correlation"],
              ["02", "Investigate cited historical cases and mitigations"],
              ["03", "Validate ingested reports and approve evidence"],
              ["04", "Browse well directory and formation intelligence"],
            ].map(([num, desc]) => (
              <div className="feature-row" key={num}>
                <span className="feat-num">{num} ›</span>
                <span>{desc}</span>
              </div>
            ))}
          </div>
        </div>

        <form className="auth-card" onSubmit={submit} id="auth-form">
          <div className="auth-logo">
            <div className="auth-mark">N</div>
            <div className="auth-brand">
              <strong>NWIS</strong>
              <small>Subsurface Observatory</small>
            </div>
          </div>

          <h2 className="auth-title">Connect to platform</h2>
          <p className="auth-desc">
            Enter your local access token to connect. Reviewers can inspect
            source pages and approve evidence; viewers see approved claims.
            Your token stays in memory only.
          </p>

          {error && (
            <div className="error-msg" role="alert">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="8" cy="8" r="7" />
                <path d="M8 5v3.5M8 11v.5" strokeLinecap="round" />
              </svg>
              {error}
            </div>
          )}

          <div className="field">
            <label className="field-label" htmlFor="access-token">Local access token</label>
            <input
              id="access-token"
              type="password"
              required
              minLength={16}
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Enter token (min 16 chars)"
              autoComplete="current-password"
            />
          </div>

          <button
            className="btn btn-primary btn-full"
            type="submit"
            id="connect-btn"
            disabled={loading || token.length < 16}
          >
            {loading ? "Connecting…" : "Connect to NWIS"}
          </button>

          <p style={{ fontSize: "0.62rem", color: "var(--text-dim)", marginTop: "14px", fontFamily: "var(--font-mono)", lineHeight: 1.6 }}>
            SIMULATED · Synthetic demo rehearsal. No trained risk model or live eRTMAC.
            Synthetic examples establish behavior, not predictive accuracy.
          </p>
        </form>
      </div>

      <footer className="app-footer">
        <span className="footer-brand">NWIS</span>
        <span className="footer-text">Historical knowledge · Traceable evidence</span>
        <span className="footer-spacer" />
        <span className="simulated-tag">SIH Prototype · Decision support, not operational instruction</span>
      </footer>
    </div>
  );
}

// ── Well Directory ─────────────────────────────────────────────
function FoundationView({
  wells,
  nearby,
  selected,
  radius,
  onSelect,
  onRadius,
  status,
}: {
  wells: Well[];
  nearby: Well[];
  selected: string;
  radius: number;
  onSelect: (id: string) => void;
  onRadius: (r: number) => void;
  status: Status;
}) {
  const selectedWell = wells.find((w) => w.id === selected);
  const components: [string, Component][] = [
    ["Database", status.database],
    ["Spatial", status.spatial],
    ["Vector", status.vector],
    ["Ingestion", status.ingestion],
    ["Replay", status.replay],
    ["Prediction", status.prediction],
  ];

  return (
    <div className="workspace">
      <div className="workspace-header">
        <div>
          <p className="ws-eyebrow"><span className="plate-num">04</span> Well Directory</p>
          <h1 className="ws-title">Well directory & platform</h1>
          <p className="ws-desc">Browse loaded wells, configure search radius, and inspect platform component status.</p>
        </div>
        <StateBadge state={`${status.source_mode} · ${status.environment}`} />
      </div>

      <div className="workspace-body">
        {/* Platform status */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <span className="live-dot" aria-hidden="true" />
              Platform Status
            </span>
            <span className="mono-sm">
              {status.datasets.length ? status.datasets.join(", ") : "No datasets"}
            </span>
          </div>
          <div className="card-body">
            <div className="status-grid">
              {components.map(([name, comp]) => (
                <div className="status-cell" key={name}>
                  <span className="status-cell-name">{name}</span>
                  <StateBadge state={comp.state} />
                  {comp.detail && <span className="status-cell-detail">{comp.detail}</span>}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="two-col">
          {/* Well selector */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Well Selector</span>
              <span className="mono-sm">{wells.length} loaded</span>
            </div>
            <div className="card-body">
              {wells.length ? (
                <>
                  <div className="field">
                    <label className="field-label" htmlFor="well-select">Active well</label>
                    <select
                      id="well-select"
                      value={selected}
                      onChange={(e) => onSelect(e.target.value)}
                    >
                      {wells.map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name} · {w.data_kind}
                        </option>
                      ))}
                    </select>
                  </div>
                  {selectedWell && (
                    <div className="well-meta-block">
                      <div className="well-id-big">{selectedWell.external_id}</div>
                      <div className="well-coord">{selectedWell.basin_name ?? "Basin unknown"}</div>
                      <div className="well-coord">
                        {selectedWell.latitude.toFixed(4)}° N, {selectedWell.longitude.toFixed(4)}° E
                      </div>
                      <StateBadge state={selectedWell.data_kind} />
                    </div>
                  )}
                </>
              ) : (
                <p className="text-muted" style={{ fontSize: "0.8rem" }}>
                  Load the golden fixture to see demonstration wells.
                </p>
              )}
            </div>
          </div>

          {/* Nearby wells */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Nearby Wells</span>
              <span className="mono-sm">Surface distance</span>
            </div>
            <div className="card-body">
              <div className="field">
                <label className="field-label" htmlFor="radius-input">
                  Search radius · <span className="text-teal">{radius} km</span>
                </label>
                <input
                  id="radius-input"
                  type="range"
                  min="1"
                  max="25"
                  value={radius}
                  onChange={(e) => onRadius(Number(e.target.value))}
                  disabled={!selected}
                />
              </div>
              {selected ? (
                <>
                  {nearby.length ? (
                    nearby.map((w) => (
                      <div className="well-entry" key={w.id}>
                        <div className="well-entry-info">
                          <span className="well-entry-name">{w.name}</span>
                          <span className="well-entry-meta">
                            {w.data_kind} · {w.basin_name}
                          </span>
                        </div>
                        <span className="well-entry-dist">
                          {((w.surface_distance_m ?? 0) / 1000).toFixed(2)} km
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-muted" style={{ fontSize: "0.8rem" }}>No wells within {radius} km radius.</p>
                  )}
                  <p className="mono-sm" style={{ marginTop: "12px", lineHeight: 1.6 }}>
                    Nearby wells selected by surface distance. Formation correlation planned for Phase 3.
                  </p>
                </>
              ) : (
                <p className="text-muted" style={{ fontSize: "0.8rem" }}>Select an active well first.</p>
              )}
            </div>
          </div>
        </div>

        <p className="mono-sm">
          Checked {new Date(status.checked_at).toLocaleString()}
        </p>
      </div>
    </div>
  );
}

// ── Context Bar ────────────────────────────────────────────────
function ContextBar({
  status,
  wells,
  selected,
  streamMode,
}: {
  status: Status;
  wells: Well[];
  selected: string;
  streamMode?: string;
}) {
  const w = wells.find((well) => well.id === selected);
  const isReplay = status.source_mode === "SYNTHETIC";
  const dotCls = isReplay ? "ctx-dot replay" : "ctx-dot live";

  return (
    <div className="context-bar" role="banner" aria-label="Well context">
      {w && (
        <>
          <div className="ctx-chip">
            <span className="ctx-label">Well</span>
            <span className="ctx-value teal">{w.external_id}</span>
          </div>
          <div className="ctx-chip">
            <span className="ctx-label">Basin</span>
            <span className="ctx-value">{w.basin_name ?? "—"}</span>
          </div>
          <div className="ctx-chip">
            <span className="ctx-label">Coords</span>
            <span className="ctx-value mono-sm">
              {w.latitude.toFixed(4)}°N {w.longitude.toFixed(4)}°E
            </span>
          </div>
        </>
      )}
      <div className="ctx-chip">
        <span className={dotCls} aria-hidden="true" />
        <span className="ctx-label">Mode</span>
        <span className={`ctx-value ${isReplay ? "ochre" : "teal"}`}>
          {status.source_mode}
        </span>
      </div>
      <div className="ctx-chip">
        <span className="ctx-label">Env</span>
        <span className="ctx-value">{status.environment.toUpperCase()}</span>
      </div>
      <div className="ctx-spacer" />
      {streamMode && (
        <span className={`ctx-stream-badge ${streamMode === "ws" ? "ws" : "http"}`}>
          {streamMode === "ws" ? "⚡ WebSocket" : "↺ HTTP"}
        </span>
      )}
      <div className="ctx-chip">
        <span className="ctx-label">Datasets</span>
        <span className="ctx-value mono-sm">
          {status.datasets.length ? status.datasets[0] : "none"}
        </span>
      </div>
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────
export default function App() {
  const [token, setEntered] = useState("");
  const [status, setStatus] = useState<Status | null>(null);
  const [wells, setWells] = useState<Well[]>([]);
  const [selected, setSelected] = useState("");
  const [nearby, setNearby] = useState<Well[]>([]);
  const [radius, setRadius] = useState(5);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("operations");

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      getJson<Status>("/api/v1/status", token),
      getJson<WellPage>("/api/v1/wells", token),
    ])
      .then(([s, page]) => {
        if (!active) return;
        setStatus(s);
        setWells(page.items);
        setSelected(
          page.items.find((w) => w.external_id === "SYN-A")?.id ??
            page.items[0]?.id ??
            "",
        );
      })
      .catch((e: Error) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [token]);

  useEffect(() => {
    if (!token || !selected) return;
    let active = true;
    const path = `/api/v1/wells/nearby?active_well_id=${selected}&radius_km=${radius}`;
    getJson<WellPage>(path, token)
      .then((page) => { if (active) setNearby(page.items); })
      .catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [token, selected, radius]);

  function disconnect() {
    setEntered("");
    setStatus(null);
    setWells([]);
    setNearby([]);
    setError("");
    setView("operations");
  }

  // Not connected
  if (!status) {
    return (
      <Landing
        onConnect={setEntered}
        loading={loading}
        error={error}
      />
    );
  }

  return (
    <div className="shell">
      {/* Navigation Rail */}
      <nav className="nav-rail" aria-label="Main navigation">
        <div className="nav-logo" title="NWIS · Nearby Wells Intelligence System">N</div>

        {NAV_ITEMS.map(({ id, label, plate, Icon }) => (
          <button
            key={id}
            className={`nav-btn${view === id ? " active" : ""}`}
            onClick={() => setView(id)}
            aria-label={`${plate} ${label}`}
            aria-current={view === id ? "page" : undefined}
            title={`${plate} · ${label}`}
          >
            <Icon />
            {plate}
          </button>
        ))}

        <div className="nav-spacer" />

        <button
          className="nav-disconnect"
          onClick={disconnect}
          title="Disconnect"
          aria-label="Disconnect from platform"
        >
          <IconDisconnect />
        </button>
      </nav>

      {/* Main body */}
      <div className="app-body">
        <ContextBar status={status} wells={wells} selected={selected} />

        <div className="main-canvas">
          {view === "operations" ? (
            <Operations token={token} />
          ) : view === "documents" ? (
            <Documents token={token} />
          ) : view === "intelligence" ? (
            <Suspense fallback={
              <div className="workspace">
                <div className="workspace-body">
                  <div className="notice">Loading the well exploration atlas…</div>
                </div>
              </div>
            }>
              <Intelligence token={token} />
            </Suspense>
          ) : view === "questions" ? (
            <ReportQuestions token={token} />
          ) : view === "prediction" ? (
            <Prediction token={token} />
          ) : (
            <FoundationView
              wells={wells}
              nearby={nearby}
              selected={selected}
              radius={radius}
              onSelect={setSelected}
              onRadius={setRadius}
              status={status}
            />
          )}
        </div>

        <footer className="app-footer">
          <span className="footer-brand">NWIS</span>
          <span className="footer-text">Historical knowledge · Traceable evidence</span>
          <span className="footer-spacer" />
          <span className="simulated-tag">SIH Prototype · Decision support, not operational instruction</span>
        </footer>
      </div>
    </div>
  );
}
