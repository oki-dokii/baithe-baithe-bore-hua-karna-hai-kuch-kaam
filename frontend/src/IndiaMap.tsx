import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  ALL_SYNTHETIC_WELLS,
  BASIN_REGISTRY,
  BasinKey,
  SyntheticBasinWell,
  haversineKm,
} from "./syntheticWellsData";

/* ── Types ────────────────────────────────────────────────────── */
export type MapWell = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  data_kind: string;
  well_id?: string;
  dataset_id?: string;
  basin?: string;
  surface_distance_m?: number;
  similarity_score?: number;
  event_count?: number;
  field_name?: string;
  target_formation?: string;
  depth_m?: number;
  primary_hazard?: string;
  incident_summary?: string;
  operator?: string;
  event_type?: string;
};

export type MapFilters = {
  basin: string;
  eventType: string;
  minRadius: number;
  maxRadius: number;
};

type IndiaMapProps = {
  active: MapWell;
  candidates: MapWell[];
  radius: number;
  proximityBasis: "surface" | "terminal_bottomhole";
  selectedId: string;
  onSelect: (id: string) => void;
  compact?: boolean;
  onExploreClick?: () => void;
  planningPoint?: { latitude: number; longitude: number } | null;
  onMapClick?: (lat: number, lng: number) => void;
};

/* ── India bounding box ───────────────────────────────────────── */
const INDIA_BOUNDS: L.LatLngBoundsExpression = [
  [6.5, 68.0],   // SW
  [37.0, 97.5],  // NE
];

const INDIA_CENTER: L.LatLngExpression = [22.5, 82.0];

/* ── Custom well marker icons ─────────────────────────────────── */
function wellIcon(
  type: "active" | "selected" | "offset" | "planning" | "basin-synth",
  hazardType?: string,
): L.DivIcon {
  const sizes: Record<string, number> = {
    active: 16,
    selected: 14,
    offset: 10,
    planning: 10,
    "basin-synth": 11,
  };
  const size = sizes[type] || 10;
  const hazardClass = hazardType ? ` hazard-${hazardType}` : "";
  return L.divIcon({
    className: `well-pin well-pin-${type}${hazardClass}`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2 - 4],
  });
}

/* ── Standard Well Detail Popup HTML ──────────────────────────── */
function wellPopupHtml(well: MapWell, isActive: boolean, activeWell?: MapWell): string {
  const distM =
    well.surface_distance_m != null
      ? well.surface_distance_m
      : activeWell && !isActive
      ? haversineKm(activeWell.latitude, activeWell.longitude, well.latitude, well.longitude) * 1000
      : null;

  const distLabel =
    distM != null
      ? `<div class="popup-row"><span class="popup-label">Surface separation</span><span class="popup-val">${(distM / 1000).toFixed(2)} km</span></div>`
      : "";
  const scoreLabel =
    well.similarity_score != null
      ? `<div class="popup-row"><span class="popup-label">Similarity</span><span class="popup-val">${(well.similarity_score * 100).toFixed(0)} / 100 · not risk</span></div>`
      : "";
  return `
    <div class="well-popup">
      <div class="popup-header">
        <span class="popup-name">${well.name}</span>
        <span class="popup-badge popup-badge-${isActive ? "active" : "offset"}">${isActive ? "ACTIVE" : "OFFSET"}</span>
      </div>
      <div class="popup-badge popup-badge-synth">SYNTHETIC DEMO</div>
      <div class="popup-row"><span class="popup-label">Well ID</span><span class="popup-val mono">${well.well_id ?? well.id.slice(0, 8)}</span></div>
      <div class="popup-row"><span class="popup-label">Dataset</span><span class="popup-val">${well.data_kind}</span></div>
      ${well.basin ? `<div class="popup-row"><span class="popup-label">Basin</span><span class="popup-val">${well.basin}</span></div>` : ""}
      <div class="popup-row"><span class="popup-label">Coordinates</span><span class="popup-val mono">${well.latitude.toFixed(4)}°N, ${well.longitude.toFixed(4)}°E</span></div>
      ${distLabel}
      ${scoreLabel}
      ${well.event_count != null ? `<div class="popup-row"><span class="popup-label">Events</span><span class="popup-val">${well.event_count} approved</span></div>` : ""}
      <div class="popup-provenance">Location: synthetic fixture · WGS 84</div>
    </div>
  `;
}

