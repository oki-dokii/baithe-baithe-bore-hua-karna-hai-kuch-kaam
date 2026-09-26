import { FormEvent, Suspense, lazy, useEffect, useState } from "react";
import Documents from "./Documents";
const Intelligence = lazy(() => import("./Intelligence"));
import Operations from "./Operations";
import Prediction from "./Prediction";

type Component = { state: string; detail: string | null };
type Status = {
  environment: string;
  source_mode: string;
  database: Component;
  spatial: Component;
  vector: Component;
  ingestion: Component;
  replay: Component;
  prediction: Component;
  datasets: string[];
  checked_at: string;
};
type Well = {
  id: string;
  external_id: string;
  name: string;
  basin_name: string | null;
  data_kind: string;
  longitude: number;
  latitude: number;
  surface_distance_m: number | null;
};
type WellPage = { items: Well[]; next_cursor: string | null };

async function getJson<T>(path: string, token: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      data.error?.message ?? `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

function StateTag({ state }: { state: string }) {
  return (
    <span className={`state state-${state}`}>{state.replaceAll("_", " ")}</span>
  );
}

export default function App() {
  const [token, setToken] = useState("");
  const [entered, setEntered] = useState("");
  const [status, setStatus] = useState<Status | null>(null);
  const [wells, setWells] = useState<Well[]>([]);
  const [selected, setSelected] = useState("");
  const [nearby, setNearby] = useState<Well[]>([]);
  const [radius, setRadius] = useState(5);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<
    "documents" | "intelligence" | "foundation" | "operations" | "prediction"
  >("operations");

  useEffect(() => {
    if (!entered) return;
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      getJson<Status>("/api/v1/status", entered),
      getJson<WellPage>("/api/v1/wells", entered),
    ])
      .then(([s, page]) => {
        if (!active) return;
        setStatus(s);
        setWells(page.items);
        setSelected(
          page.items.find((w) => w.external_id === "SYN-A")?.id ??
            page.items[0]?.id ??
            "",
        );
      })
      .catch((e: Error) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [entered]);

  useEffect(() => {
    if (!entered || !selected) return;
    let active = true;
    const path = `/api/v1/wells/nearby?active_well_id=${selected}&radius_km=${radius}`;
    getJson<WellPage>(path, entered)
      .then((page) => {
        if (active) setNearby(page.items);
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [entered, selected, radius]);

  function signIn(event: FormEvent) {
    event.preventDefault();
    setEntered(token.trim());
    setToken("");
  }

  const selectedWell = wells.find((w) => w.id === selected);
  const components: Array<[string, Component]> = status
    ? [
        ["Database", status.database],
        ["Spatial", status.spatial],
        ["Vector", status.vector],
        ["Ingestion", status.ingestion],
        ["Replay", status.replay],
        ["Prediction", status.prediction],
      ]
    : [];

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">N</span>
          <div>
            <strong>NWIS</strong>
            <small>Nearby Wells Intelligence System</small>
          </div>
        </div>
        <span className="phase">FIELD NOTES / NWIS</span>
        {status && (
          <button
            className="text-button"
            onClick={() => {
              setEntered("");
              setStatus(null);
              setWells([]);
              setNearby([]);
              setError("");
            }}
          >
            Disconnect
          </button>
        )}
      </header>
      <main>
        {!status && (
          <div className="intro">
            <p className="eyebrow">OIL · SIH prototype</p>
            <h1>
              What one well teaches,
              <br />
              the next should know.
            </h1>
            <p>
              A working archive of drilling experience. Source-led,
              human-reviewed, and built to keep the details that matter.
            </p>
          </div>
        )}

        {!status && (
          <form className="auth card" onSubmit={signIn}>
            <label htmlFor="token">Local access token</label>
            <p>
              Use a local access token. Reviewers inspect source pages and
              approve evidence; viewers see approved claims. Your token stays in
              memory.
            </p>
            <div className="form-row">
              <input
                id="token"
                type="password"
                required
                minLength={16}
                value={token}
                onChange={(e) => setToken(e.target.value)}
              />
              <button type="submit">Connect</button>
            </div>
          </form>
        )}

        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        {loading && <p role="status">Loading platform state…</p>}

        {status && (
          <>
            <nav className="workspace-nav" aria-label="Workspace">
              <button
                className={view === "operations" ? "active" : ""}
                onClick={() => setView("operations")}
              >
                00 <span>Operations</span>
              </button>
              <button
                className={view === "documents" ? "active" : ""}
                onClick={() => setView("documents")}
              >
                01 <span>Evidence room</span>
              </button>
              <button
                className={view === "intelligence" ? "active" : ""}
                onClick={() => setView("intelligence")}
              >
                02 <span>Well intelligence</span>
              </button>
              <button
                className={view === "foundation" ? "active" : ""}
                onClick={() => setView("foundation")}
              >
                03 <span>Well directory</span>
              </button>
              <button
                className={view === "prediction" ? "active" : ""}
                onClick={() => setView("prediction")}
              >
                04 <span>Model readiness</span>
              </button>
            </nav>
            {view === "documents" ? (
              <Documents token={entered} />
            ) : view === "intelligence" ? (
              <Suspense
                fallback={<p role="status">Loading the offset atlas…</p>}
              >
                <Intelligence token={entered} />
              </Suspense>
            ) : view === "operations" ? (
              <Operations token={entered} />
            ) : view === "prediction" ? (
              <Prediction token={entered} />
            ) : (
              <>
                <div className="statusline">
                  <span className="live-dot" /> {status.source_mode} DATA ·{" "}
                  {status.environment.toUpperCase()} ENVIRONMENT{" "}
                  <span className="timestamp">
                    Checked {new Date(status.checked_at).toLocaleString()}
                  </span>
                </div>
                <section className="grid">
                  <div className="card wide">
                    <div className="section-heading">
                      <h2>Platform status</h2>
                      <span>
                        {status.datasets.length
                          ? status.datasets.join(", ")
                          : "No datasets loaded"}
                      </span>
                    </div>
                    <div className="component-grid">
                      {components.map(([name, component]) => (
                        <div className="component" key={name}>
                          <span>{name}</span>
                          <StateTag state={component.state} />
                          {component.detail && (
                            <small>{component.detail}</small>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="card">
                    <div className="section-heading">
                      <h2>Well selector</h2>
                      <span>{wells.length} loaded</span>
                    </div>
                    {wells.length ? (
                      <>
                        <label htmlFor="well">Active well</label>
                        <select
                          id="well"
                          value={selected}
                          onChange={(e) => setSelected(e.target.value)}
                        >
                          {wells.map((well) => (
                            <option key={well.id} value={well.id}>
                              {well.name} · {well.data_kind}
                            </option>
                          ))}
                        </select>
                        {selectedWell && (
                          <div className="well-meta">
                            <strong>{selectedWell.external_id}</strong>
                            <span>
                              {selectedWell.basin_name ?? "Basin unknown"}
                            </span>
                            <span>
                              {selectedWell.latitude.toFixed(4)}° N,{" "}
                              {selectedWell.longitude.toFixed(4)}° E
                            </span>
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="muted">
                        Load the golden fixture to see demonstration wells.
                      </p>
                    )}
                  </div>
                  <div className="card">
                    <div className="section-heading">
                      <h2>Nearby wells</h2>
                      <span>Surface distance</span>
                    </div>
                    <label htmlFor="radius">Search radius · {radius} km</label>
                    <input
                      id="radius"
                      type="range"
                      min="1"
                      max="25"
                      value={radius}
                      onChange={(e) => setRadius(Number(e.target.value))}
                      disabled={!selected}
                    />
                    {selected ? (
                      <ul className="well-list">
                        {nearby.length ? (
                          nearby.map((well) => (
                            <li key={well.id}>
                              <div>
                                <strong>{well.name}</strong>
                                <small>
                                  {well.data_kind} · {well.basin_name}
                                </small>
                              </div>
                              <span>
                                {(
                                  (well.surface_distance_m ?? 0) / 1000
                                ).toFixed(2)}{" "}
                                km
                              </span>
                            </li>
                          ))
                        ) : (
                          <li>No wells within this radius.</li>
                        )}
                      </ul>
                    ) : (
                      <p className="muted">Select an active well first.</p>
                    )}
                    <p className="footnote">
                      Nearby wells are selected by surface distance. Formation
                      correlation is planned for Phase 3.
                    </p>
                  </div>
                </section>
              </>
            )}
          </>
        )}
      </main>
      <footer>
        <strong>NWIS</strong>
        <span>Historical knowledge. Traceable evidence.</span>
        <span>
          SIH prototype · Decision support, not operational instruction
        </span>
      </footer>
    </div>
  );
}
