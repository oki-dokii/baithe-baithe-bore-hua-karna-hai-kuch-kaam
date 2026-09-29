import { FormEvent, Suspense, lazy, useEffect, useRef, useState } from "react";
import Documents from "./Documents";
const Intelligence = lazy(() => import("./Intelligence"));
const Analytics = lazy(() => import("./Analytics"));
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
  const cls = `badge badge-${state.toLowerCase().replace(/[\s·]/g, "_")}`;
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
const IconAnalytics = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="4" cy="4.5" r="2" />
    <circle cx="12" cy="5" r="2" />
    <circle cx="8" cy="12" r="2" />
    <path d="M5.6 5.8l4.8 5M6 4.5h4M10.4 6.2L9.2 10.2" strokeLinecap="round" />
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
const IconHelp = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="8" r="6.5" />
    <path d="M6 6c0-1.1.9-2 2-2s2 .9 2 2c0 1.5-2 2-2 2.5M8 12v.5" strokeLinecap="round" />
  </svg>
);
const IconChevronLeft = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M10 12L6 8l4-4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const IconChevronRight = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const IconMenu = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M2 4h12M2 8h12M2 12h12" strokeLinecap="round" />
  </svg>
);
const IconClose = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
  </svg>
);

type View = "operations" | "intelligence" | "analytics" | "questions" | "documents" | "foundation" | "prediction";

const NAV_GROUPS = [
  {
    label: "Monitor",
    items: [
      { id: "operations" as View, label: "Observe", plate: "00", desc: "Live well desk", Icon: IconObserve },
    ],
  },
  {
    label: "Find evidence",
    items: [
      { id: "intelligence" as View, label: "Explore", plate: "01", desc: "Offsets and geology", Icon: IconExplore },
      { id: "analytics" as View, label: "Correlate", plate: "02", desc: "Response & NPT ledger", Icon: IconAnalytics },
      { id: "questions" as View, label: "Investigate", plate: "03", desc: "Answers and citations", Icon: IconInvestigate },
      { id: "documents" as View, label: "Validate", plate: "04", desc: "Review source material", Icon: IconValidate },
    ],
  },
  {
    label: "Platform",
    items: [
      { id: "foundation" as View, label: "Directory", plate: "05", desc: "Wells and system", Icon: IconDirectory },
      { id: "prediction" as View, label: "Evaluate", plate: "06", desc: "Model readiness", Icon: IconEvaluate },
    ],
  },
];

