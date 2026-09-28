"""Verify sealed held-out source identities without opening their contents for tuning."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from nwis.public_reference import REFERENCE, ROOT

MANIFEST = ROOT / "specs/evaluation/public-heldout-sources-v1.json"
MAX_PAGES = 200


def validate(manifest: dict, development: dict) -> dict:
    if manifest.get("schema_version") != "public-heldout-sources-v1":
        raise ValueError("Wrong held-out schema")
    if manifest.get("status") != "sealed_unlabeled_not_scored":
        raise ValueError("Held-out corpus must remain unlabeled and unscored")
    if manifest.get("development_reference") != REFERENCE.name:
        raise ValueError("Wrong development reference")
    if not re.fullmatch(r"[0-9a-f]{7,40}", manifest.get("extractor_revision", "")):
        raise ValueError("Missing frozen extractor revision")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) < 2:
        raise ValueError("Need at least two independent reports")
    ids = [source["id"] for source in sources]
    hashes = [source["sha256"] for source in sources]
    if len(ids) != len(set(ids)) or len(hashes) != len(set(hashes)):
        raise ValueError("Duplicate held-out source")
    dev_ids = {source["id"] for source in development["sources"]}
    dev_hashes = {source["sha256"] for source in development["sources"]}
    if set(ids) & dev_ids or set(hashes) & dev_hashes:
        raise ValueError("Held-out source overlaps development corpus")
    for source in sources:
        if not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
            raise ValueError(f"Invalid digest: {source['id']}")
        if not 1 <= source["pdf_pages"] <= MAX_PAGES or source["byte_size"] < 1:
            raise ValueError(f"Invalid PDF size or page cap: {source['id']}")
        if Path(source["local_filename"]).name != source["local_filename"]:
            raise ValueError(f"Unsafe filename: {source['id']}")
        if not source["pdf_url"].startswith("https://factpages.sodir.no/pbl/wellbore_documents/"):
            raise ValueError(f"Unrecognized source URL: {source['id']}")
    return {"sealed_sources": ids, "pages": sum(s["pdf_pages"] for s in sources),
            "labeled": False, "scored": False, "operational_evidence_eligible": False}


def verify_files(manifest: dict, raw_dir: Path) -> list[str]:
    verified = []
    for source in manifest["sources"]:
        path = raw_dir / source["local_filename"]
        if path.stat().st_size != source["byte_size"]:
            raise ValueError(f"Byte-count mismatch: {source['id']}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != source["sha256"]:
            raise ValueError(f"Checksum mismatch: {source['id']}")
        info = subprocess.check_output(["pdfinfo", str(path)], text=True)
        match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
        if not match or int(match[1]) != source["pdf_pages"]:
            raise ValueError(f"Page-count mismatch: {source['id']}")
        verified.append(source["id"])
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify sealed held-out public-report sources")
    parser.add_argument("--raw-dir", type=Path, help="Verify ignored local PDF identity")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    development = json.loads(REFERENCE.read_text())
    result = validate(manifest, development)
    if args.raw_dir:
        result["local_pdf_identity_verified"] = verify_files(manifest, args.raw_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
