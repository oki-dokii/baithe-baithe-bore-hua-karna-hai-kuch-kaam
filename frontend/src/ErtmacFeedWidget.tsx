import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

type ErtmacStatus = {
  status: string;
  active_wellbore_id: string | null;
  last_received_at: string | null;
  heartbeat_age_seconds: number | null;
  total_samples_received: number;
  source_mode: string;
};

type StreamResponse = {
  status: string;
  samples_processed: number;
  active_wellbore_id: string;
  hazard_forecast: {
    hazard_probabilities: Record<string, number>;
    highest_risk_hazard: string;
    highest_risk_level: string;
    recommended_mitigation: string;
    top_feature_attributions?: Record<string, number>;
  };
};

type WitsmlResponse = {
  status: string;
  wellbore_id: string;
  curves_ingested: string[];
  samples_count: number;
  min_md_m: number | null;
  max_md_m: number | null;
  hazard_forecast?: {
    hazard_probabilities: Record<string, number>;
    highest_risk_hazard: string;
    highest_risk_level: string;
    recommended_mitigation: string;
  };
};

export default function ErtmacFeedWidget({
  token,
  wellboreId,
  onStatusChange,
}: {
  token: string;
  wellboreId?: string;
  onStatusChange?: (isLive: boolean) => void;
}) {
  const [feedStatus, setFeedStatus] = useState<ErtmacStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [autoStreaming, setAutoStreaming] = useState(false);
  const [latestForecast, setLatestForecast] = useState<StreamResponse["hazard_forecast"] | null>(null);

  // Manual telemetry generator parameters
  const [currentMd, setCurrentMd] = useState(2145.0);
  const [rop, setRop] = useState(14.5);
  const [wob, setWob] = useState(115.0);
  const [rpm, setRpm] = useState(120.0);
  const [torque, setTorque] = useState(18.2);
  const [flow, setFlow] = useState(2600.0);
  const [mudWeight, setMudWeight] = useState(1180.0);
  const [totalGas, setTotalGas] = useState(0.55);

  // WITSML upload state
  const [witsmlFile, setWitsmlFile] = useState<File | null>(null);
  const [witsmlResult, setWitsmlResult] = useState<WitsmlResponse | null>(null);
  const [uploadingWitsml, setUploadingWitsml] = useState(false);

  const autoStreamInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/v1/ertmac/status", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data: ErtmacStatus = await res.json();
        setFeedStatus(data);
        if (onStatusChange) {
          onStatusChange(data.source_mode === "LIVE");
        }
      }
    } catch {
      // transient network error
    }
  };

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, 3000);
    return () => clearInterval(timer);
  }, [token]);

  const sendBatch = async (depth: number) => {
    setLoading(true);
    setError("");
    try {
      const sample = {
        observed_at: new Date().toISOString(),
        md_m: depth,
        tvd_m: depth * 0.985,
        rop_m_per_h: rop + (Math.random() * 2 - 1),
        weight_on_bit_kn: wob + (Math.random() * 6 - 3),
        rotary_rpm: rpm + (Math.random() * 4 - 2),
        torque_kn_m: torque + (Math.random() * 1.5 - 0.75),
        flow_rate_lpm: flow + (Math.random() * 50 - 25),
        mud_density_in_kg_m3: mudWeight,
        total_gas_pct: totalGas + (Math.random() * 0.1 - 0.05),
      };

      const res = await fetch("/api/v1/ertmac/stream", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          wellbore_id: wellboreId || feedStatus?.active_wellbore_id || null,
          samples: [sample],
        }),
      });

      const data: StreamResponse = await res.json();
      if (!res.ok) throw new Error((data as unknown as { error?: { message?: string } }).error?.message ?? "Stream push failed");

      setLatestForecast(data.hazard_forecast);
      await fetchStatus();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleManualPush = async (e: FormEvent) => {
    e.preventDefault();
    const nextDepth = currentMd + 0.5;
    setCurrentMd(nextDepth);
    await sendBatch(nextDepth);
  };

  const toggleAutoStream = () => {
    if (autoStreaming) {
      if (autoStreamInterval.current) clearInterval(autoStreamInterval.current);
      setAutoStreaming(false);
    } else {
      setAutoStreaming(true);
      autoStreamInterval.current = setInterval(() => {
        setCurrentMd((prev) => {
          const next = Number((prev + 0.3).toFixed(1));
          sendBatch(next);
          return next;
        });
      }, 2500);
    }
  };

  useEffect(() => {
    return () => {
      if (autoStreamInterval.current) clearInterval(autoStreamInterval.current);
    };
  }, []);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setWitsmlFile(e.target.files[0]);
    }
  };

  const handleUploadWitsml = async (e: FormEvent) => {
    e.preventDefault();
    if (!witsmlFile) return;
    setUploadingWitsml(true);
    setError("");
    setWitsmlResult(null);
    try {
      const formData = new FormData();
      formData.append("file", witsmlFile);
      if (wellboreId) formData.append("wellbore_id", wellboreId);

      const res = await fetch("/api/v1/ertmac/witsml-log", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      const data: WitsmlResponse = await res.json();
      if (!res.ok) throw new Error((data as unknown as { error?: { message?: string } }).error?.message ?? "WITSML ingestion failed");

      setWitsmlResult(data);
      if (data.hazard_forecast) {
        setLatestForecast(data.hazard_forecast);
      }
      await fetchStatus();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploadingWitsml(false);
    }
  };

  const isLive = feedStatus?.source_mode === "LIVE";

  return (
    <section
      className="explore-panel ertmac-widget"
      aria-label="Live eRTMAC real-time streaming feed and WITSML ingestion"
      style={{
        background: "rgba(11, 19, 30, 0.85)",
        border: isLive ? "1px solid rgba(72, 187, 120, 0.4)" : "1px solid rgba(120, 140, 160, 0.2)",
        borderRadius: "8px",
        padding: "18px",
        marginBottom: "20px",
        boxShadow: isLive ? "0 0 20px rgba(72, 187, 120, 0.1)" : "none",
        transition: "all 0.3s ease",
      }}
    >
      {/* Header & Status Indicator */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span
              style={{
                display: "inline-block",
                width: "10px",
                height: "10px",
                borderRadius: "50%",
                background: isLive ? "#48bb78" : "#ecc94b",
                boxShadow: isLive ? "0 0 10px #48bb78" : "none",
                animation: isLive ? "pulse-dot 1.5s infinite" : "none",
              }}
            />
            <h3 style={{ margin: 0, fontSize: "1.05rem", color: "#f1f5f9", fontWeight: 600 }}>
              OIL eRTMAC Live Feed & WITSML Adapter
            </h3>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: "4px",
                fontSize: "0.75rem",
                fontWeight: 700,
                letterSpacing: "0.05em",
                background: isLive ? "rgba(72, 187, 120, 0.2)" : "rgba(236, 201, 75, 0.2)",
                color: isLive ? "#68d391" : "#f6e05e",
                border: isLive ? "1px solid rgba(72, 187, 120, 0.4)" : "1px solid rgba(236, 201, 75, 0.4)",
              }}
            >
              {feedStatus?.source_mode ?? "SIMULATED"} MODE
            </span>
          </div>
          <p style={{ margin: "4px 0 0 0", fontSize: "0.8125rem", color: "#94a3b8" }}>
            Real-time drilling telemetry ingestion channel conforming to WITSML 1.3/1.4 standards and OIL eRTMAC schema.
          </p>
        </div>

        <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
          <div style={{ textAlign: "right", fontSize: "0.75rem", color: "#94a3b8", fontFamily: "var(--font-mono, monospace)" }}>
            <div>Packets Ingested: <strong style={{ color: "#fff" }}>{feedStatus?.total_samples_received ?? 0}</strong></div>
            <div>
              Heartbeat:{" "}
              <span style={{ color: isLive ? "#68d391" : "#a0aec0" }}>
                {feedStatus?.heartbeat_age_seconds != null ? `${feedStatus.heartbeat_age_seconds}s ago` : "Standby"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {error && <p className="error" role="alert" style={{ marginBottom: "12px" }}>{error}</p>}

      {/* Main Grid: Telemetry Push Generator + WITSML Uploader */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
        {/* Card 1: Live eRTMAC Streamer */}
        <div style={{ background: "rgba(16, 26, 40, 0.6)", borderRadius: "6px", padding: "14px", border: "1px solid rgba(120, 140, 160, 0.15)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <h4 style={{ margin: 0, fontSize: "0.875rem", color: "#38b2ac", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Live Rig Telemetry Stream
            </h4>
            <button
              onClick={toggleAutoStream}
              style={{
                padding: "3px 10px",
                borderRadius: "4px",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer",
                background: autoStreaming ? "rgba(229, 62, 62, 0.2)" : "rgba(56, 178, 172, 0.2)",
                color: autoStreaming ? "#fc8181" : "#38b2ac",
                border: autoStreaming ? "1px solid #e53e3e" : "1px solid #38b2ac",
              }}
            >
              {autoStreaming ? "⏹ Stop Auto-Stream" : "▶ Start Live Stream (2s)"}
            </button>
          </div>

          <form onSubmit={handleManualPush}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px", marginBottom: "8px" }}>
              <div>
                <label style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>Depth (m)</label>
                <input
                  type="number"
                  step="any"
                  value={currentMd}
                  onChange={(e) => setCurrentMd(Number(e.target.value))}
                  style={{ width: "100%", padding: "4px", fontSize: "0.75rem", background: "#0d131c", border: "1px solid #2d3748", color: "#fff", borderRadius: "3px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>ROP (m/h)</label>
                <input
                  type="number"
                  step="any"
                  value={rop}
                  onChange={(e) => setRop(Number(e.target.value))}
                  style={{ width: "100%", padding: "4px", fontSize: "0.75rem", background: "#0d131c", border: "1px solid #2d3748", color: "#fff", borderRadius: "3px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>WOB (kN)</label>
                <input
                  type="number"
                  step="any"
                  value={wob}
                  onChange={(e) => setWob(Number(e.target.value))}
                  style={{ width: "100%", padding: "4px", fontSize: "0.75rem", background: "#0d131c", border: "1px solid #2d3748", color: "#fff", borderRadius: "3px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>RPM</label>
                <input
                  type="number"
                  step="any"
                  value={rpm}
                  onChange={(e) => setRpm(Number(e.target.value))}
                  style={{ width: "100%", padding: "4px", fontSize: "0.75rem", background: "#0d131c", border: "1px solid #2d3748", color: "#fff", borderRadius: "3px" }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px", marginBottom: "10px" }}>
              <div>
                <label style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>Torque (kN·m)</label>
                <input
                  type="number"
                  step="any"
                  value={torque}
                  onChange={(e) => setTorque(Number(e.target.value))}
                  style={{ width: "100%", padding: "4px", fontSize: "0.75rem", background: "#0d131c", border: "1px solid #2d3748", color: "#fff", borderRadius: "3px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>Flow (L/m)</label>
                <input
                  type="number"
                  step="any"
                  value={flow}
                  onChange={(e) => setFlow(Number(e.target.value))}
                  style={{ width: "100%", padding: "4px", fontSize: "0.75rem", background: "#0d131c", border: "1px solid #2d3748", color: "#fff", borderRadius: "3px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>Mud (kg/m³)</label>
                <input
                  type="number"
                  step="any"
                  value={mudWeight}
                  onChange={(e) => setMudWeight(Number(e.target.value))}
                  style={{ width: "100%", padding: "4px", fontSize: "0.75rem", background: "#0d131c", border: "1px solid #2d3748", color: "#fff", borderRadius: "3px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block" }}>Gas (%)</label>
                <input
                  type="number"
                  step="any"
                  value={totalGas}
                  onChange={(e) => setTotalGas(Number(e.target.value))}
                  style={{ width: "100%", padding: "4px", fontSize: "0.75rem", background: "#0d131c", border: "1px solid #2d3748", color: "#fff", borderRadius: "3px" }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%",
                padding: "6px 12px",
                background: "var(--teal, #176a70)",
                border: "1px solid rgba(56, 178, 172, 0.4)",
                color: "#fff",
                borderRadius: "4px",
                fontSize: "0.8rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {loading ? "Streaming packet..." : "⚡ Push Single Telemetry Packet"}
            </button>
          </form>

          {/* Real-time ML Hazard Forecast */}
          {latestForecast && (
            <div style={{ marginTop: "12px", background: "rgba(10, 16, 26, 0.8)", padding: "10px", borderRadius: "4px", border: "1px solid rgba(120, 140, 160, 0.2)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.75rem", color: "#94a3b8", textTransform: "uppercase" }}>Real-Time ML Hazard Forecast</span>
                <span
                  style={{
                    fontSize: "0.7rem",
                    padding: "2px 6px",
                    borderRadius: "3px",
                    fontWeight: 700,
                    background: latestForecast.highest_risk_level === "high" || latestForecast.highest_risk_level === "critical" ? "rgba(229, 62, 62, 0.2)" : "rgba(237, 137, 54, 0.2)",
                    color: latestForecast.highest_risk_level === "high" || latestForecast.highest_risk_level === "critical" ? "#fc8181" : "#fbd38d",
                  }}
                >
                  {latestForecast.highest_risk_hazard.toUpperCase()}: {latestForecast.highest_risk_level.toUpperCase()}
                </span>
              </div>
              <div style={{ display: "flex", gap: "10px", marginTop: "6px", fontSize: "0.75rem", fontFamily: "var(--font-mono, monospace)" }}>
                {Object.entries(latestForecast.hazard_probabilities).map(([hazard, prob]) => (
                  <span key={hazard} style={{ color: prob > 0.3 ? "#fbd38d" : "#94a3b8" }}>
                    {hazard.split("_")[0]}: {(prob * 100).toFixed(0)}%
                  </span>
                ))}
              </div>
              <p style={{ margin: "6px 0 0 0", fontSize: "0.75rem", color: "#cbd5e0" }}>
                💡 <em>Mitigation:</em> {latestForecast.recommended_mitigation}
              </p>
            </div>
          )}
        </div>

        {/* Card 2: WITSML 1.3/1.4 XML Ingestion */}
        <div style={{ background: "rgba(16, 26, 40, 0.6)", borderRadius: "6px", padding: "14px", border: "1px solid rgba(120, 140, 160, 0.15)" }}>
          <h4 style={{ margin: "0 0 10px 0", fontSize: "0.875rem", color: "#4299e1", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            WITSML 1.3 / 1.4 XML File Ingestion
          </h4>
          <p style={{ margin: "0 0 12px 0", fontSize: "0.75rem", color: "#94a3b8" }}>
            Upload standard WITSML <code style={{ color: "#e2e8f0" }}>&lt;log&gt;</code> XML exports from mud logging units or rig servers.
          </p>

          <form onSubmit={handleUploadWitsml} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <input
              type="file"
              accept=".xml,.witsml"
              onChange={handleFileChange}
              style={{
                fontSize: "0.75rem",
                color: "#cbd5e0",
                background: "#0d131c",
                padding: "6px",
                borderRadius: "4px",
                border: "1px dashed #4a5568",
              }}
            />

            <button
              type="submit"
              disabled={!witsmlFile || uploadingWitsml}
              style={{
                padding: "6px 12px",
                background: witsmlFile ? "#2b6cb0" : "#2d3748",
                border: "none",
                color: "#fff",
                borderRadius: "4px",
                fontSize: "0.8rem",
                fontWeight: 600,
                cursor: witsmlFile ? "pointer" : "not-allowed",
              }}
            >
              {uploadingWitsml ? "Parsing XML Log..." : "📥 Ingest WITSML Log"}
            </button>
          </form>

          {witsmlResult && (
            <div style={{ marginTop: "12px", background: "rgba(10, 16, 26, 0.8)", padding: "10px", borderRadius: "4px", border: "1px solid rgba(72, 187, 120, 0.3)" }}>
              <div style={{ fontSize: "0.75rem", color: "#68d391", fontWeight: 600, marginBottom: "4px" }}>
                ✓ Ingested {witsmlResult.samples_count} Samples ({witsmlResult.min_md_m} – {witsmlResult.max_md_m} m MD)
              </div>
              <div style={{ fontSize: "0.7rem", color: "#94a3b8" }}>
                Curves: {witsmlResult.curves_ingested.join(", ")}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
