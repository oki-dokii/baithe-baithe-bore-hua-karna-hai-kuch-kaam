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
  const mdMin = bands.length ? Math.min(...bands.map((band) => band.top_md_m)) : 0;
  const mdMax = bands.length ? Math.max(...bands.map((band) => band.base_md_m)) : 1;
  const ppgMin = bands.length ? Math.floor(Math.min(...bands.map((band) => band.pore_pressure_ppg)) - 1) : 0;
  const ppgMax = bands.length ? Math.ceil(Math.max(...bands.map((band) => Math.max(band.fracture_gradient_ppg, band.ecd_ppg ?? 0, band.mud_weight_ppg))) + 1) : 1;
  const x = (md: number) => 80 + ((md - mdMin) / Math.max(1, mdMax - mdMin)) * 800;
  const y = (ppg: number) => 226 - ((ppg - ppgMin) / Math.max(1, ppgMax - ppgMin)) * 180;
  return <section className="explore-panel" aria-label="Cited pressure and mud-weight comparison">
    <div className="section-heading"><div><p className="eyebrow">Pressure record</p><h2>Values with a paper trail.</h2></div><span>MD · metres / ppg</span></div>
    <p className="footnote">{data?.notice ?? "Only independently approved, cited values appear here. This is not a safe operating window."}</p>
    {error && <p role="alert" className="error">{error}</p>}
    {!data && !error && <p role="status">Loading cited pressure records…</p>}
    {data && !bands.length && <p className="notice">No independently reviewed pressure and mud-weight band is available for this wellbore. No envelope is inferred.</p>}
    {!!bands.length && <><div className="mud-legend"><span className="mud-pore">Pore pressure</span><span className="mud-frac">Fracture gradient</span><span className="mud-weight">Recorded mud weight</span><span className="mud-ecd">Recorded ECD, if reviewed</span></div>
      <div className="depth-track-scroll"><svg viewBox="0 0 920 270" role="img" aria-label="Cited historical pressure and mud-weight values by measured-depth band; not an operating recommendation">
        {[0, .25, .5, .75, 1].map((fraction) => <g key={fraction}><line className="track-grid" x1="80" x2="880" y1={226 - fraction * 180} y2={226 - fraction * 180}/><text className="track-label" x="40" y={230 - fraction * 180}>{(ppgMin + fraction * (ppgMax - ppgMin)).toFixed(1)}</text></g>)}
        {bands.map((band) => <g key={band.id}><rect className="mud-envelope" x={x(band.top_md_m)} y={y(band.fracture_gradient_ppg)} width={Math.max(2, x(band.base_md_m) - x(band.top_md_m))} height={y(band.pore_pressure_ppg) - y(band.fracture_gradient_ppg)}/>
          <line className="mud-pore-line" x1={x(band.top_md_m)} x2={x(band.base_md_m)} y1={y(band.pore_pressure_ppg)} y2={y(band.pore_pressure_ppg)}/>
          <line className="mud-frac-line" x1={x(band.top_md_m)} x2={x(band.base_md_m)} y1={y(band.fracture_gradient_ppg)} y2={y(band.fracture_gradient_ppg)}/>
          <line className="mud-weight-line" x1={x(band.top_md_m)} x2={x(band.base_md_m)} y1={y(band.mud_weight_ppg)} y2={y(band.mud_weight_ppg)}/>
          {band.ecd_ppg != null && <line className="mud-ecd-line" x1={x(band.top_md_m)} x2={x(band.base_md_m)} y1={y(band.ecd_ppg)} y2={y(band.ecd_ppg)}/>}
          <title>{`${band.top_md_m}–${band.base_md_m} m MD · pore ${band.pore_pressure_ppg}, fracture ${band.fracture_gradient_ppg}, mud ${band.mud_weight_ppg}, ECD ${band.ecd_ppg ?? "unavailable"} ppg · pressure: ${band.pressure_filename} p.${band.pressure_page}; mud: ${band.mud_filename} p.${band.mud_page}`}</title>
        </g>)}
        <text className="track-label" x="80" y="250">{mdMin.toFixed(0)} m MD</text><text className="track-label" x="880" y="250" textAnchor="end">{mdMax.toFixed(0)} m MD</text>
      </svg></div><p className="footnote">{data?.source_kind.toUpperCase()} source · {bands.length} reviewed band{bands.length === 1 ? "" : "s"}. Hover each band for exact values and source pages.{data?.truncated ? " First 200 bands only." : ""}</p></>}
  </section>;
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
  const depths = data ? [
    ...data.intervals.flatMap((item) => [item.top_md_m, item.base_md_m ?? item.top_md_m]),
    ...data.events.flatMap((item) => [item.start_md_m ?? 0, item.end_md_m ?? item.start_md_m ?? 0]),
    ...data.parameters.map((item) => item.md_m),
  ].filter((value) => value > 0) : [];
  const min = depths.length ? Math.floor(Math.min(...depths) / 50) * 50 : 0;
  const max = depths.length ? Math.ceil(Math.max(...depths) / 50) * 50 + 1 : 1;
  const x = (md: number) => 122 + ((md - min) / (max - min)) * 768;
  const paramLine = (field: "rop_m_per_h" | "torque_kn_m", top: number) => {
    if (!data?.parameters.length) return "";
    const values = data.parameters.map((row) => row[field]);
    const highest = Math.max(...values, 1);
    return data.parameters.map((row, index) =>
      `${index ? "L" : "M"}${x(row.md_m).toFixed(1)},${(top + 42 - row[field] / highest * 34).toFixed(1)}`
    ).join(" ");
  };
  return (
    <section className="explore-panel" aria-label="Synchronized measured-depth track">
      <div className="section-heading"><div><p className="eyebrow">Depth register</p><h2>One ruler, several stories.</h2></div><span>MD · metres</span></div>
      {error && <p role="alert" className="error">{error}</p>}
      {!data && !error && <p role="status">Loading depth evidence…</p>}
      {data && !depths.length && <p className="notice">No reviewed depth intervals or qualified parameter samples are available for this wellbore.</p>}
      {data && !!depths.length && <div className="depth-track-scroll"><svg viewBox="0 0 920 280" role="img" aria-label="Formation, incident, rate of penetration and torque lanes aligned by measured depth">
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => <g key={fraction}><line x1={122 + fraction * 768} x2={122 + fraction * 768} y1="29" y2="258" className="track-grid"/><text x={122 + fraction * 768} y="17" textAnchor="middle" className="track-label">{(min + fraction * (max - min)).toFixed(0)}</text></g>)}
        {[["Formation", 45], ["Incident", 100], ["ROP", 155], ["Torque", 210]].map(([name, y]) => <g key={name}><text x="8" y={Number(y) + 19} className="track-lane">{name}</text><line x1="122" x2="890" y1={Number(y) + 48} y2={Number(y) + 48} className="track-grid"/></g>)}
        {data.intervals.filter((item) => item.base_md_m != null).map((item) => <g key={item.id}><rect x={x(item.top_md_m)} y="49" width={Math.max(2, x(item.base_md_m!) - x(item.top_md_m))} height="34" className="track-formation"/><title>{item.name} · {item.top_md_m}–{item.base_md_m} m MD · {item.datum}</title></g>)}
        {data.events.filter((item) => item.start_md_m != null).map((item) => <g key={item.id} role="button" tabIndex={0} onClick={() => onOpenCase(item.id)} onKeyDown={(e) => e.key === "Enter" && onOpenCase(item.id)}><circle cx={x(item.start_md_m!)} cy="117" r="8" className="track-event"/><title>{human(item.event_type)} · {item.start_md_m} m MD · open case</title></g>)}
        {!!data.parameters.length && <><path d={paramLine("rop_m_per_h", 155)} className="track-rop"/><path d={paramLine("torque_kn_m", 210)} className="track-torque"/></>}
      </svg></div>}
      {data && <p className="footnote">{data.source_kind.toUpperCase()} source · formations and incidents are reviewed; parameters are qualified historical samples. {data.parameter_note} Missing lanes: {data.missing_lanes.map(human).join(", ")}. Hover marks for details; select an incident to open its cited case.</p>}
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
