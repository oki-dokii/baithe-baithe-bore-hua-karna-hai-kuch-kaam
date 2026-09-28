# Operational evidence views (read-only)

The Intelligence page now includes three explicitly bounded aids:

- **Upper Assam name reference.** Seven regional names are transcribed from [Oil India Limited's Upper Assam basin geology description](https://www.oil-india.com/files/oldtender/global/NIT_CDG1116P20.pdf). The exact-name suggestion API normalizes case and punctuation only. It does not write `formation_alias`, approve a `formation_interval`, infer a formation from prose, or attach hazards/depths. The existing dataset-scoped reviewed-alias path remains authoritative.
- **Fishing and cementing cases.** `GET /api/v1/knowledge/special-operations?dataset_id=...` reads only approved, issue-free events with a linked source passage from a qualified dataset. It shows the case IDs, formation if recorded, and a reported outcome distribution only when at least three eligible events of that type exist. This is descriptive, not an effectiveness or success-rate estimate; ancillary fishing/outcome fields have no independent approval field in the current schema.
- **Illustrative NPT exposure.** `POST /api/v1/knowledge/npt-exposure` requires a positive user-entered `rig_day_rate` and three-letter `currency`. For each approved cited event with a recorded `npt_event`, it returns `duration_h × rate / 24`, rounded to two decimal places. The rate is not stored. No rate is presented as OIL's actual rate. There is no aggregate total because intervals may overlap, and no savings or causal claim.

All operational views require authentication. They return an error for datasets that fail the existing provenance/authorization gate. The source document and event approval still need a qualified human reviewer before real-data claims can be made; these views do not substitute for one.
