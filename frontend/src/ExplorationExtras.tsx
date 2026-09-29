import { FormEvent, useEffect, useRef, useState } from "react";
import "./exploration.css";

type DepthTrackData = {
  source_kind: string;
  intervals: { id: string; name: string; top_md_m: number; base_md_m: number | null; datum: string }[];
  events: { id: string; event_type: string; start_md_m: number | null; end_md_m: number | null; severity: string | null }[];
  parameters: { sample_id: string; md_m: number; rop_m_per_h: number; torque_kn_m: number }[];
  missing_lanes: string[];
  parameter_note: string;
};
type MudWindowData = {
  source_kind: string; state: string; truncated: boolean; notice: string;
  bands: {
    id: string; top_md_m: number; base_md_m: number; pore_pressure_ppg: number;
    fracture_gradient_ppg: number; mud_weight_ppg: number; ecd_ppg: number | null;
    pressure_filename: string; pressure_page: number; mud_filename: string; mud_page: number;
  }[];
};
type Link = {
  event_type: string;
  formation_name: string;
  mechanism: string;
  action_taken: string;
  effectiveness_counts: Record<string, number>;
  event_ids: string[];
};
type LinkResponse = { items: Link[]; source_kind: string; truncated: boolean; notice: string };
type SpecialOperations = { source_kind: string; truncated: boolean; notice: string; items: {
  event_type: string; sample_count: number; state: string; outcome_counts: Record<string, number>;
  cases: { event_id: string; formation_name: string; start_md_m: number | null; duration_h: number | null }[];
}[] };
type NptExposure = { source_kind: string; currency: string; assumed_rig_day_rate: string;
  notice: string; truncated: boolean; items: { npt_id: string; event_id: string; event_type: string;
  formation_name: string; duration_h: number; duration_source: string; illustrative_exposure: number }[] };
type AssamReference = { source_url: string; notice: string; items: { code: string; name: string; aliases: string[] }[] };
export type PlanningPoint = { latitude: number; longitude: number };
type Picture = {
  source_kind: string;
  radius_km: number;
  score_kind: string;
  notice: string;
  truncated: boolean;
  items: {
    wellbore_id: string;
    name: string;
    distance_m: number;
    hazard_counts: Record<string, number>;
    events_truncated: boolean;
    events: { id: string; event_type: string; formation_name: string | null; start_md_m: number | null }[];
  }[];
};

async function get<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...init?.headers },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message ?? `Request failed (${response.status})`);
  return data as T;
}

const human = (value: string) => value.replaceAll("_", " ");

