import { useEffect, useRef, useCallback } from "react";

export type TourStep = {
  id: string;
  heading: string;
  body: string;
  target: string | null;
  placement?: "right" | "left" | "top" | "bottom" | "center";
};

const TOUR_STEPS: TourStep[] = [
  {
    id: "well-context",
    heading: "Active well & synthetic status",
    body: "The sidebar shows your active well, its basin, and the data mode. SYNTHETIC means you are exploring historical demo data — no live rig is connected. This keeps the evidence layer safe for planning without implying operational control.",
    target: ".sidebar-well",
    placement: "right",
  },
  {
    id: "navigation",
    heading: "Six destinations, one sidebar",
    body: "Monitor, Find evidence, and Platform group your daily tasks. Observe shows the live/replay well desk. Explore maps nearby analogue wells. Correlate surfaces the response network and NPT ledger. Investigate answers questions from cited records. Validate reviews source material. You can reopen this tour any time from the sidebar bottom.",
    target: ".nav-group",
    placement: "right",
  },
  {
    id: "observe",
    heading: "Observe — live well desk",
    body: "The Observe page shows your active measured depth, current formation, simulated telemetry stream, and any evidence-backed hazard alerts. Each alert links directly to the source passage that triggered it — no claim appears without a traceable citation.",
    target: null,
    placement: "center",
  },
  {
    id: "explore-map",
    heading: "Explore — India map & offset wells",
    body: "The Explore page opens an interactive India map centred on the Assam basin. Synthetic demonstration wells are shown with clear SYNTHETIC badges. Click a well to inspect its formation history, incidents, and surface distance. Use the radius slider to widen or narrow the offset search.",
    target: null,
    placement: "center",
  },
  {
    id: "evidence",
    heading: "Investigate & Validate — source citations",
    body: "Every answer in Investigate cites a document page. Disputed or low-confidence passages stay visible rather than being resolved into a single sentence. Validate lets you review the ingestion queue, correct extracted facts, and approve records before they reach the knowledge base.",
    target: null,
    placement: "center",
  },
  {
    id: "disclaimer",
    heading: "Decision support, not operational instruction",
    body: "All wells shown are synthetic demonstration data. Live eRTMAC integration is not connected in this prototype. Evidence-backed historical patterns describe what has been observed and cited — they are not recommendations to repeat any action. Human decision authority applies throughout.",
    target: null,
    placement: "center",
  },
];

const STORAGE_KEY = "nwis_tour_done";

export function isTourDone(): boolean {
  try { return localStorage.getItem(STORAGE_KEY) === "1"; } catch { return false; }
}

export function markTourDone() {
  try { localStorage.setItem(STORAGE_KEY, "1"); } catch { /* ignore */ }
}

export function resetTour() {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
}

function getRect(selector: string | null): DOMRect | null {
  if (!selector) return null;
  const el = document.querySelector(selector);
  if (!el) return null;
  return el.getBoundingClientRect();
}

function cardPosition(
  placement: TourStep["placement"],
  rect: DOMRect | null,
): React.CSSProperties {
  const PAD = 20;
  const CARD_W = 380;
  if (!rect || placement === "center") {
    return { position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: CARD_W, maxWidth: "calc(100vw - 32px)" };
  }
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  if (placement === "right") {
    const left = Math.min(rect.right + PAD, vw - CARD_W - PAD);
    const top = Math.max(PAD, Math.min(rect.top, vh - 340));
    return { position: "fixed", top, left, width: CARD_W, maxWidth: "calc(100vw - 32px)" };
  }
  if (placement === "left") {
    const left = Math.max(PAD, rect.left - CARD_W - PAD);
    const top = Math.max(PAD, Math.min(rect.top, vh - 340));
    return { position: "fixed", top, left, width: CARD_W, maxWidth: "calc(100vw - 32px)" };
  }
  if (placement === "bottom") {
    const top = Math.min(rect.bottom + PAD, vh - 340);
    const left = Math.max(PAD, Math.min(rect.left, vw - CARD_W - PAD));
    return { position: "fixed", top, left, width: CARD_W, maxWidth: "calc(100vw - 32px)" };
  }
  const top = Math.max(PAD, rect.top - 300 - PAD);
  const left = Math.max(PAD, Math.min(rect.left, vw - CARD_W - PAD));
  return { position: "fixed", top, left, width: CARD_W, maxWidth: "calc(100vw - 32px)" };
}

function SpotlightOverlay({ target }: { target: string | null }) {
  const rect = getRect(target);
  if (!rect) {
    return <div className="tour-backdrop" aria-hidden="true" />;
  }
  const PAD = 10;
  const x = rect.left - PAD;
  const y = rect.top - PAD;
  const w = rect.width + PAD * 2;
  const h = rect.height + PAD * 2;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  return (
    <svg className="tour-backdrop tour-backdrop-svg" aria-hidden="true"
      style={{ position: "fixed", inset: 0, width: "100vw", height: "100vh" }}>
      <defs>
        <mask id="tour-mask">
          <rect width="100%" height="100%" fill="white" />
          <rect x={x} y={y} width={w} height={h} rx="8" fill="black" />
        </mask>
      </defs>
      <rect width={vw} height={vh} fill="rgba(3,10,20,0.84)" mask="url(#tour-mask)" />
      <rect x={x - 1} y={y - 1} width={w + 2} height={h + 2} rx="9"
        fill="none" stroke="rgba(34,168,178,0.8)" strokeWidth="2" />
    </svg>
  );
}

interface ProductTourProps {
  open: boolean;
  step: number;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
}

export function ProductTour({ open, step, onNext, onBack, onSkip }: ProductTourProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const current = TOUR_STEPS[step];
  const total = TOUR_STEPS.length;
  const isFirst = step === 0;
  const isLast = step === total - 1;

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!open) return;
    if (e.key === "Escape") { onSkip(); return; }
    if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); if (!isLast) onNext(); }
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); if (!isFirst) onBack(); }
  }, [open, isFirst, isLast, onNext, onBack, onSkip]);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    if (open) setTimeout(() => dialogRef.current?.focus(), 80);
  }, [open, step]);

  if (!open) return null;

  const rect = getRect(current.target);
  const cardStyle = cardPosition(current.placement, rect);

  return (
    <>
      <SpotlightOverlay target={current.target} />
      <div ref={dialogRef} className="tour-card"
        role="dialog" aria-modal="true"
        aria-label={`Product tour step ${step + 1} of ${total}: ${current.heading}`}
        tabIndex={-1} style={cardStyle}>
        <div className="tour-card-header">
          <div className="tour-progress-dots">
            {TOUR_STEPS.map((s, i) => (
              <span key={s.id}
                className={`tour-dot${i === step ? " active" : i < step ? " done" : ""}`}
                aria-hidden="true" />
            ))}
          </div>
          <span className="tour-counter">{step + 1} / {total}</span>
          <button className="tour-skip-btn" onClick={onSkip} aria-label="Skip tour">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="tour-card-body">
          <h2 className="tour-heading">{current.heading}</h2>
          <p className="tour-body">{current.body}</p>
        </div>
        <div className="tour-card-footer">
          <button className="tour-btn tour-btn-ghost" onClick={onSkip}>Skip tour</button>
          <div className="tour-nav-btns">
            {!isFirst && (
              <button className="tour-btn tour-btn-outline" onClick={onBack} aria-label="Previous step">
                Back
              </button>
            )}
            <button className="tour-btn tour-btn-primary" onClick={onNext}
              aria-label={isLast ? "Finish tour" : "Next step"}>
              {isLast ? "Complete Tour" : "Next Step"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export { TOUR_STEPS };