const VIEW_TITLES: Record<View, string> = {
  operations: "Observe",
  intelligence: "Explore",
  analytics: "Correlate",
  questions: "Investigate",
  documents: "Validate",
  foundation: "Directory",
  prediction: "Evaluate",
};

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
  const [loginBusy, setLoginBusy] = useState(false);
  const [roleError, setRoleError] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    onConnect(token.trim());
    setToken("");
  }

  async function handleRoleLogin(role: string) {
    setLoginBusy(true);
    setRoleError("");
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? data.error?.message ?? "Login failed");
      onConnect(data.token);
    } catch (err: any) {
      setRoleError(err.message ?? "Role connection failed");
    } finally {
      setLoginBusy(false);
    }
  }

  const depthTicks = [
    { depth: "1,800 m", major: false },
    { depth: "2,000 m", major: true },
    { depth: "2,100 m", major: false },
    { depth: "2,141 m", major: true },
    { depth: "2,200 m", major: false },
    { depth: "2,300 m", major: false },
  ];

  const ROLES = [
    { id: "engineer", title: "Drilling Operations Engineer", badge: "Live Ops", desc: "Telemetry monitoring, voice memos & hazard simulation" },
    { id: "reviewer", title: "Wellsite Verification Reviewer", badge: "Evidence Audit", desc: "Inspect source passages, verify & approve historical claims" },
    { id: "viewer", title: "Read-Only Viewer", badge: "Observer", desc: "View approved claims, offset briefs & nearby well logs" },
    { id: "admin", title: "Observatory Admin", badge: "Supervisory", desc: "ML model approvals, dataset seeding & retention policies" },
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

          <h2 className="auth-title">Select Operational Role</h2>
          <p className="auth-desc">
            Sign in with an authenticated role credential or enter your local bearer token.
          </p>

          {(error || roleError) && (
            <div className="error-msg" role="alert">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="8" cy="8" r="7" />
                <path d="M8 5v3.5M8 11v.5" strokeLinecap="round" />
              </svg>
              {error || roleError}
            </div>
          )}

          {/* Quick Role Selection Buttons */}
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px" }}>
            {ROLES.map((r) => (
              <button
                key={r.id}
                type="button"
                className="secondary"
                disabled={loading || loginBusy}
                onClick={() => handleRoleLogin(r.id)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  textAlign: "left",
                  padding: "10px 14px",
                  borderRadius: "var(--r-md)",
                  border: "1px solid var(--border)",
                  background: "var(--slate-dark)",
                  cursor: "pointer",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", width: "100%", alignItems: "center" }}>
                  <strong style={{ fontSize: "0.84rem", color: "var(--text-primary)" }}>{r.title}</strong>
                  <span style={{ fontSize: "0.68rem", padding: "2px 6px", borderRadius: "3px", background: "var(--basin)", color: "var(--teal-glow)", fontFamily: "var(--font-mono)" }}>
                    {r.badge}
                  </span>
                </div>
                <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "3px" }}>
                  {r.desc}
                </span>
              </button>
            ))}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px", margin: "10px 0" }}>
            <div style={{ flex: 1, height: "1px", background: "var(--border)" }} />
            <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontFamily: "var(--font-mono)" }}>or enter custom token</span>
            <div style={{ flex: 1, height: "1px", background: "var(--border)" }} />
          </div>

          <div className="field">
            <label className="field-label" htmlFor="access-token">Custom access token</label>
            <input
              id="access-token"
              type="password"
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
            disabled={loading || loginBusy || token.length < 16}
          >
            {loading || loginBusy ? "Connecting…" : "Connect with Token →"}
          </button>

          <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "14px", fontFamily: "var(--font-mono)", lineHeight: 1.6 }}>
            OIL Subsurface Observatory · Role-Based Access Control · Source-audited evidence pipeline.
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
          <h1 className="ws-title">Well directory &amp; platform</h1>
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
                <p className="text-muted" style={{ fontSize: "0.875rem" }}>
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
                    <p className="text-muted" style={{ fontSize: "0.875rem" }}>No wells within {radius} km radius.</p>
                  )}
                  <p className="mono-sm" style={{ marginTop: "12px", lineHeight: 1.6 }}>
                    Nearby wells selected by surface distance. Formation correlation planned for Phase 3.
                  </p>
                </>
              ) : (
                <p className="text-muted" style={{ fontSize: "0.875rem" }}>Select an active well first.</p>
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

// ── Sidebar Navigation ─────────────────────────────────────────
function Sidebar({
  view,
  setView,
  disconnect,
  well,
  status,
  collapsed,
  onToggleCollapse,
}: {
  view: View;
  setView: (v: View) => void;
  disconnect: () => void;
  well: Well | undefined;
  status: Status;
  collapsed: boolean;
  onToggleCollapse: () => void;
}) {
  const isSynthetic = status.source_mode === "SYNTHETIC";

  return (
    <nav
      className={`nav-sidebar${collapsed ? " collapsed" : ""}`}
      aria-label="Main navigation"
    >
      {/* Header / Branding */}
      <div className="sidebar-header">
        <div className="sidebar-mark" title="NWIS · Nearby Wells Intelligence System">N</div>
        <div className="sidebar-branding">
          <strong>NWIS</strong>
          <small>Subsurface Observatory</small>
        </div>
      </div>

      {/* Active well block */}
      {well && (
        <div className="sidebar-well" title={`Active well: ${well.external_id}`}>
          <div className="sidebar-well-id">{well.external_id}</div>
          <div className="sidebar-well-meta">{well.basin_name ?? "Basin unknown"}</div>
          <div className="sidebar-well-mode">
            <span className={`ctx-dot ${isSynthetic ? "synthetic" : "live"}`} aria-hidden="true" />
            {status.source_mode}
          </div>
        </div>
      )}

      {/* Navigation groups */}
      <div style={{ flex: 1, overflowY: "auto", padding: "4px 0" }}>
        {NAV_GROUPS.map((group, gi) => (
          <div key={gi} className="nav-group">
            <span className="nav-group-label">{group.label}</span>
            {group.items.map(({ id, label, plate, desc, Icon }) => (
              <button
                key={id}
                className={`nav-item${view === id ? " active" : ""}`}
                onClick={() => setView(id)}
                aria-label={`${plate} ${label} — ${desc}`}
                aria-current={view === id ? "page" : undefined}
                title={collapsed ? `${plate} · ${label} — ${desc}` : undefined}
              >
                <span className="nav-item-icon"><Icon /></span>
                <span className="nav-item-text">
                  <span className="nav-item-label">
                    <span className="nav-item-name">{label}</span>
                    <span className="nav-item-plate">{plate}</span>
                  </span>
                  <span className="nav-item-desc">{desc}</span>
                </span>
              </button>
            ))}
            {gi < NAV_GROUPS.length - 1 && <div className="nav-sep" />}
          </div>
        ))}
      </div>

      {/* Bottom area */}
      <div className="sidebar-bottom">
        <button
          className="nav-item nav-item-muted"
          onClick={() => {}}
          title="Take a tour of NWIS"
          aria-label="Take a tour of NWIS"
        >
          <span className="nav-item-icon"><IconHelp /></span>
          <span className="nav-item-text">
            <span className="nav-item-label">
              <span className="nav-item-name">Take a tour</span>
            </span>
            <span className="nav-item-desc">Guided walkthrough</span>
          </span>
        </button>
        <button
          className="nav-disconnect"
          onClick={disconnect}
          title="Disconnect from platform"
          aria-label="Disconnect from platform"
        >
          <IconDisconnect />
          <span className="nav-disconnect-label">Disconnect</span>
        </button>
      </div>

      {/* Collapse toggle */}
      <div className="sidebar-collapse">
        <button
          className="sidebar-collapse-btn"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <IconChevronRight /> : <IconChevronLeft />}
        </button>
      </div>
    </nav>
  );
}