export function MudWindow({ token, wellboreId }: { token: string; wellboreId: string }) {
  const [data, setData] = useState<MudWindowData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setData(null); setError("");
    get<MudWindowData>(token, `/wellbores/${wellboreId}/mud-window`)
      .then((value) => live && setData(value))
      .catch((cause) => live && setError(cause.message));
    return () => { live = false; };
  }, [token, wellboreId]);
  const bands = data?.bands ?? [];
  const mdMin = bands.length ? Math.min(...bands.map((band) => band.top_md_m)) : 1800;
  const mdMax = bands.length ? Math.max(...bands.map((band) => band.base_md_m)) : 2400;
  const ppgMin = bands.length ? Math.floor(Math.min(...bands.map((band) => band.pore_pressure_ppg)) - 1) : 8;
  const ppgMax = bands.length ? Math.ceil(Math.max(...bands.map((band) => Math.max(band.fracture_gradient_ppg, band.ecd_ppg ?? 0, band.mud_weight_ppg))) + 1) : 18;
  const x = (md: number) => 80 + ((md - mdMin) / Math.max(1, mdMax - mdMin)) * 800;
  const y = (ppg: number) => 226 - ((ppg - ppgMin) / Math.max(1, ppgMax - ppgMin)) * 180;
  return (
    <section className="explore-panel" aria-label="Cited pressure and mud-weight comparison">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Pressure record & mud window</p>
          <h2>Values with a paper trail.</h2>
        </div>
        <span>MD · metres / ppg</span>
      </div>
      <p className="footnote">
        {data?.notice ?? "Only independently approved, cited values appear here. This is not a safe operating window."}
      </p>
      {error && <p role="alert" className="error">{error}</p>}
      {!data && !error && <p role="status">Loading cited pressure records…</p>}
      {data && (
        <>
          <div className="mud-legend">
            <span className="mud-pore">Pore pressure</span>
            <span className="mud-frac">Fracture gradient</span>
            <span className="mud-weight">Recorded mud weight</span>
            <span className="mud-ecd">Recorded ECD, if reviewed</span>
          </div>
          <div className="depth-track-scroll">
            <svg viewBox="0 0 920 270" role="img" aria-label="Cited historical pressure and mud-weight values by measured-depth band; not an operating recommendation">
              {[0, 0.25, 0.5, 0.75, 1].map((fraction) => (
                <g key={fraction}>
                  <line className="track-grid" x1="80" x2="880" y1={226 - fraction * 180} y2={226 - fraction * 180} />
                  <text className="track-label" x="40" y={230 - fraction * 180}>
                    {(ppgMin + fraction * (ppgMax - ppgMin)).toFixed(1)}
                  </text>
                </g>
              ))}
              {bands.length > 0 ? (
                bands.map((band) => (
                  <g key={band.id}>
                    <rect
                      className="mud-envelope"
                      x={x(band.top_md_m)}
                      y={y(band.fracture_gradient_ppg)}
                      width={Math.max(2, x(band.base_md_m) - x(band.top_md_m))}
                      height={y(band.pore_pressure_ppg) - y(band.fracture_gradient_ppg)}
                    />
                    <line className="mud-pore-line" x1={x(band.top_md_m)} x2={x(band.base_md_m)} y1={y(band.pore_pressure_ppg)} y2={y(band.pore_pressure_ppg)} />
                    <line className="mud-frac-line" x1={x(band.top_md_m)} x2={x(band.base_md_m)} y1={y(band.fracture_gradient_ppg)} y2={y(band.fracture_gradient_ppg)} />
                    <line className="mud-weight-line" x1={x(band.top_md_m)} x2={x(band.base_md_m)} y1={y(band.mud_weight_ppg)} y2={y(band.mud_weight_ppg)} />
                    {band.ecd_ppg != null && <line className="mud-ecd-line" x1={x(band.top_md_m)} x2={x(band.base_md_m)} y1={y(band.ecd_ppg)} y2={y(band.ecd_ppg)} />}
                    <title>{`${band.top_md_m}–${band.base_md_m} m MD · pore ${band.pore_pressure_ppg}, fracture ${band.fracture_gradient_ppg}, mud ${band.mud_weight_ppg}, ECD ${band.ecd_ppg ?? "unavailable"} ppg · pressure: ${band.pressure_filename} p.${band.pressure_page}; mud: ${band.mud_filename} p.${band.mud_page}`}</title>
                  </g>
                ))
              ) : (
                <g>
                  <rect x="180" y="80" width="560" height="90" rx="8" fill="rgba(15, 23, 42, 0.85)" stroke="rgba(120, 140, 160, 0.3)" strokeDasharray="4 4" />
                  <text x="460" y="118" textAnchor="middle" fill="#94a3b8" fontSize="13" fontWeight="600" fontFamily="var(--font-mono)">
                    NO REVIEWED PRESSURE BANDS FOR THIS WELLBORE
                  </text>
                  <text x="460" y="142" textAnchor="middle" fill="#64748b" fontSize="11" fontFamily="var(--font-sans)">
                    No pore pressure or fracture gradient envelope is inferred without independently reviewed WCR/DDR records.
                  </text>
                </g>
              )}
              <text className="track-label" x="80" y="255">{mdMin.toFixed(0)} m MD</text>
              <text className="track-label" x="880" y="255" textAnchor="end">{mdMax.toFixed(0)} m MD</text>
            </svg>
          </div>
          <p className="footnote">
            {data.source_kind.toUpperCase()} source · {bands.length} reviewed band{bands.length === 1 ? "" : "s"}.
            {bands.length > 0 ? " Hover each band for exact values and source pages." : " Envelope is intentionally not extrapolated from unverified data."}
            {data.truncated ? " First 200 bands only." : ""}
          </p>
        </>
      )}
    </section>
  );
}

