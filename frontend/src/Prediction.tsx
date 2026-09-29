import { useEffect, useState } from "react";
import TelemetryDossier from "./TelemetryDossier";

type Readiness = {
  hazard: string;
  horizon_m: number;
  state: string;
  gates: string[];
  features: string[];
  note: string;
  inventory_note: string;
  historical_inventory: {
    kind: string;
    approved_events: number;
    physical_wells: number;
  }[];
};

export default function Prediction({ token }: { token: string }) {
  const [data, setData] = useState<Readiness | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/prediction/readiness", {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load model readiness");
        const result = await response.json();
        if (!controller.signal.aborted) setData(result);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [token]);

  return (
    <div className="workspace">
      <div className="workspace-header">
        <div>
          <p className="ws-eyebrow"><span className="plate-num">05</span> Evaluate</p>
          <h1 className="ws-title">Evidence before confidence.</h1>
          <p className="ws-desc">A model must earn its place beside the historical record.</p>
        </div>
        <span className="badge badge-error">NO TRAINED MODEL</span>
      </div>

      <div className="workspace-body">
        {error && <div className="error-msg" role="alert">{error}</div>}
        {!data && !error && (
          <div className="notice" role="status">Loading model readiness assessment…</div>
        )}

        {data && (
          <>
            <div className="metric-grid">
              <div className="metric-card">
                <span className="metric-label">Research target</span>
                <div className="metric-value" style={{ fontSize: "1.2rem" }}>Mud loss</div>
                <span className="metric-sub">Next {data.horizon_m} m forward-drilling horizon</span>
                <span className="badge badge-error" style={{ marginTop: "8px", alignSelf: "flex-start" }}>Not validated</span>
              </div>

              <div className="metric-card">
                <span className="metric-label">Risk score</span>
                <div className="metric-value" style={{ color: "var(--text-muted)" }}>—</div>
                <span className="metric-sub">Unavailable · no trained model</span>
              </div>

              <div className="metric-card">
                <span className="metric-label">Held-out metrics</span>
                <div className="metric-value" style={{ color: "var(--text-muted)" }}>—</div>
                <span className="metric-sub">Calibration not evaluated</span>
              </div>

              {data.historical_inventory.map((row) => (
                <div className="metric-card" key={row.kind}>
                  <span className="metric-label">{row.kind}</span>
                  <div className="metric-value">{row.approved_events}</div>
                  <span className="metric-sub">Reviewed mud-loss events · {row.physical_wells} physical wells</span>
                </div>
              ))}
            </div>

            <div className="card">
              <div className="card-header">
                <span className="card-title">Archive capability</span>
              </div>
              <div className="card-body">
                <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.65, marginBottom: "12px" }}>
                  {data.inventory_note}
                </p>
                <p className="mono-sm" style={{ lineHeight: 1.6 }}>
                  Required next: permitted telemetry, reviewed event onsets,
                  complete no-event observation windows, original well identities,
                  units, and source provenance.
                </p>
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <span className="card-title">Qualification gates</span>
                <span className="mono-sm">Must pass before first score</span>
              </div>
              <div className="card-body">
                <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.65, marginBottom: "14px" }}>{data.note}</p>
                <ol style={{ paddingLeft: "16px", display: "flex", flexDirection: "column", gap: "8px" }}>
                  {data.gates.map((gate) => (
                    <li key={gate} style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                      {gate}
                    </li>
                  ))}
                </ol>

                <details style={{ marginTop: "12px" }}>
                  <summary>Proposed feature contract ({data.features.length} features)</summary>
                  <ul style={{ paddingLeft: "16px", paddingTop: "10px", display: "flex", flexDirection: "column", gap: "6px" }}>
                    {data.features.map((feat) => (
                      <li key={feat} className="mono-sm" style={{ lineHeight: 1.5 }}>
                        {feat.replaceAll("_", " ")}
                      </li>
                    ))}
                  </ul>
                  <p className="mono-sm" style={{ marginTop: "10px", lineHeight: 1.6, color: "var(--ochre)" }}>
                    Only pre-anchor values; no outcome text or future measurements.
                    Suitability still requires domain review.
                  </p>
                </details>
              </div>
            </div>

            <div className="notice">
              Acknowledgments and "no incident observed" feedback are not ground-truth labels.
              No ML probability or drilling recommendation is available.
            </div>
          </>
        )}

        <TelemetryDossier token={token} />
      </div>
    </div>
  );
}
