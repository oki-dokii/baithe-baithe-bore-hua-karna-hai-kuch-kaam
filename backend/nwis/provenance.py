"""Source-use decisions are explicit; public or restricted does not imply approved."""


def may_approve_event(dataset: dict) -> bool:
    if dataset["kind"] == "synthetic":
        return dataset["origin_kind"] == "synthetic" and dataset["applicability"] == "demo_only"
    return (
        dataset["origin_kind"] in ("operator_record", "public_primary")
        and dataset["qualification_status"] == "qualified"
        and dataset["authorization_state"] in ("public_permitted", "restricted_authorized")
        and dataset["applicability"] in ("direct_offset", "analog_only")
    )


def operationally_eligible(dataset: dict) -> bool:
    """A synthetic demo may be reviewable but is never operational evidence."""
    return dataset["kind"] != "synthetic" and may_approve_event(dataset)
