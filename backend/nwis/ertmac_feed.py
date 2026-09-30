"""Live eRTMAC and WITSML real-time telemetry streaming adapter for NWIS.

Implements Oil India Limited (OIL) problem statement:
- Data Source vi: eRTMAC data streams & WITSML live feed
- Requirement vi: Real-time telemetry ingestion, monitoring, and proactive hazard prediction
"""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from nwis.db import connection
from nwis.decision_ledger import append_decision
from nwis.hazard_model import predict_hazard
from nwis.ingestion.api import receipt, save_receipt
from nwis.security import current_principal, require_role

router = APIRouter(prefix="/api/v1/ertmac", tags=["ertmac"])

WITSML_NS_REGEX = re.compile(r"\{http://www\.witsml\.org/schemas/1series\}")
MAX_WITSML_BYTES = 25 * 1024 * 1024


class LiveTelemetryReading(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    wellbore_id: UUID
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    md_m: float = Field(ge=0.0)
    tvd_m: Optional[float] = Field(default=None, ge=0.0)
    rop_m_per_h: Optional[float] = Field(default=None, ge=0.0)
    wob_kn: Optional[float] = Field(default=None, ge=0.0)
    rpm: Optional[float] = Field(default=None, ge=0.0)
    torque_kn_m: Optional[float] = Field(default=None, ge=0.0)
    flow_in_l_per_min: Optional[float] = Field(default=None, ge=0.0)
    mud_density_kg_per_m3: Optional[float] = Field(default=None, ge=0.0)
    standpipe_pressure_bar: Optional[float] = Field(default=None, ge=0.0)
    pit_volume_m3: Optional[float] = Field(default=None, ge=0.0)
    gas_total_pct: Optional[float] = Field(default=None, ge=0.0)
    rig_state: str = Field(default="forward_drilling")
    quality: str = Field(default="good")
    channels: Dict[str, float] = Field(default_factory=dict)


class StreamBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: str = Field(default="eRTMAC-Duliajan", min_length=2, max_length=120)
    stream_id: str = Field(min_length=1, max_length=120)
    samples: List[LiveTelemetryReading] = Field(min_length=1, max_length=500)


MNEMONIC_MAP = {
    "MD": "md_m",
    "DEPTH": "md_m",
    "TVD": "tvd_m",
    "ROP": "rop_m_per_h",
    "ROPA": "rop_m_per_h",
    "ROP_AVG": "rop_m_per_h",
    "WOB": "wob_kn",
    "WOBA": "wob_kn",
    "RPM": "rpm",
    "CRPM": "rpm",
    "SURF_RPM": "rpm",
    "TORQ": "torque_kn_m",
    "TORQUE": "torque_kn_m",
    "TRQ": "torque_kn_m",
    "FLOWIN": "flow_in_l_per_min",
    "FLOW_IN": "flow_in_l_per_min",
    "PUMP_FLOW": "flow_in_l_per_min",
    "MWIN": "mud_density_kg_per_m3",
    "MUD_WEIGHT": "mud_density_kg_per_m3",
    "MUD_DENSITY": "mud_density_kg_per_m3",
    "DENSITY": "mud_density_kg_per_m3",
    "SPP": "standpipe_pressure_bar",
    "STANDPIPE": "standpipe_pressure_bar",
    "PIT_VOL": "pit_volume_m3",
    "PVT": "pit_volume_m3",
    "GAS": "gas_total_pct",
    "TOTAL_GAS": "gas_total_pct",
}


def parse_witsml_log_xml(raw_bytes: bytes, default_wellbore_id: UUID) -> List[LiveTelemetryReading]:
    """Parse WITSML 1.3 / 1.4 XML logs payload safely without external entities."""
    if len(raw_bytes) > MAX_WITSML_BYTES:
        raise HTTPException(413, "WITSML XML payload exceeds 25 MiB limit")
    if b"<!DOCTYPE" in raw_bytes.upper() or b"<!ENTITY" in raw_bytes.upper():
        raise HTTPException(400, "DTD/Entity declarations are rejected for security")

    try:
        root = ET.fromstring(raw_bytes)
    except Exception as e:
        raise HTTPException(400, f"Malformed WITSML XML: {e}")

    # Strip namespace for uniform tag parsing
    for elem in root.iter():
        elem.tag = WITSML_NS_REGEX.sub("", elem.tag)

    readings: List[LiveTelemetryReading] = []
    now = datetime.now(timezone.utc)

    for log_elem in root.findall(".//log"):
        # Map column positions by index
        curve_names: List[str] = []
        for curve_info in log_elem.findall("logCurveInfo"):
            mnem_elem = curve_info.find("mnemonic")
            mnemonic = mnem_elem.text.strip().upper() if mnem_elem is not None and mnem_elem.text else ""
            curve_names.append(mnemonic)

        log_data = log_elem.find("logData")
        if log_data is None:
            continue

        for data_elem in log_data.findall("data"):
            line = (data_elem.text or "").strip()
            if not line:
                continue
            values = [v.strip() for v in line.split(",")]
            field_dict: Dict[str, Any] = {
                "wellbore_id": default_wellbore_id,
                "observed_at": now,
                "channels": {},
            }

            for idx, raw_val in enumerate(values):
                if idx >= len(curve_names) or not raw_val:
                    continue
                mnemonic = curve_names[idx]
                target_field = MNEMONIC_MAP.get(mnemonic)
                try:
                    num_val = float(raw_val)
                    if target_field:
                        field_dict[target_field] = num_val
                    field_dict["channels"][mnemonic] = num_val
                except ValueError:
                    pass

            if "md_m" in field_dict and field_dict["md_m"] >= 0:
                try:
                    readings.append(LiveTelemetryReading(**field_dict))
                except Exception:
                    pass

    return readings


def ingest_live_samples(conn, wellbore_id: UUID, samples: List[LiveTelemetryReading], source_name: str, actor_name: str) -> Dict[str, Any]:
    """Ingest live telemetry samples into telemetry_sample, evaluate ML risk, and update heartbeat."""
    wellbore = conn.execute("SELECT id, well_id FROM wellbore WHERE id=%s", (wellbore_id,)).fetchone()
    if not wellbore:
        raise HTTPException(404, f"Wellbore {wellbore_id} not found")

    now = datetime.now(timezone.utc)
    max_seq_row = conn.execute(
        "SELECT coalesce(max(sequence), 0) AS max_seq FROM telemetry_sample WHERE wellbore_id=%s",
        (wellbore_id,),
    ).fetchone()
    current_seq = max_seq_row["max_seq"] if max_seq_row else 0

    latest_sample = None
    latest_hazard_pred = None

    for sample in samples:
        current_seq += 1
        sample_id = uuid4()
        tvd = sample.tvd_m if sample.tvd_m is not None else sample.md_m

        # Populate channels dictionary
        channel_data = dict(sample.channels)
        if sample.rop_m_per_h is not None:
            channel_data["rop_m_per_h"] = sample.rop_m_per_h
        if sample.wob_kn is not None:
            channel_data["wob_kn"] = sample.wob_kn
        if sample.rpm is not None:
            channel_data["rpm"] = sample.rpm
        if sample.torque_kn_m is not None:
            channel_data["torque_kn_m"] = sample.torque_kn_m
        if sample.flow_in_l_per_min is not None:
            channel_data["flow_in_l_per_min"] = sample.flow_in_l_per_min
        if sample.mud_density_kg_per_m3 is not None:
            channel_data["mud_density_kg_per_m3"] = sample.mud_density_kg_per_m3
        if sample.standpipe_pressure_bar is not None:
            channel_data["standpipe_pressure_bar"] = sample.standpipe_pressure_bar
        if sample.pit_volume_m3 is not None:
            channel_data["pit_volume_m3"] = sample.pit_volume_m3
        if sample.gas_total_pct is not None:
            channel_data["gas_total_pct"] = sample.gas_total_pct

        conn.execute(
            """INSERT INTO telemetry_sample
               (id, wellbore_id, replay_session_id, sequence, observed_at, received_at, md_m, tvd_m, channels, quality)
               VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s::jsonb, %s)""",
            (
                sample_id,
                wellbore_id,
                current_seq,
                sample.observed_at,
                now,
                sample.md_m,
                tvd,
                json.dumps(channel_data),
                sample.quality,
            ),
        )
        latest_sample = sample

    # Run real-time ML hazard prediction on the latest live reading
    if latest_sample:
        features = {
            "rop_m_per_h": latest_sample.rop_m_per_h or 10.0,
            "wob_kn": latest_sample.wob_kn or 42.0,
            "rpm": latest_sample.rpm or 100.0,
            "torque_kn_m": latest_sample.torque_kn_m or 8.0,
            "flow_in_l_per_min": latest_sample.flow_in_l_per_min or 1800.0,
            "mud_density_kg_per_m3": latest_sample.mud_density_kg_per_m3 or 1180.0,
        }
        try:
            latest_hazard_pred = predict_hazard(features)
        except Exception:
            latest_hazard_pred = None

    # Update service heartbeat to immediately signal LIVE streaming mode across NWIS
    conn.execute(
        """INSERT INTO service_heartbeat (service, last_seen_at)
           VALUES ('witsml_live', now())
           ON CONFLICT (service) DO UPDATE SET last_seen_at = now()"""
    )

    # Append to decision ledger and audit trail
    append_decision(
        conn,
        actor=actor_name,
        action="ertmac_telemetry_streamed",
        entity_type="wellbore",
        entity_id=wellbore_id,
        payload={
            "source_system": source_name,
            "samples_count": len(samples),
            "latest_md_m": latest_sample.md_m if latest_sample else None,
            "risk_level": latest_hazard_pred.get("risk_level") if latest_hazard_pred else "UNKNOWN",
            "probability": latest_hazard_pred.get("probability") if latest_hazard_pred else 0.0,
        },
    )

    conn.execute(
        "INSERT INTO audit_log (actor_name, action, entity_type, entity_id) VALUES (%s, 'ertmac_stream', 'wellbore', %s)",
        (actor_name, wellbore_id),
    )

    return {
        "status": "stream_accepted",
        "wellbore_id": str(wellbore_id),
        "source_system": source_name,
        "samples_ingested": len(samples),
        "latest_sequence": current_seq,
        "latest_md_m": latest_sample.md_m if latest_sample else None,
        "hazard_prediction": latest_hazard_pred,
        "source_mode": "LIVE",
        "received_at": now.isoformat(),
    }


@router.post("/stream", status_code=202)
def stream_telemetry_batch(
    body: StreamBatchRequest,
    idempotency_key: str = Header(...),
    principal=Depends(require_role("engineer")),
):
    """Receive live telemetry batch from Oil India Limited eRTMAC or rig mud logging system."""
    with connection() as conn:
        sample_wellbores = {s.wellbore_id for s in body.samples}
        if len(sample_wellbores) != 1:
            raise HTTPException(422, "Batch must target exactly one wellbore")
        wellbore_id = next(iter(sample_wellbores))

        digest, old = receipt(
            conn,
            principal.name,
            idempotency_key,
            ["ertmac_stream", str(wellbore_id), body.stream_id, len(body.samples)],
        )
        if old:
            return old

        result = ingest_live_samples(
            conn,
            wellbore_id=wellbore_id,
            samples=body.samples,
            source_name=body.source_system,
            actor_name=principal.name,
        )
        return save_receipt(conn, principal.name, idempotency_key, digest, result)


@router.post("/witsml-log", status_code=202)
async def stream_witsml_xml(
    request: Request,
    wellbore_id: UUID,
    source_name: str = "WITSML-Rig-Feed",
    principal=Depends(require_role("engineer")),
):
    """Parse and ingest raw WITSML 1.3.1.1 / 1.4.1.1 XML log message."""
    content = await request.body()
    if not content:
        raise HTTPException(422, "Empty WITSML log body")

    samples = parse_witsml_log_xml(content, default_wellbore_id=wellbore_id)
    if not samples:
        raise HTTPException(422, "No valid log data found in WITSML XML payload")

    with connection() as conn:
        return ingest_live_samples(
            conn,
            wellbore_id=wellbore_id,
            samples=samples,
            source_name=source_name,
            actor_name=principal.name,
        )


@router.get("/status")
def ertmac_feed_status(_principal=Depends(current_principal)):
    """Inspect eRTMAC live connection status, freshness, and recent telemetry throughput."""
    heartbeat = None
    latest_sample = None
    sample_count = {"total": 0}
    try:
        with connection() as conn:
            heartbeat = conn.execute(
                """SELECT last_seen_at, (last_seen_at > now() - interval '60 seconds') AS is_live
                   FROM service_heartbeat WHERE service='witsml_live'"""
            ).fetchone()

            latest_sample = conn.execute(
                """SELECT s.wellbore_id, s.md_m, s.tvd_m, s.observed_at, s.received_at, s.channels, w.name AS well_name
                   FROM telemetry_sample s
                   JOIN wellbore b ON b.id=s.wellbore_id
                   JOIN well w ON w.id=b.well_id
                   WHERE s.replay_session_id IS NULL
                   ORDER BY s.received_at DESC LIMIT 1"""
            ).fetchone()

            sample_count = conn.execute(
                "SELECT count(*) AS total FROM telemetry_sample WHERE replay_session_id IS NULL"
            ).fetchone()
    except Exception:
        pass

    is_live = bool(heartbeat and heartbeat["is_live"])
    return {
        "service": "eRTMAC/WITSML Live Telemetry Feed",
        "feed_state": "LIVE" if is_live else "IDLE",
        "last_heartbeat": heartbeat["last_seen_at"].isoformat() if heartbeat and heartbeat["last_seen_at"] else None,
        "heartbeat_fresh": is_live,
        "total_live_samples": sample_count["total"] if sample_count else 0,
        "latest_telemetry": {
            "well_name": latest_sample["well_name"],
            "wellbore_id": str(latest_sample["wellbore_id"]),
            "md_m": float(latest_sample["md_m"]) if latest_sample and latest_sample["md_m"] is not None else None,
            "tvd_m": float(latest_sample["tvd_m"]) if latest_sample and latest_sample["tvd_m"] is not None else None,
            "observed_at": latest_sample["observed_at"].isoformat(),
            "received_at": latest_sample["received_at"].isoformat(),
            "channels": latest_sample["channels"],
        } if latest_sample else None,
    }


@router.get("/telemetry/{wellbore_id}/latest")
def latest_wellbore_telemetry(wellbore_id: UUID, _principal=Depends(current_principal)):
    """Retrieve the latest live sample and real-time hazard evaluation for a specific wellbore."""
    with connection() as conn:
        sample = conn.execute(
            """SELECT id, sequence, observed_at, received_at, md_m, tvd_m, channels, quality
               FROM telemetry_sample
               WHERE wellbore_id=%s ORDER BY received_at DESC, sequence DESC LIMIT 1""",
            (wellbore_id,),
        ).fetchone()

        if not sample:
            raise HTTPException(404, "No telemetry received for this wellbore yet")

    channels = sample["channels"] or {}
    features = {
        "rop_m_per_h": float(channels.get("rop_m_per_h", 10.0)),
        "wob_kn": float(channels.get("wob_kn", 42.0)),
        "rpm": float(channels.get("rpm", 100.0)),
        "torque_kn_m": float(channels.get("torque_kn_m", 8.0)),
        "flow_in_l_per_min": float(channels.get("flow_in_l_per_min", 1800.0)),
        "mud_density_kg_per_m3": float(channels.get("mud_density_kg_per_m3", 1180.0)),
    }
    try:
        hazard_prediction = predict_hazard(features)
    except Exception:
        hazard_prediction = None

    return {
        "sample": {
            "id": str(sample["id"]),
            "sequence": sample["sequence"],
            "observed_at": sample["observed_at"].isoformat(),
            "received_at": sample["received_at"].isoformat(),
            "md_m": float(sample["md_m"]) if sample["md_m"] is not None else None,
            "tvd_m": float(sample["tvd_m"]) if sample["tvd_m"] is not None else None,
            "quality": sample["quality"],
            "channels": channels,
        },
        "hazard_prediction": hazard_prediction,
    }
