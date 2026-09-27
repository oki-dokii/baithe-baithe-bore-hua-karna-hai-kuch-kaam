import hashlib
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from psycopg.errors import CheckViolation

from nwis.db import connection
from nwis.drilling_parameters import HistoricalBatch, eligible_anchors, stage_batch

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
RAW = b"owned test export only\n"


def sample(bore, **changes):
    return {
        "wellbore_id": bore, "source_record_id": "row-1", "revision": 1,
        "observed_at": NOW, "available_at": NOW + timedelta(seconds=2),
        "received_at": NOW + timedelta(seconds=3), "md_m": 500,
        "rig_state": "forward_drilling", "quality": "good",
        "rop_m_per_h": 10, "wob_kn": 50, "rpm": 100,
        "torque_kn_m": 8, "flow_in_l_per_min": 1000,
    } | changes


def batch(dataset, bore, **changes):
    return HistoricalBatch.model_validate({
        "schema_version": "historical-drilling-parameters-v1",
        "dataset_id": dataset, "external_id": "test-export",
        "source_sha256": hashlib.sha256(RAW).hexdigest(),
        "source_kind": "csv_export", "source_reference": "owned test fixture",
        "permission_reference": "owned test fixture", "source_timezone": "UTC",
        "md_datum": "KB", "source_units": {"md": "m", "wob": "kN"},
        "mapping_version": "test-v1", "samples": [sample(bore)],
    } | changes)


def test_contract_requires_ordered_aware_timestamps_and_no_delete_channels():
    bore = uuid4()
    with pytest.raises(ValidationError):
        batch(uuid4(), bore, samples=[sample(bore, observed_at=NOW.replace(tzinfo=None))])
    with pytest.raises(ValidationError):
        batch(uuid4(), bore, samples=[sample(bore, available_at=NOW - timedelta(seconds=1))])
    with pytest.raises(ValidationError):
        batch(uuid4(), bore, samples=[sample(bore, operation="delete")])


@pytest.mark.skipif(os.getenv("NWIS_INTEGRATION") != "1", reason="Needs initialized NWIS test DB")
def test_staging_revision_and_fail_closed_qualification():
    dataset_id, well_id, bore_id, ref_id = (uuid4() for _ in range(4))
    with connection() as conn:
        conn.execute(
            """INSERT INTO dataset(id,external_id,name,kind,version,qualification_status,
               origin_kind,authorization_state,applicability)
               VALUES (%s,%s,'Owned test','public','1','unqualified',
                       'public_primary','public_permitted','review_only')""",
            (dataset_id, f"test-historical-{dataset_id}"),
        )
        conn.execute("INSERT INTO depth_reference(id,kind) VALUES (%s,'KB')", (ref_id,))
        conn.execute(
            """INSERT INTO well(id,dataset_id,external_id,name,surface_point,depth_reference_id)
               VALUES (%s,%s,'well','Owned test',ST_SetSRID(ST_MakePoint(95,27),4326)::geography,%s)""",
            (well_id, dataset_id, ref_id),
        )
        conn.execute(
            "INSERT INTO wellbore(id,well_id,external_id) VALUES (%s,%s,'bore')",
            (bore_id, well_id),
        )
        source = batch(dataset_id, bore_id)
        with pytest.raises(ValueError, match="checksum"):
            stage_batch(conn, source, b"wrong")
        result = stage_batch(conn, source, RAW)
        assert result["staged_rows"] == 1
        assert stage_batch(conn, source, RAW)["staged_rows"] == 0
        assert eligible_anchors(conn, result["source_id"]) == []
        correction = sample(bore_id, revision=2, rop_m_per_h=12,
                            depth_reference_id=ref_id)
        corrected = batch(dataset_id, bore_id, samples=[correction])
        assert stage_batch(conn, corrected, RAW)["staged_rows"] == 1
        with pytest.raises(ValueError, match="sample_revision_changed"):
            stage_batch(conn, batch(dataset_id, bore_id,
                                   samples=[sample(bore_id, rop_m_per_h=99)]), RAW)
        with pytest.raises(CheckViolation):
            with conn.transaction():
                conn.execute("UPDATE drilling_parameter_sample SET md_m=501 WHERE source_id=%s",
                             (result["source_id"],))
        # Candidate reads need both source and dataset qualification, plus an
        # approved datum. All three are reviewed explicitly in this test only.
        conn.execute(
            """UPDATE dataset SET qualification_status='qualified',
               applicability='analog_only' WHERE id=%s""", (dataset_id,),
        )
        conn.execute("UPDATE depth_reference SET review_state='approved' WHERE id=%s", (ref_id,))
        conn.execute(
            """UPDATE drilling_parameter_source SET units_reviewed=true,
               timezone_reviewed=true, datum_reviewed=true, qualification_state='qualified',
               qualified_by='test-reviewer', qualified_at=now() WHERE id=%s""",
            (result["source_id"],),
        )
        anchors = eligible_anchors(conn, result["source_id"])
        assert len(anchors) == 1
        assert anchors[0]["rop_m_per_h"] == 12
        with pytest.raises(ValueError, match="source_no_longer_staged"):
            stage_batch(conn, batch(dataset_id, bore_id,
                                    samples=[sample(bore_id, revision=3)]), RAW)
        # Roll back all owned fixture rows; no effect on demo data.
        conn.rollback()
