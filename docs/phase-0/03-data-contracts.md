# Data contracts

This is the logical schema for Phase 1 migrations, not executable SQL. UUID primary keys, UTC timestamps, explicit foreign keys, version numbers and audited updates apply to persistent entities. Fixture IDs are readable symbolic IDs translated to UUIDs by the future loader.

## Units and coordinates

| Quantity | Canonical representation | Required context |
|---|---|---|
| Depth, length, distance | m | MD/TVD/TVDSS axis, reference datum; surface radius API accepts km explicitly |
| Surface and survey position | WGS84 longitude/latitude | EPSG:4326, GeoJSON order [longitude, latitude]; preserve original CRS and coordinates |
| Time | UTC RFC3339 | Source timezone and original timestamp retained |
| Pressure | kPa | Distinguish measured pressure from equivalent mud density |
| Mud density / ECD | kg/m3 | Preserve original ppg; convert using a tested unit library |
| WOB / hookload | kN | Original measurement/unit retained |
| Torque | kN.m | Original measurement/unit retained |
| ROP / rotation | m/h / rpm | Measurement timestamp and operating state |
| Flow / volume | L/min / m3 | In/out channel identity and original unit |
| Permeability | mD | Avoid ambiguous `md`, which is used for measured depth |
| Duration / currency | h / ISO currency code | Currency and assumed rig-day rate as separate fields |

Null means unknown. Zero is an observed zero. No unknown unit or CRS may be guessed. Preserve raw value/unit alongside normalized value and conversion version. Depth reference stores kind (KB/RT/MSL/other), elevation above MSL if known, and provenance. With positive-down TVD from a reference above MSL, `tvdss_m = tvd_m - reference_elevation_m`. Unknown reference elevations block absolute cross-well conversion. Formation-relative mapping still requires a reviewed compatible mapping method; it is not permission to ignore unknown depth context.

## Entities and relationships

| Entity | Essential fields and constraints |
|---|---|
| dataset | id, name, kind (`synthetic`, `public`, `private`), source URL, pinned version, license reference, attribution, qualification status |
| well | dataset_id, external_id, name, basin_id, field, status, surface_point, depth_reference_id; unique(dataset_id, external_id) |
| wellbore | well_id, external_id, parent_wellbore_id, status; events/surveys/telemetry belong to a wellbore so sidetracks are not merged |
| depth_reference | kind, reference_elevation_m, evidence_id, review status |
| trajectory_station | wellbore_id, survey_version, md_m, tvd_m, point, inclination_deg, azimuth_deg; unique(wellbore_id, survey_version, md_m); no assumption of monotonic TVD |
| formation | basin_id, canonical_code, display_name; unique(basin_id, canonical_code); lithology is separate |
| formation_alias | basin_id, source_dataset_id, alias, formation_id, reviewer; ambiguous aliases remain unresolved |
| formation_interval | wellbore_id, formation_id, occurrence_key, top/base MD and TVD, depth_reference_id, version, quality/review status, evidence; base > top where known |
| reservoir_property | formation_interval_id, property_type, value, unit, depth interval, evidence; equivalent density and actual pressure are distinct property types |
| drilling_run | wellbore_id, run number, start/end MD/time, bit/BHA descriptors |
| telemetry_sample | wellbore_id, session_id, sequence, observed_at, received_at, md_m, tvd_m, operational_state, normalized channels, quality; unique(session_id, sequence) |
| mud_program | wellbore_id, interval bounds, density, mud_type, rheology, evidence |
| casing_program | wellbore_id, hole/casing diameter in m, setting depth and reference, casing type, evidence |
| cementing_operation | casing_id, operation time, volume, type, recorded outcome, evidence |
| drilling_event | wellbore_id, event_type, start/end time, source depth endpoints, formation_interval_id nullable, severity nullable, mechanism, description, extraction_run_id, review state, version |
| mitigation | event_id, action_taken, action time, evidence; multiple actions allowed |
| event_outcome | event_id, mitigation_id nullable, outcome (`successful`, `partial`, `unsuccessful`, `unknown`), observation time, narrative, evidence |
| npt_event | event_id, start/end time nullable, duration_h >= 0, duration_source, evidence; analytics must not double count overlapping durations |
| fishing_operation | event_id UNIQUE, tool_left, tool_used, attempts >= 0, duration_h, outcome, recovered_pct between 0 and 100 |
| source_document | dataset_id, wellbore_id nullable, storage_key, checksum, filename, MIME type, byte size, page count, version, access class, ingest status |
| document_wellbore | document_id, wellbore_id; supports reports covering multiple wells; primary key both |
| ingestion_job | document_id, stage, attempts, lease, error code, timestamps, extractor/schema versions |
| extraction_run | document_id, extractor/model version, prompt/schema version, started/finished times, status |
| extracted_passage | document_id, page number (1-based), section, raw text, bounding box nullable, OCR applied/confidence, text version |
| fact_evidence | entity_type, entity_id, passage_id, quoted span, support kind; implementation must validate supported entity references or use typed join tables |
| event_passage | event_id, event_version, passage_id, support kind; primary key on relationship; supports many events per passage and many passages per event |
| passage_embedding | passage_id, text_version, model_id, dimension, vector; unique(passage_id, text_version, model_id) |
| review_decision | entity/version, actor_id, action, previous/new values, reason, timestamp; immutable audit history |
| interval_mapping | source/target interval versions, source event version, mapped active MD bounds, method/version, uncertainty, status/reason |
| model_version | hazard, artifact reference/checksum, dataset/split manifest, feature schema, horizon, metrics, score kind, calibration reference |
| risk_assessment | active wellbore/session/sequence, model_version_id, score nullable, score_kind, horizon, confidence description, missing-data reason |
| alert | active wellbore/session, formation interval, hazard, band, episode key UNIQUE, lifecycle, relevance, current depth, rule/config version, first/last seen, revision, count |
| alert_evidence | alert_id, event_id/version, interval_mapping_id, source passage/version, distance, snapshot; enforce foreign keys rather than UUID arrays |
| alert_risk_assessment | alert_id, risk_assessment_id; model context can change without modifying the historical firing reason |
| alert_feedback | alert_id, actor, action_taken, observed_outcome, adjudicated_label nullable, adjudicator, time, rationale |
| well_similarity | active/candidate wellbore, target interval version, survey versions, config version, component scores nullable, composite, computed_at; invalidate on input change |
| user / role / audit_log | minimal local identity, role assignment, immutable action history |

