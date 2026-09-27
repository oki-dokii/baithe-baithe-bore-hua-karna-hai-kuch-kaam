from uuid import uuid4

import pytest

from nwis.intelligence import SearchRequest
from nwis.semantic import DIMENSION, claim_hash, claim_text, query_vector, vector_literal


def test_only_reviewed_claim_fields_are_embedded():
    event = {
        "event_type": "mud_loss",
        "description": "Circulation was lost while drilling",
        "quote": "Returns decreased at the source interval.",
        "raw_text": "Unapproved unrelated page content",
    }
    assert claim_text(event) == (
        "mud_loss\nCirculation was lost while drilling\n"
        "Returns decreased at the source interval."
    )
    assert "Unapproved" not in claim_text(event)
    assert len(claim_hash(event)) == 64
    assert claim_hash(event) != claim_hash(event | {"quote": "Corrected source quote"})


def test_vector_validates_dimension_and_finite_values():
    assert vector_literal([1.0] + [0.0] * (DIMENSION - 1)).startswith("[1,0,")
    with pytest.raises(ValueError):
        vector_literal([1.0])
    with pytest.raises(ValueError):
        vector_literal([float("nan")] * DIMENSION)


def test_query_uses_model_query_embedding(monkeypatch):
    class FakeModel:
        def query_embed(self, text):
            assert text == "lost circulation"
            return iter([[1.0] + [0.0] * (DIMENSION - 1)])

    monkeypatch.setattr("nwis.semantic.model", lambda: FakeModel())
    assert query_vector("lost circulation").startswith("[1,0,")


def test_semantic_request_requires_text():
    with pytest.raises(ValueError):
        SearchRequest(dataset_id=uuid4(), mode="semantic", question="  ")
    assert SearchRequest(dataset_id=uuid4()).mode == "full_text"
