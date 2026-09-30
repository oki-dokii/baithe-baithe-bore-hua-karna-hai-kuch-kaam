/**
 * ContextBar.tsx — top well context and state status bar.
 * Extracted from App.tsx (Fix #12: break up the 1037-line monolith).
 */
import { IconMenu } from "./icons";
import { VIEW_TITLES, View } from "./nav";
import { Status, Well } from "./types";

interface ContextBarProps {
  status: Status;
  wells: Well[];
  selected: string;
  streamMode?: string;
  view: View;
  onMenuOpen: () => void;
}

export default function ContextBar({
  status,
  wells,
  selected,
  streamMode,
  view,
  onMenuOpen,
}: ContextBarProps) {
  const w = wells.find((well) => well.id === selected);
  const isLive = status.source_mode === "LIVE";
  const dotCls = isLive ? "ctx-dot live" : "ctx-dot synthetic";

  return (
    <div className="context-bar" role="banner" aria-label="Well context">
      {/* Mobile menu button */}
      <button
        className="mobile-menu-btn"
        onClick={onMenuOpen}
        aria-label="Open navigation menu"
        style={{ marginRight: "12px" }}
      >
        <IconMenu />
      </button>

      {w && (
        <>
          <div className="ctx-chip">
            <span className="ctx-label">Well</span>
            <span className="ctx-value teal">{w.external_id}</span>
          </div>
          <div className="ctx-chip">
            <span className="ctx-label">Basin</span>
            <span className="ctx-value">{w.basin_name ?? "—"}</span>
          </div>
          <div className="ctx-chip" style={{ display: "none" }} data-coords>
            <span className="ctx-label">Coords</span>
            <span className="ctx-value mono-sm">
              {w.latitude.toFixed(4)}°N {w.longitude.toFixed(4)}°E
            </span>
          </div>
        </>
      )}
      <div className="ctx-chip">
        <span className={dotCls} aria-hidden="true" />
        <span className="ctx-label">Mode</span>
        <span className={`ctx-value ${isLive ? "teal" : "ochre"}`}>
          {status.source_mode}
        </span>
      </div>
      <div className="ctx-chip">
        <span className="ctx-label">Env</span>
        <span className="ctx-value">{status.environment.toUpperCase()}</span>
      </div>

      <div className="ctx-spacer" />

      {/* Current view indicator */}
      <span style={{
        fontSize: "0.8125rem",
        fontWeight: 600,
        color: "var(--text-secondary)",
        marginRight: "12px",
        whiteSpace: "nowrap",
      }}>
        {VIEW_TITLES[view]}
      </span>

      {streamMode && (
        <span className={`ctx-stream-badge ${streamMode === "ws" ? "ws" : "http"}`}>
          {streamMode === "ws" ? "⚡ WebSocket" : "↺ HTTP"}
        </span>
      )}
      <div className="ctx-chip" style={{ borderRight: "none" }}>
        <span className="ctx-label">Datasets</span>
        <span className="ctx-value mono-sm">
          {status.datasets.length ? status.datasets[0] : "none"}
        </span>
      </div>
    </div>
  );
}