// ── Mobile Drawer ──────────────────────────────────────────────
function MobileDrawer({
  view,
  setView,
  disconnect,
  well,
  status,
  open,
  onClose,
}: {
  view: View;
  setView: (v: View) => void;
  disconnect: () => void;
  well: Well | undefined;
  status: Status;
  open: boolean;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const isSynthetic = status.source_mode === "SYNTHETIC";

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && open) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  function navigate(v: View) {
    setView(v);
    onClose();
  }

  return (
    <>
      <div
        className={`drawer-overlay${open ? " open" : ""}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        className={`nav-drawer${open ? " open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
      >
        <div className="drawer-close">
          <div className="sidebar-header" style={{ border: "none", padding: 0, minHeight: "auto" }}>
            <div className="sidebar-mark">N</div>
            <div className="sidebar-branding">
              <strong>NWIS</strong>
              <small>Subsurface Observatory</small>
            </div>
          </div>
          <button
            ref={closeRef}
            className="drawer-close-btn"
            onClick={onClose}
            aria-label="Close navigation menu"
          >
            <IconClose />
          </button>
        </div>

        {well && (
          <div className="sidebar-well" style={{ margin: "10px 12px 4px" }}>
            <div className="sidebar-well-id">{well.external_id}</div>
            <div className="sidebar-well-meta">{well.basin_name ?? "Basin unknown"}</div>
            <div className="sidebar-well-mode">
              <span className={`ctx-dot ${isSynthetic ? "synthetic" : "live"}`} aria-hidden="true" />
              {status.source_mode}
            </div>
          </div>
        )}

        <div style={{ flex: 1, overflowY: "auto", padding: "4px 8px" }}>
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi} className="nav-group" style={{ padding: 0 }}>
              <span className="nav-group-label">{group.label}</span>
              {group.items.map(({ id, label, plate, desc, Icon }) => (
                <button
                  key={id}
                  className={`nav-item${view === id ? " active" : ""}`}
                  onClick={() => navigate(id)}
                  aria-label={`${plate} ${label} — ${desc}`}
                  aria-current={view === id ? "page" : undefined}
                >
                  <span className="nav-item-icon"><Icon /></span>
                  <span className="nav-item-text">
                    <span className="nav-item-label">
                      <span className="nav-item-name">{label}</span>
                      <span className="nav-item-plate">{plate}</span>
                    </span>
                    <span className="nav-item-desc">{desc}</span>
                  </span>
                </button>
              ))}
              {gi < NAV_GROUPS.length - 1 && <div className="nav-sep" />}
            </div>
          ))}
        </div>

        <div className="sidebar-bottom">
          <button
            className="nav-item nav-item-muted"
            onClick={onClose}
            aria-label="Take a tour of NWIS"
          >
            <span className="nav-item-icon"><IconHelp /></span>
            <span className="nav-item-text">
              <span className="nav-item-label">
                <span className="nav-item-name">Take a tour</span>
              </span>
              <span className="nav-item-desc">Guided walkthrough</span>
            </span>
          </button>
          <button
            className="nav-disconnect"
            onClick={() => { disconnect(); onClose(); }}
            aria-label="Disconnect from platform"
          >
            <IconDisconnect />
            <span className="nav-disconnect-label">Disconnect</span>
          </button>
        </div>
      </div>
    </>
  );
}