/* ── Regional Basin Synthetic Well Popup HTML ─────────────────── */
function synthWellPopupHtml(well: SyntheticBasinWell, active: MapWell): string {
  const distKm = haversineKm(active.latitude, active.longitude, well.latitude, well.longitude);
  const hazardColor =
    well.event_type === "mud_loss"
      ? "var(--ochre-bright)"
      : well.event_type === "kick"
      ? "#f87171"
      : well.event_type === "stuck_pipe"
      ? "#c084fc"
      : well.event_type === "abnormal_pressure"
      ? "#fb923c"
      : well.event_type === "tight_hole"
      ? "#facc15"
      : "var(--teal-glow)";

  return `
    <div class="well-popup">
      <div class="popup-header">
        <span class="popup-name">${well.name}</span>
        <span class="popup-badge popup-badge-synth-basin">${well.basin}</span>
      </div>
      <div class="popup-badge popup-badge-synth">SYNTHETIC FIXTURE · ${well.state}</div>
      <div class="popup-row"><span class="popup-label">Field</span><span class="popup-val">${well.field_name}</span></div>
      <div class="popup-row"><span class="popup-label">Operator</span><span class="popup-val">${well.operator}</span></div>
      <div class="popup-row"><span class="popup-label">Target Formation</span><span class="popup-val font-semibold" style="color: var(--teal-glow);">${well.target_formation}</span></div>
      <div class="popup-row"><span class="popup-label">Total Depth</span><span class="popup-val mono">${well.depth_m} m MD</span></div>
      <div class="popup-row"><span class="popup-label">Distance to Active</span><span class="popup-val mono">${distKm < 50 ? `${distKm.toFixed(1)} km (Nearby)` : `${distKm.toFixed(0)} km`}</span></div>
      <div class="popup-row"><span class="popup-label">Primary Hazard</span><span class="popup-val" style="color: ${hazardColor}; font-weight: 600;">${well.primary_hazard}</span></div>
      <div class="popup-row"><span class="popup-label">Coordinates</span><span class="popup-val mono">${well.latitude.toFixed(4)}°N, ${well.longitude.toFixed(4)}°E</span></div>
      ${well.incident_summary ? `<div class="popup-quote">"${well.incident_summary}"</div>` : ""}
      <div class="popup-provenance">Geologically calibrated demo fixture · WGS 84</div>
    </div>
  `;
}

/* ═══════════════════════════════════════════════════════════════
   IndiaWellMap Component
   ═══════════════════════════════════════════════════════════════ */
