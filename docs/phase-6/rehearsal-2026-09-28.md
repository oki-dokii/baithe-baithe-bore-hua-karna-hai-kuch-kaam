# Clean-install and fresh-database rehearsal — 2026-09-28

This run used current `main` after PR #30. It is software evidence for the **synthetic** scenario, not real-well validation.

| Gate | Result | Evidence and limit |
|---|---|---|
| Fresh local Compose images and volumes | **Blocked locally** | A separate project (`nwisrehearsal0928`) with unused ports and new volumes was attempted. The backend image build stopped while installing Poppler/Tesseract: Docker reported insufficient space in `/var/cache/apt/archives`; the host had about 499 MiB free. Existing `nwis` containers and volumes were not stopped, reset or removed. No new rehearsal service reached startup. |
| Fresh database on current code | **Pass** | A new empty database, `nwis_rehearsal_20260928`, was created in the existing local PostgreSQL container. All migrations through `0016_pressure_window_evidence` applied. `nwis.demo_rehearsal` passed against it using local rules and an owned synthetic report. This is a fresh-database rehearsal, **not** a fresh-image/volume install. |
| End-to-end assertions | **Pass, synthetic only** | Ingestion and reviewer approval produced one cited event; formation-relative mapping was 2130–2140 m; an unsupported query abstained. Replay had 0 alerts at 2029 m and 1 episode from 2030 m onward, including duplicate-depth steps. `risk_score` stayed null with `model_not_available`. The database was left in place for repeatability; rerunning the guarded rehearsal requires a *new empty* database. |
| Fresh-runner Compose CI | **Pass on PR #30** | Both static and integration checks were green before merge. CI's integration job builds a fresh Compose stack, migrates and runs `nwis.demo_rehearsal`; this corroborates the install path on a runner with sufficient disk. It does not replace the failed local full-stack rerun or prove deployment at an OIL site. |

The local full-stack blocker is capacity, not an observed code failure. Before another local image rebuild, free adequate disk by reviewing host/Docker storage with the owner; do not prune existing volumes or report PDFs indiscriminately. Then use a new Compose project name and ports, and rerun `docker compose ... up --build -d --wait` followed by the guarded rehearsal on its empty database. No real report was approved or used in an alert in this rehearsal.
