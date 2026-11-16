"""RAG service — keyword-based retrieval (PRD 4.6 / FR-07).

Simple tokenized search per the recorded decision: split the query on whitespace,
lowercase, strip punctuation edges, and score each STORE_DATA paragraph by how many
query words appear in it. ALWAYS the top 5 paragraphs (fewer only when the store
has less data) — no embeddings, no vector DB; the AI is what understands meaning.
"""
from __future__ import annotations

import sqlite3

from backend.shared.constants import RAG_TOP_K
from database.queries import store_data as store_data_q

# ============== TOKENIZING & SCORING ==============

def tokenize(text: str) -> list[str]:
    """Lowercases, splits on whitespace, and strips punctuation from each token's edges."""
    return [token.strip(".,!?;:\"'()[]{}") for token in text.lower().split() if token.strip(".,!?;:\"'()[]{}")]


def score_paragraph(query_tokens: list[str], content: str) -> int:
    """Score = the number of distinct query words found in the paragraph (substring match)."""
    content_lower = content.lower()
    return sum(1 for token in set(query_tokens) if token in content_lower)


# ============== SEARCH ==============

def search_top5(conn: sqlite3.Connection, query: str) -> list[dict]:
    """Returns the top-5 paragraphs as [{row_id, item_id, content, score}], best match first.

    Always up to RAG_TOP_K items — even when scores are zero (FR-07: take what exists).
    """
    tokens = tokenize(query)
    rows = store_data_q.get_items_for_search(conn)
    scored = [
        {"row_id": int(row["id"]), "item_id": row["item_id"], "content": str(row["content"]),
         "score": score_paragraph(tokens, str(row["content"]))}
        for row in rows
    ]
    scored.sort(key=lambda item: (-item["score"], item["row_id"]))
    return scored[:RAG_TOP_K]
