/**
 * icons.tsx — shared SVG icon components used across the NWIS shell.
 * Extracted from App.tsx (Fix #12: break up the 1037-line monolith).
 */

export const IconObserve = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="8" r="3" />
    <path d="M8 1v2M8 13v2M1 8h2M13 8h2" strokeLinecap="round" />
    <path d="M3.5 3.5l1.5 1.5M11 11l1.5 1.5M11 3.5L9.5 5M3.5 12.5L5 11" strokeLinecap="round" />
  </svg>
);
export const IconExplore = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="7" r="4.5" />
    <path d="M8 11.5V15M5.5 15h5" strokeLinecap="round" />
    <circle cx="8" cy="7" r="1.5" fill="currentColor" stroke="none" />
  </svg>
);
export const IconAnalytics = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="4" cy="4.5" r="2" />
    <circle cx="12" cy="5" r="2" />
    <circle cx="8" cy="12" r="2" />
    <path d="M5.6 5.8l4.8 5M6 4.5h4M10.4 6.2L9.2 10.2" strokeLinecap="round" />
  </svg>
);
export const IconInvestigate = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="6.5" cy="6.5" r="4" />
    <path d="M9.5 9.5L14 14" strokeLinecap="round" />
  </svg>
);
export const IconValidate = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="1.5" width="10" height="13" rx="1" />
    <path d="M5 5.5h6M5 8h6M5 10.5h4" strokeLinecap="round" />
    <path d="M13 11l1.5 1.5L16 10" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
export const IconDirectory = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="1" y="4" width="14" height="10" rx="1" />
    <path d="M1 7h14M5 4V2.5h4.5" strokeLinecap="round" />
    <circle cx="8" cy="11" r="1.5" />
  </svg>
);
export const IconEvaluate = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="1" y="11" width="3" height="4" rx="0.5" />
    <rect x="6" y="7" width="3" height="8" rx="0.5" />
    <rect x="11" y="3" width="3" height="12" rx="0.5" />
    <path d="M2.5 9l4-4 4-2" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="1.5 1" />
  </svg>
);
export const IconDisconnect = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M5.5 10.5l5-5M6 4l-4 4 2 2 4-4M10 12l4-4-2-2-4 4" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M13 3l-2 2" strokeLinecap="round" />
  </svg>
);
export const IconHelp = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="8" r="6.5" />
    <path d="M6 6c0-1.1.9-2 2-2s2 .9 2 2c0 1.5-2 2-2 2.5M8 12v.5" strokeLinecap="round" />
  </svg>
);
export const IconChevronLeft = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M10 12L6 8l4-4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
export const IconChevronRight = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
export const IconMenu = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M2 4h12M2 8h12M2 12h12" strokeLinecap="round" />
  </svg>
);
export const IconClose = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
  </svg>
);