export default function IndiaWellMap({
  active,
  candidates,
  radius,
  proximityBasis,
  selectedId,
  onSelect,
  compact = false,
  onExploreClick,
  planningPoint,
  onMapClick,
}: IndiaMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);
  const radiusCircleRef = useRef<L.Circle | null>(null);
  const callbackRef = useRef(onSelect);
  callbackRef.current = onSelect;
  const mapClickRef = useRef(onMapClick);
  mapClickRef.current = onMapClick;

  const [mapReady, setMapReady] = useState(false);
  const [showProvenance, setShowProvenance] = useState(false);
  const [basinFilter, setBasinFilter] = useState<BasinKey>("all");
  const [showAllBasins, setShowAllBasins] = useState(true);

  /* ── Filtered regional synthetic wells ────────────────────────── */
  const visibleRegionalWells = useMemo(() => {
    if (!showAllBasins) return [];
    return ALL_SYNTHETIC_WELLS.filter((w) => {
      // Filter by basin tab if not "all"
      if (basinFilter !== "all" && w.basin_key !== basinFilter) return false;
      // Skip active well (it gets special active pin & pulse)
      if (w.id === active.id || (Math.abs(w.latitude - active.latitude) < 0.001 && Math.abs(w.longitude - active.longitude) < 0.001)) {
        return false;
      }
      // Skip candidate offsets (they get offset pins)
      if (candidates.some((c) => c.id === w.id || (Math.abs(c.latitude - w.latitude) < 0.001 && Math.abs(c.longitude - w.longitude) < 0.001))) {
        return false;
      }
      return true;
    });
  }, [basinFilter, showAllBasins, active, candidates]);

  /* ── Initialize Map ─────────────────────────────────────────── */
  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;

    const map = L.map(mapRef.current, {
      center: INDIA_CENTER,
      zoom: 5,
      minZoom: 4,
      maxZoom: 16,
      zoomControl: false,
      attributionControl: false,
      maxBounds: [
        [2, 60],
        [40, 102],
      ],
      maxBoundsViscosity: 0.8,
    });

    /* India States & UTs layer — loaded from /india-states.geojson (37 States & UTs) */
    fetch("/india-states.geojson")
      .then((res) => res.json())
      .then((geojsonData: GeoJSON.FeatureCollection) => {
        L.geoJSON(geojsonData, {
          style: (feature) => {
            const name = feature?.properties?.name || "";
            const isAssam = name === "Assam";
            const isOilState = ["Assam", "Gujarat", "Rajasthan", "Andhra Pradesh", "Tamil Nadu", "Maharashtra"].includes(name);
            return {
              color: isAssam
                ? "rgba(94, 234, 212, 0.75)"
                : isOilState
                ? "rgba(94, 234, 212, 0.45)"
                : "rgba(94, 234, 212, 0.28)",
              weight: isAssam ? 1.8 : isOilState ? 1.2 : 0.9,
              fillColor: isAssam
                ? "rgba(34, 168, 178, 0.18)"
                : isOilState
                ? "rgba(34, 168, 178, 0.08)"
                : "rgba(34, 168, 178, 0.03)",
              fillOpacity: 1,
              dashArray: isAssam ? "" : "3 3",
            };
          },
          onEachFeature: (feature, layer) => {
            const name = feature.properties?.name || "";
            layer.bindTooltip(name, {
              sticky: true,
              className: "state-tooltip",
              direction: "top",
              offset: [0, -8],
            });
            layer.on({
              mouseover: (e) => {
                const target = e.target;
                target.setStyle({
                  weight: 2,
                  color: "rgba(94, 234, 212, 0.95)",
                  fillColor: "rgba(34, 168, 178, 0.24)",
                  fillOpacity: 1,
                });
                target.bringToFront();
              },
              mouseout: (e) => {
                const target = e.target;
                const isAssam = name === "Assam";
                const isOilState = ["Assam", "Gujarat", "Rajasthan", "Andhra Pradesh", "Tamil Nadu", "Maharashtra"].includes(name);
                target.setStyle({
                  color: isAssam
                    ? "rgba(94, 234, 212, 0.75)"
                    : isOilState
                    ? "rgba(94, 234, 212, 0.45)"
                    : "rgba(94, 234, 212, 0.28)",
                  weight: isAssam ? 1.8 : isOilState ? 1.2 : 0.9,
                  fillColor: isAssam
                    ? "rgba(34, 168, 178, 0.18)"
                    : isOilState
                    ? "rgba(34, 168, 178, 0.08)"
                    : "rgba(34, 168, 178, 0.03)",
                  fillOpacity: 1,
                  dashArray: isAssam ? "" : "3 3",
                });
              },
            });
          },
        }).addTo(map);
      })
      .catch((err) => {
        console.warn("Failed to load India states GeoJSON:", err);
      });

    /* India National Boundary outer glow — loaded from /india-boundary.geojson */
    fetch("/india-boundary.geojson")
      .then((res) => res.json())
      .then((geojsonData: GeoJSON.FeatureCollection) => {
        L.geoJSON(geojsonData, {
          style: () => ({
            color: "rgba(94, 234, 212, 0.8)",
            weight: 2.2,
            fillOpacity: 0,
          }),
          interactive: false,
        }).addTo(map);
      })
      .catch((err) => {
        console.warn("Failed to load India boundary GeoJSON:", err);
      });

    /* Zoom controls positioned top-right */
    L.control.zoom({ position: "topright" }).addTo(map);
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);

    /* Resize observer */
    const resizer = new ResizeObserver(() => map.invalidateSize());
    resizer.observe(mapRef.current);

    mapInstance.current = map;
    markersRef.current = L.layerGroup().addTo(map);
    setMapReady(true);

    return () => {
      resizer.disconnect();
      map.remove();
      mapInstance.current = null;
      markersRef.current = null;
      setMapReady(false);
    };
  }, []);

  /* ── Map click handler for planning scenarios ───────────────── */
  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !mapReady) return;
    const handleMapClick = (e: L.LeafletMouseEvent) => {
      if (mapClickRef.current) {
        mapClickRef.current(e.latlng.lat, e.latlng.lng);
      }
    };
    map.on("click", handleMapClick);
    return () => {
      map.off("click", handleMapClick);
    };
  }, [mapReady]);

  /* ── Update markers & radius ────────────────────────────────── */
  useEffect(() => {
    const map = mapInstance.current;
    const markers = markersRef.current;
    if (!map || !markers || !mapReady) return;

    markers.clearLayers();
    if (radiusCircleRef.current) {
      map.removeLayer(radiusCircleRef.current);
      radiusCircleRef.current = null;
    }

    /* Radius circle around active well */
    if (proximityBasis === "surface") {
      radiusCircleRef.current = L.circle(
        [active.latitude, active.longitude],
        {
          radius: radius * 1000,
          color: "rgba(34, 168, 178, 0.6)",
          weight: 1.5,
          dashArray: "8 6",
          fillColor: "rgba(34, 168, 178, 0.06)",
          fillOpacity: 1,
          interactive: false,
        },
      ).addTo(map);
    }

    /* Active well marker */
    L.marker([active.latitude, active.longitude], {
      icon: wellIcon("active"),
      zIndexOffset: 1000,
      keyboard: true,
      title: `${active.name} — Active well`,
    })
      .bindPopup(wellPopupHtml(active, true), {
        className: "well-popup-wrapper",
        maxWidth: 320,
        minWidth: 260,
      })
      .addTo(markers);

    // pulse ring behind active marker
    L.circleMarker([active.latitude, active.longitude], {
      radius: 22,
      color: "rgba(34, 168, 178, 0.4)",
      weight: 2,
      fillColor: "rgba(34, 168, 178, 0.08)",
      fillOpacity: 1,
      interactive: false,
      className: "pulse-ring",
    }).addTo(markers);

    /* Immediate Candidate Offset well markers */
    for (const well of candidates) {
      const isSelected = well.id === selectedId;
      const m = L.marker([well.latitude, well.longitude], {
        icon: wellIcon(isSelected ? "selected" : "offset"),
        zIndexOffset: isSelected ? 500 : 150,
        keyboard: true,
        title: `${well.name} — ${isSelected ? "Selected offset" : "Offset well"}`,
      })
        .bindPopup(wellPopupHtml(well, false, active), {
          className: "well-popup-wrapper",
          maxWidth: 320,
          minWidth: 260,
        })
        .on("click", () => callbackRef.current(well.id))
        .addTo(markers);

      if (isSelected) {
        m.openPopup();
      }
    }

    /* Regional Basin Synthetic Wells across India */
    for (const synthWell of visibleRegionalWells) {
      const isSelected = synthWell.id === selectedId;
      const m = L.marker([synthWell.latitude, synthWell.longitude], {
        icon: wellIcon(isSelected ? "selected" : "basin-synth", synthWell.event_type),
        zIndexOffset: isSelected ? 600 : 100,
        keyboard: true,
        title: `${synthWell.name} · ${synthWell.basin} (${synthWell.primary_hazard})`,
      })
        .bindPopup(synthWellPopupHtml(synthWell, active), {
          className: "well-popup-wrapper",
          maxWidth: 330,
          minWidth: 270,
        })
        .on("click", () => callbackRef.current(synthWell.id))
        .addTo(markers);

      if (isSelected) {
        m.openPopup();
      }
    }

    /* Planning scenario point marker */
    if (planningPoint) {
      L.marker([planningPoint.latitude, planningPoint.longitude], {
        icon: wellIcon("planning"),
        zIndexOffset: 850,
        keyboard: true,
        title: `Planning scenario point: ${planningPoint.latitude.toFixed(4)}°N, ${planningPoint.longitude.toFixed(4)}°E`,
      })
        .bindPopup(`
          <div class="well-popup">
            <div class="popup-header">
              <span class="popup-name">Planning Scenario</span>
              <span class="popup-badge" style="background: var(--ochre); color: #000; font-weight: 700;">SCENARIO PIN</span>
            </div>
            <div class="popup-badge popup-badge-synth">HYPOTHETICAL TARGET</div>
            <div class="popup-row"><span class="popup-label">Coordinates</span><span class="popup-val mono">${planningPoint.latitude.toFixed(4)}°N, ${planningPoint.longitude.toFixed(4)}°E</span></div>
            <div class="popup-row"><span class="popup-label">Status</span><span class="popup-val">Hypothetical scenario location</span></div>
            <div class="popup-provenance">Click anywhere on the map to relocate scenario pin.</div>
          </div>
        `, {
          className: "well-popup-wrapper",
          maxWidth: 300,
        })
        .addTo(markers);
    }
  }, [active, candidates, visibleRegionalWells, radius, proximityBasis, selectedId, planningPoint, mapReady]);

  /* ── Map controls ───────────────────────────────────────────── */
  const resetToIndia = useCallback(() => {
    setBasinFilter("all");
    mapInstance.current?.fitBounds(INDIA_BOUNDS, { padding: [20, 20], animate: true, duration: 0.8 });
  }, []);

  const locateActiveWell = useCallback(() => {
    if (!active) return;
    mapInstance.current?.setView([active.latitude, active.longitude], 12, { animate: true });
  }, [active]);

  const fitVisibleWells = useCallback(() => {
    const allPoints: L.LatLngExpression[] = [
      [active.latitude, active.longitude],
      ...candidates.map((w) => [w.latitude, w.longitude] as L.LatLngExpression),
      ...visibleRegionalWells.map((w) => [w.latitude, w.longitude] as L.LatLngExpression),
    ];
    if (allPoints.length) {
      mapInstance.current?.fitBounds(L.latLngBounds(allPoints).pad(0.2), {
        padding: [40, 40],
        maxZoom: 13,
        animate: true,
      });
    }
  }, [active, candidates, visibleRegionalWells]);

  const handleSelectBasin = useCallback((key: BasinKey) => {
    setBasinFilter(key);
    if (key === "all") {
      mapInstance.current?.fitBounds(INDIA_BOUNDS, { padding: [20, 20], animate: true, duration: 0.8 });
    } else {
      const basin = BASIN_REGISTRY[key];
      if (basin) {
        mapInstance.current?.setView(basin.center, basin.zoom, { animate: true });
      }
    }
  }, []);

  const totalWellCount = candidates.length + 1 + (showAllBasins ? visibleRegionalWells.length : 0);

  return (
    <div className={`india-map-container${compact ? " compact-locator" : ""}`}>
      {/* Map toolbar */}
      {compact ? (
        <div className="map-toolbar">
          <div className="map-toolbar-left">
            <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--teal-glow)" }} />
              Lookahead Map Locator · {active.basin ?? "Upper Assam Basin"}
            </span>
            <span className="map-well-count" style={{ marginLeft: "8px" }}>
              {candidates.length} offset{candidates.length !== 1 ? "s" : ""} within {radius} km
            </span>
          </div>
          <div className="map-toolbar-right">
            <button
              type="button"
              className="map-btn"
              onClick={locateActiveWell}
              title="Center on active well"
            >
              Center active
            </button>
            {onExploreClick && (
              <button
                type="button"
                className="map-btn"
                style={{ borderColor: "var(--border-teal)", color: "var(--teal-glow)" }}
                onClick={onExploreClick}
                title="Open interactive Explore Atlas"
              >
                Open Explore Atlas ↗
              </button>
            )}
          </div>
        </div>
      ) : (
        <>
          <div className="map-toolbar">
            <div className="map-toolbar-left">
              <button
                type="button"
                className="map-btn"
                onClick={resetToIndia}
                title="Reset to whole-India view"
              >
                <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M8 1L1 8l7 7M1 8h14" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Whole India
              </button>
              <button
                type="button"
                className="map-btn"
                onClick={locateActiveWell}
                title="Zoom to active well"
              >
                <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="8" cy="8" r="3"/>
                  <path d="M8 1v3M8 12v3M1 8h3M12 8h3" strokeLinecap="round"/>
                </svg>
                Active well
              </button>
              <button
                type="button"
                className="map-btn"
                onClick={fitVisibleWells}
                title="Fit all visible wells"
              >
                <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="2" y="2" width="12" height="12" rx="2"/>
                  <path d="M5 8h6M8 5v6" strokeLinecap="round"/>
                </svg>
                Fit visible
              </button>
              <button
                type="button"
                className={`map-btn ${showAllBasins ? "map-btn-active-toggle" : ""}`}
                onClick={() => setShowAllBasins(!showAllBasins)}
                title="Toggle regional basin synthetic wells across India"
              >
                {showAllBasins ? "All Basins Active" : "Show All Basins"}
              </button>
            </div>
            <div className="map-toolbar-right">
              <span className="map-well-count">
                {totalWellCount} wells across India · {radius} km active radius
              </span>
              <button
                type="button"
                className="map-btn map-btn-subtle"
                onClick={() => setShowProvenance(!showProvenance)}
                title="Map data and provenance"
              >
                ⓘ Map data
              </button>
            </div>
          </div>

          {/* Basin Quick Filter Pill Bar */}
          <div className="basin-pill-bar">
            <span className="basin-pill-label">Petroleum Basins:</span>
            <button
              type="button"
              className={`basin-pill ${basinFilter === "all" ? "active" : ""}`}
              onClick={() => handleSelectBasin("all")}
            >
              All India <span className="basin-pill-count">{ALL_SYNTHETIC_WELLS.length}</span>
            </button>
            {Object.values(BASIN_REGISTRY).map((basin) => {
              const count = ALL_SYNTHETIC_WELLS.filter((w) => w.basin_key === basin.key).length;
              return (
                <button
                  key={basin.key}
                  type="button"
                  className={`basin-pill ${basinFilter === basin.key ? "active" : ""}`}
                  onClick={() => handleSelectBasin(basin.key)}
                >
                  {basin.name} <span className="basin-pill-count">{count}</span>
                </button>
              );
            })}
          </div>
        </>
      )}

      {/* Provenance disclosure */}
      {showProvenance && !compact && (
        <div className="map-provenance">
          <div className="provenance-grid">
            <div>
              <span className="provenance-label">Boundary source</span>
              <span>37 States & UTs (WGS 84) + National Outer Composite</span>
            </div>
            <div>
              <span className="provenance-label">CRS</span>
              <span className="mono">WGS 84 / EPSG:4326</span>
            </div>
            <div>
              <span className="provenance-label">Tile provider</span>
              <span>Self-contained vector map · zero third-party watermarks</span>
            </div>
            <div>
              <span className="provenance-label">Synthetic Well Registry</span>
              <span>32 geologically calibrated synthetic wells across 6 basins</span>
            </div>
            <div>
              <span className="provenance-label">Distance basis</span>
              <span>{proximityBasis === "surface" ? "Surface wellhead (geodesic)" : "Reviewed terminal position"}</span>
            </div>
          </div>
          <p className="provenance-note">
            Boundary geometry incorporates all 37 Indian States and Union
            Territories with post-2019 subdivisions (including Ladakh, Jammu &
            Kashmir, and Arunachal Pradesh) along with the authoritative national
            composite outline. All wells and drilling incident logs are synthetic
            demonstration fixtures calibrated to realistic basin stratigraphy.
          </p>
        </div>
      )}

      {/* Map canvas */}
      <div
        ref={mapRef}
        className="india-map"
        tabIndex={0}
        aria-label={`Interactive map of India displaying ${totalWellCount} wells across 6 petroleum basins`}
        style={{ outline: "none" }}
      />

      {/* Map legend */}
      {compact ? (
        <div className="map-legend">
          <div className="legend-item">
            <span className="legend-dot legend-dot-active" />
            {active.name} (Active)
          </div>
          <div className="legend-item">
            <span className="legend-dot legend-dot-offset" />
            Offset wells
          </div>
          <div className="legend-item">
            <span className="legend-line legend-line-radius" />
            {radius} km horizon
          </div>
          <div className="legend-item legend-synth">
            SYNTHETIC REHEARSAL
          </div>
        </div>
      ) : (
        <div className="map-legend">
          <div className="legend-item">
            <span className="legend-dot legend-dot-active" />
            Active well
          </div>
          <div className="legend-item">
            <span className="legend-dot legend-dot-selected" />
            Selected well
          </div>
          <div className="legend-item">
            <span className="legend-dot legend-dot-offset" />
            Offset in radius
          </div>
          <div className="legend-item">
            <span className="legend-dot legend-dot-basin" />
            Regional synthetic well
          </div>
          {proximityBasis === "surface" && (
            <div className="legend-item">
              <span className="legend-line legend-line-radius" />
              Active radius ({radius} km)
            </div>
          )}
          {(planningPoint || onMapClick) && (
            <div className="legend-item">
              <span
                className="legend-dot"
                style={{
                  background: "var(--ochre)",
                  border: "2px dashed #ffffff",
                  boxShadow: "0 0 6px rgba(245, 158, 11, 0.5)",
                }}
              />
              Scenario pin
            </div>
          )}
          <div className="legend-item legend-synth">
            32 SYNTHETIC WELLS ACROSS 6 INDIAN BASINS
          </div>
        </div>
      )}
    </div>
  );
}
