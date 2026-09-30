/**
 * Landing.tsx — unauthenticated splash / login screen.
 * Extracted from App.tsx (Fix #12: break up the 1037-line monolith).
 */
import { FormEvent, useState } from "react";

interface LandingProps {
  onConnect: (token: string, role?: string) => void;
  loading: boolean;
  error: string;
}

const DEPTH_TICKS = [
  { depth: "1,800 m", major: false },
  { depth: "2,000 m", major: true  },
  { depth: "2,100 m", major: false },
  { depth: "2,141 m", major: true  },
  { depth: "2,200 m", major: false },
  { depth: "2,300 m", major: false },
];

const ROLES = [
  { id: "engineer", title: "Drilling Operations Engineer",  badge: "Live Ops",      desc: "Telemetry monitoring, voice memos & hazard simulation" },
  { id: "reviewer", title: "Wellsite Verification Reviewer", badge: "Evidence Audit", desc: "Inspect source passages, verify & approve historical claims" },
  { id: "viewer",   title: "Read-Only Viewer",               badge: "Observer",       desc: "View approved claims, offset briefs & nearby well logs" },
  { id: "admin",    title: "Observatory Admin",               badge: "Supervisory",    desc: "ML model approvals, dataset seeding & retention policies" },
];

export default function Landing({ onConnect, loading, error }: LandingProps) {
  const [token, setToken]       = useState("");
  const [loginBusy, setLoginBusy] = useState(false);
  const [roleError, setRoleError] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    const t = token.trim();
    let detectedRole = "engineer";
    if (t.includes("admin")) detectedRole = "admin";
    else if (t.includes("reviewer")) detectedRole = "reviewer";
    else if (t.includes("viewer")) detectedRole = "viewer";
    onConnect(t, detectedRole);
    setToken("");
  }

  async function handleRoleLogin(role: string) {
    setLoginBusy(true);
    setRoleError("");
    try {
      const res  = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? data.error?.message ?? "Login failed");
      onConnect(data.token, role);
    } catch (err: any) {
      setRoleError(err.message ?? "Role connection failed");
    } finally {
      setLoginBusy(false);
    }
  }

  return (
    <div className="landing">
      <div className="landing-ruler" aria-hidden="true">
        {DEPTH_TICKS.map((t) => (
          <div key={t.depth} className={`ruler-tick${t.major ? " major" : ""}`}>
            <span>{t.depth}</span>
          </div>
        ))}
      </div>

      <div className="landing-main">
        <div className="landing-hero">
          <p className="landing-plate">OIL · SIH Prototype · Nearby Wells Intelligence System</p>
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

          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px" }}>
            {ROLES.map((r) => (
              <button
                key={r.id}
                type="button"
                className="secondary"
                disabled={loading || loginBusy}
                onClick={() => handleRoleLogin(r.id)}
                style={{
                  display: "flex", flexDirection: "column", alignItems: "flex-start",
                  textAlign: "left", padding: "10px 14px", borderRadius: "var(--r-md)",
                  border: "1px solid var(--border)", background: "var(--slate-dark)", cursor: "pointer",
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