export function DepthTrack({ token, wellboreId, onOpenCase }: {
  token: string; wellboreId: string; onOpenCase: (id: string) => void;
}) {
  const [data, setData] = useState<DepthTrackData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setData(null);
    get<DepthTrackData>(token, `/wellbores/${wellboreId}/depth-track`)
      .then((value) => live && setData(value))
      .catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [token, wellboreId]);

  const rawDepths = data ? [
    ...data.intervals.flatMap((item) => [item.top_md_m, item.base_md_m ?? item.top_md_m]),
    ...data.events.flatMap((item) => [item.start_md_m ?? 0, item.end_md_m ?? item.start_md_m ?? 0]),
    ...data.parameters.map((item) => item.md_m),
  ].filter((value) => value > 0) : [];

  const rawMin = rawDepths.length ? Math.min(...rawDepths) : 1800;
  const rawMax = rawDepths.length ? Math.max(...rawDepths) : 2400;
  const pad = Math.max(80, (rawMax - rawMin) * 0.15);
  const min = Math.max(0, Math.floor((rawMin - pad) / 50) * 50);
  const max = Math.ceil((rawMax + pad) / 50) * 50 + 1;
  const x = (md: number) => 130 + ((md - min) / Math.max(1, max - min)) * 750;

  const paramLine = (field: "rop_m_per_h" | "torque_kn_m", top: number) => {
    if (!data?.parameters.length) return "";
    const values = data.parameters.map((row) => row[field]);
    const highest = Math.max(...values, 1);
    return data.parameters.map((row, index) =>
      `${index ? "L" : "M"}${x(row.md_m).toFixed(1)},${(top + 42 - (row[field] / highest) * 34).toFixed(1)}`
    ).join(" ");
  };

  return (
    <section className="explore-panel" aria-label="Synchronized measured-depth track">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Depth register & multi-lane log</p>
          <h2>One ruler, several stories.</h2>
        </div>
        <span>MD · metres</span>
      </div>
      {error && <p role="alert" className="error">{error}</p>}
      {!data && !error && <p role="status">Loading depth evidence…</p>}
      {data && !rawDepths.length && (
        <p className="notice">No reviewed depth intervals or qualified parameter samples are available for this wellbore.</p>
      )}
      {data && !!rawDepths.length && (
        <div className="depth-track-scroll">
          <svg viewBox="0 0 920 290" role="img" aria-label="Formation, incident, rate of penetration and torque lanes aligned by measured depth">
            {/* Vertical grid lines & depth labels */}
            {[0, 0.2, 0.4, 0.6, 0.8, 1].map((fraction) => {
              const xPos = 130 + fraction * 750;
              const mdVal = min + fraction * (max - min);
              return (
                <g key={fraction}>
                  <line x1={xPos} x2={xPos} y1="28" y2="265" className="track-grid" />
                  <text x={xPos} y="18" textAnchor="middle" className="track-label">
                    {mdVal.toFixed(0)}m
                  </text>
                  <text x={xPos} y="280" textAnchor="middle" className="track-label">
                    {mdVal.toFixed(0)}m
                  </text>
                </g>
              );
            })}

            {/* Lane headers & horizontal dividers */}
            {[
              ["Formation", 45],
              ["Incident", 102],
              ["ROP (m/h)", 158],
              ["Torque (kN·m)", 214],
            ].map(([name, yPos]) => (
              <g key={name}>
                <rect x="6" y={Number(yPos)} width="114" height="42" rx="4" fill="rgba(17, 24, 39, 0.6)" />
                <text x="14" y={Number(yPos) + 26} className="track-lane">
                  {name}
                </text>
                <line x1="126" x2="885" y1={Number(yPos) + 45} y2={Number(yPos) + 45} className="track-grid" />
              </g>
            ))}

            {/* Formation intervals */}
            {data.intervals.filter((item) => item.base_md_m != null).map((item) => {
              const startX = x(item.top_md_m);
              const endX = x(item.base_md_m!);
              const width = Math.max(6, endX - startX);
              return (
                <g key={item.id}>
                  {/* Vertical boundary lines down through all lanes */}
                  <line x1={startX} x2={startX} y1="45" y2="260" stroke="#38b2ac" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />
                  <line x1={endX} x2={endX} y1="45" y2="260" stroke="#38b2ac" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />
                  {/* Formation block */}
                  <rect x={startX} y="49" width={width} height="36" className="track-formation" rx="4" />
                  <text
                    x={startX + width / 2}
                    y="72"
                    textAnchor="middle"
                    fill="#e6fffa"
                    fontFamily="var(--font-mono)"
                    fontSize="12"
                    fontWeight="700"
                    style={{ pointerEvents: "none" }}
                  >
                    {item.name} · {item.top_md_m}–{item.base_md_m}m MD
                  </text>
                  <title>{item.name} · {item.top_md_m}–{item.base_md_m} m MD · Datum: {item.datum}</title>
                </g>
              );
            })}

            {/* Incident markers */}
            {data.events.length === 0 && (
              <text x="500" y="128" textAnchor="middle" fill="#64748b" fontSize="11" fontFamily="var(--font-mono)">
                No approved historical incidents recorded in this interval
              </text>
            )}
            {data.events.filter((item) => item.start_md_m != null).map((item) => (
              <g
                key={item.id}
                role="button"
                tabIndex={0}
                onClick={() => onOpenCase(item.id)}
                onKeyDown={(e) => e.key === "Enter" && onOpenCase(item.id)}
                style={{ cursor: "pointer" }}
              >
                <circle cx={x(item.start_md_m!)} cy="123" r="10" className="track-event" />
                <text x={x(item.start_md_m!)} y="127" textAnchor="middle" fill="#fff" fontSize="10" fontWeight="bold">!</text>
                <title>{human(item.event_type)} · {item.start_md_m} m MD · Click to inspect case</title>
              </g>
            ))}

            {/* Parameters (ROP & Torque curves) */}
            {data.parameters.length > 0 ? (
              <>
                <path d={paramLine("rop_m_per_h", 158)} className="track-rop" />
                <path d={paramLine("torque_kn_m", 214)} className="track-torque" />
              </>
            ) : (
              <>
                <text x="500" y="184" textAnchor="middle" fill="#64748b" fontSize="11" fontFamily="var(--font-mono)">
                  No approved ROP parameter channel for this fixture
                </text>
                <text x="500" y="240" textAnchor="middle" fill="#64748b" fontSize="11" fontFamily="var(--font-mono)">
                  No approved Torque parameter channel for this fixture
                </text>
              </>
            )}
          </svg>
        </div>
      )}
      {data && (
        <p className="footnote">
          {data.source_kind.toUpperCase()} source · formations and incidents are reviewed; parameters are qualified historical samples.{" "}
          {data.parameter_note} Missing lanes: {data.missing_lanes.map(human).join(", ")}. Hover marks for details; click an incident icon to open its cited case.
        </p>
      )}
    </section>
  );
}

