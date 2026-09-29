
export type UserRole = "viewer" | "engineer" | "reviewer" | "admin" | "superadmin";

export type View =
  | "operations"
  | "intelligence"
  | "analytics"
  | "questions"
  | "documents"
  | "foundation"
  | "prediction";

export function RoleIcon({ role, size = 16 }: { role: UserRole; size?: number }) {
  if (role === "viewer") {
    // Eye icon
    return (
      <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M1.5 8s2.8-5 6.5-5 6.5 5 6.5 5-2.8 5-6.5 5-6.5-5-6.5-5z" strokeLinejoin="round" />
        <circle cx="8" cy="8" r="2.2" />
      </svg>
    );
  }
  if (role === "engineer") {
    // Dial / Gauge icon
    return (
      <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="8" cy="8" r="6" />
        <path d="M8 8l2.5-3.5" strokeLinecap="round" strokeWidth="1.75" />
        <circle cx="8" cy="8" r="1.2" fill="currentColor" />
        <path d="M4 11.5l1.5-1.5M12 11.5l-1.5-1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (role === "reviewer") {
    // Document audit / file checklist icon
    return (
      <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M3 2h6.5l3.5 3.5v8.5H3V2z" strokeLinejoin="round" />
        <path d="M9.5 2v3.5H13" strokeLinejoin="round" />
        <path d="M5.5 8.5h5M5.5 11h3.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (role === "admin") {
    // Shield security icon
    return (
      <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M8 1.5l5.5 2.5v4c0 3.8-3.2 6.5-5.5 7-2.3-.5-5.5-3.2-5.5-7V4L8 1.5z" strokeLinejoin="round" />
        <path d="M8 4.5v5.5M6 7.5l2 2 2-2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  // superadmin: Terminal prompt icon
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" strokeLinejoin="round" />
      <path d="M4.5 6l3 2.5-3 2.5M9.5 11h2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export interface RoleDefinition {
  id: UserRole;
  name: string;
  shortTitle: string;
  code: string;
  badge: string;
  badgeClass: string;
  shortDesc: string; // Crisp few-word explanation for login page
  fullDesc: string;
  token: string;
  defaultView: View;
  allowedViews: View[];
  allowedViewLabels: string[];
  capabilities: string[];
}

export const ROLES: Record<UserRole, RoleDefinition> = {
  viewer: {
    id: "viewer",
    name: "Viewer",
    shortTitle: "Viewer",
    code: "VW",
    badge: "READ ONLY",
    badgeClass: "badge-muted",
    shortDesc: "Read-only live well desk, offset basin maps and approved claims.",
    fullDesc: "Access approved well telemetry, cross-basin maps, and historical Q&A without editing or operational privileges.",
    token: "nwis-viewer-token-local-demo-2024",
    defaultView: "operations",
    allowedViews: ["operations", "intelligence", "questions", "foundation"],
    allowedViewLabels: ["Observe (00)", "Explore (01)", "Investigate (03)", "Directory (05)"],
    capabilities: [
      "Live telemetry stream monitoring",
      "Interactive 2D/3D offset well maps",
      "Read verified Q&A and citations",
      "Browse wellbore directory",
    ],
  },
  engineer: {
    id: "engineer",
    name: "Drilling Engineer",
    shortTitle: "Engineer",
    code: "ENG",
    badge: "OPERATIONS & ML",
    badgeClass: "badge-teal",
    shortDesc: "Live telemetry desk, parameter tuning and forward hazard ML simulation.",
    fullDesc: "Control active well parameters, correlate offset drilling dynamics, tune drilling station sliders, and run forward mud-loss ML predictions.",
    token: "nwis-engineer-token-local-demo-2024",
    defaultView: "operations",
    allowedViews: ["operations", "intelligence", "analytics", "prediction", "foundation"],
    allowedViewLabels: ["Observe (00)", "Explore (01)", "Correlate (02)", "Directory (05)", "Evaluate (06)"],
    capabilities: [
      "Full live drilling desk and telemetry controls",
      "Calibrated forward hazard prediction simulator",
      "Offset planning and NPT correlation ledger",
      "Interactive parameter sensitivity tuning",
    ],
  },
  reviewer: {
    id: "reviewer",
    name: "Geologist / Reviewer",
    shortTitle: "Reviewer",
    code: "REV",
    badge: "VALIDATION & AUDIT",
    badgeClass: "badge-warning",
    shortDesc: "Source document inspection, evidence extraction and claim verification.",
    fullDesc: "Validate ingested daily drilling reports, inspect PDF bounding boxes, sign off on cited event passages, and audit Assam-Arakan formation records.",
    token: "nwis-reviewer-token-local-demo-2024",
    defaultView: "documents",
    allowedViews: ["intelligence", "analytics", "questions", "documents", "foundation"],
    allowedViewLabels: ["Explore (01)", "Correlate (02)", "Investigate (03)", "Validate (04)", "Directory (05)"],
    capabilities: [
      "Daily drilling report PDF preview and bounding box inspection",
      "Extraction candidates review and event approval",
      "Ask report questions and audit grounded citations",
      "Formation depth and lithology cross-referencing",
    ],
  },
  admin: {
    id: "admin",
    name: "Administrator",
    shortTitle: "Admin",
    code: "ADM",
    badge: "FULL PLATFORM",
    badgeClass: "badge-success",
    shortDesc: "Platform governance, system diagnostics and complete cross-role access.",
    fullDesc: "Unrestricted operational, geological, analytical, and validation authority across all wells, datasets, and platform services.",
    token: "nwis-admin-token-local-demo-2024",
    defaultView: "operations",
    allowedViews: ["operations", "intelligence", "analytics", "questions", "documents", "foundation", "prediction"],
    allowedViewLabels: ["All Workspaces (00 - 06)"],
    capabilities: [
      "Access to all 7 operational and analytical workspaces",
      "Platform component health and diagnostic monitoring",
      "Fixture loading and dataset synchronization",
      "User role governance and audit access",
    ],
  },
  superadmin: {
    id: "superadmin",
    name: "Super Admin (Developer)",
    shortTitle: "Super Admin",
    code: "DEV",
    badge: "DEV · ROOT",
    badgeClass: "badge-dev",
    shortDesc: "Developer root with live API diagnostics, debug tools and full access.",
    fullDesc: "Specialized developer mode with live REST API diagnostics, instantaneous role impersonator, debug state inspector, and unrestricted workspace access.",
    token: "nwis-admin-token-local-demo-2024",
    defaultView: "operations",
    allowedViews: ["operations", "intelligence", "analytics", "questions", "documents", "foundation", "prediction"],
    allowedViewLabels: ["All Workspaces (00 - 06)", "+ Developer Console"],
    capabilities: [
      "Unrestricted access to all workspaces",
      "Developer console with live REST endpoint pings",
      "Instant 1-click role impersonation switcher",
      "Raw telemetry and model calibration inspection",
      "System service latency and token debugging",
    ],
  },
};

export const ROLE_LIST: UserRole[] = ["viewer", "engineer", "reviewer", "admin", "superadmin"];
