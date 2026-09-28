"""Offline, approval-scoped real-data baseline; never served by the API."""

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from nwis.db import connection
from nwis.mud_loss_adapter import AdapterError, SourceBundle
from nwis.prediction import audit
from nwis.real_ml_approval import ApprovalError, verify_approval
from nwis.train_mud_loss import TrainingRefused, fit_baseline

STATE = "offline_real_experiment_only"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="Reviewed source assertion bundle")
    parser.add_argument("--source-id", type=UUID, required=True)
    parser.add_argument("--approval-id", type=UUID, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    outputs = [args.out_dir / "real-experiment-model.json",
               args.out_dir / "real-experiment-card.json"]
    if any(path.exists() for path in outputs):
        parser.error("output_exists: experiment files will not be overwritten")
    try:
        bundle = SourceBundle.model_validate_json(args.evidence.read_text())
        with connection() as conn:
            manifest, approval = verify_approval(conn, args.approval_id, args.source_id, bundle)
        report = audit(manifest)
        artifact, card = fit_baseline(
            manifest, report, state=STATE, training_authorized=True,
            approval_id=approval["approval_id"],
        )
    except (ApprovalError, AdapterError, TrainingRefused, ValidationError) as exc:
        code = str(exc) if isinstance(exc, (ApprovalError, AdapterError, TrainingRefused)) else "evidence_schema_invalid"
        print(json.dumps({"error_code": code, "training_started": False}), file=sys.stderr)
        raise SystemExit(2) from None
    card["approval_id"] = approval["approval_id"]
    card["approval_scope"] = approval["scope"]
    card["transfer_to_oil_validated"] = False
    card["limitations"].append(
        "Manual coverage and mud-program interpretations are attested, not automatically proven by document linkage"
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    outputs[0].write_text(json.dumps(artifact, indent=2))
    outputs[1].write_text(json.dumps(card, indent=2))
    print(json.dumps({"state": STATE, "approval_id": approval["approval_id"],
                      "deployed": False, "operationally_validated": False}, indent=2))


if __name__ == "__main__":
    main()
