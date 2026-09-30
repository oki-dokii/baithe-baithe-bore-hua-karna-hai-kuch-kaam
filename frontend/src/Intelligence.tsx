import { FormEvent, useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import "./india-map.css";
import { CasingAndMudPanel, DepthTrack, MudWindow, PlanningPanel, PlanningPoint, ReservoirPropertiesPanel } from "./ExplorationExtras";
import OffsetBrief, { OffsetBriefData } from "./OffsetBrief";
import IndiaWellMap from "./IndiaMap";
import { ALL_SYNTHETIC_WELLS, haversineKm } from "./syntheticWellsData";

type SearchHit = {
  id: string;
  well_name: string;
  event_type: string;
  description: string;
  citations: Citation[];
};

type SearchResult = {
  items: SearchHit[];
  next_offset: number | null;
  abstention_reason: string | null;
  retrieval_mode: string;
  semantic_model: string | null;
  notice: string;
};

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
  const [exploreTab, setExploreTab] = useState<"incidents" | "depth" | "pressure" | "search" | "planning" | "brief">("incidents");
  const [inspectOffset, setInspectOffset] = useState(false);

  // Filter states
  const [eventTypeFilter, setEventTypeFilter] = useState("all");
  const [formationFilter, setFormationFilter] = useState<"all" | "shared_only">("all");

  // Scenario planning state
  const [planningPoint, setPlanningPoint] = useState<PlanningPoint | null>(null);
  const [planRadius, setPlanRadius] = useState(10);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [hazardFilter, setHazardFilter] = useState("");
  const [minMd, setMinMd] = useState("");
  const [maxMd, setMaxMd] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");

  // Case details
  const [record, setRecord] = useState<Case | null>(null);
  const [source, setSource] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const active = wells.find((w) => w.id === activeId);

  // Filtered offset candidates based on formation and event filters
  const allCandidates = comparison?.items ?? [];
  const filteredCandidates = allCandidates.filter((w) => {
    if (formationFilter === "shared_only" && !w.components.same_reviewed_formation) {
      return false;
    }
    if (eventTypeFilter !== "all") {
      const match = w.mappings.some((m) =>
        m.event_type.toLowerCase().includes(eventTypeFilter.toLowerCase())
      );
      if (!match) return false;
    }
    return true;
  });

  const candidate = filteredCandidates.find((w) => w.id === selected) ?? comparison?.items.find((w) => w.id === selected);
  const selectedSynthWell = ALL_SYNTHETIC_WELLS.find((w) => w.id === selected);
  const [sidebarView, setSidebarView] = useState<"radius" | "basins">("radius");
  const caseSequence = useRef(0);

  // Synchronize selection when filtered list changes (preserve selected synthetic basin wells)
  useEffect(() => {
    if (
      filteredCandidates.length > 0 &&
      !filteredCandidates.some((w) => w.id === selected) &&
      !ALL_SYNTHETIC_WELLS.some((w) => w.id === selected)
    ) {
      setSelected(filteredCandidates[0].id);
    }
  }, [filteredCandidates, selected]);

  // Close case drawer on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && record) {
        setRecord(null);
        setSource(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [record]);

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

  /* ── Perform search on verified DDR / knowledge records ──── */
  async function performSearch(e?: FormEvent, offset?: number) {
    e?.preventDefault();
    if (!active?.dataset_id) return;
    setSearching(true);
    setSearchError("");
    try {
      const params = new URLSearchParams({
        dataset_id: active.dataset_id,
      });
      if (searchQuery.trim()) params.set("query", searchQuery.trim());
      if (hazardFilter) params.set("event_type", hazardFilter);
      if (minMd) params.set("min_md_m", minMd);
      if (maxMd) params.set("max_md_m", maxMd);
      if (offset != null) params.set("offset", String(offset));
      const data = await request<SearchResult>(
        token,
        `/knowledge/search?${params.toString()}`,
      );
      if (offset && searchResults) {
        setSearchResults({
          ...data,
          items: [...searchResults.items, ...data.items],
        });
      } else {
        setSearchResults(data);
      }
    } catch (err) {
      setSearchError((err as Error).message);
    } finally {
      setSearching(false);
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
        <div>
          <label htmlFor="atlas-hazard">Hazard / event filter</label>
          <select
            id="atlas-hazard"
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value)}
          >
            <option value="all">All recorded events</option>
            <option value="kick">Kick / Well influx</option>
            <option value="loss">Losses / Mud loss</option>
            <option value="stuck">Stuck pipe</option>
            <option value="tight">Tight hole / Pack-off</option>
            <option value="pressure">Overpressure</option>
            <option value="fish">Fishing operation</option>
            <option value="cement">Cementing issue</option>
          </select>
        </div>
        <div>
          <label htmlFor="atlas-formation-match">Formation match</label>
          <select
            id="atlas-formation-match"
            value={formationFilter}
            onChange={(e) => setFormationFilter(e.target.value as "all" | "shared_only")}
          >
            <option value="all">All offset wells</option>
            <option value="shared_only">Shared reviewed formation only</option>
          </select>
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

          <div className="atlas-map-grid">
            <IndiaWellMap
              active={active}
              candidates={filteredCandidates.map((w) => ({
                ...w,
                surface_distance_m: w.surface_distance_m,
                similarity_score: w.similarity_score,
                event_count: w.mappings.length,
              }))}
              radius={radius}
              proximityBasis={proximityBasis}
              selectedId={selected}
              onSelect={(id) => {
                setSelected(id);
                setRecord(null);
                setSource(null);
                caseSequence.current++;
              }}
              planningPoint={planningPoint}
              onMapClick={(lat, lng) => {
                setPlanningPoint({
                  latitude: Number(lat.toFixed(4)),
                  longitude: Number(lng.toFixed(4)),
                });
                if (exploreTab !== "planning") {
                  setExploreTab("planning");
                }
              }}
            />

            <aside className="analogue-index">
              <div className="panel-heading" style={{ flexWrap: "wrap", gap: "6px" }}>
                <h2>{sidebarView === "radius" ? "Offset Wells" : "India Basins"}</h2>
                <div style={{ display: "flex", gap: "4px" }}>
                  <button
                    type="button"
                    className={`map-btn ${sidebarView === "radius" ? "map-btn-active-toggle" : ""}`}
                    style={{ fontSize: "0.65rem", padding: "2px 7px" }}
                    onClick={() => setSidebarView("radius")}
                    title="Show wells within active search radius"
                  >
                    Radius ({filteredCandidates.length})
                  </button>
                  <button
                    type="button"
                    className={`map-btn ${sidebarView === "basins" ? "map-btn-active-toggle" : ""}`}
                    style={{ fontSize: "0.65rem", padding: "2px 7px" }}
                    onClick={() => setSidebarView("basins")}
                    title="Show all 32 synthetic wells across 6 Indian petroleum basins"
                  >
                    All Basins ({ALL_SYNTHETIC_WELLS.length})
                  </button>
                </div>
              </div>

              {sidebarView === "radius" ? (
                filteredCandidates.length ? (
                  filteredCandidates.map((w) => (
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
                    No eligible offset wells matching active filters.
                  </p>
                )
              ) : (
                /* All India Basins List */
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  {ALL_SYNTHETIC_WELLS.map((sw) => {
                    const dist = haversineKm(active.latitude, active.longitude, sw.latitude, sw.longitude);
                    const isCurSelected = selected === sw.id;
                    return (
                      <button
                        key={sw.id}
                        type="button"
                        onClick={() => {
                          setSelected(sw.id);
                          setRecord(null);
                          setSource(null);
                          caseSequence.current++;
                        }}
                        className={`analogue-row ${isCurSelected ? "selected" : ""}`}
                        style={{ borderLeft: isCurSelected ? "3px solid var(--teal-glow)" : "3px solid transparent" }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <strong>{sw.name}</strong>
                          <span style={{ fontSize: "0.68rem", color: "var(--teal-glow)" }}>
                            {dist < 10 ? `${dist.toFixed(1)} km` : `${dist.toFixed(0)} km`}
                          </span>
                        </div>
                        <small style={{ color: "var(--text-secondary)" }}>
                          {sw.basin} · {sw.field_name}
                        </small>
                        <small style={{ color: "var(--ochre)" }}>
                          {sw.primary_hazard}
                        </small>
                      </button>
                    );
                  })}
                </div>
              )}
            </aside>
          </div>

          {comparison.truncated && (
            <p className="notice">
              Showing the nearest 100 eligible wellbores only. Narrow the radius.
            </p>
          )}

          {/* Selected Candidate Summary Banner */}
          {candidate ? (
            <div className="selected-analogue-banner">
              <div className="analogue-banner-main">
                <span className="analogue-banner-title">{candidate.name} → {active.name}</span>
                <span className="analogue-banner-badge">SYNTHETIC DEMO</span>
              </div>
              <div className="analogue-banner-meta">
                <span>{((proximityBasis === "terminal_bottomhole" ? candidate.bottomhole_horizontal_distance_m : candidate.surface_distance_m)! / 1000).toFixed(2)} km · {proximityBasis === "surface" ? "surface" : "terminal"}</span>
                <span>Similarity {(candidate.similarity_score * 100).toFixed(0)} / 100</span>
                <span style={{ color: candidate.components.same_reviewed_formation ? "var(--teal-glow)" : "var(--text-muted)" }}>
                  {candidate.components.same_reviewed_formation ? "Shared formation" : "Different formation"}
                </span>
                {bottomhole?.status === "resolved" && (
                  <span>BH sep: {Number(bottomhole.bottomhole_horizontal_distance_m).toFixed(0)} m</span>
                )}
              </div>
            </div>
          ) : selectedSynthWell ? (
            <div className="selected-analogue-banner">
              <div className="analogue-banner-main">
                <span className="analogue-banner-title">{selectedSynthWell.name} · {selectedSynthWell.basin}</span>
                <span className="analogue-banner-badge">SYNTHETIC DEMO · {selectedSynthWell.state}</span>
              </div>
              <div className="analogue-banner-meta">
                <span>{haversineKm(active.latitude, active.longitude, selectedSynthWell.latitude, selectedSynthWell.longitude).toFixed(1)} km separation (WGS 84)</span>
                <span>Target: {selectedSynthWell.target_formation} ({selectedSynthWell.depth_m} m TD)</span>
                <span style={{ color: "var(--ochre)" }}>Hazard: {selectedSynthWell.primary_hazard}</span>
                <span>Operator: {selectedSynthWell.operator}</span>
              </div>
            </div>
          ) : null}

          {/* Subsurface Research Tabs Header */}
          <div className="explore-tabs-header">
            <div className="explore-tab-nav" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={exploreTab === "incidents"}
                className={`explore-tab-btn ${exploreTab === "incidents" ? "active" : ""}`}
                onClick={() => setExploreTab("incidents")}
              >
                <span>Incidents & Correlation</span>
                <span className="explore-tab-badge">{candidate?.mappings.length ?? 0}</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={exploreTab === "depth"}
                className={`explore-tab-btn ${exploreTab === "depth" ? "active" : ""}`}
                onClick={() => setExploreTab("depth")}
              >
                <span>Depth Register & Logs</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={exploreTab === "pressure"}
                className={`explore-tab-btn ${exploreTab === "pressure" ? "active" : ""}`}
                onClick={() => setExploreTab("pressure")}
              >
                <span>Pressure & Mud Window</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={exploreTab === "search"}
                className={`explore-tab-btn ${exploreTab === "search" ? "active" : ""}`}
                onClick={() => setExploreTab("search")}
              >
                <span>DDR & Claim Search</span>
                {searchResults && (
                  <span className="explore-tab-badge">{searchResults.items.length}</span>
                )}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={exploreTab === "planning"}
                className={`explore-tab-btn ${exploreTab === "planning" ? "active" : ""}`}
                onClick={() => {
                  setExploreTab("planning");
                  if (!planningPoint && active) {
                    setPlanningPoint({
                      latitude: Number((active.latitude + 0.035).toFixed(4)),
                      longitude: Number((active.longitude + 0.045).toFixed(4)),
                    });
                  }
                }}
              >
                <span>Scenario Planning</span>
                {planningPoint && <span className="explore-tab-badge">SET</span>}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={exploreTab === "brief"}
                className={`explore-tab-btn ${exploreTab === "brief" ? "active" : ""}`}
                onClick={() => setExploreTab("brief")}
              >
                <span>Cited Offset Brief</span>
              </button>
            </div>

            {(exploreTab === "depth" || exploreTab === "pressure") && candidate && (
              <div className="wellbore-toggle-group">
                <button
                  type="button"
                  className={`wellbore-toggle-btn ${!inspectOffset ? "active" : ""}`}
                  onClick={() => setInspectOffset(false)}
                >
                  Active: {active.name}
                </button>
                <button
                  type="button"
                  className={`wellbore-toggle-btn ${inspectOffset ? "active" : ""}`}
                  onClick={() => setInspectOffset(true)}
                >
                  Offset: {candidate.name}
                </button>
              </div>
            )}
          </div>

          {/* Tab 1: Incidents & Correlation */}
          {exploreTab === "incidents" && (
            candidate ? (
              <section className="comparison-panel">
                <div className="section-heading">
                  <h2>
                    {candidate.name} → {active.name}
                  </h2>
                  <span>
                    Formation-relative comparison · {comparison.target_interval.datum}
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
                  {bottomhole?.notice ?? "Requires a reviewed true-north survey on both wells."}
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
                                Open case file →
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="notice">
                    No approved incidents to compare under current filters. This is not evidence of a risk-free well.
                  </p>
                )}
                {candidate.events_truncated && (
                  <p className="notice">
                    Only the first 100 approved events are shown.
                  </p>
                )}
                <p className="footnote">
                  Mapped depths use a formation-top TVD offset with survey interpolation, not equal raw MD or a risk prediction. Unresolved cases must not support alerts.
                </p>
              </section>
            ) : selectedSynthWell ? (
              <section className="comparison-panel">
                <div className="section-heading">
                  <h2>
                    {selectedSynthWell.name} · {selectedSynthWell.basin}
                  </h2>
                  <span className="mono">
                    SYNTHETIC BASIN REFERENCE FIXTURE · {selectedSynthWell.state}
                  </span>
                </div>
                <p className="footnote">
                  Geologically calibrated reference well fixture located in {selectedSynthWell.basin} ({selectedSynthWell.field_name}).
                  Separation from active well {active.name}: {haversineKm(active.latitude, active.longitude, selectedSynthWell.latitude, selectedSynthWell.longitude).toFixed(1)} km (Geodesic WGS 84).
                </p>
                <div className="score-explanation" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "10px", margin: "14px 0" }}>
                  <div>
                    <span className="popup-label">Field / Basin</span>
                    <strong style={{ display: "block", color: "var(--text-primary)" }}>{selectedSynthWell.field_name}</strong>
                  </div>
                  <div>
                    <span className="popup-label">Operator</span>
                    <strong style={{ display: "block", color: "var(--text-primary)" }}>{selectedSynthWell.operator}</strong>
                  </div>
                  <div>
                    <span className="popup-label">Target Formation</span>
                    <strong style={{ display: "block", color: "var(--teal-glow)" }}>{selectedSynthWell.target_formation}</strong>
                  </div>
                  <div>
                    <span className="popup-label">Total Depth</span>
                    <strong style={{ display: "block", color: "var(--text-primary)" }}>{selectedSynthWell.depth_m} m MD</strong>
                  </div>
                </div>

                <div className="table-wrapper" style={{ marginTop: "16px" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Hazard Type</th>
                        <th>Target Formation & Lithology</th>
                        <th>Incident Summary</th>
                        <th>Case File</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>
                          <span className="tag" style={{ textTransform: "capitalize" }}>
                            {readable(selectedSynthWell.event_type)}
                          </span>
                        </td>
                        <td>
                          <strong>{selectedSynthWell.target_formation}</strong>
                          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{selectedSynthWell.lithology}</div>
                        </td>
                        <td>
                          <em>"{selectedSynthWell.incident_summary}"</em>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="text-button"
                            onClick={() => {
                              setRecord({
                                id: selectedSynthWell.id,
                                well_name: selectedSynthWell.name,
                                event_type: selectedSynthWell.event_type,
                                data_kind: "synthetic",
                                start_md_m: selectedSynthWell.depth_m - 120,
                                end_md_m: selectedSynthWell.depth_m - 80,
                                description: selectedSynthWell.incident_summary,
                                source_datum: "MSL",
                                quality_issues: [],
                                evidence: [
                                  {
                                    passage_id: `synth-pass-${selectedSynthWell.id}`,
                                    document_id: `WCR-${selectedSynthWell.well_id}`,
                                    page_number: 1,
                                    filename: `WCR_${selectedSynthWell.well_id}.pdf`,
                                    quote: selectedSynthWell.incident_summary,
                                    text_version: 1,
                                    document_version: 1,
                                    raw_text: `FIELD INCIDENT RECORD: Well ${selectedSynthWell.name} (${selectedSynthWell.field_name}, ${selectedSynthWell.basin}). Formation: ${selectedSynthWell.target_formation}. Primary Hazard: ${selectedSynthWell.primary_hazard}. ${selectedSynthWell.incident_summary}`,
                                  },
                                ],
                                mitigation: [
                                  { id: "m-1", action_taken: `Sealed loss zone and conditioned mud system for ${selectedSynthWell.target_formation}` },
                                ],
                                event_outcome: [{ id: "o-1", outcome: "Wellbore stabilized; returns regained" }],
                                npt_event: [{ id: "npt-1", duration_h: 8 }],
                              });
                            }}
                          >
                            Open Case File →
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>
            ) : (
              <p className="notice">Select an offset well from the map or list to inspect historical correlation.</p>
            )
          )}

          {/* Tab 2: Depth Register & Logs */}
          {exploreTab === "depth" && (
            <div className="subsurface-logs-wrapper">
              <DepthTrack
                key={inspectOffset && selected ? selected : activeId}
                token={token}
                wellboreId={inspectOffset && selected ? selected : activeId}
                onOpenCase={openCase}
              />
            </div>
          )}

          {/* Tab 3: Pressure & Mud Window */}
          {exploreTab === "pressure" && (
            <div className="subsurface-logs-wrapper">
              <MudWindow
                key={inspectOffset && selected ? selected : activeId}
                token={token}
                wellboreId={inspectOffset && selected ? selected : activeId}
              />
            </div>
          )}

          {/* Tab 4: DDR & Incident Search */}
          {exploreTab === "search" && (
            <section className="explore-panel" aria-label="DDR and offset claim search">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Offset Document & DDR Search</p>
                  <h2>Search verified offset records.</h2>
                </div>
                <span>{active?.data_kind ?? "Indexed"}</span>
              </div>
              <p className="footnote">
                Hybrid semantic and keyword retrieval against approved DDRs, WCRs, and daily logs for this basin dataset.
              </p>

              <form onSubmit={performSearch} className="planning-controls" style={{ marginBottom: "16px" }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "10px", width: "100%" }}>
                  <div>
                    <label htmlFor="exp-search-q">Search query or symptom</label>
                    <input
                      id="exp-search-q"
                      type="text"
                      placeholder="e.g. mud losses Barail, stuck pipe..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>
                  <div>
                    <label htmlFor="exp-search-hazard">Hazard type</label>
                    <select
                      id="exp-search-hazard"
                      value={hazardFilter}
                      onChange={(e) => setHazardFilter(e.target.value)}
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
                    <label htmlFor="exp-search-from">Source MD from (m)</label>
                    <input
                      id="exp-search-from"
                      type="number"
                      min="0"
                      step="any"
                      placeholder="e.g. 1800"
                      value={minMd}
                      onChange={(e) => setMinMd(e.target.value)}
                    />
                  </div>
                  <div>
                    <label htmlFor="exp-search-to">Source MD to (m)</label>
                    <input
                      id="exp-search-to"
                      type="number"
                      min="0"
                      step="any"
                      placeholder="e.g. 2400"
                      value={maxMd}
                      onChange={(e) => setMaxMd(e.target.value)}
                    />
                  </div>
                </div>
                <div style={{ marginTop: "10px", display: "flex", gap: "10px" }}>
                  <button type="submit" disabled={searching}>
                    {searching ? "Searching verified archive…" : "Search Offset Records →"}
                  </button>
                  {searchResults && (
                    <button
                      type="button"
                      className="map-btn map-btn-subtle"
                      onClick={() => {
                        setSearchQuery("");
                        setHazardFilter("");
                        setMinMd("");
                        setMaxMd("");
                        setSearchResults(null);
                      }}
                    >
                      Clear search
                    </button>
                  )}
                </div>
              </form>

              {searchError && <p className="error" role="alert">{searchError}</p>}

              {searchResults && (
                <div aria-live="polite">
                  <p className="footnote">
                    {searchResults.retrieval_mode === "local_semantic"
                      ? `Related-meaning matches · ${searchResults.semantic_model}. ${searchResults.notice}`
                      : `Exact-term matches. ${searchResults.notice}`}
                  </p>
                  {searchResults.items.length ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {searchResults.items.map((r) => (
                        <article
                          className="search-hit"
                          key={r.id}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "flex-start",
                            padding: "14px",
                            background: "var(--glass-1)",
                            border: "1px solid var(--border)",
                            borderRadius: "var(--r-sm)",
                          }}
                        >
                          <div style={{ flex: 1, paddingRight: "16px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                              <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>{r.well_name}</strong>
                              <span className="case-drawer-badge">{readable(r.event_type)}</span>
                            </div>
                            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5, margin: "6px 0" }}>{r.description}</p>
                            <small style={{ color: "var(--teal-glow)", fontSize: "0.72rem", fontFamily: "var(--font-mono)" }}>
                              {r.citations.map((c) => `${c.filename} p.${c.page_number}`).join(" · ")}
                            </small>
                          </div>
                          <button
                            type="button"
                            className="text-button"
                            style={{ flexShrink: 0 }}
                            onClick={() => openCase(r.id)}
                          >
                            Inspect case file →
                          </button>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="notice">
                      No approved DDR or incident records match these filters.
                    </p>
                  )}
                  {searchResults.next_offset != null && (
                    <button
                      type="button"
                      style={{ marginTop: "12px" }}
                      disabled={searching}
                      onClick={() => performSearch(undefined, searchResults.next_offset!)}
                    >
                      Load more results
                    </button>
                  )}
                </div>
              )}
            </section>
          )}

          {/* Tab 5: Scenario Planning Desk */}
          {exploreTab === "planning" && active && (
            <section className="explore-panel" aria-label="Scenario location planning">
              <div className="planning-hint-banner">
                <div className="planning-hint-icon">📍</div>
                <div>
                  <strong>Interactive Coordinate Planning Scenario</strong>
                  <p>Click anywhere on the India/Basin map above to place or reposition your scenario planning point, or enter coordinates below.</p>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "12px", marginLeft: "auto", flexWrap: "wrap" }}>
                  <label htmlFor="plan-radius-input" style={{ fontSize: "0.75rem", color: "var(--ochre)", fontFamily: "var(--font-mono)", whiteSpace: "nowrap" }}>
                    Radius: {planRadius} km
                  </label>
                  <input
                    id="plan-radius-input"
                    type="range"
                    min="1"
                    max="50"
                    value={planRadius}
                    onChange={(e) => setPlanRadius(Number(e.target.value))}
                    style={{ width: "90px" }}
                  />
                  {planningPoint && (
                    <div className="planning-coords-chip">
                      <span className="mono">{planningPoint.latitude.toFixed(4)}°N, {planningPoint.longitude.toFixed(4)}°E</span>
                    </div>
                  )}
                </div>
              </div>

              <PlanningPanel
                token={token}
                datasetId={active.dataset_id}
                point={planningPoint}
                radius={planRadius}
                formationId={intervalId || null}
                onOpenCase={openCase}
              />
              <DepthTrack token={token} wellboreId={activeId} onOpenCase={openCase} />
              <MudWindow token={token} wellboreId={activeId} />
              <ReservoirPropertiesPanel token={token} wellboreId={activeId} />
              <CasingAndMudPanel token={token} wellboreId={activeId} />
            </section>
          )}

          {/* Tab 6: Cited Offset Brief */}
          {exploreTab === "brief" && (
            <div className="brief-container" style={{ marginTop: "16px" }}>
              <div className="brief-actions" style={{ marginBottom: "16px" }}>
                <button type="button" onClick={prepareBrief} disabled={briefLoading}>
                  {briefLoading ? "Preparing cited brief…" : "Prepare one-page offset brief"}
                </button>
                {brief && (
                  <button type="button" onClick={() => window.print()}>
                    Print / save as PDF
                  </button>
                )}
              </div>
              {brief ? (
                <OffsetBrief data={brief} />
              ) : (
                <p className="notice">
                  Click &ldquo;Prepare one-page offset brief&rdquo; to collate active well context, target formation, offset incidents, and cited report references into a printable shift dossier.
                </p>
              )}
            </div>
          )}
        </>
      )}

      {/* Case File Inspection Side Drawer */}
      {record && (
        <div
          className="case-drawer-backdrop"
          onClick={() => {
            setRecord(null);
            setSource(null);
            caseSequence.current++;
          }}
        >
          <aside
            className="case-drawer"
            role="dialog"
            aria-modal="true"
            aria-label={`Historical event case file: ${record.well_name} ${readable(record.event_type)}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="case-drawer-header">
              <div>
                <span className="case-drawer-eyebrow">
                  {record.data_kind} · Approved Historical Evidence
                </span>
                <h2 className="case-drawer-title">
                  {record.well_name} <span className="case-drawer-badge">{readable(record.event_type)}</span>
                </h2>
              </div>
              <button
                type="button"
                className="case-drawer-close"
                onClick={() => {
                  setRecord(null);
                  setSource(null);
                  caseSequence.current++;
                }}
                aria-label="Close case drawer (Esc)"
                title="Close (Esc)"
              >
                ✕
              </button>
            </div>

            <div className="case-drawer-body">
              <div className="case-drawer-desc">
                <p>{record.description}</p>
              </div>

              <div className="case-drawer-meta-strip">
                <div>
                  <span className="meta-label">Source MD Interval</span>
                  <span className="meta-val mono">{depth(record.start_md_m)} – {depth(record.end_md_m)}</span>
                </div>
                <div>
                  <span className="meta-label">Reference Datum</span>
                  <span className="meta-val">{record.source_datum ?? "Not specified on event"}</span>
                </div>
              </div>

              {!!record.quality_issues.length && (
                <div className="case-quality-alert">
                  <strong>⚠️ Quality issues noted:</strong> {record.quality_issues.map(readable).join(", ")}
                </div>
              )}

              <div className="case-facts-grid">
                <div className="case-fact-card">
                  <span className="fact-label">Recorded Response</span>
                  {record.mitigation.length ? (
                    record.mitigation.map((m) => (
                      <p key={m.id} className="fact-text">{m.action_taken}</p>
                    ))
                  ) : (
                    <p className="fact-muted">Not recorded in DDR</p>
                  )}
                </div>
                <div className="case-fact-card">
                  <span className="fact-label">Reported Outcome</span>
                  {record.event_outcome.length ? (
                    record.event_outcome.map((o) => (
                      <p key={o.id} className="fact-text">{readable(o.outcome)}</p>
                    ))
                  ) : (
                    <p className="fact-muted">Unknown outcome</p>
                  )}
                </div>
                <div className="case-fact-card">
                  <span className="fact-label">Reported NPT</span>
                  {record.npt_event.length ? (
                    record.npt_event.map((n) => (
                      <p key={n.id} className="fact-text mono" style={{ color: "var(--ochre)", fontWeight: 700 }}>
                        {n.duration_h} hours
                      </p>
                    ))
                  ) : (
                    <p className="fact-muted">No NPT attributed</p>
                  )}
                </div>
              </div>

              <div className="case-citations-section">
                <h3 className="section-subheading">Verified Source Citations</h3>
                <div className="citations-list">
                  {record.evidence.map((c) => (
                    <button
                      type="button"
                      className={`citation-chip ${source?.passage_id === c.passage_id ? "active" : ""}`}
                      key={c.passage_id}
                      onClick={() => openSource(c)}
                    >
                      <span className="citation-chip-file">📄 {c.filename}</span>
                      <span className="citation-chip-page">Page {c.page_number}</span>
                      <span className="citation-chip-ver">Doc v{c.document_version} / Text v{c.text_version}</span>
                    </button>
                  ))}
                </div>

                {source && (
                  <div className="case-source-quote">
                    <div className="quote-header">
                      <span className="quote-title">
                        {source.filename} · Page {source.page_number}
                      </span>
                      <span className="quote-badge">
                        {readable(source.representation ?? "Approved quote")}
                      </span>
                    </div>
                    <pre className="quote-text">
                      {source.raw_text ?? source.quote ?? "No verbatim excerpt available"}
                    </pre>
                  </div>
                )}
              </div>

              <p className="case-warning-note">
                ⓘ A recorded mitigation is a historical observation, not an operational endorsement or guarantee of cure.
              </p>
            </div>
          </aside>
        </div>
      )}
    </section>
  );
}
