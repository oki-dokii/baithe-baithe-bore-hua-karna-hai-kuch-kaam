import { FormEvent, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

type Well = {
  id: string;
  well_id: string;
  name: string;
  dataset_id: string;
  data_kind: string;
  latitude: number;
  longitude: number;
};
type Interval = {
  id: string;
  formation_id: string;
  display_name: string;
  top_md_m: number;
  base_md_m: number | null;
  datum: string;
  review_state: string;
  version: number;
};
type Mapping = {
  event_id: string;
  event_type: string;
  source_start_md_m: number | null;
  source_end_md_m: number | null;
  mapped_start_md_m: number | null;
  mapped_end_md_m: number | null;
  status: string;
  reason: string | null;
  method: string;
};
type Analogue = Well & {
  surface_distance_m: number;
  similarity_score: number;
  components: {
    same_reviewed_formation: number;
    md_thickness_similarity: number | null;
  };
  missing_components: string[];
  mappings: Mapping[];
  events_truncated: boolean;
};
type Comparison = {
  items: Analogue[];
  target_interval: Interval;
  score_formula: string;
  truncated: boolean;
};
type Citation = {
  passage_id: string;
  document_id: string;
  page_number: number;
  filename: string;
  quote: string | null;
  text_version: number;
  document_version: number;
  raw_text?: string;
  representation?: string;
};
type Case = {
  id: string;
  well_name: string;
  event_type: string;
  data_kind: string;
  start_md_m: number | null;
  end_md_m: number | null;
  description: string;
  source_datum: string | null;
  quality_issues: string[];
  evidence: Citation[];
  mitigation: { id: string; action_taken: string }[];
  event_outcome: { id: string; outcome: string }[];
  npt_event: { id: string; duration_h: number }[];
};
type SearchResult = {
  items: {
    id: string;
    well_name: string;
    event_type: string;
    description: string;
    citations: Citation[];
  }[];
  next_offset: number | null;
  abstention_reason: string | null;
};
const readable = (s: string) => s.replaceAll("_", " ");
const depth = (v: number | null) =>
  v == null ? "Unknown" : `${Number(v).toFixed(1)} m`;
async function request<T>(
  token: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...init?.headers },
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error?.message ?? `Request failed (${response.status})`,
    );
  return data;
}

