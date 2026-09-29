"""Unit tests for the Grounded RAG Q&A Engine."""

from nwis.rag_engine import (
    clean_query,
    extract_best_answer_sentence,
    KEY_ENTITIES,
)


def test_clean_query_filters_stopwords_and_punctuation():
    query = "What was the mud weight in use during severe mud loss in Tipam Sandstone?"
    tokens = clean_query(query)
    assert "mud" in tokens
    assert "weight" in tokens
    assert "tipam" in tokens
    assert "sandstone" in tokens
    assert "what" not in tokens
    assert "the" not in tokens
    assert "in" not in tokens


def test_extract_best_answer_sentence_scores_entities():
    text = (
        "Well NHK-302 drilled through Girujan clay smoothly. "
        "At depth 2145 m MD in Tipam Sandstone, encountered severe mud losses of 45 bbl/hr. "
        "Mud weight in use was 1.22 SG polymer bentonite mud. "
        "Regained full returns after pumping 25 bbl Mica LCM pill."
    )
    query_tokens = ["mud", "loss", "tipam", "bbl"]
    best_sent, score = extract_best_answer_sentence(text, query_tokens)
    assert "Tipam Sandstone" in best_sent
    assert "45 bbl/hr" in best_sent
    assert score >= 0.50


def test_key_entities_regex():
    assert KEY_ENTITIES["mud_weight"].search("mud weight 1.25 SG") is not None
    assert KEY_ENTITIES["loss_volume"].search("lost 55 bbl of mud") is not None
    assert KEY_ENTITIES["npt"].search("caused 12 hours NPT") is not None
    assert KEY_ENTITIES["lcm"].search("pumped Mica LCM pill") is not None
