import { FormEvent, useEffect, useRef, useState } from "react";
import { MitigationGraph, OperationalEvidence, PlanningPanel, PlanningPoint } from "./ExplorationExtras";

type Well = {
  id: string;
  well_id: string;
  name: string;
  dataset_id: string;
  data_kind: string;
  latitude: number;
  longitude: number;
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
  retrieval_mode: string;
  semantic_model: string | null;
  notice: string;
};

type SearchCapabilities = {
  full_text: boolean;
  semantic: boolean;
  semantic_model: string | null;
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

type TabType = "network" | "ledger" | "search" | "planning";

export default function Analytics({ token }: { token: string }) {
  const [wells, setWells] = useState<Well[]>([]);
  const [activeId, setActiveId] = useState("");
  const [activeTab, setActiveTab] = useState<TabType>("network");

  // Planning state
  const [planningPoint, setPlanningPoint] = useState<PlanningPoint | null>(null);
  const [planLat, setPlanLat] = useState("27.15");
  const [planLng, setPlanLng] = useState("94.85");
  const [planRadius, setPlanRadius] = useState(15);

  // Search state
  const [question, setQuestion] = useState("");
  const [searchMode, setSearchMode] = useState<"full_text" | "semantic">("full_text");
  const [searchCapabilities, setSearchCapabilities] = useState<SearchCapabilities | null>(null);
  const [hazard, setHazard] = useState("");
  const [minimum, setMinimum] = useState("");
  const [maximum, setMaximum] = useState("");
  const [results, setResults] = useState<SearchResult | null>(null);
  const [searching, setSearching] = useState(false);

  // Case & evidence state
  const [record, setRecord] = useState<Case | null>(null);
  const [source, setSource] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  const caseSequence = useRef(0);
  const requestSequence = useRef(0);

  const active = wells.find((w) => w.id === activeId);

  useEffect(() => {
    let live = true;
    request<SearchCapabilities>(token, "/search-capabilities")
      .then((data) => live && setSearchCapabilities(data))
      .catch(() => live && setSearchCapabilities(null));

    request<{ items: Well[] }>(token, "/intelligence/wellbores")
      .then((data) => {
        if (live) {
          setWells(data.items);
          const initial = data.items.find((w) => w.name === "SYN-A")?.id ?? data.items[0]?.id ?? "";
          setActiveId(initial);
          const found = data.items.find((w) => w.id === initial);
          if (found) {
            setPlanLat(found.latitude.toFixed(4));
            setPlanLng(found.longitude.toFixed(4));
            setPlanningPoint({ latitude: found.latitude, longitude: found.longitude });
          }
        }
      })
      .catch((e) => live && setError(e.message));

    return () => {
      live = false;
    };
  }, [token]);

  useEffect(() => {
    setResults(null);
    requestSequence.current++;
    setSearching(false);
  }, [question, hazard, minimum, maximum, activeId]);

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
          mode: searchMode,
          hazard: hazard || null,
          formation_id: null,
          min_md_m: minimum === "" ? null : Number(minimum),
          max_md_m: maximum === "" ? null : Number(maximum),
          limit: searchMode === "semantic" ? 5 : 10,
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

  function applyCoordPlanning(e: FormEvent) {
    e.preventDefault();
    const lat = parseFloat(planLat);
    const lng = parseFloat(planLng);
    if (!isNaN(lat) && !isNaN(lng)) {
      setPlanningPoint({ latitude: lat, longitude: lng });
    }
  }

  return (
    <section className="intelligence-workspace analytics-workspace">
      {/* Workspace Header */}
      <div className="archive-heading">
        <div>
          <p className="eyebrow">02 / Historical Correlate & Ledger</p>
          <h1>Response networks, operational history, and claim search.</h1>
          <p>
            Trace recorded mitigations across formations, evaluate NPT exposure, query approved historical claims, and inspect pre-drill planning points.
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

      {/* Dataset & Scope Selector */}
      <div className="atlas-controls analytics-controls">
        <div>
          <label htmlFor="analytics-well">Active wellbore context</label>
          <select
            id="analytics-well"
            value={activeId}
            onChange={(e) => {
              setActiveId(e.target.value);
              const found = wells.find((w) => w.id === e.target.value);
              if (found) {
                setPlanLat(found.latitude.toFixed(4));
                setPlanLng(found.longitude.toFixed(4));
                setPlanningPoint({ latitude: found.latitude, longitude: found.longitude });
              }
            }}
          >
            {wells.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} · {w.data_kind}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>Dataset scope</label>
          <div className="scope-badge">
            <span className="mono">{active?.dataset_id ?? "Default"}</span>
            <small>· {wells.length} wellbores indexed</small>
          </div>
        </div>
      </div>

      {/* Workspace Subview Tabs */}
      <div className="subview-tab-bar" role="tablist" aria-label="Correlation subviews">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "network"}
          className={`subview-tab-btn ${activeTab === "network" ? "active" : ""}`}
          onClick={() => setActiveTab("network")}
        >
          <span className="tab-num">01</span>
          <span className="tab-title">Response Network</span>
          <span className="tab-desc">Hazard mitigations</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "ledger"}
          className={`subview-tab-btn ${activeTab === "ledger" ? "active" : ""}`}
          onClick={() => setActiveTab("ledger")}
        >
          <span className="tab-num">02</span>
          <span className="tab-title">Operations Ledger & NPT</span>
          <span className="tab-desc">Exposure desk & formations</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "search"}
          className={`subview-tab-btn ${activeTab === "search" ? "active" : ""}`}
          onClick={() => setActiveTab("search")}
        >
          <span className="tab-num">03</span>
          <span className="tab-title">Record Search</span>
          <span className="tab-desc">Semantic & full-text query</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "planning"}
          className={`subview-tab-btn ${activeTab === "planning" ? "active" : ""}`}
          onClick={() => setActiveTab("planning")}
        >
          <span className="tab-num">04</span>
          <span className="tab-title">Pre-Drill Planning</span>
          <span className="tab-desc">Coordinate hazard analysis</span>
        </button>
      </div>

      {/* Tab 1: Response Network */}
      {activeTab === "network" && active && (
        <div className="tab-content-panel">
          <div className="tab-section-intro">
            <h2>Mitigation & Response Network</h2>
            <p className="footnote">
              Historical connections: Hazard event in formation → Recorded mitigation action → Reported effectiveness frequency.
              Click any count to inspect cited cases.
            </p>
          </div>
          <MitigationGraph token={token} datasetId={active.dataset_id} onOpenCase={openCase} />
        </div>
      )}

      {/* Tab 2: Operations Ledger & NPT Exposure */}
      {activeTab === "ledger" && active && (
        <div className="tab-content-panel">
          <div className="tab-section-intro">
            <h2>Special Operations Ledger & NPT Exposure</h2>
            <p className="footnote">
              Documented fishing and cementing operations with small-sample indicators, interactive rig day-rate cost exposure, and regional stratigraphy.
            </p>
          </div>
          <OperationalEvidence token={token} datasetId={active.dataset_id} onOpenCase={openCase} />
        </div>
      )}

      {/* Tab 3: Record Search */}
      {activeTab === "search" && (
        <div className="tab-content-panel">
          <section className="knowledge-search" style={{ borderTop: "none", marginTop: 0 }}>
            <div className="tab-section-intro">
              <h2>Search the Approved Record</h2>
              <p className="footnote">
                Search approved, cited claims in the active well’s dataset. No generated advice.
                Semantic matches are provisional candidates, not evidence of risk.
              </p>
            </div>
            <form onSubmit={search}>
              <div className="search-mode" role="group" aria-label="Search method">
                <button
                  type="button"
                  className={searchMode === "full_text" ? "selected" : ""}
                  aria-pressed={searchMode === "full_text"}
                  onClick={() => { setSearchMode("full_text"); setResults(null); }}
                >
                  Exact terms
                </button>
                <button
                  type="button"
                  className={searchMode === "semantic" ? "selected" : ""}
                  aria-pressed={searchMode === "semantic"}
                  disabled={!searchCapabilities?.semantic}
                  onClick={() => { setSearchMode("semantic"); setResults(null); }}
                >
                  Related meaning
                </button>
                {!searchCapabilities?.semantic && (
                  <span>Local semantic model not prepared</span>
                )}
              </div>
              <div className="search-primary">
                <label className="sr-only" htmlFor="evidence-query">
                  Search approved evidence
                </label>
                <input
                  id="evidence-query"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder='Try "mud losses" or "circulation disappeared"'
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
              </div>
            </form>
            {results && (
              <div aria-live="polite">
                <p className="footnote">
                  {results.retrieval_mode === "local_semantic"
                    ? `Related-meaning candidates · ${results.semantic_model}. ${results.notice}`
                    : `Exact-term matches. ${results.notice}`}
                </p>
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
        </div>
      )}

      {/* Tab 4: Pre-Drill Planning */}
      {activeTab === "planning" && active && (
        <div className="tab-content-panel">
          <div className="tab-section-intro">
            <h2>Pre-Drill Coordinate Planning Desk</h2>
            <p className="footnote">
              Test hypothetical surface coordinates against the reviewed wellbore archive. Calculates historical hazard density within the target radius.
            </p>
          </div>
          <form onSubmit={applyCoordPlanning} className="plan-coords-form">
            <div>
              <label htmlFor="plan-lat">Target Latitude (°N)</label>
              <input
                id="plan-lat"
                type="number"
                step="any"
                value={planLat}
                onChange={(e) => setPlanLat(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="plan-lng">Target Longitude (°E)</label>
              <input
                id="plan-lng"
                type="number"
                step="any"
                value={planLng}
                onChange={(e) => setPlanLng(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="plan-rad">Inspection Radius: {planRadius} km</label>
              <input
                id="plan-rad"
                type="range"
                min="1"
                max="50"
                value={planRadius}
                onChange={(e) => setPlanRadius(Number(e.target.value))}
              />
            </div>
            <button type="submit" className="plan-apply-btn">
              Update Planning Point
            </button>
          </form>

          <PlanningPanel
            token={token}
            datasetId={active.dataset_id}
            point={planningPoint}
            radius={planRadius}
            formationId={null}
            onOpenCase={openCase}
          />
        </div>
      )}

      {/* Case File Detail Modal/Panel */}
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
