/**
 * nav.ts — navigation constants shared between Sidebar and MobileDrawer.
 * Extracted from App.tsx (Fix #12).
 */
import {
  IconObserve, IconExplore, IconAnalytics, IconInvestigate,
  IconValidate, IconDirectory, IconEvaluate,
} from "./icons";

export type View =
  | "operations"
  | "intelligence"
  | "analytics"
  | "questions"
  | "documents"
  | "foundation"
  | "prediction";

export const NAV_GROUPS = [
  {
    label: "Monitor",
    items: [
      { id: "operations" as View, label: "Observe",     plate: "00", desc: "Live well desk",         Icon: IconObserve },
    ],
  },
  {
    label: "Find evidence",
    items: [
      { id: "intelligence" as View, label: "Explore",     plate: "01", desc: "Offsets and geology",    Icon: IconExplore },
      { id: "analytics"   as View, label: "Correlate",   plate: "02", desc: "Response & NPT ledger",  Icon: IconAnalytics },
      { id: "questions"   as View, label: "Investigate", plate: "03", desc: "Answers and citations",  Icon: IconInvestigate },
      { id: "documents"   as View, label: "Validate",    plate: "04", desc: "Review source material", Icon: IconValidate },
    ],
  },
  {
    label: "Platform",
    items: [
      { id: "foundation" as View, label: "Directory", plate: "05", desc: "Wells and system",   Icon: IconDirectory },
      { id: "prediction" as View, label: "Evaluate",  plate: "06", desc: "Model readiness",   Icon: IconEvaluate },
    ],
  },
];

export const VIEW_TITLES: Record<View, string> = {
  operations: "Observe",
  intelligence: "Explore",
  analytics: "Correlate",
  questions: "Investigate",
  documents: "Validate",
  foundation: "Directory",
  prediction: "Evaluate",
};