function WellMap({
  active,
  candidates,
  radius,
  onSelect,
}: {
  active: Well;
  candidates: Analogue[];
  radius: number;
  onSelect: (id: string) => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const callback = useRef(onSelect);
  callback.current = onSelect;
  useEffect(() => {
    if (!root.current) return;
    const map = L.map(root.current, {
      center: [active.latitude, active.longitude],
      zoom: 12,
      scrollWheelZoom: false,
      attributionControl: false,
    });
    const ring = L.circle([active.latitude, active.longitude], {
      radius: radius * 1000,
      color: "#78896d",
      weight: 1,
      dashArray: "4 6",
      fillColor: "#e1e8d9",
      fillOpacity: 0.45,
    }).addTo(map);
    map.fitBounds(ring.getBounds(), { padding: [35, 35] });
    const bounds = ring.getBounds().pad(0.5);
    const step = Math.max(
      0.002,
      Math.pow(
        10,
        Math.floor(Math.log10((bounds.getNorth() - bounds.getSouth()) / 5)),
      ),
    );
    for (
      let lat = Math.floor(bounds.getSouth() / step) * step;
      lat <= bounds.getNorth();
      lat += step
    )
      L.polyline(
        [
          [lat, bounds.getWest()],
          [lat, bounds.getEast()],
        ],
        { color: "#c4ccbb", weight: 1, opacity: 0.5, interactive: false },
      ).addTo(map);
    for (
      let lon = Math.floor(bounds.getWest() / step) * step;
      lon <= bounds.getEast();
      lon += step
    )
      L.polyline(
        [
          [bounds.getSouth(), lon],
          [bounds.getNorth(), lon],
        ],
        { color: "#c4ccbb", weight: 1, opacity: 0.5, interactive: false },
      ).addTo(map);
    for (const [index, well] of [active, ...candidates].entries()) {
      const current = well.id === active.id;
      const label = document.createElement("span");
      label.textContent = `${well.name}${current ? " · active" : ""}`;
      L.circleMarker([well.latitude, well.longitude], {
        radius: current ? 9 : 7,
        fillColor: current ? "#272c27" : "#617650",
        color: "#fbfaf5",
        weight: 2,
        fillOpacity: 1,
      })
        .addTo(map)
        .bindTooltip(label, {
          permanent: true,
          direction: current ? "left" : index % 2 ? "top" : "bottom",
          offset: current ? [-9, 0] : index % 2 ? [0, -9] : [0, 9],
        })
        .on("click", () => {
          if (!current) callback.current(well.id);
        });
    }
    L.control.scale({ imperial: false }).addTo(map);
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(root.current);
    return () => {
      observer.disconnect();
      map.remove();
    };
  }, [active, candidates, radius]);
  return (
    <div
      className="well-map"
      ref={root}
      role="region"
      aria-label="Interactive geographic well map. Use the adjacent well list for keyboard selection."
    />
  );
}

export default function Intelligence({ token }: { token: string }) {
  const [wells, setWells] = useState<Well[]>([]);
  const [activeId, setActiveId] = useState("");
  const [intervals, setIntervals] = useState<Interval[]>([]);
  const [intervalId, setIntervalId] = useState("");
  const [radius, setRadius] = useState(5);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [selected, setSelected] = useState("");
  const [record, setRecord] = useState<Case | null>(null);
  const [source, setSource] = useState<Citation | null>(null);
  const [question, setQuestion] = useState("");
  const [hazard, setHazard] = useState("");
  const [minimum, setMinimum] = useState("");
  const [maximum, setMaximum] = useState("");
  const [sameFormation, setSameFormation] = useState(false);
  const [results, setResults] = useState<SearchResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const active = wells.find((w) => w.id === activeId);
  const candidate = comparison?.items.find((w) => w.id === selected);
  const requestSequence = useRef(0);
  const caseSequence = useRef(0);

  useEffect(() => {
    let live = true;
    request<{ items: Well[] }>(token, "/intelligence/wellbores")
      .then((data) => {
        if (live) {
          setWells(data.items);
          setActiveId(
            data.items.find((w) => w.name === "SYN-A")?.id ??
              data.items[0]?.id ??
              "",
          );
        }
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [token]);
  useEffect(() => {
    let live = true;
    setIntervals([]);
    setIntervalId("");
    setComparison(null);
    setRecord(null);
    setSource(null);
    setResults(null);
    caseSequence.current++;
    if (activeId)
      request<{ intervals: Interval[] }>(
        token,
        `/wellbores/${activeId}/trajectory`,
      )
        .then((data) => {
          if (live) {
            const reviewed = data.intervals.filter(
              (i) => i.review_state === "approved",
            );
            setIntervals(reviewed);
            setIntervalId(reviewed[0]?.id ?? "");
          }
        })
        .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [token, activeId]);
  useEffect(() => {
    let live = true;
    setComparison(null);
    setSelected("");
    setRecord(null);
    setSource(null);
    caseSequence.current++;
    if (!activeId || !intervalId) { setLoading(false); return; }
    setLoading(true);
    setError("");
    const timer = setTimeout(
      () =>
        request<Comparison>(
          token,
          `/wellbores/${activeId}/analogues?target_interval_id=${intervalId}&radius_km=${radius}`,
        )
          .then((data) => {
            if (live) {
              setComparison(data);
              setSelected(data.items[0]?.id ?? "");
            }
          })
          .catch((e) => live && setError(e.message))
          .finally(() => live && setLoading(false)),
      200,
    );
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [token, activeId, intervalId, radius]);
  useEffect(() => {
    setResults(null);
    requestSequence.current++;
    setSearching(false);
  }, [question, hazard, minimum, maximum, sameFormation, activeId, intervalId]);
  async function openCase(id: string) {
    const sequence = ++caseSequence.current;
    setRecord(null);
    setSource(null);
    setError("");
    try {
      const data = await request<Case>(token, `/events/${id}`);
      if (sequence === caseSequence.current) setRecord(data);
    } catch (e) {
      if (sequence === caseSequence.current) setError((e as Error).message);
    }
  }
  async function openSource(citation: Citation) {
    if (!record) return;
    const sequence = ++caseSequence.current;
    setSource(null);
    try {
      const data = await request<Citation>(
        token,
        `/events/${record.id}/evidence/${citation.passage_id}`,
      );
      if (sequence === caseSequence.current) setSource(data);
    } catch (e) {
      if (sequence === caseSequence.current) setError((e as Error).message);
    }
  }
  async function search(event?: FormEvent, offset = 0) {
    event?.preventDefault();
    if (!active) return;
    if (minimum !== "" && maximum !== "" && Number(minimum) > Number(maximum)) {
      setError("Depth range is reversed.");
      return;
    }
    const sequence = ++requestSequence.current;
    setSearching(true);
    setError("");
    try {
      const data = await request<SearchResult>(token, "/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset_id: active.dataset_id,
          question,
          hazard: hazard || null,
          formation_id: sameFormation
            ? intervals.find((i) => i.id === intervalId)?.formation_id
            : null,
          min_md_m: minimum === "" ? null : Number(minimum),
          max_md_m: maximum === "" ? null : Number(maximum),
          offset,
        }),
      });
      if (sequence === requestSequence.current)
        setResults((previous) =>
          offset && previous
            ? { ...data, items: [...previous.items, ...data.items] }
            : data,
        );
    } catch (e) {
      if (sequence === requestSequence.current) setError((e as Error).message);
    } finally {
      if (sequence === requestSequence.current) setSearching(false);
    }
  }
  return (
    <section className="intelligence-workspace">
      <div className="archive-heading">
        <div>
          <p className="eyebrow">02 / The offset atlas</p>
          <h1>Nearby is a starting point.</h1>
          <p>
            Compare the formation. Read the history. Keep the evidence in view.
          </p>
        </div>
        <span className="state">
          {active?.data_kind ?? "No dataset"} · NO PREDICTIVE MODEL
        </span>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="atlas-controls">
        <div>
          <label htmlFor="atlas-active">Active wellbore</label>
          <select
            id="atlas-active"
            value={activeId}
            onChange={(e) => setActiveId(e.target.value)}
          >
            {wells.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} · {w.data_kind}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="atlas-formation">Reviewed target formation</label>
          <select
            id="atlas-formation"
            value={intervalId}
            onChange={(e) => setIntervalId(e.target.value)}
          >
            <option value="">Choose an interval</option>
            {intervals.map((i) => (
              <option key={i.id} value={i.id}>
                {i.display_name} · {depth(i.top_md_m)}–{depth(i.base_md_m)} MD ·
                v{i.version}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="atlas-radius">Surface radius · {radius} km</label>
          <input
            id="atlas-radius"
            type="range"
            min="0.1"
            max="100"
            step="0.1"
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
          />
        </div>
      </div>
      {loading && (
        <p role="status">Finding offset wells and checking depth context…</p>
      )}
      {!intervalId && (
        <p className="notice">
          A reviewed formation interval is required for geological comparison.
          No depth mapping is inferred from location alone.
        </p>
      )}
      {active && comparison && (
        <>
          <div className="atlas-grid">
            <div className="map-frame">
              <WellMap
                active={active}
                candidates={comparison.items}
                radius={radius}
                onSelect={id => { setSelected(id); setRecord(null); setSource(null); caseSequence.current++; }}
              />
              <div className="map-caption">
                <span>
                  WGS84 · {active.latitude.toFixed(4)}°,{" "}
                  {active.longitude.toFixed(4)}°
                </span>
                <span>Offline coordinate map · no terrain tiles</span>
              </div>
            </div>
            <aside className="analogue-index">
              <div className="panel-heading">
                <h2>Offset wells</h2>
                <span className="mono">
                  {comparison.items.length} IN RADIUS
                </span>
              </div>
              {comparison.items.length ? (
                comparison.items.map((w) => (
                  <button
                    key={w.id}
                    onClick={() => {
                      setSelected(w.id);
                      setRecord(null);
                      setSource(null);
                      caseSequence.current++;
                    }}
                    className={`analogue-row ${selected === w.id ? "selected" : ""}`}
                  >
                    <strong>{w.name}</strong>
                    <span>{(w.surface_distance_m / 1000).toFixed(2)} km</span>
                    <small>
                      Similarity {(w.similarity_score * 100).toFixed(0)} / 100 ·
                      not risk
                    </small>
                    <small>
                      {w.components.same_reviewed_formation
                        ? "Shared reviewed formation"
                        : "Different / unreviewed formation"}
                    </small>
                  </button>
                ))
              ) : (
                <p className="index-empty">
                  No offset wells within this radius.
                </p>
              )}
            </aside>
          </div>
          {comparison.truncated && (
            <p className="notice">
              Showing the nearest 100 wellbores only. Narrow the radius.
            </p>
          )}
          {candidate && (
            <section className="comparison-panel">
              <div className="section-heading">
                <h2>
                  {candidate.name} → {active.name}
                </h2>
                <span>
                  Formation-relative comparison ·{" "}
                  {comparison.target_interval.datum}
                </span>
              </div>
              <p className="footnote">{comparison.score_formula}</p>
              <div className="score-explanation">
                <span>
                  Shared formation:{" "}
                  {candidate.components.same_reviewed_formation ? "yes" : "no"}
                </span>
                <span>
                  MD-thickness ratio:{" "}
                  {candidate.components.md_thickness_similarity == null
                    ? "unknown"
                    : candidate.components.md_thickness_similarity.toFixed(2)}
                </span>
                <span>
                  Not included:{" "}
                  {candidate.missing_components.map(readable).join(", ")}
                </span>
              </div>
              <h3>Approved historical incidents</h3>
              {candidate.mappings.length ? (
                <div className="mapping-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Incident</th>
                        <th>Historical MD</th>
                        <th>Mapped active MD</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {candidate.mappings.map((m) => (
                        <tr key={m.event_id}>
                          <td>{readable(m.event_type)}</td>
                          <td>
                            {depth(m.source_start_md_m)}–
                            {depth(m.source_end_md_m)}
                          </td>
                          <td>
                            {m.status === "resolved" ? (
                              `${depth(m.mapped_start_md_m)}–${depth(m.mapped_end_md_m)}`
                            ) : (
                              <span className="unresolved">
                                Unresolved: {readable(m.reason ?? "unknown")}
                              </span>
                            )}
                          </td>
                          <td>
                            <button
                              className="text-button"
                              onClick={() => openCase(m.event_id)}
                            >
                              Open case →
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="notice">
                  No approved incidents to compare. This is not evidence of a
                  risk-free well.
                </p>
              )}
              {candidate.events_truncated && (
                <p className="notice">
                  Only the first 100 approved events are shown.
                </p>
              )}
              <p className="footnote">
                Mapped depths use a formation-top TVD offset with survey
                interpolation, not equal raw MD or a risk prediction. Unresolved
                cases must not support alerts.
              </p>
            </section>
          )}
        </>
      )}
      <section className="knowledge-search">
        <p className="eyebrow">03 / Search the approved record</p>
        <h2>What has happened before?</h2>
        <p className="footnote">
          Full-text search within the active well’s dataset. No semantic
          embedding model or generated advice.
        </p>
        <form onSubmit={search}>
          <div className="search-primary">
            <label className="sr-only" htmlFor="evidence-query">
              Search keywords
            </label>
            <input
              id="evidence-query"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder='Keywords, e.g. "mud losses"'
            />
            <button disabled={!active || searching}>
              {searching ? "Searching…" : "Find evidence →"}
            </button>
          </div>
          <div className="search-filters">
            <div>
              <label htmlFor="search-hazard">Hazard</label>
              <select
                id="search-hazard"
                value={hazard}
                onChange={(e) => setHazard(e.target.value)}
              >
                <option value="">All hazards</option>
                {[
                  "mud_loss",
                  "kick",
                  "stuck_pipe",
                  "overpressure",
                  "torque_spike",
                  "tight_hole",
                  "fishing",
                  "cementing_issue",
                  "other",
                ].map((h) => (
                  <option key={h} value={h}>
                    {readable(h)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="search-from">Source MD from · m</label>
              <input
                id="search-from"
                type="number"
                min="0"
                step="any"
                value={minimum}
                onChange={(e) => setMinimum(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="search-to">Source MD to · m</label>
              <input
                id="search-to"
                type="number"
                min="0"
                step="any"
                value={maximum}
                onChange={(e) => setMaximum(e.target.value)}
              />
            </div>
            <label className="check">
              <input
                type="checkbox"
                disabled={!intervalId}
                checked={sameFormation}
                onChange={(e) => setSameFormation(e.target.checked)}
              />
              Only the selected formation
            </label>
          </div>
        </form>
        {results && (
          <div aria-live="polite">
            {results.items.length ? (
              results.items.map((r) => (
                <article className="search-hit" key={r.id}>
                  <div>
                    <strong>
                      {r.well_name} / {readable(r.event_type)}
                    </strong>
                    <p>{r.description}</p>
                    <small>
                      {r.citations
                        .map((c) => `${c.filename} · page ${c.page_number}`)
                        .join("; ")}
                    </small>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => openCase(r.id)}
                  >
                    Inspect evidence →
                  </button>
                </article>
              ))
            ) : (
              <p className="notice">
                No approved supporting evidence matches these filters. No answer
                or recommendation is inferred.
              </p>
            )}
            {results.next_offset != null && (
              <button
                className="secondary"
                disabled={searching}
                onClick={() => search(undefined, results.next_offset!)}
              >
                Load more evidence
              </button>
            )}
          </div>
        )}
      </section>
      {record && (
        <section className="case-panel" aria-label="Historical event case file">
          <div className="section-heading">
            <h2>
              {record.well_name} / {readable(record.event_type)}
            </h2>
            <button
              className="text-button"
              onClick={() => {
                setRecord(null);
                setSource(null);
                caseSequence.current++;
              }}
            >
              Close case
            </button>
          </div>
          <p className="eyebrow">
            {record.data_kind} · Approved historical evidence
          </p>
          <p>{record.description}</p>
          <p className="footnote">
            Source MD {depth(record.start_md_m)}–{depth(record.end_md_m)} ·
            datum {record.source_datum ?? "not recorded on event"}
          </p>
          {!!record.quality_issues.length && (
            <p className="quality-note">
              Quality issues: {record.quality_issues.map(readable).join(", ")}
            </p>
          )}
          <div className="case-facts">
            <div>
              <h3>Recorded response</h3>
              {record.mitigation.length ? (
                record.mitigation.map((m) => <p key={m.id}>{m.action_taken}</p>)
              ) : (
                <p>Not recorded</p>
              )}
            </div>
            <div>
              <h3>Reported outcome</h3>
              {record.event_outcome.length ? (
                record.event_outcome.map((o) => (
                  <p key={o.id}>{readable(o.outcome)}</p>
                ))
              ) : (
                <p>Unknown</p>
              )}
            </div>
            <div>
              <h3>Reported NPT</h3>
              {record.npt_event.length ? (
                record.npt_event.map((n) => (
                  <p key={n.id}>{n.duration_h} hours</p>
                ))
              ) : (
                <p>Not recorded</p>
              )}
            </div>
          </div>
          <h3>Source citations</h3>
          {record.evidence.map((c) => (
            <button
              className="citation-link"
              key={c.passage_id}
              onClick={() => openSource(c)}
            >
              {c.filename} · page {c.page_number} · document v
              {c.document_version} / text v{c.text_version} ↗
            </button>
          ))}
          {source && (
            <div className="case-source">
              <h3>
                {source.filename} · page {source.page_number}
              </h3>
              <p className="eyebrow">
                {readable(source.representation ?? "approved quote")}
              </p>
              <pre>
                {source.raw_text ?? source.quote ?? "No source quote available"}
              </pre>
            </div>
          )}
          <p className="footnote">
            A recorded mitigation is an observation, not a recommendation to
            repeat it.
          </p>
        </section>
      )}
    </section>
  );
}
