import { useEffect, useState } from "react";

type Readiness = {
  hazard: string;
  horizon_m: number;
  state: string;
  gates: string[];
  features: string[];
  note: string;
  inventory_note: string;
  historical_inventory: {
    kind: string;
    approved_events: number;
    physical_wells: number;
  }[];
};

export default function Prediction({ token }: { token: string }) {
  const [data, setData] = useState<Readiness | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/prediction/readiness", {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load model readiness");
        const result = await response.json();
        if (!controller.signal.aborted) setData(result);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [token]);
  return (
    <section className="operations">
      <div className="archive-heading">
        <div>
          <p className="eyebrow">Predictive validation / Phase 05</p>
          <h1>Evidence before confidence.</h1>
          <p>A model must earn its place beside the historical record.</p>
        </div>
        <span className="state">NO TRAINED MODEL</span>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p role="status">Loading model readiness…</p>}
      {data && (
        <>
          <div className="grid">
            <article className="card">
              <p className="eyebrow">First research target</p>
              <h2>Mud loss · next {data.horizon_m} m</h2>
              <p>
                Proposed forward-drilling horizon. Not yet validated for
                operational use.
              </p>
              <p>{data.note}</p>
            </article>
            <article className="card">
              <p className="eyebrow">Prediction status</p>
              <h2>Awaiting qualified data</h2>
              <p>
                Risk score: unavailable. Held-out metrics: unavailable.
                Calibration: not evaluated.
              </p>
              <p>
                Acknowledgments and “no incident observed” feedback are not
                ground-truth labels.
              </p>
            </article>
            <article className="card wide">
              <h2>What the archive can—and cannot—tell us</h2>
              <p>{data.inventory_note}</p>
              {data.historical_inventory.length ? (
                <ul>
                  {data.historical_inventory.map((row) => (
                    <li key={row.kind}>
                      {row.kind}: {row.approved_events} reviewed mud-loss events
                      across {row.physical_wells} physical wells
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No approved mud-loss events in the archive.</p>
              )}
              <p>
                Required next: permitted telemetry, reviewed event onsets,
                complete no-event observation windows, original well identities,
                units, and source provenance.
              </p>
            </article>
            <article className="card wide">
              <h2>Before the first score</h2>
              <ol>
                {data.gates.map((gate) => (
                  <li key={gate}>{gate}</li>
                ))}
              </ol>
              <details>
                <summary>Proposed feature contract</summary>
                <ul>
                  {data.features.map((feature) => (
                    <li key={feature}>{feature.replaceAll("_", " ")}</li>
                  ))}
                </ul>
                <p>
                  Only pre-anchor values; no outcome text or future
                  measurements. Suitability still requires domain review.
                </p>
              </details>
            </article>
          </div>
        </>
      )}
    </section>
  );
}
