import copy
import json

import pytest

from nwis.public_heldout import MANIFEST, REFERENCE, validate


@pytest.fixture
def manifests():
    return json.loads(MANIFEST.read_text()), json.loads(REFERENCE.read_text())


def test_heldout_is_disjoint_and_unscored(manifests):
    result = validate(*manifests)
    assert result["sealed_sources"] == ["NOD-4247", "NOD-5000"]
    assert result["pages"] == 195
    assert not result["scored"]
    assert not result["operational_evidence_eligible"]


@pytest.mark.parametrize(
    "change",
    [
        lambda m, d: m.update(status="domain_approved"),
        lambda m, d: m["sources"][0].update(id="NOD-511"),
        lambda m, d: m["sources"][0].update(sha256=d["sources"][0]["sha256"]),
        lambda m, d: m["sources"][0].update(pdf_pages=315),
        lambda m, d: m["sources"][0].update(local_filename="../escape.pdf"),
    ],
)
def test_heldout_rejects_overclaim_overlap_or_unsafe_file(manifests, change):
    manifest, development = copy.deepcopy(manifests)
    change(manifest, development)
    with pytest.raises(ValueError):
        validate(manifest, development)
