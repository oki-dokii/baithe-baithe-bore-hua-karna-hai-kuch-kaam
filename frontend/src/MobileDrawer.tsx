/**
 * MobileDrawer.tsx — slide-out mobile drawer navigation.
 * Extracted from App.tsx (Fix #12: break up the 1037-line monolith).
 */
import { useEffect, useRef } from "react";
import { IconClose, IconDisconnect, IconHelp } from "./icons";
import { NAV_GROUPS, View } from "./nav";
import { Status, Well } from "./types";

interface MobileDrawerProps {
  view: View;
  setView: (v: View) => void;
  disconnect: () => void;
  well: Well | undefined;
  status: Status;
  open: boolean;
  onClose: () => void;
  onStartTour: () => void;
}

export default function MobileDrawer({
  view,
  setView,
  disconnect,
  well,
  status,
  open,
  onClose,
  onStartTour,
}: MobileDrawerProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const isSynthetic = status.source_mode === "SYNTHETIC";

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && open) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  function navigate(v: View) {
    setView(v);
    onClose();
  }

  return (
    <>
      <div
        className={`drawer-overlay${open ? " open" : ""}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        className={`nav-drawer${open ? " open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
      >
        <div className="drawer-close">
          <div className="sidebar-header" style={{ border: "none", padding: 0, minHeight: "auto" }}>
            <div className="sidebar-mark">N</div>
            <div className="sidebar-branding">
              <strong>NWIS</strong>
              <small>Subsurface Observatory</small>
            </div>
          </div>
          <button
            ref={closeRef}
            className="drawer-close-btn"
            onClick={onClose}
            aria-label="Close navigation menu"
          >
            <IconClose />
          </button>
        </div>

        {well && (
          <div className="sidebar-well" style={{ margin: "10px 12px 4px" }}>
            <div className="sidebar-well-id">{well.external_id}</div>
            <div className="sidebar-well-meta">{well.basin_name ?? "Basin unknown"}</div>
            <div className="sidebar-well-mode">
              <span className={`ctx-dot ${isSynthetic ? "synthetic" : "live"}`} aria-hidden="true" />
              {status.source_mode}
            </div>
          </div>
        )}

        <div style={{ flex: 1, overflowY: "auto", padding: "4px 8px" }}>
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi} className="nav-group" style={{ padding: 0 }}>
              <span className="nav-group-label">{group.label}</span>
              {group.items.map(({ id, label, plate, desc, Icon }) => (
                <button
                  key={id}
                  className={`nav-item${view === id ? " active" : ""}`}
                  onClick={() => navigate(id)}
                  aria-label={`${plate} ${label} — ${desc}`}
                  aria-current={view === id ? "page" : undefined}
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
          <button
            className="nav-item nav-item-muted"
            onClick={() => { onClose(); onStartTour(); }}
            aria-label="Take a tour of NWIS"
          >
            <span className="nav-item-icon"><IconHelp /></span>
            <span className="nav-item-text">
              <span className="nav-item-label">
                <span className="nav-item-name">Take a tour</span>
              </span>
              <span className="nav-item-desc">Guided walkthrough</span>
            </span>
          </button>
          <button
            className="nav-disconnect"
            onClick={() => { disconnect(); onClose(); }}
            aria-label="Disconnect from platform"
          >
            <IconDisconnect />
            <span className="nav-disconnect-label">Disconnect</span>
          </button>
        </div>
      </div>
    </>
  );
}
