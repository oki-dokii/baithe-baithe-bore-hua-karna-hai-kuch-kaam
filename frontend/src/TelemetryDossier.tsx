import { useEffect, useState } from "react";

type Source = {
  id: string; external_id: string; dataset_name: string; data_kind: string;
  qualification_state: string; dataset_qualification_state?: string;
  source_kind: string; source_sha256?: string; mapping_version?: string;
  units_reviewed?: boolean; timezone_reviewed?: boolean; datum_reviewed?: boolean;
  rig_state_reviewed?: boolean;
};
type BoreScreen = {
  wellbore_id: string; decision: string; blockers: string[]; current_rows: number;
  duration_minutes: number; good_complete_fraction: number;
  active_drilling_fraction: number; measured_depth_advance_m: number;
  rop_min_max: (number | null)[]; wob_min_max: (number | null)[];
  largest_gap_minutes: number; quality_counts: Record<string, number>;
  rig_state_counts: Record<string, number>;
};
type Dossier = {
  source: Source; record_counts: { stored_revisions: number; distinct_records: number };
  screen: { screen_version: string; decision: string; wellbores: BoreScreen[]; thresholds: Record<string, number> } | null;
  dossier_state: string; notice: string;
};
const label = (value: string) => value.replaceAll("_", " ");

export default function TelemetryDossier({ token }: { token: string }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState("");
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/telemetry-sources", { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
      .then(async (response) => { if (!response.ok) throw new Error("Unable to list telemetry sources"); return response.json(); })
      .then((data) => { setSources(data.items); setSelected(data.items[0]?.id ?? ""); })
      .catch((e) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [token]);
  useEffect(() => {
    if (!selected) { setDossier(null); return; }
    const controller = new AbortController();
    setDossier(null);
    fetch(`/api/v1/telemetry-sources/${selected}/quality-dossier`, {
      headers: { Authorization: `Bearer ${token}` }, signal: controller.signal,
    })
      .then(async (response) => { if (!response.ok) throw new Error("Unable to load quality dossier"); return response.json(); })
      .then((data) => setDossier(data))
      .catch((e) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [selected, token]);
  return <article className="card wide telemetry-dossier">
    <p className="eyebrow">Historical telemetry / source evidence</p>
    <h2>Quality dossier</h2>
    <p>Current-revision drilling-ahead screen, distinct from source qualification and model validation.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {!sources.length && !error && <p className="notice">No historical telemetry source is staged. This is not a passing screen.</p>}
    {!!sources.length && <>
      <label htmlFor="telemetry-source">Source</label>
      <select id="telemetry-source" value={selected} onChange={(e) => setSelected(e.target.value)}>
        {sources.map((source) => <option key={source.id} value={source.id}>{source.dataset_name} / {source.external_id}</option>)}
      </select>
    </>}
    {selected && !dossier && !error && <p role="status">Screening current revisions…</p>}
    {dossier && <>
      <p className="notice">{dossier.notice}</p>
      <p><strong>Source:</strong> {dossier.source.external_id} · {label(dossier.source.source_kind)} · {label(dossier.source.data_kind)}</p>
      <p><strong>States:</strong> screen {label(dossier.screen?.decision ?? dossier.dossier_state)} · source {label(dossier.source.qualification_state)} · dataset {label(dossier.source.dataset_qualification_state ?? "unknown")}</p>
      <p><strong>Review flags:</strong> units {dossier.source.units_reviewed ? "reviewed" : "pending"} · timezone {dossier.source.timezone_reviewed ? "reviewed" : "pending"} · depth datum {dossier.source.datum_reviewed ? "reviewed" : "pending"} · rig state {dossier.source.rig_state_reviewed ? "reviewed" : "pending"}</p>
      <p><strong>Identity:</strong> {dossier.record_counts.distinct_records} records / {dossier.record_counts.stored_revisions} revisions · mapping {dossier.source.mapping_version} · SHA-256 {dossier.source.source_sha256?.slice(0, 16)}…</p>
      {dossier.screen?.wellbores.map((bore) => <div className="dossier-bore" key={bore.wellbore_id}>
        <h3>Wellbore {bore.wellbore_id.slice(0, 8)} · {label(bore.decision)}</h3>
        <p>{bore.current_rows} current rows · {bore.duration_minutes} min · {(bore.good_complete_fraction * 100).toFixed(0)}% complete good channels · {(bore.active_drilling_fraction * 100).toFixed(0)}% active drilling · {bore.measured_depth_advance_m} m MD advance · largest gap {bore.largest_gap_minutes} min</p>
        <p>ROP range {bore.rop_min_max.join("–")} m/h · WOB range {bore.wob_min_max.join("–")} kN</p>
        <p>Quality: {Object.entries(bore.quality_counts).map(([key, value]) => `${label(key)} ${value}`).join(" · ")}</p>
        <p>Rig state: {Object.entries(bore.rig_state_counts).map(([key, value]) => `${label(key)} ${value}`).join(" · ")}</p>
        {bore.blockers.length ? <p className="error">Blockers: {bore.blockers.map(label).join("; ")}</p> : <p>Screen blockers: none. Human review still required.</p>}
      </div>)}
      {dossier.screen && <details><summary>Screen thresholds · {dossier.screen.screen_version}</summary><ul>{Object.entries(dossier.screen.thresholds).map(([key, value]) => <li key={key}>{label(key)}: {value}</li>)}</ul></details>}
    </>}
  </article>;
}
