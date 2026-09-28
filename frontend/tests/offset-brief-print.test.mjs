import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/intelligence.css", import.meta.url), "utf8");
const component = readFileSync(new URL("../src/OffsetBrief.tsx", import.meta.url), "utf8");

test("print view isolates the brief on an A4 sheet", () => {
  const print = css.match(/@media print\s*\{([\s\S]*?)\n\}/)?.[1];
  assert.ok(print, "print stylesheet missing");
  assert.match(print, /@page\s*\{\s*size:\s*A4 portrait;\s*margin:\s*12mm;/i);
  assert.match(print, /body \*\s*\{\s*visibility:\s*hidden !important;/);
  assert.match(print, /\.offset-brief, \.offset-brief \*\s*\{\s*visibility:\s*visible !important;/);
  assert.match(print, /\.brief-offset\s*\{\s*break-inside:\s*avoid;/);
});

test("print view visibly discloses provenance, exclusions and clipping", () => {
  assert.match(component, /offset\.authorization_state/);
  assert.match(component, /offset\.applicability/);
  assert.match(component, /event\.citations\.map/);
  assert.match(component, /data\.truncated \? "Additional wells or events omitted/);
  assert.match(component, /data\.omitted_uncited/);
  assert.match(component, /data\.omitted_unresolved/);
});