export function MitigationGraph({ token, datasetId, onOpenCase }: {
  token: string; datasetId: string; onOpenCase: (id: string) => void;
}) {
  const [data, setData] = useState<LinkResponse | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setData(null);
    get<LinkResponse>(token, `/knowledge/mitigation-links?dataset_id=${datasetId}`)
      .then((value) => live && setData(value))
      .catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [token, datasetId]);
  return <section className="explore-panel" aria-label="Historical response links">
    <div className="section-heading"><div><p className="eyebrow">Response network</p><h2>What was tried, and what was reported?</h2></div><span>{data?.source_kind ?? "—"}</span></div>
    <p className="footnote">A linked observation is not proof of cure. Grouping preserves formation and recorded mechanism; unknown effectiveness stays visible.</p>
    {error && <p role="alert" className="error">{error}</p>}
    {!data && !error && <p role="status">Loading reviewed response links…</p>}
    {data && !data.items.length && <p className="notice">No approved event has a linked recorded mitigation in this dataset.</p>}
    {data?.items.map((item, index) => <div className="response-link" key={`${item.event_type}-${item.formation_name}-${item.mechanism}-${item.action_taken}-${index}`}>
      <div><small>EVENT / FORMATION</small><strong>{human(item.event_type)}</strong><span>{item.formation_name} · {item.mechanism}</span></div>
      <span className="response-arrow" aria-hidden="true">→</span>
      <div><small>REPORTED RESPONSE</small><strong>{item.action_taken}</strong></div>
      <span className="response-arrow" aria-hidden="true">→</span>
      <div><small>RECORDED EFFECTIVENESS</small>{Object.entries(item.effectiveness_counts).map(([status, count]) => <span key={status}>{human(status)} · {count}</span>)}<button className="text-button" onClick={() => onOpenCase(item.event_ids[0])}>Inspect cited case →</button></div>
    </div>)}
    {data?.truncated && <p className="notice">First 500 cited response rows only; narrow the dataset before interpreting counts.</p>}
  </section>;
}

