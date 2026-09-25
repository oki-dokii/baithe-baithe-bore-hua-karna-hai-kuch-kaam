# Scope and acceptance criteria

## Product goal

Give an engineer evidence about what happened in relevant offset wells before the active well reaches a comparable interval. An engineer must be able to inspect the source, understand the comparison, and record a response.

The user-supplied problem statement requires document extraction, a radius-based map, searchable institutional memory, geological/drilling correlation, predictive analytics, real-time alerts and recommendations, and a dashboard for office and field users.

## Delivery boundaries

The rules MVP includes ingestion and review, nearby-well mapping, formation-relative correlation, cited retrieval, deterministic replay alerts, feedback, and a minimal field view. Initially implement mud-loss behavior end to end while preserving the full event vocabulary. Add stuck-pipe and kick scenarios after that path works.

The SIH demonstration additionally needs documented real-report extraction and at least one relevant predictive-model evaluation on independently held-out wells. If suitable labeled data cannot be qualified, record the prediction requirement as unmet; a rules engine or synthetic-data classifier must not be presented as validated prediction on real drilling data.

Deferred: live eRTMAC connectivity, multi-basin onboarding, knowledge graphs, fishing decision thresholds, mechanistic cement modeling, broad per-hazard model coverage, production deployment, and advanced financial analytics. Casing/cementing/mud records remain in the data model and basic evidence views because they are named in the problem statement.

## Acceptance matrix

These are planned checks, not achieved results. All latency targets are prototype budgets measured on a recorded machine, dataset size, network, provider, and warm/cold state.

| ID | Requirement / phase | Pass condition |
|---|---|---|
| ING-01 | Text and scanned reports / 2 | One text PDF and one scanned report enter upload → extraction → review; page/section evidence is preserved; OCR is applied only where needed |
| ING-02 | Normalization / 2 | Missing values stay null; unknown units, depth reference, formation aliases, and contradictory facts enter review rather than silently receiving defaults |
| ING-03 | Review and retries / 2 | Correction records reviewer/time/before/after; only approved event versions support alerts; retrying the same upload does not duplicate a document or event |
| MAP-01 | Nearby wells / 3 | Results match independent geodesic expectations for within/outside/boundary fixtures; radius input is in km and stored/query distance in m; selected well is excluded |
| COR-01 | Correlation / 3 | Golden historical interval maps to active MD 2130–2140 m; unresolved formation/datum or extrapolated survey data blocks numerical mapping with an explanation |
| COR-02 | Analog ranking / 3 | Surface distance and analog similarity are displayed separately; each score explains its available components and missing data |
| RET-01 | Institutional memory / 3 | Answers contain supported claims and working document/page links; zero supporting evidence produces an explicit no-evidence answer |
| RET-02 | Structured retrieval / 3 | Hazard, formation, well, and depth filters constrain semantic results; malformed filters fail validation; extraction/retrieval never executes LLM-authored SQL |
| ALR-01 | Proactive alert / 4 | At golden active MD 2030 m, lookahead 100 m, one mud-loss alert opens with approved supporting evidence, mapped interval, and rule/config version; at 2029 m none opens |
| ALR-02 | Lifecycle / 4 | Repeated ticks and reconnects do not duplicate an alert; acknowledgment does not resolve it; dismiss requires reason; escalation updates an existing episode visibly |
| ALR-03 | Degraded input / 4 | Stale telemetry stops new alerts; missing ML score does not stop historical alerts; missing/revoked historical evidence cannot silently support a new alert |
| UX-01 | Dashboard / 4 | Active well, MD with datum, formation, replay/connectivity labels, map, alerts, and evidence are accessible; missing risk displays unknown rather than 0% |
| UX-02 | Field view / 4 | Mobile view exposes recent alerts and evidence summary without loading maps/charts; cached values show their timestamp and staleness; disconnected acknowledgment is not shown as server-confirmed |
| FBK-01 | Institutional feedback / 4 | Engineer action, observed event, uncertainty, and adjudication are separate, auditable fields |
| ML-01 | Prediction / 5 | At least one relevant hazard model is compared with a simple baseline using well-grouped held-out data; labels, horizon, available features, class balance, leakage checks, and precision/recall/F1 are documented |
| ML-02 | Honest scoring / 5 | Every score carries model version, intended horizon, evaluation context and score kind; probability display requires calibration evidence; unsupported input returns null plus reason |
| OPS-01 | Reproducibility / 1–6 | Fresh setup, migrations and fixture loading are documented; demo replay can reset without deleting reviewed source records |
| OPS-02 | Access / 2–4 | Viewer reads; engineer updates alerts; reviewer validates extractions; admin manages imports/users; unauthorized actions are rejected server-side and audited |
| PERF-01 | Prototype performance / 6 | Record p95 under 2 s for radius and retrieval-only queries over 100 wells/10,000 passages; document LLM answer latency separately |
| PERF-02 | Prototype ingestion / 6 | Record under 120 s for a declared <=10-page demo report; provider latency/errors remain visible; report slower scans rather than hiding them |

## Quality and prioritization

Evidence, correct correlation and clear unknown states take precedence over extra screens. Predictions require a declared horizon and an outcome definition; a numerical score is not automatically a probability. Historical mitigations are cited observations for engineer review and do not establish guaranteed efficacy.

No equipment control or autonomous operational decision is in scope. Keep synthetic, real-public, and future private OIL data distinguishable throughout the API and UI.
