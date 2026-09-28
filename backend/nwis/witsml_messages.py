"""Extract WITSML 1.4.1.1 Message objects as review-only event leads."""

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

NS = "{http://www.witsml.org/schemas/1series}"
MAX_BYTES = 25 * 1024 * 1024
KEYWORDS = {
    "mud_loss": re.compile(r"\b(?:loss(?:es)?|lost circulation|lost returns)\b", re.I),
    "kick": re.compile(r"\b(?:kick|influx|positive flow|well control)\b", re.I),
    "stuck_pipe": re.compile(r"\b(?:stuck pipe|stuck string|differentially stuck)\b", re.I),
}


def child_text(parent: ET.Element, name: str) -> str | None:
    child = parent.find(NS + name)
    if child is None or child.text is None:
        return None
    return child.text.strip() or None


def extract(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("WITSML message export exceeds local 25 MiB review limit")
    raw = path.read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD/entity declarations are not accepted")
    root = ET.fromstring(raw)
    if root.tag != NS + "messages" or root.attrib.get("version") != "1.4.1.1":
        raise ValueError("Expected WITSML 1.4.1.1 messages root")
    results = []
    for item in root.findall(NS + "message"):
        timestamp = child_text(item, "dTim")
        if timestamp is not None:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError("WITSML message timestamp lacks UTC offset")
        message_text = child_text(item, "messageText")
        if not message_text:
            continue
        md_element = item.find(NS + "md")
        md_text = md_element.text.strip() if md_element is not None and md_element.text else None
        results.append({
            "message_uid": item.attrib.get("uid"),
            "source_well_uid": item.attrib.get("uidWell"),
            "source_wellbore_uid": item.attrib.get("uidWellbore"),
            "message_at": timestamp,
            "message_type": child_text(item, "typeMessage"),
            "message_md": md_text,
            "message_md_unit": md_element.attrib.get("uom") if md_element is not None else None,
            "message_text": message_text,
            "keyword_hits": [name for name, pattern in KEYWORDS.items()
                             if pattern.search(message_text)],
            "review_state": "unreviewed_message_not_event",
            "onset_basis": "unestablished",
        })
    return {
        "schema_version": "witsml-message-leads-v1",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_kind": "witsml_1_4_1_1_messages",
        "messages": results,
        "candidate_count": sum(bool(row["keyword_hits"]) for row in results),
        "approved_event_count": 0,
        "note": "Message time is not incident onset; keyword hits require independent review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract review-only WITSML message leads")
    parser.add_argument("xml", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = extract(args.xml)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({"messages": len(result["messages"]),
                      "candidate_count": result["candidate_count"],
                      "approved_event_count": 0, "source_sha256": result["source_sha256"]}))


if __name__ == "__main__":
    main()
