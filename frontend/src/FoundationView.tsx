import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Component, Status, Well } from "./types";
import { StateBadge } from "./Sidebar";

function GeospatialWellMap({
  active,
  allWells,
  nearbyWells,
  radiusKm,
  onSelect,
}: {
  active?: Well;
  allWells: Well[];
  nearbyWells: Well[];
  radiusKm: number;
  onSelect: (id: string) => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const callback = useRef(onSelect);
  callback.current = onSelect;

  useEffect(() => {
    if (!root.current || !active) return;

    const map = L.map(root.current, {
      center: [active.latitude, active.longitude],
      zoom: 12,
      scrollWheelZoom: true,
      attributionControl: false,
    });

    // Circular radius ring around active well
    const radiusCircle = L.circle([active.latitude, active.longitude], {
      radius: radiusKm * 1000,
      color: "#06b6d4",
      weight: 2,
      dashArray: "6 6",
      fillColor: "#0891b2",
      fillOpacity: 0.12,
    }).addTo(map);

    const bounds = radiusCircle.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds.pad(0.18), { padding: [30, 30], maxZoom: 13 });
    }

    // High-tech coordinate grid (dark GIS aesthetic)
    const gridBounds = bounds.pad(0.35);
    const step = Math.max(
      0.005,
      Math.pow(10, Math.floor(Math.log10(Math.max(0.01, gridBounds.getNorth() - gridBounds.getSouth()) / 4))),
    );

    for (let lat = Math.floor(gridBounds.getSouth() / step) * step; lat <= gridBounds.getNorth(); lat += step) {
      L.polyline([[lat, gridBounds.getWest()], [lat, gridBounds.getEast()]], {
        color: "#334155",
        weight: 1,
        opacity: 0.4,
        interactive: false,
      }).addTo(map);
    }

    for (let lon = Math.floor(gridBounds.getWest() / step) * step; lon <= gridBounds.getEast(); lon += step) {
      L.polyline([[gridBounds.getSouth(), lon], [gridBounds.getNorth(), lon]], {
        color: "#334155",
        weight: 1,
        opacity: 0.4,
        interactive: false,
      }).addTo(map);
    }

    const nearbyIds = new Set(nearbyWells.map((w) => w.id));

    // Plot all loaded wells
    for (const well of allWells) {
      const isActive = well.id === active.id;
      const isNearby = nearbyIds.has(well.id);

      const label = document.createElement("div");
      label.style.fontFamily = "var(--font-mono, monospace)";
      label.style.fontSize = "11px";
      label.innerHTML = `<strong>${well.name}</strong><br/>${
        isActive
          ? '<span style="color:#f59e0b">● Active Well</span>'
          : isNearby
          ? `<span style="color:#10b981">● In Radius (${((well.surface_distance_m ?? 0) / 1000).toFixed(2)} km)</span>`
          : '<span style="color:#94a3b8">○ Outside Radius</span>'
      }`;

      const marker = L.circleMarker([well.latitude, well.longitude], {
        radius: isActive ? 10 : isNearby ? 8 : 5,
        fillColor: isActive ? "#f59e0b" : isNearby ? "#10b981" : "#475569",
        color: isActive ? "#fbbf24" : isNearby ? "#34d399" : "#64748b",
        weight: isActive ? 3 : isNearby ? 2 : 1,
        fillOpacity: isActive ? 1 : isNearby ? 0.9 : 0.45,
      })
        .addTo(map)
        .bindTooltip(label, {
          permanent: isActive,
          direction: "top",
          offset: [0, -8],
        });

      if (!isActive) {
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
  }, [active, allWells, nearbyWells, radiusKm]);

  if (!active) {
    return (
      <div className="card-body" style={{ textAlign: "center", padding: "60px 20px", color: "var(--text-muted)" }}>
        Select a well to initialize geospatial proximity mapping.
      </div>
    );
  }

  return (
    <div style={{ position: "relative", height: "420px", width: "100%", borderRadius: "8px", overflow: "hidden" }}>
      <div
        ref={root}
        style={{ height: "100%", width: "100%" }}
        role="region"
        aria-label="Geospatial nearby well map"
      />
      <div className="map-caption">
        <span>Active: <strong>{active.name}</strong> ({active.latitude.toFixed(4)}°N, {active.longitude.toFixed(4)}°E)</span>
        <span>Radius: <strong className="text-teal">{radiusKm} km</strong> ({nearbyWells.length} wells in range) · Click offset to switch</span>
      </div>
    </div>
  );
}

interface FoundationViewProps {
  wells: Well[];
  nearby: Well[];
  selected: string;
  radius: number;
  onSelect: (id: string) => void;
  onRadius: (r: number) => void;
  status: Status;
}

export default function FoundationView({
  wells,
  nearby,
  selected,
  radius,
  onSelect,
  onRadius,
  status,
}: FoundationViewProps) {
  const selectedWell = wells.find((w) => w.id === selected);
  const components: [string, Component][] = [
    ["Database", status.database],
    ["Spatial", status.spatial],
    ["Vector", status.vector],
    ["Ingestion", status.ingestion],
    ["Replay", status.replay],
    ["Prediction", status.prediction],
  ];

  return (
    <div className="workspace">
      <div className="workspace-header">
        <div>
          <p className="ws-eyebrow"><span className="plate-num">04</span> Well Directory</p>
          <h1 className="ws-title">Well directory &amp; platform</h1>
          <p className="ws-desc">Browse loaded wells, configure search radius, and inspect platform component status.</p>
        </div>
        <StateBadge state={`${status.source_mode} · ${status.environment}`} />
      </div>

      <div className="workspace-body">
        {/* Platform status */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <span className="live-dot" aria-hidden="true" />
              Platform Status
            </span>
            <span className="mono-sm">
              {status.datasets.length ? status.datasets.join(", ") : "No datasets"}
            </span>
          </div>
          <div className="card-body">
            <div className="status-grid">
              {components.map(([name, comp]) => (
                <div className="status-cell" key={name}>
                  <span className="status-cell-name">{name}</span>
                  <StateBadge state={comp.state} />
                  {comp.detail && <span className="status-cell-detail">{comp.detail}</span>}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="two-col">
          {/* Well selector */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Well Selector</span>
              <span className="mono-sm">{wells.length} loaded</span>
            </div>
            <div className="card-body">
              {wells.length ? (
                <>
                  <div className="field">
                    <label className="field-label" htmlFor="well-select">Active well</label>
                    <select
                      id="well-select"
                      value={selected}
                      onChange={(e) => onSelect(e.target.value)}
                    >
                      {wells.map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name} · {w.data_kind}
                        </option>
                      ))}
                    </select>
                  </div>
                  {selectedWell && (
                    <div className="well-meta-block">
                      <div className="well-id-big">{selectedWell.external_id}</div>
                      <div className="well-coord">{selectedWell.basin_name ?? "Basin unknown"}</div>
                      <div className="well-coord">
                        {selectedWell.latitude.toFixed(4)}° N, {selectedWell.longitude.toFixed(4)}° E
                      </div>
                      <StateBadge state={selectedWell.data_kind} />
                    </div>
                  )}
                </>
              ) : (
                <p className="text-muted" style={{ fontSize: "0.875rem" }}>
                  Load the golden fixture to see demonstration wells.
                </p>
              )}
            </div>
          </div>

          {/* Nearby wells */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Nearby Wells</span>
              <span className="mono-sm">Surface distance</span>
            </div>
            <div className="card-body">
              <div className="field">
                <label className="field-label" htmlFor="radius-input">
                  Search radius · <span className="text-teal">{radius} km</span>
                </label>
                <input
                  id="radius-input"
                  type="range"
                  min="1"
                  max="25"
                  value={radius}
                  onChange={(e) => onRadius(Number(e.target.value))}
                  disabled={!selected}
                />
              </div>
              {selected ? (
                <>
                  {nearby.length ? (
                    nearby.map((w) => (
                      <div className="well-entry" key={w.id}>
                        <div className="well-entry-info">
                          <span className="well-entry-name">{w.name}</span>
                          <span className="well-entry-meta">
                            {w.data_kind} · {w.basin_name}
                          </span>
                        </div>
                        <span className="well-entry-dist">
                          {((w.surface_distance_m ?? 0) / 1000).toFixed(2)} km
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-muted" style={{ fontSize: "0.875rem" }}>No wells within {radius} km radius.</p>
                  )}
                  <p className="mono-sm" style={{ marginTop: "12px", lineHeight: 1.6 }}>
                    Nearby wells selected by surface distance. Formation correlation planned for Phase 3.
                  </p>
                </>
              ) : (
                <p className="text-muted" style={{ fontSize: "0.875rem" }}>Select an active well first.</p>
              )}
            </div>
          </div>
        </div>

        {/* Interactive Geospatial Map */}
        <div className="card" style={{ marginTop: "16px" }}>
          <div className="card-header">
            <span className="card-title">
              <span className="live-dot" aria-hidden="true" />
              Geospatial Offset Proximity Map
            </span>
            <span className="mono-sm">
              {selectedWell ? `${selectedWell.name} · ${radius} km radius` : "Select a well"}
            </span>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            <GeospatialWellMap
              active={selectedWell}
              allWells={wells}
              nearbyWells={nearby}
              radiusKm={radius}
              onSelect={onSelect}
            />
          </div>
        </div>

        <p className="mono-sm">
          Checked {new Date(status.checked_at).toLocaleString()}
        </p>
      </div>
    </div>
  );
}
