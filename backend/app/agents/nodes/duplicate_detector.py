"""Duplicate Complaint Detection: generates sentence embeddings and finds similar committed complaints via pgvector."""
import logging
import hashlib
import math
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Lazy-load the model to avoid slowing startup
_model = None
_model_attempted = False


def _hash_embedding(text: str, dim: int = 384) -> List[float]:
    """
    Generates a deterministic 384-dimensional normalized vector using subword/word feature hashing.
    Used as an ultra-fast, memory-safe fallback (0 MB additional RAM).
    """
    words = text.lower().split()
    vec = [0.0] * dim

    tokens = list(words)
    for i in range(len(words) - 1):
        tokens.append(f"{words[i]}_{words[i+1]}")
    for w in words:
        if len(w) >= 3:
            for j in range(len(w) - 2):
                tokens.append(w[j:j+3])

    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 16) & 1 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [round(x / norm, 6) for x in vec]
    return vec


def _get_model():
    """Lazy-loads sentence-transformers model. If unavailable or low-memory, safely returns None."""
    global _model, _model_attempted
    if not _model_attempted:
        _model_attempted = True
        try:
            import os
            # If running in constrained environment, limit thread count
            os.environ["OMP_NUM_THREADS"] = "1"
            os.environ["MKL_NUM_THREADS"] = "1"
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("sentence-transformers model loaded: all-MiniLM-L6-v2")
        except BaseException as e:
            logger.warning(f"sentence-transformers unavailable or low-memory environment ({e}); using lightweight vectorizer.")
            _model = None
    return _model


def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generates a 384-dimensional embedding vector for the given text.
    Uses sentence-transformers when available, falling back safely to deterministic hashing.
    Never crashes or causes OOM.
    """
    if not text or not text.strip():
        return None
    model = _get_model()
    if model is not None:
        try:
            embedding = model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except BaseException as e:
            logger.warning(f"SentenceTransformer encoding failed ({e}); falling back to hashing vectorizer.")
    return _hash_embedding(text, dim=384)


async def save_embedding(db, complaint_id: str, embedding: List[float]) -> None:
    """Safely updates embedding column using native Postgres vector cast without ORM type issues."""
    try:
        from sqlalchemy import text as sql_text
        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
        await db.execute(
            sql_text("UPDATE complaints SET embedding = CAST(:vec_str AS vector) WHERE id = :id"),
            {"vec_str": vec_str, "id": complaint_id},
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist embedding for {complaint_id}: {e}")


async def find_similar_complaints(
    db,
    embedding: List[float],
    exclude_id: Optional[str] = None,
    threshold: float = 0.82,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Performs pgvector cosine similarity search against committed complaints.

    Args:
        db: AsyncSession instance
        embedding: 384-dim query vector
        exclude_id: Complaint ID to exclude (the complaint being checked)
        threshold: Minimum cosine similarity (0-1). Default 0.82.
        limit: Maximum number of results to return

    Returns:
        List of dicts with complaint id, summary, category, severity, similarity score
    """
    try:
        from sqlalchemy import text as sql_text

        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
        exclude_clause = "AND id != :exclude_id" if exclude_id else ""

        query_str = f"""
            SELECT
                id,
                customer_name,
                product_name,
                batch_lot_number,
                complaint_category,
                severity_suggested,
                complaint_summary,
                complaint_date,
                1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
            FROM complaints
            WHERE
                embedding IS NOT NULL
                AND status = 'committed'
                {exclude_clause}
                AND 1 - (embedding <=> CAST(:query_vec AS vector)) >= :threshold
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :limit
        """

        params = {
            "query_vec": vec_str,
            "threshold": threshold,
            "limit": limit,
        }
        if exclude_id:
            params["exclude_id"] = exclude_id

        result = await db.execute(sql_text(query_str), params)
        rows = result.fetchall()

        return [
            {
                "id": row.id,
                "customer_name": row.customer_name,
                "product_name": row.product_name,
                "batch_lot_number": row.batch_lot_number,
                "complaint_category": row.complaint_category,
                "severity_suggested": row.severity_suggested,
                "complaint_summary": row.complaint_summary,
                "complaint_date": str(row.complaint_date) if row.complaint_date else None,
                "similarity": round(float(row.similarity), 3),
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Duplicate similarity search failed: {e}")
        return []
