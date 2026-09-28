export type OffsetBriefData = {
  active_name: string;
  target_formation: string;
  radius_km: number;
  score_formula: string;
  notice: string;
  truncated: boolean;
  omitted_uncited: number;
  omitted_unresolved: number;
  offsets: {
    wellbore_id: string;
    name: string;
    surface_distance_m: number;
    similarity_score: number;
    data_kind: string;
    origin_kind: string;
    authorization_state: string;
    applicability: string;
    events: {
      event_id: string;
      event_type: string;
      description: string;
      source_start_md_m: number | null;
      mapped_start_md_m: number | null;
      citations: { filename: string; page_number: number; passage_id: string }[];
      citations_truncated: boolean;
    }[];
  }[];
};

const label = (value: string) => value.replaceAll("_", " ");
const md = (value: number | null) => value == null ? "unknown" : `${Number(value).toFixed(0)} m MD`;

export default function OffsetBrief({ data }: { data: OffsetBriefData }) {
  return <article className="offset-brief" aria-label="Printable offset brief">
    <p className="eyebrow">NWIS / FIELD NOTE</p>
    <h2>Offset evidence brief</h2>
    <p className="brief-deck">{data.active_name} · {data.target_formation} · {data.radius_km} km surface search</p>
    <p className="brief-guard">{data.notice}</p>
    {data.offsets.map((offset, index) => <section key={offset.wellbore_id} className="brief-offset">
      <h3><span>{String(index + 1).padStart(2, "0")}</span> {offset.name} <small>{(offset.surface_distance_m / 1000).toFixed(2)} km surface</small></h3>
      <p className="brief-meta">{label(offset.data_kind)} · {label(offset.origin_kind)} · {label(offset.authorization_state)} · {label(offset.applicability)} · similarity {(offset.similarity_score * 100).toFixed(0)}/100, not risk</p>
      {offset.events.length ? offset.events.map((event) => <div key={event.event_id} className="brief-event">
        <strong>{label(event.event_type)}</strong> · historical {md(event.source_start_md_m)} → mapped {md(event.mapped_start_md_m)}
        <p>{event.description}</p>
        <small>Source: {event.citations.map((c) => `${c.filename}, p. ${c.page_number} [${c.passage_id.slice(0, 8)}]`).join("; ")}{event.citations_truncated ? "; more citations in case file" : ""}</small>
      </div>) : <p className="brief-empty">No resolved, cited event in this bounded brief; this does not establish a risk-free interval.</p>}
    </section>)}
    <p className="brief-footer">{data.score_formula} {data.truncated ? "Additional wells or events omitted by one-page limit. " : ""}{data.omitted_uncited} uncited and {data.omitted_unresolved} unresolved event(s) excluded. Verify source case files before decisions. Engineer retains authority.</p>
  </article>;
}
