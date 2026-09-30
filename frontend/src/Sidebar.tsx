/**
 * Sidebar.tsx — collapsible desktop navigation sidebar.
 * Extracted from App.tsx (Fix #12: break up the 1037-line monolith).
 */
import {
  IconDisconnect, IconHelp, IconChevronLeft, IconChevronRight,
} from "./icons";
import { NAV_GROUPS, View } from "./nav";

import { Status, Well } from "./types";

interface SidebarProps {
  view: View;
  setView: (v: View) => void;
  disconnect: () => void;
  well: Well | undefined;
  status: Status;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function StateBadge({ state }: { state: string }) {
  const cls = `badge badge-${state.toLowerCase().replace(/[\s·]/g, "_")}`;
  return <span className={cls}>{state.replaceAll("_", " ")}</span>;
}

export default function Sidebar({
  view, setView, disconnect, well, status, collapsed, onToggleCollapse,
}: SidebarProps) {
  const isSynthetic = status.source_mode === "SYNTHETIC";

  return (
    <nav className={`nav-sidebar${collapsed ? " collapsed" : ""}`} aria-label="Main navigation">
      <div className="sidebar-header">
        <div className="sidebar-mark" title="NWIS · Nearby Wells Intelligence System">N</div>
        <div className="sidebar-branding">
          <strong>NWIS</strong>
          <small>Subsurface Observatory</small>
        </div>
      </div>

      {well && (
        <div className="sidebar-well" title={`Active well: ${well.external_id}`}>
          <div className="sidebar-well-id">{well.external_id}</div>
          <div className="sidebar-well-meta">{well.basin_name ?? "Basin unknown"}</div>
          <div className="sidebar-well-mode">
            <span className={`ctx-dot ${isSynthetic ? "synthetic" : "live"}`} aria-hidden="true" />
            {status.source_mode}
          </div>
        </div>
      )}

      <div style={{ flex: 1, overflowY: "auto", padding: "4px 0" }}>
        {NAV_GROUPS.map((group, gi) => (
          <div key={gi} className="nav-group">
            <span className="nav-group-label">{group.label}</span>
            {group.items.map(({ id, label, plate, desc, Icon }) => (
              <button
                key={id}
                className={`nav-item${view === id ? " active" : ""}`}
                onClick={() => setView(id)}
                aria-label={`${plate} ${label} — ${desc}`}
                aria-current={view === id ? "page" : undefined}
                title={collapsed ? `${plate} · ${label} — ${desc}` : undefined}
              >
                <span className="nav-item-icon"><Icon /></span>
                <span className="nav-item-text">
                  <span className="nav-item-label">
                    <span className="nav-item-name">{label}</span>
                    <span className="nav-item-plate">{plate}</span>
                  </span>
                  <span className="nav-item-desc">{desc}</span>
                </span>
              </button>
            ))}
            {gi < NAV_GROUPS.length - 1 && <div className="nav-sep" />}
          </div>
        ))}
      </div>

      <div className="sidebar-bottom">
        <button className="nav-item nav-item-muted" onClick={() => {}} title="Take a tour of NWIS" aria-label="Take a tour of NWIS">
          <span className="nav-item-icon"><IconHelp /></span>
          <span className="nav-item-text">
            <span className="nav-item-label"><span className="nav-item-name">Take a tour</span></span>
            <span className="nav-item-desc">Guided walkthrough</span>
          </span>
        </button>
        <button className="nav-disconnect" onClick={disconnect} title="Disconnect from platform" aria-label="Disconnect from platform">
          <IconDisconnect />
          <span className="nav-disconnect-label">Disconnect</span>
        </button>
      </div>

      <div className="sidebar-collapse">
        <button
          className="sidebar-collapse-btn"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <IconChevronRight /> : <IconChevronLeft />}
        </button>
      </div>
    </nav>
  );
}
