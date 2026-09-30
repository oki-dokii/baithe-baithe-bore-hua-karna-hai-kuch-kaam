import { Suspense, lazy, useEffect, useState } from "react";
import Documents from "./Documents";
import Operations from "./Operations";
import Prediction from "./Prediction";
import ReportQuestions from "./ReportQuestions";
import Landing from "./Landing";
import Sidebar from "./Sidebar";
import MobileDrawer from "./MobileDrawer";
import ContextBar from "./ContextBar";
import FoundationView from "./FoundationView";
import { ProductTour, isTourDone, TOUR_STEPS } from "./ProductTour";
import DevConsole from "./DevConsole";
import { UserRole } from "./roles";
import { Component, Status, Well, WellPage } from "./types";
import { View } from "./nav";
import "./styles.css";

const Intelligence = lazy(() => import("./Intelligence"));
const Analytics = lazy(() => import("./Analytics"));

export type { Component, Status, Well, WellPage };

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

export default function App() {
  const [token, setEntered] = useState("");
  const [activeRole, setActiveRole] = useState<UserRole>("engineer");
  const [status, setStatus] = useState<Status | null>(null);
  const [wells, setWells] = useState<Well[]>([]);
  const [selected, setSelected] = useState("");
  const [nearby, setNearby] = useState<Well[]>([]);
  const [radius, setRadius] = useState(5);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("operations");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [tourStep, setTourStep] = useState(0);

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      getJson<Status>("/api/v1/status", token),
      getJson<WellPage>("/api/v1/wells", token),
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
  }, [token]);

  useEffect(() => {
    if (!token || !selected) return;
    let active = true;
    const path = `/api/v1/wells/nearby?active_well_id=${selected}&radius_km=${radius}`;
    getJson<WellPage>(path, token)
      .then((page) => {
        if (active) setNearby(page.items);
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [token, selected, radius]);

  useEffect(() => {
    if (status && !isTourDone()) {
      setTourStep(0);
      setTourOpen(true);
    }
  }, [status]);

  function handleTourNext() {
    if (tourStep < TOUR_STEPS.length - 1) {
      setTourStep((s) => s + 1);
    } else {
      try {
        localStorage.setItem("nwis_tour_done", "1");
      } catch {}
      setTourOpen(false);
    }
  }

  function handleTourBack() {
    if (tourStep > 0) setTourStep((s) => s - 1);
  }

  function handleTourSkip() {
    try {
      localStorage.setItem("nwis_tour_done", "1");
    } catch {}
    setTourOpen(false);
  }

  function handleStartTour() {
    setTourStep(0);
    setTourOpen(true);
  }

  function handleResetTour() {
    try {
      localStorage.removeItem("nwis_tour_done");
    } catch {}
    setTourStep(0);
    setTourOpen(true);
  }

  async function handleImpersonate(role: UserRole) {
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: role === "superadmin" ? "admin" : role }),
      });
      if (res.ok) {
        const data = await res.json();
        setEntered(data.token);
        setActiveRole(role);
      }
    } catch (err) {
      console.error("Failed to impersonate role:", err);
    }
  }

  function disconnect() {
    setEntered("");
    setActiveRole("engineer");
    setStatus(null);
    setWells([]);
    setNearby([]);
    setError("");
    setView("operations");
    setSidebarCollapsed(false);
    setTourOpen(false);
  }

  // Not connected
  if (!status) {
    return (
      <Landing
        onConnect={(tok, role) => {
          setEntered(tok);
          if (role) setActiveRole(role as UserRole);
        }}
        loading={loading}
        error={error}
      />
    );
  }

  const activeWell = wells.find((w) => w.id === selected);

  return (
    <div className="shell">
      {/* Descriptive sidebar */}
      <Sidebar
        view={view}
        setView={setView}
        disconnect={disconnect}
        well={activeWell}
        status={status}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
        onStartTour={handleStartTour}
      />

      {/* Mobile drawer */}
      <MobileDrawer
        view={view}
        setView={setView}
        disconnect={disconnect}
        well={activeWell}
        status={status}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onStartTour={handleStartTour}
      />

      {/* Main body */}
      <div className={`app-body${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
        <ContextBar
          status={status}
          wells={wells}
          selected={selected}
          view={view}
          onMenuOpen={() => setDrawerOpen(true)}
        />

        <div className="main-canvas">
          {view === "operations" ? (
            <Operations token={token} />
          ) : view === "documents" ? (
            <Documents token={token} />
          ) : view === "intelligence" ? (
            <Suspense
              fallback={
                <div className="workspace">
                  <div className="workspace-body">
                    <div className="notice">Loading the well exploration atlas…</div>
                  </div>
                </div>
              }
            >
              <Intelligence token={token} />
            </Suspense>
          ) : view === "analytics" ? (
            <Suspense
              fallback={
                <div className="workspace">
                  <div className="workspace-body">
                    <div className="notice">Loading correlation analytics & ledger…</div>
                  </div>
                </div>
              }
            >
              <Analytics token={token} />
            </Suspense>
          ) : view === "questions" ? (
            <ReportQuestions token={token} />
          ) : view === "prediction" ? (
            <Prediction token={token} />
          ) : (
            <FoundationView
              wells={wells}
              nearby={nearby}
              selected={selected}
              radius={radius}
              onSelect={setSelected}
              onRadius={setRadius}
              status={status}
            />
          )}
        </div>

        <footer className="app-footer">
          <span className="footer-brand">NWIS</span>
          <span className="footer-text">Historical knowledge · Traceable evidence</span>
          <span className="footer-spacer" />
          <span className="simulated-tag">SIH Prototype · Decision support, not operational instruction</span>
        </footer>
      </div>

      <ProductTour
        open={tourOpen}
        step={tourStep}
        onNext={handleTourNext}
        onBack={handleTourBack}
        onSkip={handleTourSkip}
      />
      <DevConsole
        token={token}
        activeRole={activeRole}
        onImpersonate={handleImpersonate}
        onResetTour={handleResetTour}
      />
    </div>
  );
}