Source-backed facts outside events also need provenance: formation tops, trajectory, reservoir properties, programs and costs must not become uncited facts. `fact_evidence` is a logical relationship; avoid unenforced polymorphic IDs in physical migrations by using typed joins for supported entities.

## Event vocabulary

Canonical types: `mud_loss`, `kick`, `stuck_pipe`, `overpressure`, `torque_spike`, `tight_hole`, `fishing`, `cementing_issue`, `other`. This extends the draft enum to cover the problem statement's overpressure and torque-spike requirements explicitly. Unknown labels map to `other` with original text and review, never a guessed hazard.

Stuck-pipe mechanism: `differential`, `mechanical`, `key_seat`, `other`, `unknown`. Severity: `low`, `medium`, `high`, `critical`, or null. A kick is not automatically equivalent to an overpressure event. Do not infer a mitigation outcome if the report only says the action was attempted.

## Evidence and confidence

Keep OCR confidence, extraction validation, review state, analog similarity, mapping quality, model uncertainty, and operational severity separate. LLM self-reported confidence is optional uncalibrated metadata and cannot grant approval. Operational review state is `draft`, `needs_review`, `approved`, `rejected`, or `superseded`.

Mapped evidence quality uses documented categories: `reviewed_complete`, `reviewed_limited`, `unresolved`. No conversion of these categories into risk percentages. Store rejected/superseded facts for audit but exclude them from new operational answers and alerts. Existing alerts retain their evidence snapshot and show a review-required revision when evidence is revoked.

## Physical migration requirements

Create required extensions explicitly. Add GiST indexes for spatial points; B-tree indexes for wellbore/depth and wellbore/time; full-text index for passages; vector index only after the embedding model/dimension is selected. Add NOT NULL on required foreign keys, valid numeric ranges, finite coordinates, valid lat/lon bounds, uniqueness and interval checks. Prevent mismatched wellbore/run/event relationships transactionally. Preserve document/event evidence with restricted deletion and logical archival. Timestamp/authorship defaults must not imply approval.

Use a versioned migration tool in Phase 1; prove apply-to-empty and repeat setup. Physical SQL and generated OpenAPI are Phase 1 deliverables, not artifacts claimed by this specification.