// ── Context Bar ────────────────────────────────────────────────
function ContextBar({
  status,
  wells,
  selected,
  streamMode,
  view,
  onMenuOpen,
}: {
  status: Status;
  wells: Well[];
  selected: string;
  streamMode?: string;
  view: View;
  onMenuOpen: () => void;
}) {
  const w = wells.find((well) => well.id === selected);
  const isReplay = status.source_mode === "SYNTHETIC";
  const dotCls = isReplay ? "ctx-dot synthetic" : "ctx-dot live";

  return (
    <div className="context-bar" role="banner" aria-label="Well context">
      {/* Mobile menu button */}
      <button
        className="mobile-menu-btn"
        onClick={onMenuOpen}
        aria-label="Open navigation menu"
        style={{ marginRight: "12px" }}
      >
        <IconMenu />
      </button>

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
          <div className="ctx-chip" style={{ display: "none" }} data-coords>
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

      {/* Current view indicator */}
      <span style={{
        fontSize: "0.8125rem",
        fontWeight: 600,
        color: "var(--text-secondary)",
        marginRight: "12px",
        whiteSpace: "nowrap",
      }}>
        {VIEW_TITLES[view]}
      </span>

      {streamMode && (
        <span className={`ctx-stream-badge ${streamMode === "ws" ? "ws" : "http"}`}>
          {streamMode === "ws" ? "⚡ WebSocket" : "↺ HTTP"}
        </span>
      )}
      <div className="ctx-chip" style={{ borderRight: "none" }}>
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

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
    setSidebarCollapsed(false);
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

  const activeWell = wells.find((w) => w.id === selected);

  return (
    <div className="shell">
      {/* Descriptive sidebar */}
      <Sidebar
        view={view}
        setView={setView}
        disconnect={disconnect}
        well={activeWell}
        status={status}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
      />

      {/* Mobile drawer */}
      <MobileDrawer
        view={view}
        setView={setView}
        disconnect={disconnect}
        well={activeWell}
        status={status}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />

      {/* Main body */}
      <div className={`app-body${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
        <ContextBar
          status={status}
          wells={wells}
          selected={selected}
          view={view}
          onMenuOpen={() => setDrawerOpen(true)}
        />

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
          ) : view === "analytics" ? (
            <Suspense fallback={
              <div className="workspace">
                <div className="workspace-body">
                  <div className="notice">Loading correlation analytics & ledger…</div>
                </div>
              </div>
            }>
              <Analytics token={token} />
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