export function OperationalEvidence({ token, datasetId, onOpenCase }: {
  token: string; datasetId: string; onOpenCase: (id: string) => void;
}) {
  const [special, setSpecial] = useState<SpecialOperations | null>(null);
  const [reference, setReference] = useState<AssamReference | null>(null);
  const [exposure, setExposure] = useState<NptExposure | null>(null);
  const [rate, setRate] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setSpecial(null); setExposure(null); setError("");
    get<SpecialOperations>(token, `/knowledge/special-operations?dataset_id=${datasetId}`)
      .then((value) => { if (live) setSpecial(value); })
      .catch((cause) => { if (live) setError(cause.message); });
    get<AssamReference>(token, "/reference/assam-formations")
      .then((value) => { if (live) setReference(value); })
      .catch((cause) => { if (live) setError(cause.message); });
    return () => { live = false; };
  }, [token, datasetId]);
  async function calculate(event: FormEvent) {
    event.preventDefault(); setError(""); setExposure(null);
    try {
      const result = await get<NptExposure>(token, "/knowledge/npt-exposure", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_id: datasetId, rig_day_rate: rate, currency }),
      });
      setExposure(result);
    } catch (cause) { setError((cause as Error).message); }
  }
  return <section className="explore-panel" aria-label="Special operations and illustrative NPT exposure">
    <div className="section-heading"><div><p className="eyebrow">Operations ledger</p><h2>What the cited record actually says.</h2></div><span>{special?.source_kind ?? "—"}</span></div>
    <p className="footnote">Fishing and cementing are shown only from approved, cited events. A small sample is marked insufficient, not turned into a success rate.</p>
    {error && <p role="alert" className="error">{error}</p>}
    {!special && !error && <p role="status">Loading reviewed operations…</p>}
    <div className="operations-grid">{special?.items.map((group) => <article key={group.event_type}>
      <small>{human(group.event_type).toUpperCase()}</small>
      <h3>{group.sample_count} cited {group.sample_count === 1 ? "case" : "cases"}</h3>
      {group.state === "insufficient" ? <p>Insufficient (n={group.sample_count}); outcome distribution withheld.</p>
        : <p>{Object.entries(group.outcome_counts).map(([outcome, count]) => `${human(outcome)} ${count}`).join(" · ")}</p>}
      {group.cases.slice(0, 12).map((item) => <button key={item.event_id} className="text-button" onClick={() => onOpenCase(item.event_id)}>
        {item.formation_name} · {item.start_md_m ?? "?"} m MD{item.duration_h != null ? ` · ${item.duration_h} h` : ""} ↗
      </button>)}
      {group.cases.length > 12 && <p className="footnote">First 12 cases shown here.</p>}
    </article>)}</div>
    {special?.truncated && <p className="notice">Results capped at 200 events; counts are incomplete.</p>}
    <div className="operations-divider" />
    <div className="section-heading"><div><p className="eyebrow">Assumption desk</p><h2>Illustrative NPT exposure.</h2></div><span>No OIL rate assumed</span></div>
    <p className="footnote">Enter your own rig-day rate. Each cited duration is calculated separately; overlapping episodes are not summed, and these figures are not proven savings.</p>
    <form className="planning-controls" onSubmit={calculate}>
      <label>Rig-day rate <input aria-label="Assumed rig-day rate" type="number" min="0.01" max="999999999999.99" step="0.01" required value={rate} onChange={(e) => { setRate(e.target.value); setExposure(null); }} /></label>
      <label>Currency <select aria-label="Currency" value={currency} onChange={(e) => { setCurrency(e.target.value); setExposure(null); }}><option>INR</option><option>USD</option></select></label>
      <button>Calculate per episode →</button>
    </form>
    {exposure && <div className="operations-grid">{exposure.items.length ? exposure.items.map((item) => <article key={item.npt_id}>
      <small>{human(item.event_type).toUpperCase()} / {item.formation_name}</small>
      <h3>{new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(item.illustrative_exposure)} {exposure.currency}</h3>
      <p>{item.duration_h} h · {human(item.duration_source)} duration</p>
      <button className="text-button" onClick={() => onOpenCase(item.event_id)}>Inspect cited case →</button>
    </article>) : <p className="notice">No approved cited event with a recorded NPT duration.</p>}
      {exposure.truncated && <p className="notice">First 200 events only; no dataset total is calculated.</p>}
    </div>}
    {exposure && <p className="footnote">{exposure.notice}</p>}
    {reference && <details className="formation-reference"><summary>Upper Assam formation name reference</summary>
      <p>{reference.notice} These names are not hazard or depth claims.</p>
      <div className="operations-grid">{reference.items.map((item) => <article key={item.code}>
        <strong>{item.name}</strong><p>Exact-name forms: {item.aliases.join(" · ")}</p>
      </article>)}</div>
      <a href={reference.source_url} target="_blank" rel="noreferrer">Oil India regional source ↗</a>
    </details>}
  </section>;
}

