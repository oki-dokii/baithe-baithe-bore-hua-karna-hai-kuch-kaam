import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { DepthTrack, MudWindow } from "./ExplorationExtras";
import OffsetBrief, { OffsetBriefData } from "./OffsetBrief";

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
  bottomhole_horizontal_distance_m?: number;
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
  proximity_basis: "surface" | "terminal_bottomhole";
  proximity_notice: string;
  excluded_unresolved_survey_count: number;
  score_formula: string;
  truncated: boolean;
};

type BottomholeProximity = {
  status: "resolved" | "unresolved";
  source_scope: "owned_synthetic_demo_only" | "reviewed_dataset_pair";
  active_position: { status: string; reason?: string };
  offset_position: { status: string; reason?: string };
  bottomhole_horizontal_distance_m: number | null;
  notice: string;
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
  proximityBasis,
  selectedId,
  onSelect,
}: {
  active: Well;
  candidates: Analogue[];
  radius: number;
  proximityBasis: "surface" | "terminal_bottomhole";
  selectedId: string;
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

    const bounds = proximityBasis === "surface"
      ? L.circle([active.latitude, active.longitude], {
          radius: radius * 1000,
          color: "#78896d",
          weight: 1.5,
          dashArray: "4 6",
          fillColor: "#e1e8d9",
          fillOpacity: 0.35,
        }).addTo(map).getBounds()
      : L.latLngBounds([active, ...candidates].map((well) => [well.latitude, well.longitude]));

    if (bounds.isValid() && (proximityBasis === "surface" || candidates.length))
      map.fitBounds(bounds.pad(0.15), { padding: [35, 35], maxZoom: 13 });

    const gridBounds = bounds.pad(0.5);
    const step = Math.max(
      0.002,
      Math.pow(
        10,
        Math.floor(Math.log10(Math.max(0.01, gridBounds.getNorth() - gridBounds.getSouth()) / 5)),
      ),
    );

    for (
      let lat = Math.floor(gridBounds.getSouth() / step) * step;
      lat <= gridBounds.getNorth();
      lat += step
    )
      L.polyline(
        [
          [lat, gridBounds.getWest()],
          [lat, gridBounds.getEast()],
        ],
        { color: "#c4ccbb", weight: 1, opacity: 0.5, interactive: false },
      ).addTo(map);

    for (
      let lon = Math.floor(gridBounds.getWest() / step) * step;
      lon <= gridBounds.getEast();
      lon += step
    )
      L.polyline(
        [
          [gridBounds.getSouth(), lon],
          [gridBounds.getNorth(), lon],
        ],
        { color: "#c4ccbb", weight: 1, opacity: 0.5, interactive: false },
      ).addTo(map);

    for (const [index, well] of [active, ...candidates].entries()) {
      const current = well.id === active.id;
      const isSelected = well.id === selectedId;
      const label = document.createElement("span");
      label.textContent = `${well.name}${current ? " · active" : isSelected ? " · selected" : ""}`;
      
      const marker = L.circleMarker([well.latitude, well.longitude], {
        radius: current ? 10 : isSelected ? 9 : 7,
        fillColor: current ? "#272c27" : isSelected ? "#3a8274" : "#617650",
        color: isSelected ? "#52b7a5" : "#fbfaf5",
        weight: isSelected ? 3 : 2,
        fillOpacity: 1,
      })
        .addTo(map)
        .bindTooltip(label, {
          permanent: current || isSelected,
          direction: current ? "left" : index % 2 ? "top" : "bottom",
          offset: current ? [-9, 0] : index % 2 ? [0, -9] : [0, 9],
        });

      if (!current) {
        marker.on("click", () => callback.current(well.id));
      }
    }

    L.control.scale({ imperial: false }).addTo(map);
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(root.current);

    return () => {
      observer.disconnect();
      map.remove();
    };
  }, [active, candidates, radius, proximityBasis, selectedId]);

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
  const [proximityBasis, setProximityBasis] = useState<"surface" | "terminal_bottomhole">("surface");
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [bottomhole, setBottomhole] = useState<BottomholeProximity | null>(null);
  const [brief, setBrief] = useState<OffsetBriefData | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [selected, setSelected] = useState("");
  const [exploreView, setExploreView] = useState<"atlas" | "subsurface">("atlas");

  // Case details
  const [record, setRecord] = useState<Case | null>(null);
  const [source, setSource] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const active = wells.find((w) => w.id === activeId);
  const candidate = comparison?.items.find((w) => w.id === selected);
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
    setBottomhole(null);
    setBrief(null);
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
          `/wellbores/${activeId}/analogues?target_interval_id=${intervalId}&radius_km=${radius}&proximity_basis=${proximityBasis}`,
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
  }, [token, activeId, intervalId, radius, proximityBasis]);

  useEffect(() => {
    let live = true;
    setBottomhole(null);
    if (activeId && selected) {
      request<BottomholeProximity>(token,
        `/wellbores/${activeId}/bottomhole-proximity?offset_wellbore_id=${selected}`)
        .then((data) => { if (live) setBottomhole(data); })
        .catch(() => { if (live) setBottomhole(null); });
    }
    return () => { live = false; };
  }, [token, activeId, selected]);

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

  async function prepareBrief() {
    if (!activeId || !intervalId) return;
    setBriefLoading(true);
    setBrief(null);
    try {
      const data = await request<OffsetBriefData>(token,
        `/wellbores/${activeId}/offset-brief?target_interval_id=${intervalId}&radius_km=${radius}&proximity_basis=${proximityBasis}`);
      setBrief(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBriefLoading(false);
    }
  }

  return (
    <section className="intelligence-workspace">
      {/* Workspace Header */}
      <div className="archive-heading">
        <div>
          <p className="eyebrow">01 / The offset atlas</p>
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

      {/* Atlas Search & Comparison Controls */}
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
          <label htmlFor="atlas-basis">Proximity basis</label>
          <select
            id="atlas-basis"
            value={proximityBasis}
            onChange={(e) => setProximityBasis(e.target.value as "surface" | "terminal_bottomhole")}
          >
            <option value="surface">Surface wellhead</option>
            <option value="terminal_bottomhole">Reviewed terminal position</option>
          </select>
        </div>
        <div>
          <label htmlFor="atlas-radius">
            {proximityBasis === "surface" ? "Surface" : "Terminal"} radius · {radius} km
          </label>
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
          <p className="notice">
            {comparison.proximity_notice} Map markers show surface wellheads.
            {comparison.excluded_unresolved_survey_count > 0 &&
              ` ${comparison.excluded_unresolved_survey_count} candidate(s) excluded for unresolved survey geometry.`}
          </p>

          <div className="brief-actions">
            <button type="button" onClick={prepareBrief} disabled={briefLoading}>
              {briefLoading ? "Preparing cited brief…" : "Prepare one-page offset brief"}
            </button>
            {brief && <button type="button" onClick={() => window.print()}>Print / save as PDF</button>}
          </div>

          {brief && <OffsetBrief data={brief} />}

          {/* Subview Toggle */}
          <div className="subview-tab-bar" role="tablist" aria-label="Explore views">
            <button
              type="button"
              role="tab"
              aria-selected={exploreView === "atlas"}
              className={`subview-tab-btn ${exploreView === "atlas" ? "active" : ""}`}
              onClick={() => setExploreView("atlas")}
            >
              <span className="tab-num">01</span>
              <span className="tab-title">Offset Atlas & Analogues</span>
              <span className="tab-desc">Geographic map & incident mappings</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={exploreView === "subsurface"}
              className={`subview-tab-btn ${exploreView === "subsurface" ? "active" : ""}`}
              onClick={() => setExploreView("subsurface")}
            >
              <span className="tab-num">02</span>
              <span className="tab-title">Subsurface Logs</span>
              <span className="tab-desc">Depth register & pore pressure envelope</span>
            </button>
          </div>

          {/* Subview 1: The Offset Atlas Grid & Selected Analogue Comparison */}
          {exploreView === "atlas" && (
            <>
              <div className="atlas-grid">
                <div className="map-frame">
                  <WellMap
                    active={active}
                    candidates={comparison.items}
                    radius={radius}
                    proximityBasis={proximityBasis}
                    selectedId={selected}
                    onSelect={(id) => {
                      setSelected(id);
                      setRecord(null);
                      setSource(null);
                      caseSequence.current++;
                    }}
                  />
                  <div className="map-caption">
                    <span>
                      WGS84 · {active.latitude.toFixed(4)}°,{" "}
                      {active.longitude.toFixed(4)}°
                    </span>
                    <span>Click markers to compare offset analogues within {radius} km</span>
                  </div>
                </div>

                <aside className="analogue-index">
                  <div className="panel-heading">
                    <h2>Offset wells</h2>
                    <span className="mono">
                      {comparison.items.length} IN {proximityBasis === "surface" ? "SURFACE" : "TERMINAL"} RADIUS
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
                        <span>
                          {((proximityBasis === "terminal_bottomhole"
                            ? w.bottomhole_horizontal_distance_m
                            : w.surface_distance_m)! / 1000).toFixed(2)} km
                        </span>
                        <small>
                          Similarity {(w.similarity_score * 100).toFixed(0)} / 100 · not risk
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
                      No eligible offset wells within this radius.
                    </p>
                  )}
                </aside>
              </div>

              {comparison.truncated && (
                <p className="notice">
                  Showing the nearest 100 eligible wellbores only. Narrow the radius.
                </p>
              )}

              {/* Selected Candidate Detailed Comparison */}
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
                  <p className="footnote">
                    {proximityBasis === "surface"
                      ? "Surface-selected pair"
                      : "Terminal-position-selected pair"}{" "}
                    · bottom-hole horizontal separation:{" "}
                    {bottomhole?.status === "resolved"
                      ? `${Number(bottomhole.bottomhole_horizontal_distance_m).toFixed(0)} m`
                      : "unavailable"}.{" "}
                    {bottomhole?.status === "unresolved"
                      ? `Active: ${readable(bottomhole.active_position.reason ?? "ready")}; offset: ${readable(bottomhole.offset_position.reason ?? "ready")}. `
                      : ""}
                    {bottomhole?.source_scope === "owned_synthetic_demo_only"
                      ? "Owned synthetic geometry only. "
                      : ""}
                    {bottomhole?.notice ??
                      "Requires a reviewed true-north survey on both wells."}
                  </p>
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

          {/* Subview 2: Subsurface Wellbore Logs */}
          {exploreView === "subsurface" && (
            <div className="subsurface-logs-wrapper">
              <div className="tab-section-intro">
                <h2>Active Wellbore Subsurface Logs</h2>
                <p className="footnote">
                  Correlated formation depth register and pore pressure/fracture gradient envelope for {active.name}.
                </p>
              </div>
              <DepthTrack token={token} wellboreId={activeId} onOpenCase={openCase} />
              <MudWindow token={token} wellboreId={activeId} />
            </div>
          )}
        </>
      )}

      {/* Case File Inspection Modal/Drawer */}
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
