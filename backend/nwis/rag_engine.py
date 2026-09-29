"""Intelligent Grounded RAG Q&A Engine for NWIS drilling reports and records."""

import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from psycopg import Connection

STOPWORDS = {
    "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
    "the", "a", "an", "in", "on", "at", "to", "for", "with", "by", "about",
    "was", "were", "is", "are", "been", "being", "have", "has", "had", "do",
    "does", "did", "and", "or", "but", "if", "then", "of", "off", "from",
    "tell", "me", "show", "give", "explain", "find", "during", "occurred",
}

KEY_ENTITIES = {
    "mud_weight": re.compile(r"\b(\d+\.?\d*)\s*(?:sg|ppg|kg/m3|kg/m³|specific gravity)\b", re.I),
    "loss_volume": re.compile(r"\b(\d+\.?\d*)\s*(?:bbl(?:/hr)?|barrels?|m3|m³)\b", re.I),
    "depth": re.compile(r"\b(\d[\d,]*(?:\.\d+)?)\s*(?:m|meters?|ft|feet)\b", re.I),
    "npt": re.compile(r"\b(\d+\.?\d*)\s*(?:hours?|hrs?)\s*(?:npt)?\b", re.I),
    "pressure": re.compile(r"\b(\d+)\s*(?:psi|bar|kpa)\b", re.I),
    "lcm": re.compile(r"\b(?:mica|nut[- ]plug|calcium carbonate|caco3|walnut|pill|spotting fluid)\b", re.I),
}


def clean_query(question: str) -> List[str]:
    raw_tokens = re.findall(r"\b[a-z0-9_-]{2,}\b", question.casefold())
    return [t for t in raw_tokens if t not in STOPWORDS]


def extract_best_answer_sentence(text: str, query_tokens: List[str]) -> Tuple[str, float]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    best_sent = ""
    best_score = 0.0

    for sentence in sentences:
        s_clean = sentence.casefold()
        matched = sum(1 for token in query_tokens if token in s_clean)
        if matched == 0:
            continue
        
        score = matched / max(len(query_tokens), 1)
        
        # Boost for containing specific domain entities (mud weight, bbl, depth, etc.)
        for regex in KEY_ENTITIES.values():
            if regex.search(sentence):
                score += 0.25
                break

        if score > best_score:
            best_score = score
            best_sent = sentence.strip()

    return best_sent, min(0.98, best_score)


def query_rag_engine(
    conn: Connection,
    dataset_id: UUID,
    question: str,
    wellbore_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """Search ingested source passages and verified facts to answer free-form drilling questions."""
    # 1. First check if an approved fact directly answers this
    cur = conn.cursor()
    cur.execute(
        """SELECT f.id, f.answer, f.quote, f.reviewer_name, p.page_number, p.section_label,
                  sd.id AS document_id, sd.filename
           FROM reviewed_report_fact f
           JOIN extracted_passage p ON p.id=f.passage_id
           JOIN source_document sd ON sd.id=p.document_id
           WHERE f.dataset_id=%s AND f.state='approved'
             AND (f.fact_key ILIKE %s OR f.answer ILIKE %s)
           LIMIT 1""",
        (dataset_id, f"%{question.strip()[:20]}%", f"%{question.strip()[:20]}%"),
    )
    direct_fact = cur.fetchone()
    if direct_fact:
        return {
            "question": question,
            "status": "answered",
            "answer": direct_fact["answer"],
            "confidence": 1.0,
            "answer_kind": "reviewer_curated_fact",
            "reason": None,
            "citations": [
                {
                    "document_id": str(direct_fact["document_id"]),
                    "filename": direct_fact["filename"],
                    "page_number": direct_fact["page_number"],
                    "section_label": direct_fact["section_label"],
                    "quote": direct_fact["quote"],
                    "verified_by": direct_fact["reviewer_name"],
                    "relevance_score": 1.0,
                }
            ],
        }

    # 2. Search extracted passages across documents in this dataset
    tokens = clean_query(question)
    if not tokens:
        return {
            "question": question,
            "status": "no_evidence_found",
            "answer": None,
            "confidence": 0.0,
            "reason": "query_too_short_or_generic",
            "citations": [],
        }

    # Build ILIKE search pattern or token clauses
    like_conditions = " OR ".join(["p.raw_text ILIKE %s" for _ in tokens[:6]])
    params: List[Any] = [dataset_id]
    if wellbore_id:
        bore_clause = "AND EXISTS (SELECT 1 FROM document_wellbore dw WHERE dw.document_id=sd.id AND dw.wellbore_id=%s)"
        params.append(wellbore_id)
    else:
        bore_clause = ""

    params.extend([f"%{t}%" for t in tokens[:6]])

    query_sql = f"""
        SELECT p.id, p.page_number, p.section_label, p.raw_text,
               sd.id AS document_id, sd.filename
        FROM extracted_passage p
        JOIN source_document sd ON sd.id=p.document_id
        WHERE sd.dataset_id=%s
        {bore_clause}
        AND ({like_conditions})
        ORDER BY p.id LIMIT 25
    """

    rows = cur.execute(query_sql, tuple(params)).fetchall()

    scored_citations = []
    best_overall_answer = ""
    highest_confidence = 0.0

    for row in rows:
        passage_text = row["raw_text"]
        best_sentence, confidence = extract_best_answer_sentence(passage_text, tokens)
        if confidence > 0.20:
            scored_citations.append({
                "document_id": str(row["document_id"]),
                "filename": row["filename"],
                "page_number": row["page_number"],
                "section_label": row["section_label"],
                "quote": best_sentence or passage_text[:250],
                "full_passage": passage_text,
                "relevance_score": round(confidence, 3),
            })
            if confidence > highest_confidence:
                highest_confidence = confidence
                best_overall_answer = best_sentence or passage_text

    scored_citations.sort(key=lambda c: c["relevance_score"], reverse=True)

    if scored_citations and highest_confidence >= 0.35:
        return {
            "question": question,
            "status": "answered",
            "answer": best_overall_answer,
            "confidence": round(highest_confidence, 2),
            "answer_kind": "grounded_passage_extraction",
            "reason": None,
            "citations": scored_citations[:4],
        }

    return {
        "question": question,
        "status": "no_evidence_found",
        "answer": None,
        "confidence": 0.0,
        "reason": "no_supporting_passages_found",
        "citations": [],
    }
