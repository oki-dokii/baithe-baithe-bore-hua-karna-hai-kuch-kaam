import { useState } from "react";
import { ROLES, RoleIcon, UserRole } from "./roles";

interface DevConsoleProps {
  token: string;
  activeRole: UserRole;
  onImpersonate: (role: UserRole) => void;
  onResetTour: () => void;
}

type PingResult = {
  url: string;
  status: number | string;
  latencyMs: number;
  time: string;
  ok: boolean;
};

export default function DevConsole({
  token,
  activeRole,
  onImpersonate,
  onResetTour,
}: DevConsoleProps) {
  const [open, setOpen] = useState(false);
  const [pingResults, setPingResults] = useState<PingResult[]>([]);
  const [pinging, setPinging] = useState(false);
  const [showToken, setShowToken] = useState(false);

  async function testEndpoint(name: string, url: string, method = "GET", body?: any) {
    setPinging(true);
    const start = performance.now();
    try {
      const res = await fetch(url, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      const end = performance.now();
      const latencyMs = Math.round(end - start);
      setPingResults((prev) => [
        {
          url: `${method} ${name}`,
          status: res.status,
          latencyMs,
          time: new Date().toLocaleTimeString(),
          ok: res.ok,
        },
        ...prev.slice(0, 7),
      ]);
    } catch (err) {
      const end = performance.now();
      setPingResults((prev) => [
        {
          url: `${method} ${name}`,
          status: (err as Error).message,
          latencyMs: Math.round(end - start),
          time: new Date().toLocaleTimeString(),
          ok: false,
        },
        ...prev.slice(0, 7),
      ]);
    } finally {
      setPinging(false);
    }
  }

  function runAllPings() {
    testEndpoint("/healthz", "/healthz");
    testEndpoint("/api/v1/status", "/api/v1/status");
    testEndpoint("/api/v1/prediction/readiness", "/api/v1/prediction/readiness");
    testEndpoint(
      "/api/v1/prediction/evaluate",
      "/api/v1/prediction/evaluate",
      "POST",
      {
        rop_m_per_h: 8.5,
        wob_kn: 35.0,
        rpm: 90.0,
        torque_kn_m: 6.0,
        flow_in_l_per_min: 1600.0,
        mud_density_kg_per_m3: 1220.0,
      }
    );
  }

  return (
    <div className="dev-console-wrapper">
      {/* Floating launcher badge */}
      <button
        type="button"
        className={`dev-launcher-btn ${open ? "active" : ""}`}
        onClick={() => setOpen(!open)}
        title="Super Admin Developer Console"
        aria-label="Toggle Developer Console"
      >
        <span className="dev-pulse-dot" />
        <span className="dev-launcher-text">DEV CONSOLE</span>
        <span className="dev-tag">SUPER ADMIN</span>
      </button>

      {open && (
        <div className="dev-console-modal" role="dialog" aria-label="Developer Console">
          <div className="dev-console-header">
            <div className="dev-console-title">
              <span className="dev-terminal-icon">
                <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" />
                  <path d="M4.5 6l3 2.5-3 2.5M9.5 11h2.5" strokeLinecap="round" />
                </svg>
              </span>
              <div>
                <strong>NWIS Developer Console</strong>
                <small>Super Admin Diagnostics & Role Impersonator</small>
              </div>
            </div>
            <button
              type="button"
              className="dev-close-btn"
              onClick={() => setOpen(false)}
              aria-label="Close Developer Console"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          <div className="dev-console-body">
            {/* Quick Role Impersonator */}
            <div className="dev-section">
              <div className="dev-section-title">
                <span>DEMO ROLE IMPERSONATION</span>
                <small>Switch active role on-the-fly to test view filtering</small>
              </div>
              <div className="dev-roles-grid">
                {(["viewer", "engineer", "reviewer", "admin", "superadmin"] as UserRole[]).map((r) => {
                  const roleDef = ROLES[r];
                  const isActive = activeRole === r;
                  return (
                    <button
                      key={r}
                      type="button"
                      className={`dev-role-btn ${isActive ? "active" : ""}`}
                      onClick={() => onImpersonate(r)}
                    >
                      <span className="dev-role-icon">
                        <RoleIcon role={r} size={15} />
                      </span>
                      <span className="dev-role-info">
                        <span className="dev-role-name">{roleDef.shortTitle}</span>
                        <span className="dev-role-tag">{roleDef.badge}</span>
                      </span>
                      {isActive && <span className="dev-active-check">Active</span>}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* API Health & Pingers */}
            <div className="dev-section">
              <div className="dev-section-title">
                <span>REST API DIAGNOSTICS</span>
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  onClick={runAllPings}
                  disabled={pinging}
                  style={{ fontSize: "0.72rem", padding: "2px 8px" }}
                >
                  {pinging ? "Testing…" : "Run Full Suite"}
                </button>
              </div>

              <div className="dev-api-buttons">
                <button
                  type="button"
                  className="dev-ping-btn"
                  onClick={() => testEndpoint("/healthz", "/healthz")}
                  disabled={pinging}
                >
                  GET /healthz
                </button>
                <button
                  type="button"
                  className="dev-ping-btn"
                  onClick={() => testEndpoint("/api/v1/status", "/api/v1/status")}
                  disabled={pinging}
                >
                  GET /api/v1/status
                </button>
                <button
                  type="button"
                  className="dev-ping-btn"
                  onClick={() => testEndpoint("/api/v1/prediction/readiness", "/api/v1/prediction/readiness")}
                  disabled={pinging}
                >
                  GET /prediction/readiness
                </button>
                <button
                  type="button"
                  className="dev-ping-btn"
                  onClick={() =>
                    testEndpoint(
                      "/api/v1/prediction/evaluate",
                      "/api/v1/prediction/evaluate",
                      "POST",
                      {
                        rop_m_per_h: 8.5,
                        wob_kn: 35.0,
                        rpm: 90.0,
                        torque_kn_m: 6.0,
                        flow_in_l_per_min: 1600.0,
                        mud_density_kg_per_m3: 1220.0,
                      }
                    )
                  }
                  disabled={pinging}
                >
                  POST /prediction/evaluate
                </button>
              </div>

              {pingResults.length > 0 && (
                <div className="dev-ping-results">
                  {pingResults.map((res, i) => (
                    <div key={i} className="dev-ping-row">
                      <span className={`dev-ping-status ${res.ok ? "ok" : "err"}`}>
                        {res.status}
                      </span>
                      <span className="dev-ping-url">{res.url}</span>
                      <span className="dev-ping-latency">{res.latencyMs}ms</span>
                      <span className="dev-ping-time">{res.time}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Environment & Utilities */}
            <div className="dev-section">
              <div className="dev-section-title">
                <span>SECURITY & STORAGE UTILITIES</span>
              </div>
              <div className="dev-utils-row">
                <div className="dev-token-box">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                    <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Active Bearer Token:</span>
                    <button
                      type="button"
                      onClick={() => setShowToken(!showToken)}
                      style={{ background: "none", border: "none", color: "var(--teal-glow)", cursor: "pointer", fontSize: "0.72rem" }}
                    >
                      {showToken ? "Hide" : "Reveal"}
                    </button>
                  </div>
                  <div className="mono-sm dev-token-str">
                    {showToken ? token : token.slice(0, 12) + "••••••••••••••••"}
                  </div>
                </div>

                <div className="dev-actions-col">
                  <button
                    type="button"
                    className="btn btn-sm btn-outline"
                    onClick={() => {
                      onResetTour();
                      alert("Product tour reset. Refresh or click 'Take a tour' in the sidebar.");
                    }}
                    style={{ fontSize: "0.75rem", width: "100%" }}
                  >
                    Reset Product Tour Flag
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-ghost"
                    onClick={() => {
                      localStorage.clear();
                      alert("LocalStorage cleared.");
                    }}
                    style={{ fontSize: "0.75rem", width: "100%", color: "var(--text-muted)" }}
                  >
                    Clear LocalStorage
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