export function PlanningPanel({ token, datasetId, point, radius, formationId, onOpenCase }: {
  token: string; datasetId: string; point: PlanningPoint | null; radius: number;
  formationId: string | null; onOpenCase: (id: string) => void;
}) {
  const [picture, setPicture] = useState<Picture | null>(null);
  const [sameFormation, setSameFormation] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const requestVersion = useRef(0);
  useEffect(() => { requestVersion.current += 1; setPicture(null); setBusy(false); }, [point, datasetId, radius, formationId]);
  async function inspect(event?: FormEvent) {
    event?.preventDefault();
    if (!point) return;
    setBusy(true); setError(""); setPicture(null);
    const version = ++requestVersion.current;
    try {
      const data = await get<Picture>(token, "/planning/offset-picture", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_id: datasetId, ...point, radius_km: radius,
          formation_id: sameFormation ? formationId : null,
          min_md_m: from === "" ? null : Number(from), max_md_m: to === "" ? null : Number(to) }),
      });
      if (requestVersion.current === version) setPicture(data);
    } catch (e) { if (requestVersion.current === version) setError((e as Error).message); }
    finally { if (requestVersion.current === version) setBusy(false); }
  }
  return <section className="explore-panel planning-panel" aria-label="Hypothetical location planning view">
    <div className="section-heading"><div><p className="eyebrow">Planning desk</p><h2>Move the pin. Read the record.</h2></div><span>Location scenario only</span></div>
    <p>Click a point on the map. The same approved archive is searched around that location; no drilling parameters are simulated.</p>
    <form onSubmit={inspect} className="planning-controls">
      <span className="mono">{point ? `${point.latitude.toFixed(4)}° N · ${point.longitude.toFixed(4)}° E` : "No point selected"}</span>
      <label><input type="checkbox" checked={sameFormation} disabled={!formationId} onChange={(e) => setSameFormation(e.target.checked)}/> Selected formation only</label>
      <label>MD from <input type="number" min="0" step="any" value={from} onChange={(e) => setFrom(e.target.value)}/></label>
      <label>MD to <input type="number" min="0" step="any" value={to} onChange={(e) => setTo(e.target.value)}/></label>
      <button disabled={!point || busy}>{busy ? "Inspecting…" : "Inspect this point →"}</button>
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    {picture && <><p className="footnote">{picture.notice} {picture.source_kind.toUpperCase()} source · {picture.radius_km} km radius.</p>
      {picture.items.length ? <div className="planning-results">{picture.items.map((well) => <article key={well.wellbore_id}><div><strong>{well.name}</strong><span>{(well.distance_m / 1000).toFixed(2)} km</span></div><p>{Object.entries(well.hazard_counts).length ? Object.entries(well.hazard_counts).map(([hazard, count]) => `${human(hazard)} ${count}`).join(" · ") : "No approved cited hazards under these filters"}</p>{well.events.map((item) => <button key={item.id} className="text-button" onClick={() => onOpenCase(item.id)}>{human(item.event_type)} · {item.formation_name ?? "formation unknown"} · {item.start_md_m ?? "?"} m MD ↗</button>)}{well.events_truncated && <small>Events truncated</small>}</article>)}</div> : <p className="notice">No mapped wells are in this radius. This is not a risk-free finding.</p>}
      {picture.truncated && <p className="notice">First 100 wellbores only.</p>}
    </>}
  </section>;
}
